from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import base64

class UserData(BaseModel):
    """Model for user-provided information."""
    employers: List[str] = Field(..., description="List of target employers.")
    job_title: str = Field(..., description="Target job title.")
    experience: str = Field(..., description="User's work experience.")
    skills: str = Field(..., description="User's skills.")
    achievements: str = Field(..., description="User's achievements.")
    attachments: List[str] = Field(default_factory=list, description="List of base64 encoded image strings.")

class SearchResults(BaseModel):
    """Model for search agent results."""
    employer_name: str = Field(..., description="Name of the employer.")
    company_info: str = Field(..., description="Information about the company found online.")
    job_specific_info: str = Field(..., description="Information specific to the job role, if found.")

class ResumeDraft(BaseModel):
    """Model for resume drafts."""
    draft_content: str = Field(..., description="The content of the resume draft.")
    is_validated: bool = Field(default=False, description="Whether the resume passed the checker agent.")
    validation_feedback: str = Field(default="", description="Feedback from the checker agent.")

class AgentState(BaseModel):
    """Model representing the state of the workflow."""
    user_data: Optional[UserData] = None
    current_employer: Optional[str] = None
    search_results: Optional[SearchResults] = None
    resume_draft: Optional[ResumeDraft] = None
    iteration_count: int = 0 # To prevent infinite loops during validation
    max_iterations: int = 3 # Maximum number of validation/generation cycles
    error_message: Optional[str] = None
    output_file_path: Optional[str] = None