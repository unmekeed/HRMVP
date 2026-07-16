import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PlanTier(str, enum.Enum):
    free = "free"
    pro = "pro"
    enterprise = "enterprise"


class Role(str, enum.Enum):
    owner = "owner"
    admin = "admin"
    recruiter = "recruiter"


# Порядок ролей для сравнения прав (больше = больше прав)
ROLE_ORDER = {Role.recruiter: 0, Role.admin: 1, Role.owner: 2}


class VacancyStatus(str, enum.Enum):
    active = "active"
    closed = "closed"
    archived = "archived"


class CandidateStatus(str, enum.Enum):
    new = "new"
    reviewed = "reviewed"
    shortlist = "shortlist"
    interview = "interview"
    offer = "offer"
    rejected = "rejected"


class AnalysisStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    done = "done"
    error = "error"


class BatchStatus(str, enum.Enum):
    processing = "processing"
    done = "done"
    error = "error"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    # Активное рабочее пространство пользователя
    active_org_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    vacancies: Mapped[list["Vacancy"]] = relationship(back_populates="owner")


class Organization(Base):
    """Рабочее пространство (команда): содержит вакансии, участников, тариф."""

    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255))
    plan: Mapped[PlanTier] = mapped_column(Enum(PlanTier), default=PlanTier.free)
    # Счётчик анализов за текущий период (сбрасывается раз в 30 дней)
    analyses_used: Mapped[int] = mapped_column(Integer, default=0)
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("org_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.recruiter)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    organization: Mapped[Organization] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship()


class Invitation(Base):
    __tablename__ = "invitations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.recruiter)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True, default=_uuid)
    accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Vacancy(Base):
    __tablename__ = "vacancies"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    requirements: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[VacancyStatus] = mapped_column(
        Enum(VacancyStatus), default=VacancyStatus.active
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    owner: Mapped[User] = relationship(back_populates="vacancies")
    candidates: Mapped[list["Candidate"]] = relationship(
        back_populates="vacancy", cascade="all, delete-orphan"
    )


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    vacancy_id: Mapped[str] = mapped_column(ForeignKey("vacancies.id"), index=True)
    filename: Mapped[str] = mapped_column(String(512))
    resume_text: Mapped[str] = mapped_column(Text, default="")

    # Извлекается AI из резюме
    full_name: Mapped[str] = mapped_column(String(255), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(64), default="")

    # Результат анализа
    analysis_status: Mapped[AnalysisStatus] = mapped_column(
        Enum(AnalysisStatus), default=AnalysisStatus.pending
    )
    analysis_error: Mapped[str] = mapped_column(Text, default="")
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    verdict: Mapped[str] = mapped_column(String(32), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    strengths: Mapped[list] = mapped_column(JSON, default=list)
    weaknesses: Mapped[list] = mapped_column(JSON, default=list)
    matched_requirements: Mapped[list] = mapped_column(JSON, default=list)
    missing_requirements: Mapped[list] = mapped_column(JSON, default=list)
    recommendation: Mapped[str] = mapped_column(Text, default="")

    status: Mapped[CandidateStatus] = mapped_column(
        Enum(CandidateStatus), default=CandidateStatus.new
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    vacancy: Mapped[Vacancy] = relationship(back_populates="candidates")


class AnalysisBatch(Base):
    """Пачка резюме, отправленная в Anthropic Message Batches API."""

    __tablename__ = "analysis_batches"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    vacancy_id: Mapped[str] = mapped_column(ForeignKey("vacancies.id"), index=True)
    provider_batch_id: Mapped[str] = mapped_column(String(255), index=True)
    status: Mapped[BatchStatus] = mapped_column(
        Enum(BatchStatus), default=BatchStatus.processing
    )
    candidate_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
