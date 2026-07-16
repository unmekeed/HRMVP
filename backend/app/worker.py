"""arq-воркер: выполняет задачи анализа резюме вне процесса API.

Запуск: arq app.worker.WorkerSettings
"""

from arq.connections import RedisSettings

from .config import get_settings
from .services.tasks import run_analysis


async def analyze_candidate(ctx, candidate_id: str) -> None:
    await run_analysis(candidate_id)


class WorkerSettings:
    functions = [analyze_candidate]
    max_jobs = 10
    keep_result = 3600

    @staticmethod
    def redis_settings() -> RedisSettings:
        return RedisSettings.from_dsn(get_settings().redis_url)
