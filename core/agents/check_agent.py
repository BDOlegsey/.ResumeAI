# core/agents/check_agent.py
import logging
from typing import Dict, Any, Tuple, List

from .schemas import validate_json_payload

logger = logging.getLogger('core.agents')

def _to_skill_set(value) -> set:
    """
    Преобразует вход (list[str] | str | None) в множество нижнего регистра.
    Поддерживает варианты: ["C++", "Python"], "C++, Python", "C++ Python".
    """
    if value is None:
        return set()
    if isinstance(value, list):
        items = []
        for v in value:
            if isinstance(v, dict):
                # иногда модели отдают [{"name": "Python"}]
                name = v.get("name") or v.get("skill") or ""
                if name:
                    items.append(str(name))
            else:
                items.append(str(v))
        return set(s.strip().lower() for s in items if str(s).strip())
    # строка
    s = str(value)
    # нормализуем разделители: запятые и точки с запятой -> пробел
    for sep in [',', ';', '|', '/', '\n']:
        s = s.replace(sep, ' ')
    parts = [p.strip().lower() for p in s.split(' ') if p.strip()]
    return set(parts)

def _to_bullets(value) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(x).lower() for x in value if str(x).strip()]
    return [str(value).lower()]

def check_resume_json(user_profile: Dict[str, Any],
                      search_data: Dict[str, Any],
                      generated: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Проверка: соответствие схеме + примитивная детекция галлюцинаций по навыкам.
    """
    errors = validate_json_payload(generated)

    # Достаем навыки профиля (в пайплайне это список строк)
    profile_skills = _to_skill_set(user_profile.get('skills'))

    # Навыки, которые выдал генератор: поддерживаем и skills, и key_skills
    gen_skills = _to_skill_set(generated.get('skills'))
    if not gen_skills:
        gen_skills = _to_skill_set(generated.get('key_skills'))

    # Буллеты из поиска — допускаем добавление навыков, если они встречаются в поисковом контексте
    bullets = _to_bullets((search_data or {}).get('findings', {}).get('bullets'))

    if gen_skills:
        # Если вообще нет пересечения с профилем, проверим подтверждение поиском
        if profile_skills and not (gen_skills & profile_skills):
            confirmed = {s for s in gen_skills if any(s in b for b in bullets)}
            # требуем чтобы хоть часть была подтверждена контекстом
            if len(confirmed) < max(1, len(gen_skills) // 3):
                errors.append("skills: возможны галлюцинации — навыки не подтверждены профилем или поиском")

    approved = len(errors) == 0
    logger.debug("Check agent approved=%s errors=%s", approved, errors)
    return approved, errors
