from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import get_current_membership, get_current_org, get_current_user, require_role
from ..models import (
    Invitation,
    Membership,
    Organization,
    Role,
    User,
    Vacancy,
)
from ..plans import PLAN_LIMITS, limits_for
from ..schemas import (
    AcceptInvite,
    InvitationOut,
    InviteCreate,
    MemberOut,
    OrgOut,
    OrgSummary,
    PlanChange,
    PlanInfo,
    RoleChange,
    SwitchOrg,
)
from ..services.limits import enforce_member_limit

router = APIRouter(prefix="/api/org", tags=["organizations"])


async def _org_out(org: Organization, role: Role, db: AsyncSession) -> OrgOut:
    vacancies = await db.scalar(
        select(func.count(Vacancy.id)).where(Vacancy.org_id == org.id)
    )
    members = await db.scalar(
        select(func.count(Membership.id)).where(Membership.org_id == org.id)
    )
    return OrgOut(
        id=org.id,
        name=org.name,
        plan=org.plan,
        role=role,
        limits=limits_for(org.plan),
        usage={
            "analyses_used": org.analyses_used,
            "vacancies": vacancies or 0,
            "members": members or 0,
        },
    )


@router.get("", response_model=OrgOut)
async def get_org(
    membership: Membership = Depends(get_current_membership),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    return await _org_out(org, membership.role, db)


@router.get("s", response_model=list[OrgSummary])
async def list_my_orgs(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.execute(
        select(Organization, Membership.role)
        .join(Membership, Membership.org_id == Organization.id)
        .where(Membership.user_id == user.id)
        .order_by(Organization.created_at)
    )
    return [
        OrgSummary(id=o.id, name=o.name, role=role) for o, role in rows.all()
    ]


@router.post("/switch", response_model=OrgOut)
async def switch_org(
    payload: SwitchOrg,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await db.scalar(
        select(Membership).where(
            Membership.org_id == payload.org_id, Membership.user_id == user.id
        )
    )
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пространство не найдено")
    user.active_org_id = payload.org_id
    await db.commit()
    org = await db.get(Organization, payload.org_id)
    return await _org_out(org, membership.role, db)


# --- тарифы / биллинг ---

@router.get("/plans", response_model=list[PlanInfo])
async def list_plans(org: Organization = Depends(get_current_org)):
    return [
        PlanInfo(
            plan=tier,
            label=cfg["label"],
            price=cfg["price"],
            max_vacancies=cfg["max_vacancies"],
            monthly_analyses=cfg["monthly_analyses"],
            max_members=cfg["max_members"],
            current=(tier == org.plan),
        )
        for tier, cfg in PLAN_LIMITS.items()
    ]


@router.post("/plan", response_model=OrgOut)
async def change_plan(
    payload: PlanChange,
    membership: Membership = Depends(require_role(Role.owner)),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    # MVP: смена тарифа без реального платёжного провайдера. В проде здесь
    # создаётся Stripe Checkout Session, а тариф меняется по webhook оплаты.
    org.plan = payload.plan
    await db.commit()
    return await _org_out(org, membership.role, db)


# --- участники ---

@router.get("/members", response_model=list[MemberOut])
async def list_members(
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.org_id == org.id)
        .order_by(Membership.created_at)
    )
    return [
        MemberOut(id=m.id, user_id=u.id, email=u.email, name=u.name, role=m.role)
        for m, u in rows.all()
    ]


@router.patch("/members/{membership_id}", response_model=MemberOut)
async def change_member_role(
    membership_id: str,
    payload: RoleChange,
    actor: Membership = Depends(require_role(Role.admin)),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    target = await db.get(Membership, membership_id)
    if target is None or target.org_id != org.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Участник не найден")
    if target.role == Role.owner:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Нельзя изменить роль владельца")
    if payload.role == Role.owner:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Назначить владельца через этот метод нельзя"
        )
    target.role = payload.role
    await db.commit()
    user = await db.get(User, target.user_id)
    return MemberOut(
        id=target.id, user_id=user.id, email=user.email, name=user.name, role=target.role
    )


@router.delete("/members/{membership_id}", status_code=204)
async def remove_member(
    membership_id: str,
    actor: Membership = Depends(require_role(Role.admin)),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    target = await db.get(Membership, membership_id)
    if target is None or target.org_id != org.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Участник не найден")
    if target.role == Role.owner:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Нельзя удалить владельца")
    await db.delete(target)
    await db.commit()


# --- приглашения ---

@router.post("/invitations", response_model=InvitationOut, status_code=201)
async def create_invitation(
    payload: InviteCreate,
    actor: Membership = Depends(require_role(Role.admin)),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    if payload.role == Role.owner:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Нельзя пригласить владельца")
    await enforce_member_limit(org, db)
    invitation = Invitation(org_id=org.id, email=payload.email, role=payload.role)
    db.add(invitation)
    await db.commit()
    # В проде здесь отправляется письмо со ссылкой на приглашение.
    return InvitationOut.model_validate(invitation)


@router.get("/invitations", response_model=list[InvitationOut])
async def list_invitations(
    actor: Membership = Depends(require_role(Role.admin)),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.scalars(
        select(Invitation)
        .where(Invitation.org_id == org.id, Invitation.accepted.is_(False))
        .order_by(Invitation.created_at.desc())
    )
    return [InvitationOut.model_validate(i) for i in rows.all()]


invite_router = APIRouter(prefix="/api/invitations", tags=["organizations"])


@invite_router.post("/accept", response_model=OrgOut)
async def accept_invitation(
    payload: AcceptInvite,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    invitation = await db.scalar(
        select(Invitation).where(
            Invitation.token == payload.token, Invitation.accepted.is_(False)
        )
    )
    if invitation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Приглашение не найдено или уже принято")

    existing = await db.scalar(
        select(Membership).where(
            Membership.org_id == invitation.org_id, Membership.user_id == user.id
        )
    )
    if existing is None:
        org = await db.get(Organization, invitation.org_id)
        await enforce_member_limit(org, db)
        membership = Membership(
            org_id=invitation.org_id, user_id=user.id, role=invitation.role
        )
        db.add(membership)
        role = invitation.role
    else:
        role = existing.role

    invitation.accepted = True
    user.active_org_id = invitation.org_id
    await db.commit()
    org = await db.get(Organization, invitation.org_id)
    return await _org_out(org, role, db)
