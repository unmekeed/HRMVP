"""arq-воркер: выполняет задачи анализа резюме вне процесса API.

Запуск: arq app.worker.WorkerSettings
"""

from arq.connections import RedisSettings

from .config import get_settings
from .services.batch import poll_batch, submit_batch
from .services.tasks import run_analysis


async def analyze_candidate(ctx, candidate_id: str) -> None:
    await run_analysis(candidate_id)


async def submit_analysis_batch(ctx, vacancy_id: str, candidate_ids: list[str]) -> None:
    await submit_batch(vacancy_id, candidate_ids, ctx.get("redis"))


async def poll_analysis_batch(ctx, batch_id: str) -> None:
    await poll_batch(batch_id, ctx.get("redis"))


class WorkerSettings:
    functions = [analyze_candidate, submit_analysis_batch, poll_analysis_batch]
    max_jobs = 10
    keep_result = 3600

    @staticmethod
    def redis_settings() -> RedisSettings:
        return RedisSettings.from_dsn(get_settings().redis_url)
