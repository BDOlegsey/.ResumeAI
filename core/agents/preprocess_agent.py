from typing import List
from . import main_agent  # placeholder: can be extended to LLM validation rules

REQUIRED_PROFILE_FIELDS = ["first_name", "last_name", "email", "profession"]

def validate_profile(user_profile) -> List[str]:
    """
    Preprocess agent: validate profile adequacy to avoid wasting tokens.
    Returns list of warnings for user to fix.
    """
    warnings = []
    for f in REQUIRED_PROFILE_FIELDS:
        if not getattr(user_profile, f, None):
            warnings.append(f"Заполните поле профиля: {f} — это поможет улучшить резюме.")
    # Minimal skills length
    if not user_profile.skills or len(user_profile.skills.split(',')) < 3:
        warnings.append("Добавьте больше навыков (≥ 3) в профиль для точного матчинга.")
    return warnings
