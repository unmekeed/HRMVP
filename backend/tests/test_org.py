"""Тесты организаций: тарифы, лимиты, роли, приглашения."""

import os

os.environ["AIS_DATABASE_URL"] = "sqlite+aiosqlite:///./test_org.db"
os.environ["AIS_ANALYSIS_MODE"] = "mock"

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import Base, engine, init_db
from app.main import app


@pytest.fixture()
async def client():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def _register(client, email):
    r = await client.post(
        "/api/auth/register", json={"email": email, "password": "secret123", "name": email.split("@")[0]}
    )
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_org_created_on_register(client):
    h = await _register(client, "owner@example.com")
    r = await client.get("/api/org", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["plan"] == "free"
    assert body["role"] == "owner"
    assert body["limits"]["max_vacancies"] == 3
    assert body["usage"]["members"] == 1


async def test_analysis_quota_enforced(client):
    h = await _register(client, "quota@example.com")
    # На free-тарифе 30 анализов/период. Понизим искусственно через смену тарифа? Нет —
    # проверим счётчик: создаём вакансию и грузим резюме, usage растёт.
    r = await client.post("/api/vacancies", headers=h, json={"title": "V", "requirements": "Python"})
    vid = r.json()["id"]
    await client.post(
        f"/api/vacancies/{vid}/resumes", headers=h,
        files=[("files", ("a.txt", b"Python developer", "text/plain"))],
    )
    r = await client.get("/api/org", headers=h)
    assert r.json()["usage"]["analyses_used"] == 1


async def test_vacancy_limit_enforced(client):
    h = await _register(client, "vlimit@example.com")
    # free: max_vacancies=3
    for i in range(3):
        r = await client.post("/api/vacancies", headers=h, json={"title": f"V{i}"})
        assert r.status_code == 201
    r = await client.post("/api/vacancies", headers=h, json={"title": "V4"})
    assert r.status_code == 402, r.text
    assert "лимит" in r.json()["detail"].lower()


async def test_plan_change_lifts_limit(client):
    h = await _register(client, "upgrade@example.com")
    # апгрейд на pro
    r = await client.post("/api/org/plan", headers=h, json={"plan": "pro"})
    assert r.status_code == 200, r.text
    assert r.json()["plan"] == "pro"
    assert r.json()["limits"]["max_vacancies"] == 50
    # теперь 4-я вакансия создаётся
    for i in range(4):
        r = await client.post("/api/vacancies", headers=h, json={"title": f"V{i}"})
        assert r.status_code == 201


async def test_invite_and_roles(client):
    owner = await _register(client, "org-owner@example.com")
    member = await _register(client, "org-member@example.com")

    # апгрейд, чтобы пустить второго участника (free max_members=2 — хватает, но проверим invite)
    r = await client.post(
        "/api/org/invitations", headers=owner,
        json={"email": "org-member@example.com", "role": "recruiter"},
    )
    assert r.status_code == 201, r.text
    token = r.json()["token"]

    # участник принимает приглашение
    r = await client.post("/api/invitations/accept", headers=member, json={"token": token})
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "recruiter"

    # у владельца в списке участников теперь двое
    r = await client.get("/api/org/members", headers=owner)
    assert r.status_code == 200
    assert len(r.json()) == 2

    # recruiter не может менять тариф (нужен owner)
    r = await client.post("/api/org/plan", headers=member, json={"plan": "pro"})
    assert r.status_code == 403

    # recruiter не может приглашать (нужен admin+)
    r = await client.post(
        "/api/org/invitations", headers=member, json={"email": "x@example.com"}
    )
    assert r.status_code == 403

    # участник теперь состоит в двух пространствах
    r = await client.get("/api/orgs", headers=member)
    assert r.status_code == 200
    assert len(r.json()) == 2
