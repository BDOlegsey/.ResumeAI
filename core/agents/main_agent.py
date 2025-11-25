import logging
from typing import Dict, List

logger = logging.getLogger('core.agents')

def plan_for_target(user_profile: dict, target: dict, request_controls: dict) -> Dict:
    """
    Main agent: decide what to search and how to prompt generator.
    """
    company = (target.get('company') or '').strip()
    role = (target.get('role') or '').strip()
    url = (target.get('url') or '').strip()

    search_goals = []
    if url:
        search_goals.append(f"Извлечь требования, обязанности и ключевые навыки для вакансии по URL: {url}")
    if company:
        if role:
            search_goals.append(f"Найти требования к вакансии '{role}' в компании '{company}'")
        search_goals.append(f"Понять специфику компании '{company}': продукт, технологии, тон коммуникации, корпоративные ценности")

    # Expandable from profile
    expand_fields = []
    if user_profile.get('skills'):
        expand_fields.append("Расширить навыки синонимами и близкими технологиями (без выдумок)")

    strict = request_controls.get('strict_matching', True)
    add_skills = request_controls.get('add_skills', False)
    specific_conditions = (request_controls.get('specific_conditions') or "").strip()
    extra_instructions = (request_controls.get('extra_instructions') or "").strip()

    generator_directives = {
        "strict_matching": strict,
        "add_skills": add_skills,
        "specific_conditions": specific_conditions,
        "extra_instructions": extra_instructions,
        "tone": "профессиональный, лаконичный",
        "language": "ru",
    }

    plan = {
        "search_goals": search_goals,
        "expand_fields": expand_fields,
        "generator_directives": generator_directives,
        "company": company,
        "role": role,
        "url": url
    }
    logger.debug("Plan for target %s: %s", company, plan)
    return plan
