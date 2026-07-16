from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "AI Screening"
    database_url: str = "sqlite+aiosqlite:///./ai_screening.db"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"
    # Без API-ключа анализ работает в mock-режиме (эвристика по ключевым словам)
    analysis_mode: str = "auto"  # auto | claude | mock

    # Очередь задач. Пусто → анализ выполняется in-process (dev/тесты);
    # задан → задачи уходят в arq-воркер через Redis.
    redis_url: str = ""

    # dev/тесты создают таблицы через create_all; в проде схемой управляет
    # Alembic (AIS_AUTO_CREATE_TABLES=false + alembic upgrade head).
    auto_create_tables: bool = True

    # Batch API: при загрузке пачки резюме >= batch_threshold отправлять один
    # batch вместо N запросов (−50% стоимости). Требует Redis и claude-режим.
    use_batch_api: bool = False
    batch_threshold: int = 5

    # OCR для сканированных PDF (нужны бинарники tesseract + poppler)
    ocr_enabled: bool = True
    ocr_lang: str = "rus+eng"
    ocr_max_pages: int = 15

    max_upload_size_mb: int = 10
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    class Config:
        env_file = ".env"
        env_prefix = "AIS_"


@lru_cache
def get_settings() -> Settings:
    return Settings()
