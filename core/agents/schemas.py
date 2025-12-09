# core/agents/schemas.py
import json
import os
from typing import List, Optional, Literal, Dict, Any

from django.conf import settings
from jsonschema import Draft7Validator

from pydantic import BaseModel, Field, EmailStr, conint


SCHEMA_PATH = os.path.join(settings.BASE_DIR, "schema.json")


def load_schema():
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


SCHEMA = load_schema()
VALIDATOR = Draft7Validator(SCHEMA)


def validate_json_payload(payload: dict):
    errors = sorted(VALIDATOR.iter_errors(payload), key=lambda e: e.path)
    messages = []
    for e in errors:
        path = ".".join([str(x) for x in e.path])
        messages.append(f"{path or ''}: {e.message}")
    return messages


class ExperienceItem(BaseModel):
    period: str = ""
    company: str = ""
    position: str = ""
    location: str = ""          # вместо Optional[str] = None
    industry: str = ""          # вместо Optional[str] = None
    duties: List[str] = Field(default_factory=list)
    achievements: List[str] = Field(default_factory=list)


class EducationItem(BaseModel):
    year: conint(ge=1900, le=2100) = 2000
    university: str = ""
    degree: str = ""
    faculty: str = ""           # вместо Optional[str] = None
    program: str = ""           # вместо Optional[str] = None


class LanguageItem(BaseModel):
    name: str = ""
    level: str = ""


class ReferenceItem(BaseModel):
    name: str = ""
    company: str = ""
    position: str = ""          # вместо Optional[str] = None


class ResumeModel(BaseModel):
    # Личные данные (required в schema.json)
    full_name: str = ""
    gender: str = ""
    age: conint(ge=14, le=100) = 30
    birth_date: str = ""
    phone: str = ""
    email: str = ""             # строка, формат email проверит jsonschema
    location: str = ""
    citizenship: str = ""
    work_permit: str = ""
    relocation_status: str = ""  # вместо Optional[str] = None
    travel_readiness: str = ""   # вместо Optional[str] = None

    # Желаемая позиция
    desired_position: str = ""
    salary: str = ""            # вместо Optional[str] = None
    specializations: List[str] = Field(default_factory=list)
    employment_type: str = ""
    schedules: List[str] = Field(default_factory=list)
    commute_time: str = ""      # вместо Optional[str] = None

    # Опыт
    total_experience: str = ""
    experience: List[ExperienceItem] = Field(default_factory=list)

    # Образование
    education: List[EducationItem] = Field(default_factory=list)

    # Языки / навыки
    languages: List[LanguageItem] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)

    # Прочее
    driving: str = ""           # вместо Optional[str] = None
    references: List[ReferenceItem] = Field(default_factory=list)
    about: str = ""             # вместо Optional[str] = None

    class Config:
        extra = "forbid"        # соответствует additionalProperties: false


# --- Auxiliary agent interfaces ---


class IssueModel(BaseModel):
    field: str = ""
    severity: Literal["info", "warn", "error"] = "warn"
    message: str = ""
    suggestion: str = ""


class ValidationResultModel(BaseModel):
    status: Literal["ok", "warn", "block"] = "ok"
    issues: List[IssueModel] = Field(default_factory=list)

    @property
    def as_messages(self) -> List[str]:
        msgs = []
        for issue in self.issues:
            base = issue.message or issue.field
            if issue.suggestion:
                base = f"{base} — {issue.suggestion}"
            msgs.append(base)
        return msgs


class SearchStrategyModel(BaseModel):
    need_search: bool = True
    depth: Literal["shallow", "normal", "deep"] = "normal"
    max_rounds: int = 1


class PlanModel(BaseModel):
    search_goals: List[str] = Field(default_factory=list)
    search_strategy: SearchStrategyModel = Field(
        default_factory=SearchStrategyModel
    )
    generator_directives: Dict[str, Any] = Field(default_factory=dict)
    target_summary: str = ""
    company: str = ""
    role: str = ""
    url: str = ""


class SearchFindingsModel(BaseModel):
    summary: str = ""
    requirements: List[str] = Field(default_factory=list)
    tech_stack: List[str] = Field(default_factory=list)
    soft_skills: List[str] = Field(default_factory=list)
    company_profile: Dict[str, Any] = Field(default_factory=dict)
    red_flags: List[str] = Field(default_factory=list)
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    coverage_score: float = 0.0
    bullets: List[str] = Field(default_factory=list)


class ReviewResultModel(BaseModel):
    approved: bool = False
    issues: List[IssueModel] = Field(default_factory=list)
    regeneration_directives: Dict[str, Any] = Field(default_factory=dict)
