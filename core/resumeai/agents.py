import logging
from langchain_perplexity import ChatPerplexity
from langchain_core.prompts import ChatPromptTemplate
from .models import UserData, SearchResults, ResumeDraft, AgentState
from .database import get_employer_info, store_employer_info

logger = logging.getLogger(__name__)

llm = ChatPerplexity(model="sonar", temperature=0.1)


def search_agent_node(state: AgentState) -> AgentState:
    """Ищет информацию о компании в интернете"""
    logger.info(f"Search Agent: researching {state.current_employer}")

    if not state.current_employer:
        state.error_message = "Работодатель не задан."
        return state

    # Проверяем кэш
    cached = get_employer_info(state.current_employer)
    if cached:
        logger.info(f"Using cached info for {state.current_employer}")
        state.search_results = cached
        return state

    # Запрос к Perplexity с веб-поиском
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "Ты — исследователь компании с доступом к веб‑поиску Perplexity. "
         "Отвечай на русском языке. Возвращай строго JSON по заданной схеме."),
        ("human",
         "Исследуй работодателя '{employer}' для роли '{title}'. "
         "Верни JSON с полями: "
         "company_info (миссия, ценности, культура, свежие новости) и "
         "job_specific_info (ключевые навыки и требования для этой роли).")
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
        logger.info(f"Successfully researched {state.current_employer}")
    except Exception as e:
        logger.error(f"Search failed for {state.current_employer}: {e}")
        state.error_message = f"Ошибка поиска: {e}"

    return state


def generator_agent_node(state: AgentState) -> AgentState:
    """Генерирует текст резюме"""
    logger.info(f"Generator Agent: creating resume for {state.current_employer}")

    if not state.search_results or not state.user_data:
        state.error_message = "Нет данных для генерации."
        return state

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "Ты — эксперт по написанию резюме. Пиши на русском языке. "
         "Составь профессиональное, лаконичное и ATS-дружественное резюме "
         "под позицию '{job_title}' в компании '{employer_name}', "
         "основываясь на данных пользователя и требованиях компании. "
         "Используй формат с заголовками (# и ##), маркированными списками (- ) и выделением (**текст**)."),
        ("human",
         "Опыт работы: {experience}\n"
         "Навыки: {skills}\n"
         "Достижения: {achievements}\n\n"
         "Информация о компании: {company_info}\n"
         "Требования по роли: {job_specific_info}\n\n"
         "Создай профессиональное резюме, которое подчеркивает релевантный опыт "
         "и соответствует культуре компании {employer_name}.")
    ])
    chain = prompt | llm

    try:
        response = chain.invoke({
            "job_title": state.user_data.job_title,
            "employer_name": state.current_employer,
            "experience": state.user_data.experience or "Не указан",
            "skills": state.user_data.skills or "Не указаны",
            "achievements": state.user_data.achievements,
            "company_info": state.search_results.company_info,
            "job_specific_info": state.search_results.job_specific_info
        })
        content = response.content if hasattr(response, "content") else str(response)
        state.resume_draft = ResumeDraft(draft_content=content, is_validated=False)
        state.iteration_count += 1
        logger.info(f"Generated draft for {state.current_employer}, iteration {state.iteration_count}")
    except Exception as e:
        logger.error(f"Generation failed for {state.current_employer}: {e}")
        state.error_message = f"Ошибка генерации: {e}"

    return state


def checker_agent_node(state: AgentState) -> AgentState:
    """Проверяет качество резюме"""
    logger.info(f"Checker Agent: reviewing resume for {state.current_employer}")

    if not state.resume_draft:
        state.error_message = "Нет черновика для проверки."
        return state

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "Ты — редактор резюме. Пиши на русском языке. "
         "Проверь резюме на соответствие требованиям роли, качество языка, "
         "наличие ключевых слов (ATS-оптимизация) и убедительность. "
         "Если всё хорошо — напиши 'VALIDATED'. "
         "Если есть замечания — дай конкретные рекомендации."),
        ("human",
         "Компания: {employer_name}\n"
         "Требования: {job_specific_info}\n\n"
         "Черновик резюме:\n{draft_content}\n\n"
         "Твой отзыв:")
    ])
    chain = prompt | llm

    try:
        response = chain.invoke({
            "employer_name": state.current_employer,
            "job_specific_info": state.search_results.job_specific_info if state.search_results else "Не указаны",
            "draft_content": state.resume_draft.draft_content
        })
        feedback = response.content if hasattr(response, "content") else str(response)

        if "VALIDATED" in feedback.upper():
            state.resume_draft.is_validated = True
            state.resume_draft.validation_feedback = ""
            logger.info(f"Resume validated for {state.current_employer}")
        else:
            state.resume_draft.is_validated = False
            state.resume_draft.validation_feedback = feedback
            logger.info(f"Resume needs revision for {state.current_employer}")
    except Exception as e:
        logger.error(f"Checker failed for {state.current_employer}: {e}")
        state.error_message = f"Ошибка проверки: {e}"
        # Продолжаем с текущим черновиком
        state.resume_draft.is_validated = False

    return state
