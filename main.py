from typing import Dict, Any
import json
import asyncio
import redis.asyncio as redis
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from langgraph.graph import END
from StateTypes import GraphState
from workflow import create_graph
from queue_manager import RedisQueueManager
import os
import redis as sync_redis

load_dotenv()

# Enable LangGraph debugging
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)-10s - %(levelname)-8s - %(message)s'
)

logger = logging.getLogger(__name__)

logger.setLevel(logging.DEBUG)
logging.getLogger("langgraph").setLevel(logging.DEBUG)
logging.getLogger("langgraph.pregel").setLevel(logging.DEBUG)
logging.getLogger("mock_llm").setLevel(logging.DEBUG)
logging.getLogger("AssessDefence").setLevel(logging.DEBUG)
logging.getLogger("AssessRisk").setLevel(logging.DEBUG)
logging.getLogger("CreateLeavePlan").setLevel(logging.DEBUG)
logging.getLogger("CreateStayPlan").setLevel(logging.DEBUG)
logging.getLogger("ShowPlan").setLevel(logging.DEBUG)
logging.getLogger("context_utils").setLevel(logging.DEBUG)
logging.getLogger("postgres_checkpointer").setLevel(logging.DEBUG)



# Redis connection and queue manager
redis_password = os.getenv('REDIS_PASSWORD', '')
redis_service = os.getenv('REDIS_SERVICE', '')
redis_client = redis.Redis(host=redis_service, port=6379, password=redis_password, decode_responses=True, db=0)

# Create sync Redis client for workflow nodes
sync_redis_client = sync_redis.Redis(host=redis_service, port=6379, password=redis_password, decode_responses=True, db=0)
queue_manager = RedisQueueManager(redis_client)

# Initialize LLM and graph
use_mock = os.getenv('USE_MOCK_LLM', 'false').lower() == 'true'

if use_mock:
    from mock_llm import MockBushfireLLM
    llm = MockBushfireLLM()
else:
    llm = init_chat_model("gpt-4o")

graph = create_graph(llm, sync_redis_client)

async def process_inbound_message(session_id: str, message: Dict[str, Any]):
    """Process inbound message with lock-and-drop pattern"""
    
    # Try to acquire processing lock atomically
    if not await queue_manager.acquire_processing_lock(session_id):
        logger.info(f"[{session_id}] Message dropped - already processing: {message['type']}")
        return
    
    try:
        logger.info(f"[{session_id}] Processing message: {message['type']}")
        
        if message["type"] == "start_new_plan":
            await start_planning_session(session_id, message["motivation"])
        elif message["type"] == "answers":
            await handle_answers(session_id, message)
        elif message["type"] == "choice":
            await handle_choice(session_id, message)
        elif message["type"] == "connect" or message["type"] == "reconnect":
            tab_id = message.get("tab_id")
            await handle_connect(session_id, tab_id)
            
    finally:
        await queue_manager.release_processing_lock(session_id)

async def handle_connect(session_id: str, tab_id: str = None):
    """Handle connect/reconnect messages - only called by instance with lock"""
    config = {"configurable": {"thread_id": session_id}}
    current_state = graph.get_state(config)
    logger.debug(f"[{session_id} / {tab_id}] Fetch any existing session len = {len(current_state.values)}")
    existing_session = False
    if current_state.values and len(current_state.values) > 0:
        # Session has data - send last UI state for context to specific tab
        existing_session = await handle_reconnect(session_id, tab_id)
    if not existing_session:
        # New session - send no_session to specific tab
        logger.info(f"[{session_id}] New session, sending no_session")
        message = {"type": "no_session"}
        if tab_id:
            message["tab_id"] = tab_id
        await queue_manager.publish_outbound(session_id, message)

async def start_planning_session(session_id: str, motivation: str):
    logger.info(f"[{session_id}] Starting Planning Session")
    
    # Clear last UI state for new session
    await redis_client.delete(f"last_ui_state:{session_id}")
    
    # Reset mock LLM counters for new session
    if use_mock and hasattr(llm, 'reset_mock'):
        llm.reset_mock()
        logger.debug(f"[{session_id}] Reset mock LLM")
    
    prompt = """You are an expert emergency management consultant specializing in Australian bushfire preparedness. 
Introduce yourself and explain the bushfire planning process. You will collect essential information about 
their property, location, household composition, and any specific concerns as the process unfolds.

Do not ask a question more than once.

"""

    # Add session_id to state for nodes to use
    initial_state: GraphState = {
        "messages": [HumanMessage(content=prompt)],
        "user_motivation": motivation,
        "session_id": session_id
    }
    
    # Start the graph execution in background
    logger.debug(f"[{session_id}] Initial call to graph")
    asyncio.create_task(run_graph(session_id, initial_state))

async def run_graph(session_id: str, initial_state: dict):
    
    # Construct the config with session_id
    config = {"configurable": {"thread_id": session_id}}

    try:
        if initial_state:
            logger.info(f"[{session_id}] Initial call to graph")
            graph.invoke(initial_state, config)
        else:
            logger.info(f"[{session_id}] Resuming graph")
            graph.invoke(Command(resume={}), config)
        
        current_state = graph.get_state(config)
        logger.info(f"[{session_id}] Graph execution complete. Next node: {current_state.next}")
        logger.info(f"[{session_id}] Current state: {current_state}")
        logger.debug(f"[{session_id}] Current values keys: {list(current_state.values.keys()) if current_state.values else 'None'}")
        
        if not current_state.next or current_state.next == END:
            plan = current_state.values.get('final_plan')
            if not plan or not plan.get('content') or len(plan.get('content', [])) == 0:
                logger.warning(f"[{session_id}] No plan generated.")
                await send_message_to_frontend(session_id, {
                    "type": "plan_complete",
                    "plan": []
                })
            else:
                await send_message_to_frontend(session_id, {
                    "type": "plan_complete",
                    "plan": plan.get('content', []) if plan else []
                })

        # Send any pending messages from memory
        else:
            logger.info(f"[{session_id}] Graph paused at node: {current_state.next}")
            pending = await redis_client.lrange(f"pending:{session_id}", 0, -1)
            logger.info(f"[{session_id}] Pending messages for session: {len(pending)}")
            if pending:
                logger.info(f"[{session_id}] Pending messages being sent: {len(pending)}")
                for msg_json in pending:
                    message = json.loads(msg_json)
                    await send_message_to_frontend(session_id, message)
                await redis_client.delete(f"pending:{session_id}")
            else:
                logger.info(f"[{session_id}] No pending messages, resuming graph from {current_state.next}")
                asyncio.create_task(run_graph(session_id, None))
        
    except Exception as e:
        logger.error(f"[{session_id}] Error in run_graph: {e}")
        await send_message_to_frontend(session_id, {
            "type": "error",
            "message": str(e),
            "show_header": True
        })

async def handle_answers(session_id: str, message: dict):
    logger.debug(f"[{session_id}] handle_answers: {message}")

    # Store user responses in Redis
    answers = message["answers"]
    if isinstance(answers, dict):
        await redis_client.hset(f"responses:{session_id}", mapping=answers)
        await redis_client.expire(f"responses:{session_id}", 3600)
    else:
        logger.error(f"[{session_id}] Answers should be a dict, got {type(answers)}")

    # Resume workflow
    logger.debug(f"[{session_id}] Completed handling answers")
    asyncio.create_task(run_graph(session_id, None))

async def handle_choice(session_id: str, message: dict):
    logger.debug(f"[{session_id}] handle_choice: {message}")

    # Store user responses in Redis
    choice = message["choice"]
    if isinstance(choice, str):
        await redis_client.hset(f"responses:{session_id}", mapping={'choice': choice})
        await redis_client.expire(f"responses:{session_id}", 3600)
    else:
        logger.error(f"[{session_id}] Choice should be a string, got {type(choice)}")

    # Resume workflow
    logger.debug(f"[{session_id}] Completed handling selection")
    asyncio.create_task(run_graph(session_id, None))

async def handle_reconnect(session_id: str, tab_id: str = None) -> bool:
    """Handle reconnect by sending last UI state"""
    logger.info(f"[{session_id}] Reconnecting to session")
    last_state = await redis_client.get(f"last_ui_state:{session_id}")
    if last_state:
        message = json.loads(last_state)
        if tab_id:
            message["tab_id"] = tab_id
        logger.info(f"[{session_id}] Sending cached UI state on reconnect")
        await queue_manager.publish_outbound(session_id, message)
        return True
    else:
        logger.warning(f"[{session_id}] No last UI state found for existing session")
        return False

async def send_message_to_frontend(session_id: str, message: dict):
    """Send message to frontend via queue and record UI state"""
    if "type" not in message:
        logger.error(f"[{session_id}] Message missing 'type' field: {message}")
        return
    
    # Record all UI messages except internal ones
    ui_message_types = {"questions", "choice", "plan_complete", "error", "info"}
    if message["type"] in ui_message_types:
        logger.debug(f"[{session_id}] Recording last UI message: {message['type']}")
        await redis_client.set(f"last_ui_state:{session_id}", json.dumps(message), ex=86400)
        
    await queue_manager.publish_outbound(session_id, message)



async def main():
    """Main entry point for the queue processor service"""
    logger.info("Starting Bushfire Plan Queue Processor")
    
    # Initialize queues
    await queue_manager.initialize_queues()
    
    # Start consuming messages
    logger.info("Queue consumer started")
    await queue_manager.consume_inbound(process_inbound_message)

if __name__ == "__main__":
    asyncio.run(main())
