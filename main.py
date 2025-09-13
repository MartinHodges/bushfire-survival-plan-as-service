from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict, Any
import uuid
import json
import asyncio
import threading
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from langgraph.graph import END
from StateTypes import GraphState
from workflow import create_graph

load_dotenv()

# Enable LangGraph debugging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logging.getLogger("langgraph").setLevel(logging.DEBUG)
logging.getLogger("langgraph.pregel").setLevel(logging.DEBUG)
logging.getLogger("__main__").setLevel(logging.DEBUG)

app = FastAPI(title="Bushfire Plan WebSocket API")

# Global storage for sessions and websockets
sessions: Dict[str, Dict[str, Any]] = {}
websockets: Dict[str, WebSocket] = {}
pending_messages: Dict[str, list] = {}
user_responses: Dict[str, Dict[str, str]] = {}

# Thread locks for global dictionaries
sessions_lock = threading.Lock()
websockets_lock = threading.Lock()
pending_messages_lock = threading.Lock()
user_responses_lock = threading.Lock()

sessions_lock = threading.Lock()
websockets_lock = threading.Lock()
pending_messages_lock = threading.Lock()
user_responses_lock = threading.Lock()

# Initialize LLM and graph
llm = init_chat_model("gpt-4o")

graph = create_graph(llm, pending_messages, user_responses, pending_messages_lock)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session_id = str(uuid.uuid4())
    websockets[session_id] = websocket
    
    try:
        await websocket.send_text(json.dumps({
            "type": "session_started",
            "session_id": session_id
        }))
        
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            logging.info(f"[] Received ws message: {message} Type: {message['type']}")
            
            if message["type"] == "start_session":
                await start_planning_session(session_id, message["motivation"])
            elif message["type"] == "user_response":
                await handle_user_response(session_id, message)
                
    except WebSocketDisconnect:
        if session_id in websockets:
            del websockets[session_id]
        if session_id in sessions:
            del sessions[session_id]

async def start_planning_session(session_id: str, motivation: str):
    logging.info(f"[{session_id}] Starting Planning Session")
    config = {"configurable": {"thread_id": session_id}}
    
    prompt = """You are an expert emergency management consultant specializing in Australian bushfire preparedness. 
Introduce yourself and explain the bushfire planning process. You will collect essential information about 
their property, location, household composition, and any specific concerns as the process unfolds.

Do not ask a question more than once.

"""

    # Add session_id to state for WebSocket nodes to use
    initial_state: GraphState = {
        "messages": [HumanMessage(content=prompt)],
        "user_motivation": motivation,
        "session_id": session_id
    }
    
    sessions[session_id] = {"config": config}
    
    # Start the graph execution in background
    asyncio.create_task(run_graph(session_id, initial_state, config))

async def run_graph(session_id: str, initial_state: dict, config: dict):
    try:
        if initial_state:
            logging.info(f"[{session_id}] Initial call to graph")
            graph.invoke(initial_state, config)
        else:
            logging.info(f"[{session_id}] Resuming graph")
            graph.invoke(Command(resume={}), config)
        
        current_state = graph.get_state(config)
        logging.info(f"[{session_id}] Graph execution complete. Next node: {current_state.next}")
        logging.debug(f"[{session_id}] Current values keys: {list(current_state.values.keys()) if current_state.values else 'None'}")
        
        if not session_id in websockets:
            logging.warning(f"[{session_id}] No websocket found, ending graph.")
            return

        if not current_state.next or current_state.next == END:
            plan = current_state.values.get('final_plan')
            if session_id in websockets:
                if not plan or not plan.get('content') or len(plan.get('content', [])) == 0:
                    logging.warning(f"[{session_id}] No plan generated.")
                    await websockets[session_id].send_text(json.dumps({
                        "type": "plan_complete",
                        "plan": []
                    }))
                else:
                    await websockets[session_id].send_text(json.dumps({
                        "type": "plan_complete",
                        "plan": plan.get('content', []) if plan else []
                    }))

        # Send any pending WebSocket messages
        elif session_id in pending_messages:
            logging.info(f"[{session_id}] Pending message being sent:")
            logging.info(f"[{session_id}] {pending_messages[session_id]}")
            with pending_messages_lock:
                for message in pending_messages[session_id]:
                    await websockets[session_id].send_text(json.dumps(message))
                pending_messages[session_id] = []
        else:
            # nothing to do, so continue with workflow
            asyncio.create_task(run_graph(session_id, None, config))
        
    except Exception as e:
        logging.error(f"[{session_id}] Error in run_graph: {e}")
        if session_id in websockets:
            await websockets[session_id].send_text(json.dumps({
                "type": "error",
                "message": str(e)
            }))

async def handle_user_response(session_id: str, message: dict):
    logging.debug(f"[{session_id}] handle_user_response: {message}")

    if session_id not in sessions:
        return

    with user_responses_lock:
        user_responses[session_id] = message["answers"]

    # Resume workflow with user_response passed to the next node
    config = sessions[session_id]["config"]
    asyncio.create_task(run_graph(session_id, None, config))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
