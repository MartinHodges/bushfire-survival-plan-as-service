# mock_llm.py
from langchain_core.language_models.base import BaseLanguageModel
from langchain_core.messages import AIMessage
import json
import logging
from typing import Any

# Create logger for this module
logger = logging.getLogger(__name__)

class MockBushfireLLM(BaseLanguageModel):
    call_count: int = 0
    risk_calls: int = 0
    defence_calls: int = 0
    plan_creation_calls: int = 0
    
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self.call_count = 0
        self.risk_calls = 0
        self.defence_calls = 0
        self.plan_creation_calls = 0
        
    def reset_counters(self):
        """Reset all call counters for a new session"""
        self.call_count = 0
        self.risk_calls = 0
        self.defence_calls = 0
        self.plan_creation_calls = 0
        logger.debug("MockBushfireLLM counters reset")
        
    def invoke(self, *args, **kwargs):
        self.call_count += 1
        # Extract input from args - could be messages, prompt, or other formats
        input_data = args[0] if args else []
        logger.debug(f"MockBushfireLLM {self.call_count}: invoked with type: {type(input_data)}")
        
        # Handle different input types
        if hasattr(input_data, 'to_string'):
            # StringPromptValue or similar
            last_message = input_data.to_string()
        elif hasattr(input_data, 'text'):
            # PromptValue with text attribute
            last_message = input_data.text
        elif isinstance(input_data, list) and input_data:
            # List of messages
            if hasattr(input_data[-1], 'content'):
                last_message = str(input_data[-1].content)
            else:
                last_message = str(input_data[-1])
        elif isinstance(input_data, str):
            # Direct string
            last_message = input_data
        else:
            # Fallback
            last_message = str(input_data)

        logger.debug(f"MockBushfireLLM {self.call_count}: message: {last_message[:1000]}...")

        # Detect expected response type from JSON schema in prompt
        if "Phase: Risk Assessment" in last_message:
            self.risk_calls += 1
            logging.debug(f"MockBushfireLLM {self.call_count}: Risk Assessment call #{self.risk_calls}")
            
            if self.risk_calls == 1:
                # First call - ask questions
                return AIMessage(content=json.dumps({
                    "risk_level": "unclear",
                    "message": "I need more information to assess your bushfire risk.",
                    "assessment": "Initial risk assessment requires property details.",
                    "questions": {
                        "questions": [
                            "What is your property address?",
                            "How close is your property to bushland?",
                            "What type of vegetation surrounds your property?"
                        ],
                        "answers": {}
                    }
                }))
            else:
                # Second+ call - return completed assessment
                return AIMessage(content=json.dumps({
                    "risk_level": "high",
                    "message": "Based on your responses, you have high bushfire risk.",
                    "assessment": "Your property is in a high-risk bushfire area with significant vegetation nearby."
                }))
        
        if "Phase: Capability Assessment" in last_message:
            self.defence_calls += 1
            logging.debug(f"MockBushfireLLM {self.call_count}: Capability Assessment call #{self.defence_calls}")
            
            if self.defence_calls == 1:
                # First call - ask questions
                return AIMessage(content=json.dumps({
                    "capability_level": "unclear", 
                    "message": "I need to understand your defense capabilities.",
                    "assessment": "Defense assessment requires equipment and experience details.",
                    "questions": {
                        "questions": [
                            "Do you have firefighting equipment?",
                            "Have you defended property before?",
                            "How many able-bodied adults are available?"
                        ],
                        "answers": {}
                    }
                }))
            else:
                # Second+ call - return completed assessment
                return AIMessage(content=json.dumps({
                    "capability_level": "high",
                    "message": "Based on your responses, you have good defense capabilities.",
                    "assessment": "You have adequate equipment and experience to defend your property."
                }))
        
        if "Phase: Leave Plan Creation" in last_message:
            self.plan_creation_calls += 1
            logging.debug(f"MockBushfireLLM {self.call_count}: Detected Leave Plan Creation phase")
            if self.plan_creation_calls == 1:
                # First call - ask questions
                return AIMessage(content=json.dumps({
                    "plan_status": "more",
                    "questions": {
                        "questions": [
                            "What is your primary evacuation route?",
                            "How long do you estimate it will take to evacuate?",
                            "What factors could delay your evacuation?"
                        ],
                        "answers": {}
                    },
                    "when_to_leave": None,
                    "where_to_go": None,
                    "how_to_get_there": None,
                    "what_to_take": None,
                    "who_to_tell": None,
                    "backup_plan": None
                }))
            else:
                # Second+ call - return completed assessment
                return AIMessage(content=json.dumps({
                    "plan_status": "done",
                    "when_to_leave": "Leave when Fire Danger Rating reaches Severe or above",
                    "where_to_go": "Evacuation center at local community hall",
                    "how_to_get_there": "Take main highway route avoiding back roads",
                    "what_to_take": "Emergency kit, important documents, medications",
                    "who_to_tell": "Family members, neighbors, and emergency services",
                    "backup_plan": "If roads blocked, shelter in place with emergency supplies"
                }))
        if "Phase: Stay Plan Creation" in last_message:
            self.plan_creation_calls += 1
            logging.debug(f"MockBushfireLLM {self.call_count}: Detected Stay Plan Creation phase")
            if self.plan_creation_calls == 1:
                # First call - ask questions
                return AIMessage(content=json.dumps({
                    "plan_status": "more",
                    "questions": {
                        "questions": [
                            "What is your primary shelter location?",
                            "What resources do you have on hand?",
                            "How will you monitor the fire situation?"
                        ],
                        "answers": {}
                    },
                    "when_to_start": None,
                    "before_the_fire": None,
                    "during_the_fire": None,
                    "after_the_fire": None,
                    "who_can_help": None,
                    "peoples_roles": None,
                    "backup_plan": None
                }))
            else:
                # Second+ call - return completed assessment
                return AIMessage(content=json.dumps({
                    "plan_status": "done",
                    "when_to_start": "Start preparations when Fire Danger Rating reaches High",
                    "before_the_fire": "Clear gutters, fill water tanks, prepare firefighting equipment",
                    "during_the_fire": "Monitor conditions, defend property, stay in safe zone",
                    "after_the_fire": "Check for spot fires, assess damage, contact authorities",
                    "who_can_help": "Trained family members and neighbors with firefighting experience",
                    "peoples_roles": "Adults handle hoses, children stay in safe room with radio",
                    "backup_plan": "If fire too intense, retreat to bunker or evacuate immediately"
                }))
        if "Phase: Creating Final Plan" in last_message:
            logging.debug(f"MockBushfireLLM {self.call_count}: Detected Creating Final Plan phase")

            return AIMessage(content=
"""
<h1>Bushfire Survival Plan</h1>
<h2>Risk Level: HIGH</h2>
<h2>Strategy: Leave Early</h2>
<ol>
<li>Monitor fire danger ratings daily</li>
<li>Leave before Total Fire Ban days</li>
<li>Have evacuation route planned</li>
</ol>
"""
            )
        
        # Default response
        return AIMessage(content="Mock LLM response")
    
    def _generate(self, messages, **kwargs):
        result = self.invoke(messages, **kwargs)
        from langchain_core.outputs import LLMResult, Generation
        return LLMResult(generations=[[Generation(text=result.content)]])
        
    async def _agenerate(self, messages, **kwargs):
        return self._generate(messages, **kwargs)
        
    def generate_prompt(self, prompts, **kwargs):
        from langchain_core.outputs import LLMResult, Generation
        generations = []
        for prompt in prompts:
            result = self.invoke([prompt], **kwargs)
            generations.append([Generation(text=result.content)])
        return LLMResult(generations=generations)
        
    async def agenerate_prompt(self, prompts, **kwargs):
        return self.generate_prompt(prompts, **kwargs)
        
    def predict(self, text, **kwargs):
        from langchain_core.messages import HumanMessage
        result = self.invoke([HumanMessage(content=text)], **kwargs)
        return result.content
        
    async def apredict(self, text, **kwargs):
        return self.predict(text, **kwargs)
        
    def predict_messages(self, messages, **kwargs):
        result = self.invoke(messages, **kwargs)
        return result
        
    async def apredict_messages(self, messages, **kwargs):
        return self.predict_messages(messages, **kwargs)
        
    @property
    def _llm_type(self):
        return "mock_bushfire_llm"
