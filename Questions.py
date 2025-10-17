from StateTypes import GraphState
import logging
import json

logger = logging.getLogger(__name__)

class Questions:
    def __init__(self, section, sync_redis_client=None):
        self.section = section
        self.sync_redis = sync_redis_client

    def __call__(self, state: GraphState):
        session_id = state.session_id
        logger.debug(f"[{session_id}] Questions node ({self.section})")
        if not session_id:
            logger.error(f"[{session_id}] No session_id in state")
            return {}
        
        section_obj = getattr(state, self.section, None)
        questions_section = getattr(section_obj, 'questions', None) if section_obj else None
        questions = questions_section.questions if questions_section else []
        
        if len(questions) == 0:
            logger.warning(f"[{session_id}] No questions to ask in section {self.section}")
            return {}
        
        # Store message in Redis for cross-context access
        message = {
            "type": "questions",
            "section": self.section,
            "questions": questions
        }
        
        if self.sync_redis:
            self.sync_redis.lpush(f"pending:{session_id}", json.dumps(message))
            self.sync_redis.expire(f"pending:{session_id}", 3600)
            logger.info(f"[{session_id}] Questions node added pending message to Redis")
        
        return {}

class Answers:
    def __init__(self, section, sync_redis_client=None):
        self.section = section
        self.sync_redis = sync_redis_client

    def __call__(self, state: GraphState):
        session_id = state.session_id
        logger.debug(f"[{session_id}] Answers section ({self.section})")
        if not session_id:
            logger.error(f"[{session_id}] No session_id in state")
            return {}

        # Get user responses from Redis
        user_response = self.sync_redis.hgetall(f"responses:{session_id}") if self.sync_redis else {}
        
        if not user_response:
            return {}

        # Update answers in place
        section_obj = getattr(state, self.section, None)
        if section_obj and hasattr(section_obj, 'questions'):
            section_obj.questions.answers.update(user_response)
        return {}