import json
import logging
import os
from typing import Dict, Any, List

from django.conf import settings
from langchain_perplexity import ChatPerplexity
from langchain_core.output_parsers import PydanticOutputParser

from .schemas import SearchFindingsModel

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


def search_for_target(plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    LLM‑поисковый агент: использует Perplexity для сбора требований, стека и культуры компании.
    Возвращает структурированный JSON (findings) + сырой текст ответа (raw) для отладки.
    """
    search_goals: List[str] = plan.get("search_goals", []) or []
    if not search_goals:
        return {"findings": {}, "raw": ""}

    logger.info("Search agent querying Perplexity for %d goals", len(search_goals))

    system_instructions = (
        "Ты аналитик рынка труда. Выполни веб‑поиск по целям ниже и верни краткий структурированный отчет "
        "в формате одного JSON‑объекта."
    )

    parser = PydanticOutputParser(pydantic_object=SearchFindingsModel)
    format_instructions = parser.get_format_instructions()

    prompt = (
        f"{system_instructions}\n\n"
        "Список поисковых целей (запросов):\n"
        + "\n".join(f"- {g}" for g in search_goals)
        + "\n\n"
        f"{format_instructions}\n"
        "Верни только один JSON‑объект."
    )

    llm = _get_llm()
    resp = llm.invoke(prompt)
    content = str(getattr(resp, "content", resp)).strip()

    findings: Dict[str, Any] = SearchFindingsModel().model_dump()

    try:
        findings = parser.parse(content).model_dump()
    except Exception as exc:
        logger.warning("Search agent JSON parse failed, using fallback: %s", exc)
        # Пытаемся вытянуть JSON вручную
        import re

        match = re.search(r"\{.*\}\s*$", content, re.S)
        json_text = match.group(0) if match else content
        try:
            data = json.loads(json_text)
            if isinstance(data, dict):
                findings.update(data)
        except Exception:
            findings["summary"] = content[:1000]
    if not findings.get("summary"):
        findings["summary"] = content[:1000]

    logger.debug(
        "Search findings summary_len=%d, bullets=%d",
        len(findings.get("summary", "")),
        len(findings.get("bullets", []) or []),
    )

    return {"findings": findings, "raw": content}
