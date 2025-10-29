from pydantic import BaseModel, Field
from typing import List, Optional

class UserData(BaseModel):
    employers: List[str] = Field(..., description="Список целевых работодателей.")
    job_title: str = Field(..., description="Целевая должность.")
    experience: str = Field(default="", description="Опыт работы пользователя.")
    skills: str = Field(default="", description="Навыки пользователя.")
    achievements: str = Field(..., description="Достижения пользователя.")
    attachments: List[str] = Field(default_factory=list, description="Список base64‑строк вложений.")

class SearchResults(BaseModel):
    employer_name: str = Field(default="", description="Имя работодателя.")
    company_info: str = Field(..., description="Информация о компании.")
    job_specific_info: str = Field(..., description="Информация по роли/требования.")

class ResumeDraft(BaseModel):
    draft_content: str = Field(..., description="Содержимое черновика резюме.")
    is_validated: bool = Field(default=False, description="Пройден ли чекер.")
    validation_feedback: str = Field(default="", description="Обратная связь чекера.")

class AgentState(BaseModel):
    user_data: Optional[UserData] = None
    current_employer: Optional[str] = None
    search_results: Optional[SearchResults] = None
    resume_draft: Optional[ResumeDraft] = None
    iteration_count: int = 0
    max_iterations: int = 3
    error_message: Optional[str] = None
