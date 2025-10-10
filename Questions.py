from StateTypes import GraphState
import logging
import json
import redis

class WebSocketQuestions:
    def __init__(self, section, redis_client=None):
        self.section = section

    def __call__(self, state: GraphState):
        session_id = state.session_id
        logging.debug(f"[{session_id}] WebSocketQuestions node ({self.section})")
        if not session_id:
            logging.error(f"[{session_id}] No session_id in state")
            return {}
        
        section_obj = getattr(state, self.section, None)
        questions_section = getattr(section_obj, 'questions', None) if section_obj else None
        questions = questions_section.questions if questions_section else []
        
        if len(questions) == 0:
            logging.warning(f"[{session_id}] No questions to ask in section {self.section}")
            return {}
        
        # Store message in memory for main.py to send
        message = {
            "type": "questions",
            "section": self.section,
            "questions": questions
        }
        
        # Import main module to access pending_messages
        import main
        if session_id not in main.pending_messages:
            main.pending_messages[session_id] = []
        main.pending_messages[session_id].append(message)
        
        return {}

class WebSocketAnswers:
    def __init__(self, section, redis_client=None):
        self.section = section

    def __call__(self, state: GraphState):
        session_id = state.session_id
        logging.debug(f"[{session_id}] WebSocketAnswers section ({self.section})")
        if not session_id:
            logging.error(f"[{session_id}] No session_id in state")
            return {}

        # Get user responses from memory
        import main
        user_response = main.user_responses.get(session_id, {})
        
        if not user_response:
            return {}

        # Update answers in place
        section_obj = getattr(state, self.section, None)
        if section_obj and hasattr(section_obj, 'questions'):
            section_obj.questions.answers.update(user_response)
        return {}