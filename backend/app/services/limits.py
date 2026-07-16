"""Проверка и учёт тарифных лимитов организации."""

from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Membership, Organization, Vacancy
from ..models import _now  # общий источник времени
from ..plans import PERIOD_DAYS, limits_for

PLAN_LIMIT_EXCEEDED = status.HTTP_402_PAYMENT_REQUIRED


async def _reset_period_if_needed(org: Organization, db: AsyncSession) -> None:
    start = org.period_start
    if start.tzinfo is None:
        from datetime import timezone

        start = start.replace(tzinfo=timezone.utc)
    if _now() - start >= timedelta(days=PERIOD_DAYS):
        org.analyses_used = 0
        org.period_start = _now()
        await db.flush()


async def enforce_vacancy_limit(org: Organization, db: AsyncSession) -> None:
    limit = limits_for(org.plan)["max_vacancies"]
    if limit is None:
        return
    count = await db.scalar(
        select(func.count(Vacancy.id)).where(Vacancy.org_id == org.id)
    )
    if count >= limit:
        raise HTTPException(
            PLAN_LIMIT_EXCEEDED,
            f"Достигнут лимит вакансий тарифа ({limit}). Обновите тариф.",
        )


async def enforce_member_limit(org: Organization, db: AsyncSession) -> None:
    limit = limits_for(org.plan)["max_members"]
    if limit is None:
        return
    count = await db.scalar(
        select(func.count(Membership.id)).where(Membership.org_id == org.id)
    )
    if count >= limit:
        raise HTTPException(
            PLAN_LIMIT_EXCEEDED,
            f"Достигнут лимит участников тарифа ({limit}). Обновите тариф.",
        )


async def consume_analyses(org: Organization, n: int, db: AsyncSession) -> None:
    """Проверить остаток анализов на период и списать n. Сбрасывает период."""
    await _reset_period_if_needed(org, db)
    limit = limits_for(org.plan)["monthly_analyses"]
    if limit is not None and org.analyses_used + n > limit:
        remaining = max(0, limit - org.analyses_used)
        raise HTTPException(
            PLAN_LIMIT_EXCEEDED,
            f"Недостаточно квоты анализов: осталось {remaining} из {limit} за период. "
            "Обновите тариф.",
        )
    org.analyses_used += n
    await db.flush()
