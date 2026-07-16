from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .models import ROLE_ORDER, Membership, Organization, Role, User
from .security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Не авторизован")
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Недействительный токен")
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Пользователь не найден")
    return user


async def get_current_membership(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Membership:
    if user.active_org_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Не выбрано рабочее пространство")
    membership = await db.scalar(
        select(Membership).where(
            Membership.org_id == user.active_org_id,
            Membership.user_id == user.id,
        )
    )
    if membership is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Нет доступа к рабочему пространству")
    return membership


async def get_current_org(
    membership: Membership = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
) -> Organization:
    return await db.get(Organization, membership.org_id)


def require_role(min_role: Role):
    """Зависимость: требует роль не ниже min_role в активном пространстве."""

    async def _dep(membership: Membership = Depends(get_current_membership)) -> Membership:
        if ROLE_ORDER[membership.role] < ROLE_ORDER[min_role]:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Недостаточно прав (требуется роль {min_role.value} или выше)",
            )
        return membership

    return _dep
