"""Staff and roles (ORG-04, AUTH-05): administrators manage the members of their organization."""

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import OrgContext
from app.core.errors import AppError
from app.core.security import hash_password
from app.domain.enums import ACTIVE_ASSIGNMENT_STATUSES, Role
from app.models import (
    Assignment,
    OrganizationMembership,
    TechnicianProfile,
    User,
    UserSession,
)
from app.schemas.users import UserCreate, UserOut, UserUpdate
from app.services.audit import record_audit


def _require_admin(ctx: OrgContext) -> None:
    if ctx.role != Role.ADMIN:
        raise AppError(403, "forbidden", "Only administrators manage staff")


def _technician_ids(db: Session, org_id: int) -> dict[int, int]:
    rows = db.execute(
        select(TechnicianProfile.user_id, TechnicianProfile.id).where(
            TechnicianProfile.organization_id == org_id
        )
    )
    return {user_id: profile_id for user_id, profile_id in rows}


def _out(user: User, membership: OrganizationMembership, techs: dict[int, int]) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=membership.role,
        is_active=membership.is_active,
        technician_id=techs.get(user.id) if membership.role == Role.TECHNICIAN else None,
    )


def list_users(db: Session, ctx: OrgContext) -> list[UserOut]:
    _require_admin(ctx)
    techs = _technician_ids(db, ctx.org_id)
    rows = db.execute(
        select(User, OrganizationMembership)
        .join(OrganizationMembership, OrganizationMembership.user_id == User.id)
        .where(OrganizationMembership.organization_id == ctx.org_id)
        .order_by(User.full_name, User.id)
    ).all()
    return [_out(user, membership, techs) for user, membership in rows]


def _ensure_technician_profile(db: Session, org_id: int, user_id: int) -> None:
    existing = db.scalar(
        select(TechnicianProfile.id).where(
            TechnicianProfile.organization_id == org_id, TechnicianProfile.user_id == user_id
        )
    )
    if existing is None:
        db.add(TechnicianProfile(organization_id=org_id, user_id=user_id))
        db.flush()
    else:  # a returning technician becomes schedulable again
        db.execute(
            update(TechnicianProfile).where(TechnicianProfile.id == existing).values(is_active=True)
        )


def create_user(db: Session, ctx: OrgContext, data: UserCreate) -> UserOut:
    _require_admin(ctx)
    user = db.scalar(select(User).where(User.email == data.email))
    created_account = user is None
    if user is None:
        user = User(
            email=data.email, full_name=data.full_name, password_hash=hash_password(data.password)
        )
        db.add(user)
        try:
            db.flush()
        except IntegrityError as err:  # a parallel request created the same e-mail
            db.rollback()
            raise AppError(409, "user_exists", "A user with this e-mail already exists") from err
    already = db.scalar(
        select(OrganizationMembership.id).where(
            OrganizationMembership.organization_id == ctx.org_id,
            OrganizationMembership.user_id == user.id,
        )
    )
    if already is not None:
        db.rollback()
        raise AppError(409, "already_member", "This person is already a member of the organization")
    membership = OrganizationMembership(organization_id=ctx.org_id, user_id=user.id, role=data.role)
    db.add(membership)
    if data.role == Role.TECHNICIAN:
        _ensure_technician_profile(db, ctx.org_id, user.id)
    db.flush()
    record_audit(
        db,
        action="user.created",
        object_type="user",
        object_id=user.id,
        organization_id=ctx.org_id,
        actor_user_id=ctx.user.id,
        after={"email": user.email, "role": data.role.value, "new_account": created_account},
    )
    db.commit()
    return _out(user, membership, _technician_ids(db, ctx.org_id))


def _load_member(db: Session, ctx: OrgContext, user_id: int) -> tuple[User, OrganizationMembership]:
    row = db.execute(
        select(User, OrganizationMembership)
        .join(OrganizationMembership, OrganizationMembership.user_id == User.id)
        .where(
            OrganizationMembership.organization_id == ctx.org_id,
            OrganizationMembership.user_id == user_id,
        )
        .with_for_update(of=OrganizationMembership)
    ).first()
    if row is None:
        raise AppError(404, "user_not_found", "User not found")
    return row[0], row[1]


def _active_jobs(db: Session, org_id: int, profile_id: int) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(Assignment)
            .where(
                Assignment.organization_id == org_id,
                Assignment.technician_id == profile_id,
                Assignment.status.in_(ACTIVE_ASSIGNMENT_STATUSES),
            )
        )
        or 0
    )


def update_user(db: Session, ctx: OrgContext, user_id: int, data: UserUpdate) -> UserOut:
    _require_admin(ctx)
    user, membership = _load_member(db, ctx, user_id)
    new_role = data.role if data.role is not None else membership.role
    new_active = data.is_active if data.is_active is not None else membership.is_active
    before = {"role": membership.role.value, "is_active": membership.is_active}
    if new_role == membership.role and new_active == membership.is_active:
        return _out(user, membership, _technician_ids(db, ctx.org_id))

    was_admin = membership.role == Role.ADMIN and membership.is_active
    if was_admin and not (new_role == Role.ADMIN and new_active):
        # lock every active admin row so two simultaneous demotions cannot both succeed
        admins = db.scalars(
            select(OrganizationMembership.id)
            .where(
                OrganizationMembership.organization_id == ctx.org_id,
                OrganizationMembership.role == Role.ADMIN,
                OrganizationMembership.is_active.is_(True),
            )
            .with_for_update()
        ).all()
        if len(admins) <= 1:
            raise AppError(
                409, "last_admin", "The organization must keep at least one administrator"
            )

    if membership.role == Role.TECHNICIAN and (new_role != Role.TECHNICIAN or not new_active):
        profile_id = db.scalar(
            select(TechnicianProfile.id).where(
                TechnicianProfile.organization_id == ctx.org_id,
                TechnicianProfile.user_id == user.id,
            )
        )
        if profile_id is not None:
            if _active_jobs(db, ctx.org_id, profile_id):
                raise AppError(
                    409,
                    "technician_has_active_assignments",
                    "Reassign or cancel this technician's active jobs first",
                )
            db.execute(
                update(TechnicianProfile)
                .where(TechnicianProfile.id == profile_id)
                .values(is_active=False)
            )

    membership.role = new_role
    membership.is_active = new_active
    if new_role == Role.TECHNICIAN and new_active:
        _ensure_technician_profile(db, ctx.org_id, user.id)
    if before["is_active"] and not new_active:
        # a deactivated member loses access at once: every open session is revoked (AUTH-05)
        revoked = db.execute(
            update(UserSession)
            .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
            .values(revoked_at=func.now())
            .returning(UserSession.id)
        )
        record_audit(
            db,
            action="auth.sessions_revoked",
            object_type="user",
            object_id=user.id,
            organization_id=ctx.org_id,
            actor_user_id=ctx.user.id,
            after={"count": len(revoked.all()), "reason": "member deactivated"},
        )
    db.flush()

    role_changed = before["role"] != new_role.value
    active_changed = before["is_active"] != new_active
    if role_changed:
        record_audit(
            db,
            action="user.role_changed",
            object_type="user",
            object_id=user.id,
            organization_id=ctx.org_id,
            actor_user_id=ctx.user.id,
            before={"role": before["role"]},
            after={"role": new_role.value},
        )
    if active_changed:
        record_audit(
            db,
            action="user.activated" if new_active else "user.deactivated",
            object_type="user",
            object_id=user.id,
            organization_id=ctx.org_id,
            actor_user_id=ctx.user.id,
            before={"is_active": before["is_active"]},
            after={"is_active": new_active},
        )
    db.commit()
    return _out(user, membership, _technician_ids(db, ctx.org_id))
