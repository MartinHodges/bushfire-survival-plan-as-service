from StateTypes import GraphState
import logging
import json
import redis

logger = logging.getLogger(__name__)

class WebSocketChoice:
    def __init__(self, section, message_section, prompt, choices, redis_client=None):
        self.section = section
        self.prompt = prompt
        self.choices = choices
        self.message_section = message_section

    def __call__(self, state: GraphState):
        session_id = state.session_id
        logger.debug(f"[{session_id}] WebSocketChoice node ({self.section})")
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
        
        # Import main module to access pending_messages
        import main
        if session_id not in main.pending_messages:
            main.pending_messages[session_id] = []
        main.pending_messages[session_id].append(message_data)

        # Return update to ensure state persistence
        return {
            self.section: {
                "choice_prompt": self.prompt
            }
        }

class WebSocketSelection:
    def __init__(self, section, redis_client=None):
        self.section = section

    def __call__(self, state: GraphState):
        session_id = state.session_id
        logger.debug(f"[{session_id}] WebSocketSelection section ({self.section})")
        if not session_id:
            logger.error(f"[{session_id}] No session_id in state")
            return {}

        # Get user responses from memory
        import main
        user_response_dict = main.user_responses.get(session_id, {})
        
        if not user_response_dict:
            return {}
        logger.info(f"[{session_id}] User choice: {user_response_dict}")
        # Extract the actual choice value
        user_choice = user_response_dict.get('choice', None)
        if not user_choice:
            return {}

        logger.info(f"[{session_id}] User choice: {user_choice}")
        # Update answers in place
        choice_obj = getattr(state, self.section, None)
        choice_prompt = choice_obj.choice_prompt
        choice_obj.choices_made.update({
            choice_prompt: user_choice
        })
        choice_obj.last_choice = user_choice

        return {self.section: choice_obj}