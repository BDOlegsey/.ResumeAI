import logging
from typing import Dict, Any, List
import os
import sys
from django.conf import settings

from langchain_perplexity import ChatPerplexity

sys.path.append(os.path.abspath('C:\\Users\\Алексей\\OneDrive\\Рабочий стол\\ВУЗ\\ResumeAI\\core\\agents'))
from system_prompts import SYSTEM_INSTRUCTIONS_SEARCHER

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

def search_for_target(plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    Search agent: use Perplexity to gather requirements, stack, culture for the company/role.
    """
    search_goals: List[str] = plan.get('search_goals', [])
    if not search_goals:
        return {"findings": [], "summary": "", "citations": []}

    llm = _get_llm()
    prompt = (
        f"{SYSTEM_INSTRUCTIONS_SEARCHER}\n\n"
        "Запросы:\n- " + "\n- ".join(search_goals) + "\n\n"
        "Ответ верни в JSON с полями: summary (строка), bullets (список строк), citations (список URL).\n"
    )
    logger.info("Search agent querying Perplexity for goals: %s", search_goals)
    resp = llm.invoke(prompt)  # returns LC message; assume .content holds text JSON or text
    content = str(getattr(resp, 'content', resp))
    # naive extraction: try to find JSON block
    import json, re
    json_text = None
    m = re.search(r'\{.*\}', content, re.S)
    if m:
        json_text = m.group(0)
    findings = {"summary": "", "bullets": [], "citations": []}
    if json_text:
        try:
            findings = json.loads(json_text)
        except Exception:
            pass
    if not findings.get('summary'):
        findings['summary'] = content[:1000]
    logger.debug("Search findings: %s", findings)
    return {"findings": findings, "raw": content}
