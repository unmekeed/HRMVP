from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import get_current_user
from ..models import Candidate, User, Vacancy
from ..schemas import VacancyCreate, VacancyOut, VacancyUpdate

router = APIRouter(prefix="/api/vacancies", tags=["vacancies"])


async def get_own_vacancy(
    vacancy_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Vacancy:
    vacancy = await db.get(Vacancy, vacancy_id)
    if vacancy is None or vacancy.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Вакансия не найдена")
    return vacancy


@router.post("", response_model=VacancyOut, status_code=201)
async def create_vacancy(
    payload: VacancyCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    vacancy = Vacancy(owner_id=user.id, **payload.model_dump())
    db.add(vacancy)
    await db.commit()
    return VacancyOut.model_validate(vacancy)


@router.get("", response_model=list[VacancyOut])
async def list_vacancies(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    counts = (
        select(Candidate.vacancy_id, func.count(Candidate.id).label("cnt"))
        .group_by(Candidate.vacancy_id)
        .subquery()
    )
    rows = await db.execute(
        select(Vacancy, func.coalesce(counts.c.cnt, 0))
        .outerjoin(counts, counts.c.vacancy_id == Vacancy.id)
        .where(Vacancy.owner_id == user.id)
        .order_by(Vacancy.created_at.desc())
    )
    result = []
    for vacancy, cnt in rows.all():
        out = VacancyOut.model_validate(vacancy)
        out.candidates_count = cnt
        result.append(out)
    return result


@router.get("/{vacancy_id}", response_model=VacancyOut)
async def get_vacancy(
    vacancy: Vacancy = Depends(get_own_vacancy),
    db: AsyncSession = Depends(get_db),
):
    cnt = await db.scalar(
        select(func.count(Candidate.id)).where(Candidate.vacancy_id == vacancy.id)
    )
    out = VacancyOut.model_validate(vacancy)
    out.candidates_count = cnt or 0
    return out


@router.patch("/{vacancy_id}", response_model=VacancyOut)
async def update_vacancy(
    payload: VacancyUpdate,
    vacancy: Vacancy = Depends(get_own_vacancy),
    db: AsyncSession = Depends(get_db),
):
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(vacancy, field, value)
    await db.commit()
    return VacancyOut.model_validate(vacancy)


@router.delete("/{vacancy_id}", status_code=204)
async def delete_vacancy(
    vacancy: Vacancy = Depends(get_own_vacancy),
    db: AsyncSession = Depends(get_db),
):
    await db.delete(vacancy)
    await db.commit()
