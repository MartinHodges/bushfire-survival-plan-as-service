from StateTypes import GraphState
import logging
import json
import asyncio

class WebSocketQuestions:
    def __init__(self, section, redis_client):
        self.section = section
        self.redis_client = redis_client

    def __call__(self, state: GraphState):
        session_id = state.session_id
        logging.debug(f"[{session_id}]WebSocketQuestions node ({self.section})")
        if not session_id:
            logging.error(f"[{session_id}] No session_id in state")
            return {}
        
        section_obj = getattr(state, self.section, None)
        questions_section = getattr(section_obj, 'questions', None) if section_obj else None
        questions = questions_section.questions if questions_section else []
        
        if len(questions) == 0:
            logging.warning(f"[{session_id}] No questions to ask in section {self.section}")
            return {}
        
        # Store message in Redis
        message = {
            "type": "questions",
            "section": self.section,
            "questions": questions
        }
        
        # Use asyncio to run Redis operation
        loop = asyncio.get_event_loop()
        loop.create_task(self._store_message(session_id, message))
        
        return {}
    
    async def _store_message(self, session_id, message):
        await self.redis_client.lpush(f"pending:{session_id}", json.dumps(message))
        await self.redis_client.expire(f"pending:{session_id}", 3600)

class WebSocketAnswers:
    def __init__(self, section, redis_client):
        self.section = section
        self.redis_client = redis_client

    def __call__(self, state: GraphState):
        session_id = state.session_id
        logging.debug(f"[{session_id}]WebSocketAnswers node ({self.section})")
        if not session_id:
            logging.error(f"[{session_id}] No session_id in state")
            return {}

        # Get user responses from Redis
        loop = asyncio.get_event_loop()
        user_response = loop.run_until_complete(self._get_responses(session_id))
        
        if not user_response:
            return {}

        # Update answers in place
        section_obj = getattr(state, self.section, None)
        if section_obj and hasattr(section_obj, 'questions'):
            section_obj.questions.answers.update(user_response)
        return {}
    
    async def _get_responses(self, session_id):
        return await self.redis_client.hgetall(f"responses:{session_id}")