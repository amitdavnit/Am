from __future__ import annotations

from langgraph.graph import END, StateGraph

from agent.state import AIDQXState
from services.dqx_service import execute_rules, generate_rules, run_profiling


def profiling_node(state: AIDQXState) -> AIDQXState:
    try:
        profile = run_profiling(
            state["catalog"],
            state["schema"],
            state["table"],
        )
        return {**state, "profile_result": profile, "error": ""}
    except Exception as exc:
        return {**state, "error": str(exc)}


def rules_node(state: AIDQXState) -> AIDQXState:
    if state.get("error"):
        return state
    rules = generate_rules(state["profile_result"])
    return {
        **state,
        "generated_rules": rules,
        "approved_rules": rules,
    }


def execution_node(state: AIDQXState) -> AIDQXState:
    if state.get("error"):
        return state
    result = execute_rules(
        state["catalog"],
        state["schema"],
        state["table"],
        state.get("approved_rules", state.get("generated_rules", [])),
    )
    return {**state, "execution_result": result}


def route_after_rules(state: AIDQXState):
    action = state.get("requested_action", "profile_and_rules")
    if action == "execute":
        return "execute"
    return "end"


def build_graph():
    workflow = StateGraph(AIDQXState)

    workflow.add_node("profile", profiling_node)
    workflow.add_node("generate_rules", rules_node)
    workflow.add_node("execute", execution_node)

    workflow.set_entry_point("profile")
    workflow.add_edge("profile", "generate_rules")
    workflow.add_conditional_edges(
        "generate_rules",
        route_after_rules,
        {
            "execute": "execute",
            "end": END,
        },
    )
    workflow.add_edge("execute", END)

    return workflow.compile()


aidqx_graph = build_graph()
