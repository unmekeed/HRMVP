import csv
import io

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import get_db
from ..deps import get_current_user
from ..models import AnalysisStatus, Candidate, User, Vacancy
from ..schemas import CandidateOut, CandidateStatusUpdate
from ..services.batch import should_use_batch
from ..services.extraction import ExtractionError, extract_text
from ..services.tasks import enqueue_analysis, enqueue_batch
from .vacancies import get_own_vacancy

router = APIRouter(prefix="/api", tags=["candidates"])


@router.post(
    "/vacancies/{vacancy_id}/resumes",
    response_model=list[CandidateOut],
    status_code=201,
)
async def upload_resumes(
    background: BackgroundTasks,
    files: list[UploadFile],
    vacancy: Vacancy = Depends(get_own_vacancy),
    db: AsyncSession = Depends(get_db),
):
    if not files:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Файлы не переданы")
    max_bytes = get_settings().max_upload_size_mb * 1024 * 1024

    created: list[Candidate] = []
    errors: list[str] = []
    for upload in files:
        data = await upload.read()
        filename = upload.filename or "resume"
        if len(data) > max_bytes:
            errors.append(f"{filename}: файл больше {get_settings().max_upload_size_mb} МБ")
            continue
        try:
            text = extract_text(filename, data)
        except ExtractionError as exc:
            errors.append(f"{filename}: {exc}")
            continue
        candidate = Candidate(
            vacancy_id=vacancy.id, filename=filename, resume_text=text
        )
        db.add(candidate)
        created.append(candidate)

    if not created:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "; ".join(errors) or "Не удалось обработать файлы",
        )
    await db.commit()

    ids = [c.id for c in created]
    if should_use_batch(len(ids)):
        await enqueue_batch(vacancy.id, ids)
    else:
        for candidate_id in ids:
            await enqueue_analysis(candidate_id, background)

    return [CandidateOut.model_validate(c) for c in created]


@router.get("/vacancies/{vacancy_id}/candidates", response_model=list[CandidateOut])
async def list_candidates(
    vacancy: Vacancy = Depends(get_own_vacancy),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.scalars(
        select(Candidate)
        .where(Candidate.vacancy_id == vacancy.id)
        .order_by(
            case((Candidate.score.is_(None), 1), else_=0),
            Candidate.score.desc(),
            Candidate.created_at.desc(),
        )
    )
    return [CandidateOut.model_validate(c) for c in rows.all()]


async def _get_own_candidate(
    candidate_id: str, user: User, db: AsyncSession
) -> Candidate:
    candidate = await db.get(Candidate, candidate_id)
    if candidate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Кандидат не найден")
    vacancy = await db.get(Vacancy, candidate.vacancy_id)
    if vacancy is None or vacancy.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Кандидат не найден")
    return candidate


@router.get("/candidates/{candidate_id}", response_model=CandidateOut)
async def get_candidate(
    candidate_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return CandidateOut.model_validate(await _get_own_candidate(candidate_id, user, db))


@router.patch("/candidates/{candidate_id}/status", response_model=CandidateOut)
async def update_candidate_status(
    candidate_id: str,
    payload: CandidateStatusUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    candidate = await _get_own_candidate(candidate_id, user, db)
    candidate.status = payload.status
    await db.commit()
    return CandidateOut.model_validate(candidate)


@router.post("/candidates/{candidate_id}/reanalyze", response_model=CandidateOut)
async def reanalyze_candidate(
    candidate_id: str,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    candidate = await _get_own_candidate(candidate_id, user, db)
    candidate.analysis_status = AnalysisStatus.pending
    candidate.analysis_error = ""
    await db.commit()
    await enqueue_analysis(candidate.id, background)
    return CandidateOut.model_validate(candidate)


@router.get("/vacancies/{vacancy_id}/export")
async def export_candidates_csv(
    vacancy: Vacancy = Depends(get_own_vacancy),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.scalars(
        select(Candidate)
        .where(Candidate.vacancy_id == vacancy.id)
        .order_by(
            case((Candidate.score.is_(None), 1), else_=0),
            Candidate.score.desc(),
        )
    )
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(
        ["ФИО", "Email", "Телефон", "Балл", "Вердикт", "Статус",
         "Сильные стороны", "Слабые стороны", "Рекомендация", "Файл"]
    )
    for c in rows.all():
        writer.writerow([
            c.full_name, c.email, c.phone,
            "" if c.score is None else int(c.score),
            c.verdict, c.status.value,
            "; ".join(c.strengths or []), "; ".join(c.weaknesses or []),
            c.recommendation, c.filename,
        ])
    # BOM — чтобы Excel корректно открывал кириллицу в UTF-8
    data = "﻿" + buf.getvalue()
    return StreamingResponse(
        iter([data]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="candidates_{vacancy.id}.csv"'
        },
    )
