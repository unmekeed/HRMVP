"""Батч-анализ резюме через Anthropic Message Batches API (−50% стоимости).

Поток: submit_batch создаёт batch на стороне Anthropic и планирует poll_batch;
poll_batch периодически проверяет готовность и раскладывает результаты по
кандидатам. Обе задачи выполняются в arq-воркере (нужен Redis).
"""

import logging
from datetime import timedelta

from ..config import get_settings
from ..database import SessionLocal
from ..models import AnalysisBatch, AnalysisStatus, BatchStatus, Candidate, Vacancy
from .analysis import (
    ANALYSIS_SCHEMA,
    SYSTEM_PROMPT,
    build_user_message,
    parse_analysis_json,
    resolve_mode,
)
from .tasks import _apply_result

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 30


def should_use_batch(count: int) -> bool:
    s = get_settings()
    return bool(
        s.use_batch_api
        and s.redis_url
        and resolve_mode() == "claude"
        and count >= s.batch_threshold
    )


async def submit_batch(vacancy_id: str, candidate_ids: list[str], redis) -> None:
    from anthropic import AsyncAnthropic
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    settings = get_settings()
    async with SessionLocal() as db:
        vacancy = await db.get(Vacancy, vacancy_id)
        if vacancy is None:
            return
        requests = []
        for cid in candidate_ids:
            candidate = await db.get(Candidate, cid)
            if candidate is None:
                continue
            candidate.analysis_status = AnalysisStatus.processing
            requests.append(
                Request(
                    custom_id=cid,
                    params=MessageCreateParamsNonStreaming(
                        model=settings.anthropic_model,
                        max_tokens=4096,
                        system=[
                            {
                                "type": "text",
                                "text": SYSTEM_PROMPT,
                                "cache_control": {"type": "ephemeral"},
                            }
                        ],
                        output_config={
                            "format": {"type": "json_schema", "schema": ANALYSIS_SCHEMA}
                        },
                        messages=[
                            {
                                "role": "user",
                                "content": build_user_message(
                                    vacancy.title,
                                    vacancy.description,
                                    vacancy.requirements,
                                    candidate.resume_text,
                                ),
                            }
                        ],
                    ),
                )
            )
        await db.commit()

        if not requests:
            return

        try:
            client = AsyncAnthropic(api_key=settings.anthropic_api_key or None)
            provider = await client.messages.batches.create(requests=requests)
        except Exception:
            logger.exception("Failed to submit batch for vacancy %s", vacancy_id)
            for cid in candidate_ids:
                candidate = await db.get(Candidate, cid)
                if candidate is not None:
                    candidate.analysis_status = AnalysisStatus.error
                    candidate.analysis_error = "Не удалось создать batch"
            await db.commit()
            return

        batch = AnalysisBatch(
            vacancy_id=vacancy_id,
            provider_batch_id=provider.id,
            status=BatchStatus.processing,
            candidate_count=len(requests),
        )
        db.add(batch)
        await db.commit()
        batch_id = batch.id

    await redis.enqueue_job(
        "poll_analysis_batch", batch_id, _defer_by=timedelta(seconds=POLL_INTERVAL_SECONDS)
    )


async def poll_batch(batch_id: str, redis) -> None:
    from anthropic import AsyncAnthropic

    settings = get_settings()
    async with SessionLocal() as db:
        batch = await db.get(AnalysisBatch, batch_id)
        if batch is None or batch.status != BatchStatus.processing:
            return
        provider_id = batch.provider_batch_id

    client = AsyncAnthropic(api_key=settings.anthropic_api_key or None)
    info = await client.messages.batches.retrieve(provider_id)
    if info.processing_status != "ended":
        if redis is not None:
            await redis.enqueue_job(
                "poll_analysis_batch",
                batch_id,
                _defer_by=timedelta(seconds=POLL_INTERVAL_SECONDS),
            )
        return

    async with SessionLocal() as db:
        async for result in await client.messages.batches.results(provider_id):
            candidate = await db.get(Candidate, result.custom_id)
            if candidate is None:
                continue
            try:
                if result.result.type == "succeeded":
                    text = next(
                        b.text
                        for b in result.result.message.content
                        if b.type == "text"
                    )
                    _apply_result(candidate, parse_analysis_json(text))
                    candidate.analysis_status = AnalysisStatus.done
                    candidate.analysis_error = ""
                else:
                    candidate.analysis_status = AnalysisStatus.error
                    candidate.analysis_error = f"batch: {result.result.type}"
            except Exception as exc:
                logger.exception("Batch result apply failed for %s", result.custom_id)
                candidate.analysis_status = AnalysisStatus.error
                candidate.analysis_error = str(exc)[:2000]

        batch = await db.get(AnalysisBatch, batch_id)
        if batch is not None:
            batch.status = BatchStatus.done
        await db.commit()
