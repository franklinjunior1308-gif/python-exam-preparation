import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Response
from sqlalchemy import select

from app.api.deps import AuthDep, DbDep
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import create_access_token, verify_password
from app.models import AuditEvent, Organization, OrganizationMembership, User, UserSession
from app.schemas.auth import LoginIn, MembershipOut, MeOut, TokenOut
from app.services.audit import record_audit

router = APIRouter(tags=["auth"])


def _refuse_when_locked(db: DbDep, email: str) -> None:
    """SEC-03: too many failed attempts for one e-mail pause sign-in, even with the right password.

    Failures are the `auth.login_failed` audit rows, so the count is shared by all workers.
    """
    settings = get_settings()
    window = timedelta(minutes=settings.login_window_minutes)
    since = datetime.now(UTC) - window
    failures = db.scalars(
        select(AuditEvent.created_at)
        .where(
            AuditEvent.action == "auth.login_failed",
            AuditEvent.after["email"].astext == email,
            AuditEvent.created_at >= since,
        )
        .order_by(AuditEvent.created_at)
    ).all()
    if len(failures) >= settings.login_max_failures:
        retry = max(1, int((failures[0] + window - datetime.now(UTC)).total_seconds()))
        raise AppError(
            429,
            "too_many_attempts",
            f"Too many failed sign-in attempts. Try again in {max(1, retry // 60 + 1)} minutes.",
        )


@router.post("/auth/login", response_model=TokenOut)
def login(data: LoginIn, db: DbDep) -> TokenOut:
    email = data.email.strip().lower()
    _refuse_when_locked(db, email)
    user = db.scalar(select(User).where(User.email == email))

    if user is None or not verify_password(user.password_hash, data.password):
        # failed logins are audited; the password itself is never logged (AUTH-05)
        record_audit(
            db,
            action="auth.login_failed",
            object_type="user",
            object_id=user.id if user else "unknown",
            actor_user_id=user.id if user else None,
            after={"email": email},
        )
        db.commit()
        raise AppError(401, "invalid_credentials", "Invalid email or password")
    if not user.is_active:
        record_audit(
            db,
            action="auth.login_blocked_disabled",
            object_type="user",
            object_id=user.id,
            actor_user_id=user.id,
        )
        db.commit()
        raise AppError(403, "account_disabled", "Account is disabled")

    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=get_settings().access_token_minutes)
    session = UserSession(
        id=str(uuid.uuid4()), user_id=user.id, created_at=now, expires_at=expires_at
    )
    db.add(session)
    db.commit()
    return TokenOut(access_token=create_access_token(session.id, expires_at), expires_at=expires_at)


@router.post("/auth/logout", status_code=204)
def logout(auth: AuthDep, db: DbDep) -> Response:
    auth.session.revoked_at = datetime.now(UTC)
    # AUTH-05: a revoked session is audited (by user, never with the token or the session id)
    record_audit(
        db,
        action="auth.session_revoked",
        object_type="user",
        object_id=auth.user.id,
        actor_user_id=auth.user.id,
        after={"reason": "logout"},
    )
    db.commit()
    return Response(status_code=204)


@router.get("/me", response_model=MeOut)
def me(auth: AuthDep, db: DbDep) -> MeOut:
    rows = db.execute(
        select(Organization, OrganizationMembership)
        .join(OrganizationMembership, OrganizationMembership.organization_id == Organization.id)
        .where(
            OrganizationMembership.user_id == auth.user.id,
            OrganizationMembership.is_active.is_(True),
            Organization.is_active.is_(True),
        )
        .order_by(Organization.id)
    ).all()
    return MeOut(
        id=auth.user.id,
        email=auth.user.email,
        full_name=auth.user.full_name,
        memberships=[
            MembershipOut(
                organization_id=org.id,
                organization_name=org.name,
                timezone=org.timezone,
                role=membership.role,
            )
            for org, membership in rows
        ],
    )
