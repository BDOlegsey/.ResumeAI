import logging
from typing import Dict, Any
import os
import json
from django.conf import settings
from langchain_perplexity import ChatPerplexity
from langchain_core.output_parsers import JsonOutputParser
from .schemas import SCHEMA

logger = logging.getLogger('core.agents')

def _resolve_api_key() -> str:
    key = getattr(settings, 'PERPLEXITY_API_KEY', '') or \
          os.getenv('PERPLEXITY_API_KEY') or os.getenv('PPLX_API_KEY') or os.getenv('OPENAI_API_KEY')
    if not key:
        msg = ("Не найден API-ключ Perplexity. Установите PPLX_API_KEY/PERPLEXITY_API_KEY/OPENAI_API_KEY "
               "или задайте settings.PERPLEXITY_API_KEY.")
        logger.error(msg)
        raise RuntimeError(msg)
    return key

def _get_llm():
    api_key = _resolve_api_key()
    return ChatPerplexity(model="sonar-pro", api_key=api_key, temperature=0.2)

SYSTEM_INSTRUCTIONS = (
    "Ты помощник по созданию резюме. Верни строго валидный JSON по схеме. "
    "Не выдумывай фактов, улучшай формулировки и стиль без искажения смысла. "
    "Ответ должен содержать только JSON, без пояснений."
)

def generate_resume_json(user_profile: Dict[str, Any], target: Dict[str, Any],
                         plan: Dict[str, Any], search_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Структурный вывод: заставляем LLM вернуть чистый JSON и затем валидируем по schema.json.
    """
    parser = JsonOutputParser()
    format_instructions = parser.get_format_instructions()
    schema_text = json.dumps(SCHEMA, ensure_ascii=False)

    prompt = (
        f"{SYSTEM_INSTRUCTIONS}\n\n"
        f"JSON Schema (ориентир для ключей/типов):\n{schema_text}\n\n"
        "Данные пользователя:\n"
        f"{json.dumps(user_profile, ensure_ascii=False, indent=2)}\n\n"
        "Цель (компания/роль/URL):\n"
        f"{json.dumps(target, ensure_ascii=False, indent=2)}\n\n"
        "Контекст вакансии (поиск):\n"
        f"{json.dumps(search_data.get('findings', {}), ensure_ascii=False, indent=2)}\n\n"
        "Директивы оформления:\n"
        f"{json.dumps(plan.get('generator_directives', {}), ensure_ascii=False, indent=2)}\n\n"
        f"{format_instructions}\n"
        "Верни только JSON."
    )

    llm = _get_llm()
    logger.info("Generator agent producing structured JSON for company=%s role=%s", target.get('company'), target.get('role'))
    resp = llm.invoke(prompt)
    content = str(getattr(resp, 'content', resp)).strip()

    # Парсим как JSON
    try:
        data = parser.parse(content)
    except Exception:
        # fallback: прямой json.loads
        import re
        m = re.search(r'\{.*\}\s*$', content, re.S)
        json_text = m.group(0) if m else content
        try:
            data = json.loads(json_text)
        except Exception as e:
            logger.warning("Failed to parse JSON from LLM, returning empty: %s", e)
            data = {}
    return data
