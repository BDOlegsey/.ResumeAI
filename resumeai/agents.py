import logging
from langchain_perplexity import ChatPerplexity
from langchain_core.prompts import ChatPromptTemplate
from .models import UserData, SearchResults, ResumeDraft, AgentState
from .database import get_employer_info, store_employer_info

logger = logging.getLogger(__name__)

llm = ChatPerplexity(model="sonar", temperature=0.1)

def main_agent_node(state: AgentState) -> AgentState:
    logger.info("Main Agent: selecting employer")
    if not state.user_data:
        state.error_message = "Нет пользовательских данных."
        return state
    if state.current_employer is None:
        if state.user_data.employers:
            state.current_employer = state.user_data.employers[0]
        else:
            state.error_message = "Список работодателей пуст."
    return state

def search_agent_node(state: AgentState) -> AgentState:
    logger.info(f"Search Agent: {state.current_employer}")
    if not state.current_employer:
        state.error_message = "Работодатель не задан."
        return state

    cached = get_employer_info(state.current_employer)
    if cached:
        logger.info("Using cached employer info")
        state.search_results = cached
        return state

    prompt = ChatPromptTemplate.from_messages([
        ("system", "Ты — исследователь компании с доступом к веб‑поиску Perplexity. Отвечай на русском."),
        ("human", "Исследуй работодателя '{employer}' для роли '{title}'. Верни JSON с полями: company_info и job_specific_info.")
    ])
    chain = prompt | llm.with_structured_output(SearchResults)

    try:
        result = chain.invoke(
            {"employer": state.current_employer, "title": state.user_data.job_title},
            extra_body={"search_mode": "web", "search_recency_filter": "year"}
        )
        result.employer_name = state.current_employer
        store_employer_info(result)
        state.search_results = result
    except Exception as e:
        logger.error(f"Search failed: {e}")
        state.error_message = f"Ошибка поиска: {e}"
    return state

def generator_agent_node(state: AgentState) -> AgentState:
    logger.info("Generator Agent: creating resume")
    if not state.search_results or not state.user_data:
        state.error_message = "Нет данных для генерации."
        return state

    prompt = ChatPromptTemplate.from_messages([
        ("system", "Ты — эксперт по написанию резюме. Составь профессиональное резюме на русском под позицию '{job_title}' в '{employer_name}'."),
        ("human", "Опыт: {experience}\nНавыки: {skills}\nДостижения: {achievements}\n\nО компании: {company_info}\nПо роли: {job_specific_info}\n\nСоздай резюме.")
    ])
    chain = prompt | llm

    try:
        response = chain.invoke({
            "job_title": state.user_data.job_title,
            "employer_name": state.current_employer,
            "experience": state.user_data.experience,
            "skills": state.user_data.skills,
            "achievements": state.user_data.achievements,
            "company_info": state.search_results.company_info,
            "job_specific_info": state.search_results.job_specific_info
        })
        content = response.content if hasattr(response, "content") else str(response)
        state.resume_draft = ResumeDraft(draft_content=content, is_validated=False)
        state.iteration_count += 1
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        state.error_message = f"Ошибка генерации: {e}"
    return state

def checker_agent_node(state: AgentState) -> AgentState:
    logger.info("Checker Agent: reviewing")
    if not state.resume_draft:
        state.error_message = "Нет черновика для проверки."
        return state

    prompt = ChatPromptTemplate.from_messages([
        ("system", "Ты — редактор резюме. Проверь качество. Если всё хорошо — напиши 'VALIDATED'. Пиши на русском."),
        ("human", "Черновик:\n{draft_content}\n\nОтзыв:")
    ])
    chain = prompt | llm

    try:
        response = chain.invoke({"draft_content": state.resume_draft.draft_content})
        feedback = response.content if hasattr(response, "content") else str(response)
        if "VALIDATED" in feedback.upper():
            state.resume_draft.is_validated = True
        else:
            state.resume_draft.validation_feedback = feedback
    except Exception as e:
        logger.error(f"Checker failed: {e}")
        state.error_message = f"Ошибка проверки: {e}"
    return state
