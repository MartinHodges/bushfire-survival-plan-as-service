from StateTypes import GraphState
import logging
import json
import asyncio

class WebSocketChoice:
    def __init__(self, section, message_section, prompt, choices, redis_client):
        self.section = section
        self.prompt = prompt
        self.choices = choices
        self.message_section = message_section
        self.redis_client = redis_client

    def __call__(self, state: GraphState):
        session_id = state.session_id
        logging.debug(f"[{session_id}]WebSocketChoice node ({self.section})")
        if not session_id:
            logging.error(f"[{session_id}] No session_id in state")
            return {}
        
        msg_section_obj = getattr(state, self.message_section, None)
        message = getattr(msg_section_obj, 'message', '') if msg_section_obj else ''
        assessment = getattr(msg_section_obj, 'assessment', '') if msg_section_obj else ''
        risk_level = getattr(msg_section_obj, 'risk_level', '') if msg_section_obj else ''
        capability_level = getattr(msg_section_obj, 'capability_level', '') if msg_section_obj else ''
        if len(risk_level) > 0:
            level_label = "Risk Level"
        elif len(capability_level) > 0:
            level_label = "Capability Level"
        else:
            level_label = None
        level = risk_level + capability_level

        # Store message in Redis
        message_data = {
            "type": "choice",
            "section": self.section,
            "prompt": self.prompt,
            "choices": self.choices,
            "message": message,
            "assessment": assessment,
            "level_label": level_label,
            "level": level
        }
        
        # Use asyncio to run Redis operation
        loop = asyncio.get_event_loop()
        loop.create_task(self._store_message(session_id, message_data))

        # Return update to ensure state persistence
        return {
            self.section: {
                "choice_prompt": self.prompt
            }
        }
    
    async def _store_message(self, session_id, message):
        await self.redis_client.lpush(f"pending:{session_id}", json.dumps(message))
        await self.redis_client.expire(f"pending:{session_id}", 3600)

class WebSocketSelection:
    def __init__(self, section, redis_client):
        self.section = section
        self.redis_client = redis_client

    def __call__(self, state: GraphState):
        session_id = state.session_id
        logging.debug(f"[{session_id}]WebSocketSelection node ({self.section})")
        if not session_id:
            logging.error(f"[{session_id}] No session_id in state")
            return {}

        # Get user responses from Redis
        loop = asyncio.get_event_loop()
        user_response_dict = loop.run_until_complete(self._get_responses(session_id))
        
        if not user_response_dict:
            return {}
        
        # Extract the actual choice value
        user_response = list(user_response_dict.values())[0] if user_response_dict else None
        if not user_response:
            return {}

        # Update answers in place
        choice_obj = getattr(state, self.section, None)
        choice_prompt = choice_obj.choice_prompt
        choice_obj.choices_made.update({
            choice_prompt: user_response
        })
        choice_obj.last_choice = user_response

        return {self.section: choice_obj}
    
    async def _get_responses(self, session_id):
        return await self.redis_client.hgetall(f"responses:{session_id}")