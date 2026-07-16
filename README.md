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
| Миграции | **Alembic** (async) | В проде схемой управляет Alembic (`alembic upgrade head` в entrypoint); dev/тесты используют `create_all` |
| Очередь | **Redis + arq** | Анализ вынесен в отдельный воркер; без Redis — in-process fallback |
| Аутентификация | JWT (PyJWT) + bcrypt | Стандарт для SPA + API |
| Команды/биллинг | Организации, роли (owner/admin/recruiter), тарифы | Рабочие пространства, RBAC, лимиты по тарифу, mock-биллинг |
| Извлечение текста | `pypdf`, `python-docx`, **OCR** (tesseract + poppler) | PDF / DOCX / TXT; сканированные PDF распознаются через OCR (rus+eng) |
| AI-анализ | **Anthropic API**, модель `claude-opus-4-8`, structured outputs | Валидный JSON по схеме; prompt caching системного промпта; **Batch API** (−50%) для больших пачек |
| Frontend | **React 18 + Vite + TypeScript**, React Router | SPA: вакансии, загрузка резюме, ранжирование, карточка кандидата, настройки команды/тарифа |
| Инфраструктура | docker-compose (PostgreSQL + Redis + backend + worker + nginx/frontend) | Один `docker compose up` для запуска всего продукта |

Без `AIS_ANTHROPIC_API_KEY` анализ работает в **mock-режиме** (эвристика по
ключевым словам) — весь пользовательский поток можно проверить без ключа.

### Архитектура анализа

```
upload резюме → extraction (PDF/DOCX/TXT + OCR для сканов)
             → enqueue_analysis
                ├─ Redis есть → arq-воркер (по одному) ─┐
                │  либо Batch API (пачка ≥ порога) ─────┤→ analyze_resume
                └─ Redis нет → in-process (dev/тесты) ──┘   (claude | mock)
             → результат в БД, кандидаты ранжируются по баллу
```

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
| `AIS_REDIS_URL` | — | Redis для очереди; пусто = анализ in-process |
| `AIS_AUTO_CREATE_TABLES` | `true` | dev: create_all; в проде `false` + Alembic |
| `AIS_JWT_SECRET` | `change-me-in-production` | Секрет подписи JWT |
| `AIS_ANTHROPIC_API_KEY` | — | Ключ Anthropic API |
| `AIS_ANTHROPIC_MODEL` | `claude-opus-4-8` | Модель анализа |
| `AIS_ANALYSIS_MODE` | `auto` | `auto` / `claude` / `mock` |
| `AIS_USE_BATCH_API` | `false` | Batch API для пачек ≥ порога (нужен Redis + claude) |
| `AIS_BATCH_THRESHOLD` | `5` | Порог кол-ва резюме для батча |
| `AIS_OCR_ENABLED` | `true` | OCR для сканированных PDF |
| `AIS_OCR_LANG` | `rus+eng` | Языки распознавания tesseract |
| `AIS_MAX_UPLOAD_SIZE_MB` | `10` | Лимит размера файла резюме |

## Тарифы

| Тариф | Вакансии | Анализы/период | Участники |
|---|---|---|---|
| Free | 3 | 30 | 2 |
| Pro ($49/мес) | 50 | 1000 | 10 |
| Enterprise | ∞ | ∞ | ∞ |

Смена тарифа (`POST /api/org/plan`) в MVP — без реального платёжного провайдера;
в проде здесь Stripe Checkout + webhook оплаты.

## Роли

- **owner** — полный доступ, смена тарифа, управление всеми участниками.
- **admin** — управление участниками и приглашениями, вакансии, кандидаты.
- **recruiter** — вакансии и кандидаты (без управления командой и тарифом).

## API (кратко)

- `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`
- `GET|POST /api/vacancies`, `GET|PATCH|DELETE /api/vacancies/{id}`
- `POST /api/vacancies/{id}/resumes` — multi-upload резюме, запускает анализ
- `GET /api/vacancies/{id}/candidates` — список, отсортированный по баллу
- `GET /api/vacancies/{id}/export` — CSV
- `GET /api/candidates/{id}`, `PATCH /api/candidates/{id}/status`,
  `POST /api/candidates/{id}/reanalyze`

Полная интерактивная документация: `http://localhost:8000/docs`.

## Реализовано сверх MVP

- ✅ Очередь задач (Redis + arq) вместо in-process — воркер масштабируется отдельно.
- ✅ Alembic-миграции вместо `create_all` в проде.
- ✅ Батч-анализ через Anthropic Message Batches API (−50% при больших пачках).
- ✅ Командные аккаунты, роли, тарифные лимиты, mock-биллинг.
- ✅ OCR сканированных PDF (tesseract + poppler, rus+eng).

## Дальнейшие шаги

- Реальный платёжный провайдер (Stripe Checkout + webhooks) вместо mock-биллинга.
- Отправка приглашений участникам по email (сейчас токен возвращается в ответе).
- Метрики/наблюдаемость воркера (Prometheus), алерты на ошибки анализа.
