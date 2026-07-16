"""Диспетчеризация фоновых задач анализа.

Есть Redis (AIS_REDIS_URL) → задача уходит в arq-воркер.
Нет Redis → выполняется in-process (BackgroundTasks или напрямую) — для
локальной разработки и тестов без инфраструктуры.
"""

import asyncio
import logging

from ..config import get_settings
from ..database import SessionLocal
from ..models import AnalysisStatus, Candidate, Vacancy
from .analysis import analyze_resume

logger = logging.getLogger(__name__)

_pool = None
_pool_lock = asyncio.Lock()


async def run_analysis(candidate_id: str) -> None:
    """Анализ одного резюме в собственной сессии БД. Идемпотентно по кандидату."""
    async with SessionLocal() as db:
        candidate = await db.get(Candidate, candidate_id)
        if candidate is None:
            return
        vacancy = await db.get(Vacancy, candidate.vacancy_id)
        candidate.analysis_status = AnalysisStatus.processing
        await db.commit()
        try:
            result = await analyze_resume(
                vacancy.title,
                vacancy.description,
                vacancy.requirements,
                candidate.resume_text,
            )
            _apply_result(candidate, result)
            candidate.analysis_status = AnalysisStatus.done
            candidate.analysis_error = ""
        except Exception as exc:  # ошибка анализа не должна ронять воркер
            logger.exception("Analysis failed for candidate %s", candidate_id)
            candidate.analysis_status = AnalysisStatus.error
            candidate.analysis_error = str(exc)[:2000]
        await db.commit()


def _apply_result(candidate: Candidate, result: dict) -> None:
    candidate.full_name = result["full_name"]
    candidate.email = result["email"]
    candidate.phone = result["phone"]
    candidate.score = float(result["score"])
    candidate.verdict = result["verdict"]
    candidate.summary = result["summary"]
    candidate.strengths = result["strengths"]
    candidate.weaknesses = result["weaknesses"]
    candidate.matched_requirements = result["matched_requirements"]
    candidate.missing_requirements = result["missing_requirements"]
    candidate.recommendation = result["recommendation"]


async def _get_pool():
    global _pool
    if _pool is None:
        async with _pool_lock:
            if _pool is None:
                from arq import create_pool
                from arq.connections import RedisSettings

                _pool = await create_pool(
                    RedisSettings.from_dsn(get_settings().redis_url)
                )
    return _pool


async def enqueue_analysis(candidate_id: str, background=None) -> None:
    """Поставить задачу анализа: в очередь (Redis) либо in-process."""
    settings = get_settings()
    if settings.redis_url:
        pool = await _get_pool()
        await pool.enqueue_job("analyze_candidate", candidate_id)
    elif background is not None:
        background.add_task(run_analysis, candidate_id)
    else:
        await run_analysis(candidate_id)
