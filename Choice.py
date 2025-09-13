from StateTypes import GraphState
import logging

class WebSocketChoice:
    def __init__(self, section, message_section, prompt, choices, pending_messages, lock):
        self.section = section
        self.prompt = prompt
        self.choices = choices
        self.message_section = message_section
        self.pending_messages = pending_messages
        self.lock = lock

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

        # Store message to send later
        with self.lock:
            if session_id not in self.pending_messages:
                self.pending_messages[session_id] = []
            
            self.pending_messages[session_id].append({
                "type": "choice",
                "section": self.section,
                "prompt": self.prompt,
                "choices": self.choices,
                "message": message,
                "assessment": assessment,
                "level_label": level_label,
                "level": level
            })

        # Return update to ensure state persistence
        return {
            self.section: {
                "choice_prompt": self.prompt
            }
        }

class WebSocketSelection:
    def __init__(self, section, user_responses):
        self.section = section
        self.user_responses = user_responses

    def __call__(self, state: GraphState):
        session_id = state.session_id
        logging.debug(f"[{session_id}]WebSocketSelection node ({self.section})")
        if not session_id:
            logging.error(f"[{session_id}] No session_id in state")
            return {}

        if session_id not in self.user_responses:
            return {}
            
        user_response = self.user_responses[session_id]

        # Update answers in place
        choice_obj = getattr(state, self.section, None)
        choice_prompt = choice_obj.choice_prompt
        choice_obj.choices_made.update({
            choice_prompt: user_response
        })
        choice_obj.last_choice = user_response

        return {self.section: choice_obj}