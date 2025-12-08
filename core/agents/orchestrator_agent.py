"""
Агент-оркестратор для управления взаимодействием между другими агентами
"""
import logging
from typing import Dict, Any, List, TypedDict
from langgraph.graph import StateGraph, END
from .main_agent import plan_for_target
from .search_agent import search_for_target
from .generator_agent import generate_resume_json
from .template_selector_agent import select_template
from .validation_agent import validate_resume_json

logger = logging.getLogger('core.agents')

MAX_RETRIES = 2

class ResumeState(TypedDict, total=False):
    user_profile: Dict[str, Any]
    target: Dict[str, Any]
    request_controls: Dict[str, Any]
    plan: Dict[str, Any]
    search_data: Dict[str, Any]
    template_info: Dict[str, Any]
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

def _template_selection_node(state: ResumeState) -> ResumeState:
    template_info = select_template(state["user_profile"], state["target"], state["request_controls"])
    state["template_info"] = template_info
    return state

def _generate_node(state: ResumeState) -> ResumeState:
    generated = generate_resume_json(
        user_profile=state["user_profile"],
        target=state["target"],
        plan=state["plan"],
        search_data=state["search_data"],
        template_info=state["template_info"]
    )
    state["generated"] = generated or {}
    return state

def _validate_node(state: ResumeState) -> ResumeState:
    approved, errors = validate_resume_json(
        user_profile=state["user_profile"],
        search_data=state["search_data"],
        generated=state["generated"],
        template_info=state["template_info"]
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

def build_orchestrated_resume_graph():
    """
    Создает граф с оркестрацией, где агенты взаимодействуют через оркестратор
    """
    graph = StateGraph(ResumeState)
    
    # Добавляем все узлы
    graph.add_node("plan", _plan_node)
    graph.add_node("search", _search_node)
    graph.add_node("template_selection", _template_selection_node)
    graph.add_node("generate", _generate_node)
    graph.add_node("validate", _validate_node)
    
    # Устанавливаем начальную точку
    graph.set_entry_point("plan")
    
    # Определяем последовательность узлов
    graph.add_edge("plan", "search")
    graph.add_edge("search", "template_selection")
    graph.add_edge("template_selection", "generate")
    graph.add_edge("generate", "validate")
    
    # Условные переходы после валидации
    graph.add_conditional_edges("validate", _should_retry, {
        "generate": "generate",
        "end": END,
    })
    
    return graph.compile()

# Функция для запуска оркестрированного процесса
def run_orchestrated_resume_generation(user_profile: Dict[str, Any], 
                                    target: Dict[str, Any], 
                                    request_controls: Dict[str, Any]) -> Dict[str, Any]:
    """
    Запуск оркестрированного процесса генерации резюме
    """
    initial_state = {
        "user_profile": user_profile,
        "target": target,
        "request_controls": request_controls,
        "retries": 0
    }
    
    graph = build_orchestrated_resume_graph()
    result = graph.invoke(initial_state)
    
    return result