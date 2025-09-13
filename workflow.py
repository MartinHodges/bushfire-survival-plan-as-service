from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from StateTypes import GraphState
import nodes
from context_utils import value_with_default, value_with_default_and_questions
from AssessRisk import AssessRisk
from AssessDefence import AssessDefence
from CreateLeavePlan import CreateLeavePlan
from CreateStayPlan import CreateStayPlan
from ShowPlan import ShowPlan
from Questions import WebSocketQuestions, WebSocketAnswers
from Choice import WebSocketChoice, WebSocketSelection

def create_graph(llm, pending_messages, user_responses, pending_messages_lock):
    graph_builder = StateGraph(GraphState)
    graph_builder.add_node(nodes.ASSESS_RISK_NODE, AssessRisk(llm))
    graph_builder.add_node(nodes.ASK_RISK_QUESTIONS_NODE, WebSocketQuestions("risk_assessment", pending_messages, pending_messages_lock))
    graph_builder.add_node(nodes.GET_RISK_ANSWERS_NODE, WebSocketAnswers("risk_assessment", user_responses))

    graph_builder.add_node(nodes.ASK_CONTINUE_WITH_PLAN_NODE, WebSocketChoice("continue_with_plan", "risk_assessment", "Continue with plan?", ["yes","no"], pending_messages, pending_messages_lock))
    graph_builder.add_node(nodes.GET_CONTINUE_WITH_PLAN_NODE, WebSocketSelection("continue_with_plan", user_responses))
    
    graph_builder.add_node(nodes.ASSESS_DEFENCE_NODE, AssessDefence(llm))
    graph_builder.add_node(nodes.ASK_DEFENCE_QUESTIONS_NODE, WebSocketQuestions("defence_assessment", pending_messages, pending_messages_lock))
    graph_builder.add_node(nodes.GET_DEFENCE_ANSWERS_NODE, WebSocketAnswers("defence_assessment", user_responses))

    graph_builder.add_node(nodes.ASK_STRATEGY_NODE, WebSocketChoice("stay_or_leave_plan", "defence_assessment", "Do you want to create a leave early or stay and defend plan?", ["leave", "stay"], pending_messages, pending_messages_lock))
    graph_builder.add_node(nodes.GET_STRATEGY_NODE, WebSocketSelection("stay_or_leave_plan", user_responses))
    
    graph_builder.add_node(nodes.CREATE_LEAVE_PLAN_NODE, CreateLeavePlan(llm))
    graph_builder.add_node(nodes.ASK_LEAVE_PLAN_QUESTIONS_NODE, WebSocketQuestions("leave_plan", pending_messages, pending_messages_lock))
    graph_builder.add_node(nodes.GET_LEAVE_PLAN_ANSWERS_NODE, WebSocketAnswers("leave_plan", user_responses))
    
    graph_builder.add_node(nodes.CREATE_STAY_PLAN_NODE, CreateStayPlan(llm))
    graph_builder.add_node(nodes.ASK_STAY_PLAN_QUESTIONS_NODE, WebSocketQuestions("stay_plan", pending_messages, pending_messages_lock))
    graph_builder.add_node(nodes.GET_STAY_PLAN_ANSWERS_NODE, WebSocketAnswers("stay_plan", user_responses))
    
    graph_builder.add_node(nodes.SHOW_PLAN_NODE, ShowPlan(llm))

    # Add edges
    graph_builder.add_edge(START, nodes.ASSESS_RISK_NODE)
    graph_builder.add_edge(nodes.ASK_RISK_QUESTIONS_NODE, nodes.GET_RISK_ANSWERS_NODE)
    graph_builder.add_edge(nodes.GET_RISK_ANSWERS_NODE, nodes.ASSESS_RISK_NODE)
    graph_builder.add_edge(nodes.ASK_CONTINUE_WITH_PLAN_NODE, nodes.GET_CONTINUE_WITH_PLAN_NODE)

    graph_builder.add_edge(nodes.ASK_DEFENCE_QUESTIONS_NODE, nodes.GET_DEFENCE_ANSWERS_NODE)
    graph_builder.add_edge(nodes.ASK_STRATEGY_NODE, nodes.GET_STRATEGY_NODE)

    graph_builder.add_edge(nodes.ASK_STAY_PLAN_QUESTIONS_NODE, nodes.GET_STAY_PLAN_ANSWERS_NODE)
    graph_builder.add_edge(nodes.GET_STAY_PLAN_ANSWERS_NODE, nodes.CREATE_STAY_PLAN_NODE)

    graph_builder.add_edge(nodes.ASK_LEAVE_PLAN_QUESTIONS_NODE, nodes.GET_LEAVE_PLAN_ANSWERS_NODE)
    graph_builder.add_edge(nodes.GET_LEAVE_PLAN_ANSWERS_NODE, nodes.CREATE_LEAVE_PLAN_NODE)

    graph_builder.add_edge(nodes.SHOW_PLAN_NODE, END)

    # Add conditional edges
    graph_builder.add_conditional_edges(
        source=nodes.ASSESS_RISK_NODE,
        path=lambda state: value_with_default_and_questions(
            state.risk_assessment.risk_level, 
            ['low', 'high', 'unclear'], 
            state.risk_assessment.questions,
            state
            ),
        path_map={
            "unclear": nodes.ASK_RISK_QUESTIONS_NODE,
            "low": nodes.ASK_CONTINUE_WITH_PLAN_NODE,
            "high": nodes.ASK_CONTINUE_WITH_PLAN_NODE,
            "default": nodes.ASSESS_RISK_NODE,
            "undetermined": nodes.ASK_CONTINUE_WITH_PLAN_NODE,
        }
    )

    graph_builder.add_conditional_edges(
        source=nodes.GET_CONTINUE_WITH_PLAN_NODE,
        path=lambda state: value_with_default(state.continue_with_plan.last_choice, ['no', 'yes'], state),
        path_map={
            "yes": nodes.ASSESS_DEFENCE_NODE,
            "no": END,
            "default": nodes.GET_CONTINUE_WITH_PLAN_NODE
        }
    )

    graph_builder.add_conditional_edges(
        source=nodes.ASSESS_DEFENCE_NODE,
        path=lambda state: value_with_default_and_questions(
            state.defence_assessment.capability_level, 
            ['low', 'high', 'unclear'], 
            state.defence_assessment.questions,
            state
            ),
        path_map={
            "unclear": nodes.ASK_DEFENCE_QUESTIONS_NODE,
            "low": nodes.ASK_STRATEGY_NODE,
            "high": nodes.ASK_STRATEGY_NODE,
            "default": nodes.ASK_STRATEGY_NODE,
            "undetermined": nodes.ASK_STRATEGY_NODE
        }
    )

    graph_builder.add_conditional_edges(
        source=nodes.GET_STRATEGY_NODE,
        path=lambda state: value_with_default(state.stay_or_leave_plan.last_choice, ['stay', 'leave'], state),
        path_map={
            "stay": nodes.CREATE_STAY_PLAN_NODE,
            "leave": nodes.CREATE_LEAVE_PLAN_NODE,
            "default": nodes.ASK_STRATEGY_NODE
        }
    )

    graph_builder.add_conditional_edges(
        source=nodes.CREATE_LEAVE_PLAN_NODE,
        path=lambda state: (
            value_with_default(state.leave_plan.plan_status, ['more', 'done'], state)
        ),
        path_map={
            "more": nodes.ASK_LEAVE_PLAN_QUESTIONS_NODE,
            "done": nodes.SHOW_PLAN_NODE,
            "default": nodes.SHOW_PLAN_NODE
        }
    )

    graph_builder.add_conditional_edges(
        source=nodes.CREATE_STAY_PLAN_NODE,
        path=lambda state: value_with_default(state.stay_plan.plan_status, ['more', 'done'], state),
        path_map={
            "more": nodes.ASK_STAY_PLAN_QUESTIONS_NODE,
            "done": nodes.SHOW_PLAN_NODE,
            "default": nodes.SHOW_PLAN_NODE
        }
    )

    return graph_builder.compile(
        checkpointer=MemorySaver(),
        interrupt_before=[
            nodes.GET_RISK_ANSWERS_NODE,
            nodes.GET_CONTINUE_WITH_PLAN_NODE,
            nodes.GET_DEFENCE_ANSWERS_NODE,
            nodes.GET_STRATEGY_NODE,
            nodes.GET_LEAVE_PLAN_ANSWERS_NODE,
            nodes.GET_STAY_PLAN_ANSWERS_NODE
        ]
    )