"""End-to-end тесты API: регистрация → вакансия → загрузка резюме → анализ (mock)."""

import asyncio
import os

os.environ["AIS_DATABASE_URL"] = "sqlite+aiosqlite:///./test_ai_screening.db"
os.environ["AIS_ANALYSIS_MODE"] = "mock"

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import engine, init_db, Base
from app.main import app

RESUME_TXT = """Иванов Иван Иванович
Python-разработчик, 5 лет опыта
ivanov@example.com, +7 999 123-45-67

Опыт: FastAPI, PostgreSQL, Docker, SQLAlchemy, REST API, asyncio.
Разрабатывал микросервисы, настраивал CI/CD.
"""


@pytest.fixture()
async def client():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def test_full_flow(client: AsyncClient):
    # регистрация
    r = await client.post(
        "/api/auth/register",
        json={"email": "hr@example.com", "password": "secret123", "name": "HR"},
    )
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # повторная регистрация — конфликт
    r = await client.post(
        "/api/auth/register",
        json={"email": "hr@example.com", "password": "secret123"},
    )
    assert r.status_code == 409

    # логин
    r = await client.post(
        "/api/auth/login",
        json={"email": "hr@example.com", "password": "secret123"},
    )
    assert r.status_code == 200

    # без токена — 401
    r = await client.get("/api/vacancies")
    assert r.status_code == 401

    # создание вакансии
    r = await client.post(
        "/api/vacancies",
        headers=headers,
        json={
            "title": "Python-разработчик",
            "description": "Разработка backend-сервисов",
            "requirements": "Python\nFastAPI\nPostgreSQL\nKubernetes",
        },
    )
    assert r.status_code == 201, r.text
    vacancy_id = r.json()["id"]

    # загрузка резюме
    r = await client.post(
        f"/api/vacancies/{vacancy_id}/resumes",
        headers=headers,
        files=[("files", ("ivanov.txt", RESUME_TXT.encode(), "text/plain"))],
    )
    assert r.status_code == 201, r.text
    candidate_id = r.json()[0]["id"]

    # фоновая задача BackgroundTasks в ASGITransport выполняется после ответа
    for _ in range(50):
        r = await client.get(f"/api/candidates/{candidate_id}", headers=headers)
        if r.json()["analysis_status"] == "done":
            break
        await asyncio.sleep(0.1)
    body = r.json()
    assert body["analysis_status"] == "done", body
    assert body["score"] is not None
    assert body["email"] == "ivanov@example.com"

    # список кандидатов отсортирован и не пуст
    r = await client.get(f"/api/vacancies/{vacancy_id}/candidates", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) == 1

    # смена статуса кандидата
    r = await client.patch(
        f"/api/candidates/{candidate_id}/status",
        headers=headers,
        json={"status": "shortlist"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "shortlist"

    # экспорт CSV
    r = await client.get(f"/api/vacancies/{vacancy_id}/export", headers=headers)
    assert r.status_code == 200
    assert "ФИО" in r.text

    # неподдерживаемый формат
    r = await client.post(
        f"/api/vacancies/{vacancy_id}/resumes",
        headers=headers,
        files=[("files", ("photo.jpg", b"\xff\xd8\xff", "image/jpeg"))],
    )
    assert r.status_code == 422

    # чужая вакансия недоступна
    r2 = await client.post(
        "/api/auth/register",
        json={"email": "other@example.com", "password": "secret123"},
    )
    other_headers = {"Authorization": f"Bearer {r2.json()['access_token']}"}
    r = await client.get(f"/api/vacancies/{vacancy_id}", headers=other_headers)
    assert r.status_code == 404
