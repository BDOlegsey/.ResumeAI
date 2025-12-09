import json
import logging
import os
import re
from typing import List, Dict, Any, Union

from django.conf import settings
from langchain_perplexity import ChatPerplexity

from .schemas import ValidationResultModel, IssueModel

logger = logging.getLogger("resume_ai")

REQUIRED_PROFILE_FIELDS = [
    "first_name",
    "last_name",
    "email",
    "profession",
]


def _resolve_api_key() -> str:
    key = (
            getattr(settings, "PERPLEXITY_API_KEY", "")
            or os.getenv("PERPLEXITY_API_KEY")
            or os.getenv("PPLX_API_KEY")
            or os.getenv("OPENAI_API_KEY")
    )
    if not key:
        logger.warning("Preprocess agent: API Perplexity не найден, будет работать только базовая валидация.")
        raise RuntimeError("no_api_key")
    return key


def _get_llm() -> ChatPerplexity:
    api_key = _resolve_api_key()
    return ChatPerplexity(model="sonar", api_key=api_key, temperature=0.0)


def _profile_to_brief_dict(user_profile: Any) -> Dict[str, Any]:
    """
    Формирует упрощенный dict для проверки LLM.
    Принимает user_profile, который является объектом модели UserProfile.
    """
    # Безопасное получение атрибутов профиля
    full_name = getattr(user_profile, "full_name", "")
    profession = getattr(user_profile, "profession", "")
    skills = getattr(user_profile, "skills", "") or ""
    additional_info = getattr(user_profile, "additional_info", "")
    has_photo = bool(getattr(user_profile, "photo", None))

    # Получаем email (может быть в профиле или в user)
    profile_email = getattr(user_profile, "email", "")
    user_obj = getattr(user_profile, "user", None)
    user_email = getattr(user_obj, "email", "") if user_obj else ""
    email_present = bool(profile_email or user_email)

    # Считаем опыт и образование через связанные модели User
    work_experience_count = 0
    education_count = 0

    if user_obj:
        # work_experiences связаны с User через related_name='work_experiences'
        we_manager = getattr(user_obj, "work_experiences", None)
        if we_manager and hasattr(we_manager, "count"):
            work_experience_count = we_manager.count()

        # educations связаны с User через related_name='educations'
        edu_manager = getattr(user_obj, "educations", None)
        if edu_manager and hasattr(edu_manager, "count"):
            education_count = edu_manager.count()

    return {
        "full_name": full_name,
        "profession": profession,
        "skills": skills,
        "additional_info": additional_info,
        "has_photo": has_photo,
        "email_present": email_present,
        "work_experience_count": work_experience_count,
        "education_count": education_count,
    }


def _rule_based_warnings(user_profile: Any) -> List[IssueModel]:
    """
    Базовые проверки без использования LLM.
    """
    issues: List[IssueModel] = []

    # 1. Проверка обязательных полей
    # Проверяем атрибуты модели UserProfile
    for f in REQUIRED_PROFILE_FIELDS:
        val = getattr(user_profile, f, None)
        if not val:
            # Для email проверяем также и в User
            if f == "email":
                user_obj = getattr(user_profile, "user", None)
                if user_obj and getattr(user_obj, "email", None):
                    continue

            issues.append(
                IssueModel(
                    field=f,
                    severity="warn",
                    message=f"Поле '{f}' не заполнено",
                    suggestion="Заполните это поле для корректной генерации.",
                )
            )

    # 2. Проверка навыков (количество)
    skills_raw = getattr(user_profile, "skills", "") or ""
    skills_count = len([s for s in skills_raw.replace(";", ",").split(",") if s.strip()])
    if skills_count < 3:
        issues.append(
            IssueModel(
                field="skills",
                severity="warn",
                message="Указано менее 3 навыков.",
                suggestion="Добавьте больше ключевых навыков, чтобы резюме было информативным.",
            )
        )

    return issues


def validate_profile(user_profile: Any) -> ValidationResultModel:
    """
    Агент валидации профиля перед генерацией.
    Принимает объект модели UserProfile.
    """
    result = ValidationResultModel(status="ok", issues=[])

    # 1. Rule-based
    base_issues = _rule_based_warnings(user_profile)
    if base_issues:
        result.status = "warn"
        result.issues = base_issues

    # 2. LLM-based
    try:
        llm = _get_llm()
    except RuntimeError:
        # Если нет ключа, возвращаем только rule-based
        return result

    brief = _profile_to_brief_dict(user_profile)
    system_instructions = (
        "Ты аналитик профилей соискателей. "
        "Твоя задача — проверить качество заполнения профиля для генерации резюме. "
        "Оценивай очень мягко, не придирайся к мелочам, ищи только серьезные проблемы (пустой опыт для сеньора, невнятная профессия и т.д.). "
        "Верни результат в формате JSON."
        "Если нет критических ошибок (опечатки - это не критическая ошибка), то пропускай "
    )

    try:
        prompt = (
            f"{system_instructions}\n"
            f"{json.dumps(brief, ensure_ascii=False, indent=2)}\n\n"
            "Верни JSON со структурой: { \"status\": \"ok\"|\"warn\"|\"block\", \"issues\": [{ \"field\": \"...\", \"severity\": \"warn\"|\"error\", \"message\": \"...\", \"suggestion\": \"...\" }] }"
        )

        resp = llm.invoke(prompt)
        content = str(getattr(resp, "content", resp)).strip()

        # Ищем JSON-объект, чтобы отбросить возможный вводный текст
        match = re.search(r"\{.*\}", content, re.S)
        json_text = match.group(0) if match else content

        if not json_text.strip():
            raise ValueError("Empty response from LLM")

        data = json.loads(json_text)
        llm_result = ValidationResultModel.model_validate(data)

    except Exception as exc:
        logger.exception("Preprocess agent LLM failed, using only rule‑based warnings: %s", exc)
        return result

    # 3. Merge results
    combined = base_issues + (llm_result.issues or [])

    # Дедупликация по message
    seen = set()
    merged_issues: List[IssueModel] = []
    for issue in combined:
        key = (issue.field, issue.message)
        if key in seen:
            continue
        seen.add(key)
        merged_issues.append(issue)

    final_status = llm_result.status
    if any(i.severity == "error" for i in merged_issues):
        final_status = "block"
    elif merged_issues and final_status == "ok":
        final_status = "warn"

    logger.info(
        "Preprocess agent validation status=%s issues=%d",
        final_status,
        len(merged_issues),
    )

    return ValidationResultModel(status=final_status, issues=merged_issues)
