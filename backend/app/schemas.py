from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .models import AnalysisStatus, CandidateStatus, VacancyStatus


# --- auth ---

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    name: str = ""


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    name: str


# --- vacancies ---

class VacancyCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = ""
    requirements: str = ""


class VacancyUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    requirements: str | None = None
    status: VacancyStatus | None = None


class VacancyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str
    requirements: str
    status: VacancyStatus
    created_at: datetime
    candidates_count: int = 0


# --- candidates ---

class CandidateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    vacancy_id: str
    filename: str
    full_name: str
    email: str
    phone: str
    analysis_status: AnalysisStatus
    analysis_error: str
    score: float | None
    verdict: str
    summary: str
    strengths: list
    weaknesses: list
    matched_requirements: list
    missing_requirements: list
    recommendation: str
    status: CandidateStatus
    created_at: datetime


class CandidateStatusUpdate(BaseModel):
    status: CandidateStatus
