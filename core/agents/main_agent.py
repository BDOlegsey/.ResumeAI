import json
import logging
import os
from typing import Dict, Any

from django.conf import settings
from langchain_perplexity import ChatPerplexity
from langchain_core.output_parsers import PydanticOutputParser

from .schemas import PlanModel

logger = logging.getLogger("resume_ai")


def _resolve_api_key() -> str:
    """
    Вспомогательная функция для получения API‑ключа Perplexity из настроек/окружения.
    """
    key = (
        getattr(settings, "PERPLEXITY_API_KEY", "")
        or os.getenv("PERPLEXITY_API_KEY")
        or os.getenv("PPLX_API_KEY")
        or os.getenv("OPENAI_API_KEY")
    )
    if not key:
        msg = (
            "Не найден API‑ключ Perplexity. "
            "Установите PPLX_API_KEY/PERPLEXITY_API_KEY/OPENAI_API_KEY "
            "или задайте settings.PERPLEXITY_API_KEY."
        )
        logger.error(msg)
        raise RuntimeError(msg)
    return key


def _get_llm() -> ChatPerplexity:
    api_key = _resolve_api_key()
    return ChatPerplexity(model="sonar", api_key=api_key, temperature=0.2)


def _build_fallback_plan(
    user_profile: Dict[str, Any],
    target: Dict[str, Any],
    request_controls: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Детерминированный план на случай, если LLM недоступен или вернул невалидный JSON.
    Логика основана на первоначальной реализации планировщика.
    """
    company = (target.get("company") or "").strip()
    role = (target.get("role") or "").strip()
    url = (target.get("url") or "").strip()

    search_goals = []
    if url:
        search_goals.append(
            f"Извлечь требования, обязанности и ключевые навыки для вакансии по URL: {url}"
        )
    if company:
        if role:
            search_goals.append(
                f"Найти требования к вакансии '{role}' в компании '{company}'"
            )
        search_goals.append(
            f"Понять специфику компании '{company}': продукт, технологии, тон коммуникации, корпоративные ценности"
        )

    expand_fields = []
    if user_profile.get("skills"):
        expand_fields.append(
            "Расширить навыки синонимами и близкими технологиями (без выдумок)"
        )

    strict = request_controls.get("strict_matching", True)
    add_skills = request_controls.get("add_skills", False)
    specific_conditions = (request_controls.get("specific_conditions") or "").strip()
    extra_instructions = (request_controls.get("extra_instructions") or "").strip()
    additional_wishes = (request_controls.get("additional_wishes") or "").strip()

    generator_directives = {
        "strict_matching": strict,
        "add_skills": add_skills,
        "specific_conditions": specific_conditions,
        "extra_instructions": extra_instructions,
        "additional_wishes": additional_wishes,
        "tone": "профессиональный, лаконичный",
        "language": "ru",
        "forbid_ai_mentions": True,
    }

    plan: Dict[str, Any] = {
        "search_goals": search_goals,
        "expand_fields": expand_fields,
        "generator_directives": generator_directives,
        "company": company,
        "role": role,
        "url": url,
        "target_summary": "",
    }
    return plan


def plan_for_target(
    user_profile: Dict[str, Any],
    target: Dict[str, Any],
    request_controls: Dict[str, Any],
) -> Dict[str, Any]:
    """
    LLM‑агент планирования:
    - формирует цели поиска;
    - определяет стратегию поиска;
    - собирает директивы для генератора (тон, ограничения, условия).
    Если LLM недоступен/ошибся — используется детерминированный fallback‑план.
    """
    company = (target.get("company") or "").strip()
    role = (target.get("role") or "").strip()

    logger.info(
        "Main agent planning for user_id=%s company=%s role=%s",
        user_profile.get("user_id", "n/a"),
        company or "<unknown>",
        role or "<unknown>",
    )

    # Минимизируем персональные данные в промпте: не отправляем контакты
    profile_brief = {
        "full_name": user_profile.get("full_name", ""),
        "profession": user_profile.get("profession", ""),
        "skills": user_profile.get("skills", []),
        "work_experience_count": len(user_profile.get("work_experience", [])),
        "education_count": len(user_profile.get("education", [])),
        "additional_info": user_profile.get("additional_info", ""),
    }

    controls_brief = {
        "strict_matching": bool(request_controls.get("strict_matching", True)),
        "add_skills": bool(request_controls.get("add_skills", False)),
        "specific_conditions": (request_controls.get("specific_conditions") or "").strip(),
        "extra_instructions": (request_controls.get("extra_instructions") or "").strip(),
        "additional_wishes": (request_controls.get("additional_wishes") or "").strip(),
    }

    system_instructions = (
        "Ты выступаешь в роли оркестратора мультиагентной системы по генерации резюме. "
        "На основе краткого профиля пользователя и цели (компания/роль/URL) "
        "нужно спланировать, что искать и как настроить генератор резюме. "
        "Верни строго один JSON‑объект без пояснений."
    )

    try:
        llm = _get_llm()
        parser = PydanticOutputParser(pydantic_object=PlanModel)
        format_instructions = parser.get_format_instructions()
        prompt = (
            f"{system_instructions}\n\n"
            f"{format_instructions}\n\n"
            "Краткий профиль пользователя:\n"
            f"{json.dumps(profile_brief, ensure_ascii=False, indent=2)}\n\n"
            "Цель:\n"
            f"{json.dumps(target, ensure_ascii=False, indent=2)}\n\n"
            "Управляющие флаги:\n"
            f"{json.dumps(controls_brief, ensure_ascii=False, indent=2)}\n\n"
            "Верни только JSON‑объект."
        )

        resp = llm.invoke(prompt)
        content = str(getattr(resp, "content", resp)).strip()

        # Пытаемся вытащить JSON
        import re

        match = re.search(r"\{.*\}\s*$", content, re.S)
        json_text = match.group(0) if match else content
        plan_model = parser.parse(json_text)
        data = plan_model.model_dump()

        search_goals = data.get("search_goals") or []
        strategy = data.get("search_strategy") or {}
        generator_directives = data.get("generator_directives") or {}
        target_summary = data.get("target_summary") or ""

        # Объединяем с контролами и дефолтами
        fallback = _build_fallback_plan(user_profile, target, request_controls)
        merged_directives = {**fallback["generator_directives"], **generator_directives}

        plan: Dict[str, Any] = {
            "search_goals": search_goals or fallback["search_goals"],
            "expand_fields": fallback["expand_fields"],
            "generator_directives": merged_directives,
            "company": fallback["company"],
            "role": fallback["role"],
            "url": fallback["url"],
            "search_strategy": {
                "need_search": bool(strategy.get("need_search", True)),
                "depth": strategy.get("depth", "normal"),
                "max_rounds": int(strategy.get("max_rounds", 1)) or 1,
            },
            "target_summary": target_summary,
        }
        logger.debug("Main agent LLM plan for company=%s: %s", company, plan)
        return plan
    except Exception as exc:
        logger.exception(
            "Main agent LLM failed for company=%s role=%s, falling back: %s",
            company or "<unknown>",
            role or "<unknown>",
            exc,
        )
        plan = _build_fallback_plan(user_profile, target, request_controls)
        logger.debug("Main agent fallback plan for company=%s: %s", company, plan)
        return plan
