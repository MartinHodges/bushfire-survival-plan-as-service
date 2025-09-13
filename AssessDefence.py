from StateTypes import GraphState, DefenceAnalysis
from context_utils import build_context
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
import logging

defence_analysis_parser = PydanticOutputParser(pydantic_object=DefenceAnalysis)

defence_analysis_prompt = PromptTemplate(
    template="""
 Situation
You are an expert Australian bushfire risk assessor evaluating my
capability, as a property owner, to defend my home during a bushfire emergency. 
Your assessment will directly impact my bushfire survival plan and potentially 
save lives.

Task
Conduct a thorough, evidence-based assessment of the my defense capability based 
solely on the information provided in the context. Categorize my capability 
level and provide appropriate next steps tailored to Australian bushfire safety
protocols.

Objective
Deliver a clear, actionable assessment that helps me make an informed decision about
whether to stay and defend or leave early during a bushfire threat, prioritizing 
human safety above property protection in accordance with Australian bushfire safety
principles.

Knowledge
Australian bushfire defense capability depends on multiple factors: physical ability, 
equipment, water supply, property preparation, knowledge of fire behavior, and 
emotional readiness.
Stay and defend decisions require significant preparation and capability.
Early evacuation is the safest option for those with limited capability.
The "prepare, act, survive" doctrine emphasizes preparation regardless of the chosen 
plan.
Different Australian states may have varying specific recommendations.
Capability assessment must consider vulnerable household members (children, 
elderly, disabled, pets).

Next Steps:

Record your defence assessment ('low', 'high', 'unclear') in capability_level.
Use 'unclear' if you you need to ask more questions. Record your questions in questions.
Do not ask the same question.

If you have determined a level of high or low capability, conclude your response 
by showing your defence assessment more than once.

It is crucial that you provide an accurate, unbiased assessment that could
save lives during a bushfire emergency. Do not downplay risks or overstate 
capabilities. Be direct and honest in your evaluation, as people's safety 
depends on your assessment.

    Context: {full_context}
    
    {format_instructions}
    """,
    input_variables=["full_context"],
    partial_variables={"format_instructions": defence_analysis_parser.get_format_instructions()},
)

class AssessDefence:
  def __init__(self, llm):
    self.llm = llm
    self.llm_chain = defence_analysis_prompt | llm | defence_analysis_parser

  def __call__(self, state: GraphState):
    """
    Assesses the ability for users to defend their property against bushfire risk using an LLM and structured parsing.
    """

    logging.debug(f"[{state.session_id}] Assessing stay and defend capability")

    full_context = build_context(state)
    parsed_response = self.llm_chain.invoke({"full_context": full_context})

    return {
      "defence_assessment": parsed_response,
    }