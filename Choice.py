from StateTypes import GraphState
import logging
import redis
import json

logger = logging.getLogger(__name__)

class Choice:
    def __init__(self, section, message_section, prompt, choices, sync_redis_client=None):
        self.section = section
        self.prompt = prompt
        self.choices = choices
        self.message_section = message_section
        self.sync_redis = sync_redis_client

    def __call__(self, state: GraphState):
        session_id = state.session_id
        logger.debug(f"[{session_id}] Choice node ({self.section})")
        if not session_id:
            logger.error(f"[{session_id}] No session_id in state")
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

        # Store message in memory
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
        
        # Store message in Redis for cross-context access
        self.sync_redis.lpush(f"pending:{session_id}", json.dumps(message_data))
        self.sync_redis.expire(f"pending:{session_id}", 3600)
        logger.info(f"[{session_id}] Choice node added pending message to Redis")

        # Return update to ensure state persistence
        return {
            self.section: {
                "choice_prompt": self.prompt
            }
        }

class Selection:
    def __init__(self, section, sync_redis_client=None):
        self.section = section
        self.sync_redis = sync_redis_client

    def __call__(self, state: GraphState):
        session_id = state.session_id
        logger.debug(f"[{session_id}] Selection section ({self.section})")
        if not session_id:
            logger.error(f"[{session_id}] No session_id in state - cannot read selection")
            return {}

        # Get user responses from Redis
        user_response_dict = self.sync_redis.hgetall(f"responses:{session_id}") if self.sync_redis else {}
        
        if not user_response_dict:
            logger.info(f"[{session_id}] No user selection provided")
            exit(1)
            return {}
        logger.info(f"[{session_id}] User selection: {user_response_dict}")
        # Extract the actual choice value
        user_choice = user_response_dict.get('choice', None)
        if not user_choice:
            return {}

        logger.info(f"[{session_id}] User selection: {user_choice}")
        # Update answers in place
        choice_obj = getattr(state, self.section, None)
        choice_prompt = choice_obj.choice_prompt
        choice_obj.choices_made.update({
            choice_prompt: user_choice
        })
        choice_obj.last_choice = user_choice

        return {self.section: choice_obj}