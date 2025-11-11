import logging
from typing import Dict, Any, List, TypedDict

from langgraph.graph import StateGraph, END

from .main_agent import plan_for_target
from .search_agent import search_for_target
from .generator_agent import generate_resume_json
from .check_agent import check_resume_json

logger = logging.getLogger('core.agents')

MAX_RETRIES = 2

class ResumeState(TypedDict, total=False):
    user_profile: Dict[str, Any]
    target: Dict[str, Any]
    request_controls: Dict[str, Any]
    plan: Dict[str, Any]
    search_data: Dict[str, Any]
    generated: Dict[str, Any]
    approved: bool
    errors: List[str]
    retries: int

def _plan_node(state: ResumeState) -> ResumeState:
    plan = plan_for_target(state["user_profile"], state["target"], state["request_controls"])
    state["plan"] = plan
    return state

def _search_node(state: ResumeState) -> ResumeState:
    search_data = search_for_target(state["plan"])
    state["search_data"] = search_data
    return state

def _generate_node(state: ResumeState) -> ResumeState:
    generated = generate_resume_json(
        user_profile=state["user_profile"],
        target=state["target"],
        plan=state["plan"],
        search_data=state["search_data"],
    )
    state["generated"] = generated or {}
    return state

def _check_node(state: ResumeState) -> ResumeState:
    approved, errors = check_resume_json(
        user_profile=state["user_profile"],
        search_data=state["search_data"],
        generated=state["generated"],
    )
    state["approved"] = approved
    state["errors"] = errors

    if not approved:
        state["retries"] = state.get("retries", 0) + 1

    return state

def _should_retry(state: ResumeState) -> str:
    if state.get("approved"):
        return "end"
    if state.get("retries", 0) < MAX_RETRIES:
        logger.info("Retrying generation (%s/%s) for company=%s",
                    state["retries"], MAX_RETRIES, state["target"].get("company"))
        return "generate"
    return "end"

def build_resume_graph():
    graph = StateGraph(ResumeState)
    graph.add_node("plan", _plan_node)
    graph.add_node("search", _search_node)
    graph.add_node("generate", _generate_node)
    graph.add_node("check", _check_node)

    graph.set_entry_point("plan")
    graph.add_edge("plan", "search")
    graph.add_edge("search", "generate")
    graph.add_edge("generate", "check")
    graph.add_conditional_edges("check", _should_retry, {
        "generate": "generate",
        "end": END,
    })
    return graph.compile()
