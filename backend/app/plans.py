"""Тарифы и их лимиты. None = без ограничений."""

from .models import PlanTier

PLAN_LIMITS: dict[PlanTier, dict] = {
    PlanTier.free: {
        "label": "Free",
        "price": 0,
        "max_vacancies": 3,
        "monthly_analyses": 30,
        "max_members": 2,
    },
    PlanTier.pro: {
        "label": "Pro",
        "price": 49,
        "max_vacancies": 50,
        "monthly_analyses": 1000,
        "max_members": 10,
    },
    PlanTier.enterprise: {
        "label": "Enterprise",
        "price": None,  # индивидуально
        "max_vacancies": None,
        "monthly_analyses": None,
        "max_members": None,
    },
}

PERIOD_DAYS = 30


def limits_for(plan: PlanTier) -> dict:
    return PLAN_LIMITS[plan]
