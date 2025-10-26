# agents.py
import logging
from langchain_perplexity import ChatPerplexity
from langchain_core.prompts import ChatPromptTemplate
from models import UserData, SearchResults, ResumeDraft, AgentState
from database import get_employer_info, store_employer_info

logger = logging.getLogger(__name__)

# Валидная модель Perplexity; ключ берётся из PPLX_API_KEY
llm = ChatPerplexity(
    model="sonar",  # при необходимости: "sonar-pro"
    temperature=0.1,
)

def main_agent_node(state: AgentState) -> AgentState:
    logger.info("Main Agent processing user data and selecting employer.")
    if not state.user_data:
        logger.error("Main Agent: No user data provided.")
        state.error_message = "Нет пользовательских данных."
        return state
    if state.current_employer is None:
        if state.user_data.employers:
            state.current_employer = state.user_data.employers[0]
            logger.info(f"Main Agent: Selected first employer - {state.current_employer}")
        else:
            logger.error("Main Agent: No employers listed in user data.")
            state.error_message = "Список работодателей пуст."
            return state
    else:
        current_index = state.user_data.employers.index(state.current_employer)
        if current_index + 1 < len(state.user_data.employers):
            state.current_employer = state.user_data.employers[current_index + 1]
            logger.info(f"Main Agent: Selected next employer - {state.current_employer}")
            state.search_results = None
            state.resume_draft = None
            state.iteration_count = 0
        else:
            logger.info("Main Agent: All employers processed.")
            return state
    return state

def search_agent_node(state: AgentState) -> AgentState:
    logger.info(f"Search Agent starting for employer: {state.current_employer}")
    if not state.current_employer:
        logger.error("Search Agent: No current employer set.")
        state.error_message = "Работодатель не задан."
        return state

    cached = get_employer_info(state.current_employer)
    if cached:
        logger.info(f"Search Agent: Found cached info for {state.current_employer} in database.")
        state.search_results = cached
        return state

    # Русские промпты + строго структурированный вывод в модель SearchResults
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "Ты — исследователь компании с доступом к веб‑поиску Perplexity. "
         "Отвечай на русском. Возвращай строго JSON по заданной схеме."),
        ("human",
         "Исследуй работодателя '{employer}' для роли '{title}'. "
         "Верни JSON с полями: company_info (миссия/ценности/культура/свежие новости) и "
         "job_specific_info (ключевые навыки/требования).")
    ])
    chain = prompt | llm.with_structured_output(SearchResults)

    try:
        result: SearchResults = chain.invoke(
            {"employer": state.current_employer, "title": state.user_data.job_title},
            extra_body={"search_mode": "web", "search_recency_filter": "year"}
        )
        result.employer_name = state.current_employer
        store_employer_info(result)
        state.search_results = result
        logger.info(f"Search Agent completed for {state.current_employer}.")
    except Exception as e:
        logger.error(f"Search Agent failed for {state.current_employer}: {e}")
        state.error_message = f"Ошибка поиска: {e}"
    return state

def generator_agent_node(state: AgentState) -> AgentState:
    logger.info(f"Generator Agent starting for employer: {state.current_employer}")
    if not state.search_results or not state.user_data:
        logger.error("Generator Agent: Missing user data or search results.")
        state.error_message = "Нет данных пользователя или результатов поиска."
        return state

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "Ты — эксперт по написанию резюме. Пиши на русском. "
         "Составь профессиональное, лаконичное и ATS‑дружественное резюме под позицию "
         "'{job_title}' в компании '{employer_name}' на основе данных пользователя. Ты можешь перефразировать, но не выдумай информации, которую не предоставлял пользователь. Учитывай требования и культуру компании."),
        ("human",
         "Данные пользователя:\n"
         "Опыт: {experience}\n"
         "Навыки: {skills}\n"
         "Достижения: {achievements}\n\n"
         "Данные работодателя:\n"
         "О компании: {company_info}\n"
         "По роли: {job_specific_info}\n\n"
         "Вложения: {attachments}\n\n"
         "Сгенерируй текст резюме на русском языке.")
    ])
    chain = prompt | llm

    attachments_str = "\n".join([f"Вложение {i+1}" for i in range(len(state.user_data.attachments))]) or "Не предоставлены."

    try:
        response = chain.invoke({
            "job_title": state.user_data.job_title,
            "employer_name": state.current_employer,
            "experience": state.user_data.experience,
            "skills": state.user_data.skills,
            "achievements": state.user_data.achievements,
            "company_info": state.search_results.company_info,
            "job_specific_info": state.search_results.job_specific_info,
            "attachments": attachments_str
        })
        content = response.content if hasattr(response, "content") else str(response)
        state.resume_draft = ResumeDraft(draft_content=content, is_validated=False, validation_feedback="")
        state.iteration_count += 1
        logger.info(f"Generator Agent created draft for {state.current_employer}. Iteration: {state.iteration_count}")
    except Exception as e:
        logger.error(f"Generator Agent failed for {state.current_employer}: {e}")
        state.error_message = f"Ошибка генерации: {e}"
    return state

def checker_agent_node(state: AgentState) -> AgentState:
    logger.info(f"Checker Agent reviewing draft for employer: {state.current_employer}")
    if not state.resume_draft or not state.user_data or not state.search_results:
        logger.error("Checker Agent: Missing resume draft, user data, or search results.")
        state.error_message = "Нет черновика, данных пользователя или результатов поиска."
        return state

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "Ты — редактор резюме. Пиши на русском. Проверь соответствие резюме требованиям роли, "
         "качество языка, ключевые слова (ATS), убедительность. Если всё хорошо — напиши 'VALIDATED'."),
        ("human",
         "Данные пользователя:\n"
         "Опыт: {experience}\n"
         "Навыки: {skills}\n"
         "Достижения: {achievements}\n\n"
         "Данные работодателя:\n"
         "О компании: {company_info}\n"
         "По роли: {job_specific_info}\n\n"
         "Черновик резюме:\n{draft_content}\n\n"
         "Дай отзыв:")
    ])
    chain = prompt | llm

    try:
        response = chain.invoke({
            "experience": state.user_data.experience,
            "skills": state.user_data.skills,
            "achievements": state.user_data.achievements,
            "company_info": state.search_results.company_info,
            "job_specific_info": state.search_results.job_specific_info,
            "draft_content": state.resume_draft.draft_content
        })
        feedback = response.content if hasattr(response, "content") else str(response)
        if "VALIDATED" in feedback.upper():
            state.resume_draft.is_validated = True
            state.resume_draft.validation_feedback = ""
            logger.info(f"Checker Agent validated resume for {state.current_employer}.")
        else:
            state.resume_draft.is_validated = False
            state.resume_draft.validation_feedback = feedback
            logger.info(f"Checker Agent found issues for {state.current_employer}.")
    except Exception as e:
        logger.error(f"Checker Agent failed for {state.current_employer}: {e}")
        state.error_message = f"Ошибка проверки: {e}"
        state.resume_draft.is_validated = False
        state.resume_draft.validation_feedback = f"Во время проверки возникла ошибка: {e}"
    return state
