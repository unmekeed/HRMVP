from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .models import AnalysisStatus, CandidateStatus, PlanTier, Role, VacancyStatus


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


# --- organizations / billing / members ---

class OrgOut(BaseModel):
    id: str
    name: str
    plan: PlanTier
    role: Role  # роль текущего пользователя в этом пространстве
    limits: dict
    usage: dict  # {analyses_used, vacancies, members}


class OrgSummary(BaseModel):
    id: str
    name: str
    role: Role


class PlanInfo(BaseModel):
    plan: PlanTier
    label: str
    price: int | None
    max_vacancies: int | None
    monthly_analyses: int | None
    max_members: int | None
    current: bool


class PlanChange(BaseModel):
    plan: PlanTier


class MemberOut(BaseModel):
    id: str  # membership id
    user_id: str
    email: str
    name: str
    role: Role


class RoleChange(BaseModel):
    role: Role


class InviteCreate(BaseModel):
    email: EmailStr
    role: Role = Role.recruiter


class InvitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    role: Role
    token: str
    accepted: bool
    created_at: datetime


class AcceptInvite(BaseModel):
    token: str


class SwitchOrg(BaseModel):
    org_id: str
