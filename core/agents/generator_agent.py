# core/agents/generator_agent.py
import json
import logging
import os
import re
from datetime import date
from typing import Dict, Any, Optional

from django.conf import settings
from langchain_perplexity import ChatPerplexity
from langchain_core.output_parsers import PydanticOutputParser

from .schemas import SCHEMA, ResumeModel

logger = logging.getLogger("resume_ai")


def _resolve_api_key() -> str:
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


SYSTEM_INSTRUCTIONS = (
    "Ты помощник по созданию резюме. "
    "Составь качественное структурированное резюме на основе профиля пользователя и контекста вакансии. "
    "Не выдумывай фактов: нельзя добавлять опыт, компании, даты или навыки, которых нет в профиле пользователя "
    "или явно не подсказаны поисковым контекстом. "
    "Не упоминай, что текст сгенерирован ИИ. "
    "ОБЯЗАТЕЛЬНО заполни ВСЕ поля схемы: если данных нет, используй аккуратные нейтральные формулировки "
    "или выводы из профиля/описания вакансии, но не пропускай ключи. "
    "Ответ должен содержать строго один валидный JSON‑объект по заданной схеме, без пояснений."
)


def _derive_age(user_profile: Dict[str, Any]) -> int:
    bd = user_profile.get("birth_date")
    if not bd:
        return 30
    try:
        year = int(str(bd)[:4])
        today = date.today()
        age = today.year - year
        if 14 <= age <= 100:
            return age
    except Exception:
        pass
    return 30


def _normalize_nones_to_empty_strings(value: Any) -> Any:
    """
    Рекурсивно проходит по dict/list и заменяет все None на "".
    Это устраняет ошибки jsonschema вида "None is not of type 'string'"
    для commute_time, driving, faculty, email, industry, location и т.п.
    """
    if isinstance(value, dict):
        for k, v in list(value.items()):
            if v is None:
                value[k] = ""
            elif isinstance(v, (dict, list)):
                value[k] = _normalize_nones_to_empty_strings(v)
        return value
    if isinstance(value, list):
        for i, v in enumerate(value):
            if v is None:
                value[i] = ""
            elif isinstance(v, (dict, list)):
                value[i] = _normalize_nones_to_empty_strings(v)
        return value
    return value


def _apply_profile_defaults(
    data: Dict[str, Any],
    user_profile: Dict[str, Any],
    target: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Дожимает обязательные поля из профиля/таргета и чистит все None -> "".
    """
    if not isinstance(data, dict):
        data = {}

    def take(key: str, profile_key: Optional[str] = None, default: str = "") -> str:
        src_key = profile_key or key
        val = user_profile.get(src_key)
        if val is None:
            return default
        return str(val)

    # Личные данные
    data.setdefault("full_name", take("full_name"))
    data.setdefault("gender", take("gender"))
    data.setdefault("birth_date", take("birth_date"))
    data.setdefault("phone", take("phone"))
    data.setdefault("email", take("email"))
    data.setdefault("location", take("location"))
    data.setdefault("citizenship", take("citizenship"))
    data.setdefault("work_permit", data.get("work_permit") or "")

    # Возраст
    data.setdefault("age", _derive_age(user_profile))

    # Желаемая позиция
    desired = (target.get("role") or "").strip()
    data.setdefault("desired_position", desired)

    # Поля‑массивы из required
    if "specializations" not in data or data["specializations"] is None:
        data["specializations"] = []
    if "schedules" not in data or data["schedules"] is None:
        data["schedules"] = []

    # Навыки: если LLM не заполнил, берём из профиля
    if not data.get("skills"):
        skills = user_profile.get("skills", [])
        if isinstance(skills, str):
            parts = [s.strip() for s in skills.replace(";", ",").split(",") if s.strip()]
            data["skills"] = parts
        else:
            data["skills"] = skills or []

    # Глобально чистим None -> "" по всему объекту (включая experience/education)
    data = _normalize_nones_to_empty_strings(data)

    return data


def generate_resume_json(
    user_profile: Dict[str, Any],
    target: Dict[str, Any],
    plan: Dict[str, Any],
    search_data: Dict[str, Any],
    feedback_directives: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    parser = PydanticOutputParser(pydantic_object=ResumeModel)
    format_instructions = parser.get_format_instructions()
    schema_text = json.dumps(SCHEMA, ensure_ascii=False)

    generator_directives = plan.get("generator_directives", {}) or {}
    if feedback_directives:
        generator_directives = {**generator_directives, **feedback_directives}

    safe_profile = dict(user_profile)
    safe_profile.pop("email", None)
    safe_profile.pop("phone", None)

    findings = (search_data or {}).get("findings", {})

    prompt = (
        f"{SYSTEM_INSTRUCTIONS}\n\n"
        "JSON Schema (ориентир для ключей/типов):\n"
        f"{schema_text}\n\n"
        "Краткие данные пользователя (без контактов):\n"
        f"{json.dumps(safe_profile, ensure_ascii=False, indent=2)}\n\n"
        "Цель (компания / роль / URL):\n"
        f"{json.dumps(target, ensure_ascii=False, indent=2)}\n\n"
        "Контекст вакансии (поиск):\n"
        f"{json.dumps(findings, ensure_ascii=False, indent=2)}\n\n"
        "Директивы оформления и ограничений:\n"
        f"{json.dumps(generator_directives, ensure_ascii=False, indent=2)}\n\n"
        f"{format_instructions}\n"
        "Верни только JSON."
    )

    llm = _get_llm()
    logger.info(
        "Generator agent producing structured JSON for company=%s role=%s",
        target.get("company") or "",
        target.get("role") or "",
    )

    resp = llm.invoke(prompt)
    raw_content = str(getattr(resp, "content", resp))

    clean = raw_content.strip()
    clean = re.sub(r"\s*```$", "", clean)

    try:
        resume_obj: ResumeModel = parser.parse(clean)
    except Exception as e:
        try:
            match = re.search(r"\{.*\}", clean, re.S)
            json_text = match.group(0) if match else clean
            resume_obj = ResumeModel.model_validate_json(json_text)
        except Exception as e2:
            logger.error(
                "Failed to obtain valid ResumeModel from LLM output: %s / %s",
                e,
                e2,
            )
            raise

    data = resume_obj.model_dump()
    data = _apply_profile_defaults(data, user_profile, target)
    return data
