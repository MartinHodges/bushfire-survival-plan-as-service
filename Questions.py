from StateTypes import GraphState
import logging

class WebSocketQuestions:
    def __init__(self, section, pending_messages, lock):
        self.section = section
        self.pending_messages = pending_messages
        self.lock = lock

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
        
        # Store message to send later
        with self.lock:
            if session_id not in self.pending_messages:
                self.pending_messages[session_id] = []

            self.pending_messages[session_id].append({
                "type": "questions",
                "section": self.section,
                "questions": questions
            })
        
        return {}

class WebSocketAnswers:
    def __init__(self, section, user_responses):
        self.section = section
        self.user_responses = user_responses

    def __call__(self, state: GraphState):
        session_id = state.session_id
        logging.debug(f"[{session_id}]WebSocketAnswers node ({self.section})")
        if not session_id:
            logging.error(f"[{session_id}] No session_id in state")
            return {}

        if session_id not in self.user_responses:
            return {}
        
        user_response = self.user_responses[session_id]

        # Update answers in place
        section_obj = getattr(state, self.section, None)
        if section_obj and hasattr(section_obj, 'questions'):
            section_obj.questions.answers.update(user_response)
        return {}