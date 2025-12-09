# core/graph.py

import logging
from typing import Dict, Any
from langgraph.graph import StateGraph, END

from .main_agent import plan_for_target
from .search_agent import search_for_target
from .generator_agent import generate_resume_json
from .check_agent import check_resume_json

state_logger = logging.getLogger("resume_ai")


def build_resume_graph(max_regens: int = 1):
    """
    Простой ацикличный граф:
    1) plan -> main_agent
    2) search -> search_agent
    3) generate -> generator_agent
    4) check -> check_agent
    """
    workflow = StateGraph(dict)

    def node_plan(state: Dict[str, Any]) -> Dict[str, Any]:
        user_profile = state.get("user_profile") or {}
        target = state.get("target") or {}
        controls = state.get("request_controls") or {}

        state_logger.info(
            "Graph node plan: user_id=%s company=%s role=%s",
            user_profile.get("user_id", "n/a"),
            target.get("company", ""),
            target.get("role", ""),
        )

        plan = plan_for_target(user_profile, target, controls)
        state["plan"] = plan
        # Инициализируем retries, если нет
        state.setdefault("retries", 0)
        return state

    def node_search(state: Dict[str, Any]) -> Dict[str, Any]:
        plan = state.get("plan") or {}
        strategy = plan.get("search_strategy") or {}
        need_search = bool(strategy.get("need_search", True))

        state_logger.info("Graph node search: need_search=%s", need_search)

        if not need_search:
            state["search_data"] = {"findings": {}, "raw": ""}
            return state

        search_data = search_for_target(plan)
        state["search_data"] = search_data
        return state

    def node_generate(state: Dict[str, Any]) -> Dict[str, Any]:
        user_profile = state.get("user_profile") or {}
        target = state.get("target") or {}
        plan = state.get("plan") or {}
        search_data = state.get("search_data") or {}
        feedback = state.get("regen_directives") or {}

        state_logger.info(
            "Graph node generate: company=%s role=%s retry=%s",
            target.get("company", ""),
            target.get("role", ""),
            state.get("retries", 0),
        )

        generated = generate_resume_json(
            user_profile=user_profile,
            target=target,
            plan=plan,
            search_data=search_data,
            feedback_directives=feedback or None,
        )
        state["generated"] = generated
        return state

    def node_check(state: Dict[str, Any]) -> Dict[str, Any]:
        user_profile = state.get("user_profile") or {}
        search_data = state.get("search_data") or {}
        generated = state.get("generated") or {}
        controls = state.get("request_controls") or {}

        approved, errors, regen = check_resume_json(
            user_profile=user_profile,
            search_data=search_data,
            generated=generated,
            request_controls=controls,
        )

        state["approved"] = approved
        state["errors"] = errors
        state["regen_directives"] = regen or {}

        # ВАЖНО: не сбрасываем retries здесь, он управляется в _decide_next

        state_logger.info(
            "Graph node check: approved=%s errors=%d retries=%s",
            approved,
            len(errors),
            state.get("retries", 0),
        )
        return state

    workflow.add_node("plan", node_plan)
    workflow.add_node("search", node_search)
    workflow.add_node("generate", node_generate)
    workflow.add_node("check", node_check)

    workflow.set_entry_point("plan")
    workflow.add_edge("plan", "search")
    workflow.add_edge("search", "generate")
    workflow.add_edge("generate", "check")

    def _decide_next(state: Dict[str, Any]) -> str:
        approved = bool(state.get("approved"))
        retries = int(state.get("retries", 0))

        if approved:
            state_logger.info("Graph decision: approved -> END")
            return "end"

        if retries < max_regens:
            # Инкрементируем счетчик ТОЛЬКО здесь
            state["retries"] = retries + 1
            state_logger.info(
                "Graph decision: regen (try %s of %s)", state["retries"], max_regens
            )
            return "regen"

        state_logger.warning(
            "Graph decision: max retries reached -> END (retries=%s)", retries
        )
        return "end"

    workflow.add_conditional_edges(
        "check",
        _decide_next,
        {
            "regen": "generate",
            "end": END,
        },
    )

    return workflow.compile()
