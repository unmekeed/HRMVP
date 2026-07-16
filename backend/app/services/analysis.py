"""AI-анализ резюме относительно вакансии.

Режимы (AIS_ANALYSIS_MODE):
- claude — анализ через Anthropic API (structured outputs, валидный JSON гарантирован);
- mock   — эвристика по ключевым словам, без внешних вызовов (dev/тесты);
- auto   — claude при наличии AIS_ANTHROPIC_API_KEY, иначе mock.
"""

import json
import re

from ..config import get_settings

ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "full_name": {"type": "string", "description": "ФИО кандидата из резюме"},
        "email": {"type": "string"},
        "phone": {"type": "string"},
        "score": {
            "type": "integer",
            "description": "Соответствие вакансии от 0 до 100",
        },
        "verdict": {
            "type": "string",
            "enum": ["strong_match", "good_match", "partial_match", "weak_match"],
        },
        "summary": {
            "type": "string",
            "description": "Краткое резюме кандидата и вывод о соответствии, 2-3 предложения",
        },
        "strengths": {"type": "array", "items": {"type": "string"}},
        "weaknesses": {"type": "array", "items": {"type": "string"}},
        "matched_requirements": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Требования вакансии, которым кандидат соответствует",
        },
        "missing_requirements": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Требования вакансии, подтверждения которых нет в резюме",
        },
        "recommendation": {
            "type": "string",
            "description": "Рекомендация для HR: приглашать ли на интервью и на что обратить внимание",
        },
    },
    "required": [
        "full_name", "email", "phone", "score", "verdict", "summary",
        "strengths", "weaknesses", "matched_requirements",
        "missing_requirements", "recommendation",
    ],
    "additionalProperties": False,
}

SYSTEM_PROMPT = (
    "Ты — опытный рекрутер-аналитик. Тебе дают описание вакансии и текст резюме "
    "кандидата. Оцени соответствие кандидата вакансии строго по фактам из резюме: "
    "не додумывай опыт, которого нет. Шкала score: 85-100 — strong_match, "
    "70-84 — good_match, 50-69 — partial_match, 0-49 — weak_match. "
    "Отвечай на русском языке."
)

MAX_RESUME_CHARS = 60_000


class AnalysisResult(dict):
    """Результат анализа — dict с ключами схемы ANALYSIS_SCHEMA."""


async def analyze_resume(
    vacancy_title: str,
    vacancy_description: str,
    vacancy_requirements: str,
    resume_text: str,
) -> AnalysisResult:
    settings = get_settings()
    mode = settings.analysis_mode
    if mode == "auto":
        mode = "claude" if settings.anthropic_api_key else "mock"
    if mode == "claude":
        return await _analyze_claude(
            vacancy_title, vacancy_description, vacancy_requirements, resume_text
        )
    return _analyze_mock(
        vacancy_title, vacancy_description, vacancy_requirements, resume_text
    )


async def _analyze_claude(
    title: str, description: str, requirements: str, resume_text: str
) -> AnalysisResult:
    from anthropic import AsyncAnthropic

    settings = get_settings()
    client = AsyncAnthropic(api_key=settings.anthropic_api_key or None)

    user_message = (
        f"<vacancy>\n<title>{title}</title>\n"
        f"<description>\n{description}\n</description>\n"
        f"<requirements>\n{requirements}\n</requirements>\n</vacancy>\n\n"
        f"<resume>\n{resume_text[:MAX_RESUME_CHARS]}\n</resume>\n\n"
        "Проанализируй соответствие кандидата вакансии."
    )

    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        output_config={"format": {"type": "json_schema", "schema": ANALYSIS_SCHEMA}},
        messages=[{"role": "user", "content": user_message}],
    )

    if response.stop_reason == "refusal":
        raise RuntimeError("Модель отказалась анализировать этот документ")

    text = next(b.text for b in response.content if b.type == "text")
    data = json.loads(text)
    data["score"] = max(0, min(100, int(data["score"])))
    return AnalysisResult(data)


# --- mock-режим: простая эвристика, чтобы продукт работал без API-ключа ---

_STOPWORDS = {
    "и", "в", "на", "с", "по", "для", "от", "до", "из", "или", "не", "что",
    "the", "and", "for", "with", "of", "to", "in", "a", "an", "or",
}


def _keywords(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9+#.]{3,}", text.lower())
    return {w for w in words if w not in _STOPWORDS}


def _analyze_mock(
    title: str, description: str, requirements: str, resume_text: str
) -> AnalysisResult:
    req_lines = [
        line.strip(" -•*\t")
        for line in (requirements or description).splitlines()
        if line.strip(" -•*\t")
    ]
    resume_kw = _keywords(resume_text)

    matched, missing = [], []
    for line in req_lines[:30]:
        line_kw = _keywords(line)
        if not line_kw:
            continue
        overlap = len(line_kw & resume_kw) / len(line_kw)
        (matched if overlap >= 0.4 else missing).append(line)

    total = len(matched) + len(missing)
    score = round(100 * len(matched) / total) if total else 50
    verdict = (
        "strong_match" if score >= 85
        else "good_match" if score >= 70
        else "partial_match" if score >= 50
        else "weak_match"
    )

    email_m = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", resume_text)
    phone_m = re.search(r"(?:\+?\d[\d\s()-]{8,}\d)", resume_text)
    first_line = next(
        (line.strip() for line in resume_text.splitlines() if line.strip()), ""
    )

    return AnalysisResult(
        full_name=first_line[:80],
        email=email_m.group(0) if email_m else "",
        phone=phone_m.group(0).strip() if phone_m else "",
        score=score,
        verdict=verdict,
        summary=(
            f"[Mock-анализ] Совпадение с требованиями вакансии «{title}»: "
            f"{len(matched)} из {total or '—'} пунктов."
        ),
        strengths=matched[:5],
        weaknesses=missing[:5],
        matched_requirements=matched,
        missing_requirements=missing,
        recommendation=(
            "Это результат эвристического mock-режима. Задайте AIS_ANTHROPIC_API_KEY, "
            "чтобы получить полноценный AI-анализ."
        ),
    )
