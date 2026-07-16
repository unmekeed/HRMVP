# AI Screening — SaaS для автоматического анализа резюме

MVP 1.0 по техническому заданию: HR загружает описание вакансии и пачку резюме,
система извлекает текст, анализирует каждое резюме с помощью AI, рассчитывает
степень соответствия (0–100), выделяет сильные и слабые стороны, ранжирует
кандидатов и формирует рекомендации.

## Стек

| Слой | Технология | Почему |
|---|---|---|
| Backend | Python 3.11, **FastAPI**, SQLAlchemy 2 (async) | Быстрая разработка API, нативная асинхронность для фонового AI-анализа, автодокументация OpenAPI (`/docs`) |
| БД | **PostgreSQL** (prod) / SQLite (dev) | Одна кодовая база через `AIS_DATABASE_URL`; локальная разработка без инфраструктуры |
| Аутентификация | JWT (PyJWT) + bcrypt | Стандарт для SPA + API |
| Извлечение текста | `pypdf`, `python-docx` | PDF / DOCX / TXT без внешних сервисов |
| AI-анализ | **Anthropic API**, модель `claude-opus-4-8`, structured outputs | Гарантированно валидный JSON по схеме (балл, вердикт, сильные/слабые стороны, рекомендация); prompt caching системного промпта снижает стоимость |
| Frontend | **React 18 + Vite + TypeScript**, React Router | SPA: список вакансий, загрузка резюме, ранжированная таблица кандидатов, карточка кандидата, live-обновление статуса анализа |
| Инфраструктура | docker-compose (PostgreSQL + backend + nginx/frontend) | Один `docker compose up` для запуска всего продукта |

Без `AIS_ANTHROPIC_API_KEY` анализ работает в **mock-режиме** (эвристика по
ключевым словам) — весь пользовательский поток можно проверить без ключа.

## Что реализовано (пользовательский сценарий ТЗ)

1. Регистрация / вход (JWT).
2. Создание вакансии: название, описание, ключевые требования.
3. Загрузка пачки резюме (PDF / DOCX / TXT, до 10 МБ каждое, multi-upload).
4. Автоматическое извлечение текста.
5. Фоновый AI-анализ каждого резюме: балл 0–100, вердикт
   (`strong/good/partial/weak match`), ФИО/email/телефон, сильные и слабые
   стороны, покрытые и непокрытые требования, рекомендация для HR.
6. Ранжированный список кандидатов (сортировка по баллу) с live-обновлением.
7. Карточка кандидата с деталями оценки и повторным анализом при ошибке.
8. Смена статуса кандидата (новый → шорт-лист → интервью → оффер / отказ).
9. Экспорт кандидатов в CSV (совместим с Excel).

## Быстрый старт

### Docker (всё сразу)

```bash
cp .env.example .env          # при желании впишите AIS_ANTHROPIC_API_KEY
docker compose up --build
# UI:  http://localhost:8080
# API: http://localhost:8000/docs
```

### Локальная разработка

Backend:

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Frontend (проксирует `/api` на `localhost:8000`):

```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

Тесты:

```bash
cd backend && .venv/bin/python -m pytest tests/ -q
```

## Конфигурация (env, префикс `AIS_`)

| Переменная | По умолчанию | Описание |
|---|---|---|
| `AIS_DATABASE_URL` | `sqlite+aiosqlite:///./ai_screening.db` | Строка подключения SQLAlchemy |
| `AIS_JWT_SECRET` | `change-me-in-production` | Секрет подписи JWT |
| `AIS_ANTHROPIC_API_KEY` | — | Ключ Anthropic API |
| `AIS_ANTHROPIC_MODEL` | `claude-opus-4-8` | Модель анализа |
| `AIS_ANALYSIS_MODE` | `auto` | `auto` / `claude` / `mock` |
| `AIS_MAX_UPLOAD_SIZE_MB` | `10` | Лимит размера файла резюме |

## API (кратко)

- `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`
- `GET|POST /api/vacancies`, `GET|PATCH|DELETE /api/vacancies/{id}`
- `POST /api/vacancies/{id}/resumes` — multi-upload резюме, запускает анализ
- `GET /api/vacancies/{id}/candidates` — список, отсортированный по баллу
- `GET /api/vacancies/{id}/export` — CSV
- `GET /api/candidates/{id}`, `PATCH /api/candidates/{id}/status`,
  `POST /api/candidates/{id}/reanalyze`

Полная интерактивная документация: `http://localhost:8000/docs`.

## Дальнейшие шаги (за рамками MVP)

- Очередь задач (Redis + arq/Celery) вместо in-process BackgroundTasks — для
  горизонтального масштабирования анализа.
- Alembic-миграции вместо `create_all`.
- Батч-анализ через Anthropic Message Batches API (−50% стоимости при больших
  пачках резюме).
- Командные аккаунты/роли, лимиты тарифов, биллинг.
- OCR для сканированных PDF.
