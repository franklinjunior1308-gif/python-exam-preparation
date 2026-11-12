from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import OrgContext
from app.core.errors import AppError
from app.domain.enums import Role
from app.models import Notification, OrganizationMembership


def notify(
    db: Session,
    *,
    org_id: int,
    user_id: int,
    type: str,
    title: str,
    body: str = "",
    request_id: int | None = None,
) -> None:
    """Add a notification to the current transaction (kept or dropped together with the change)."""
    db.add(
        Notification(
            organization_id=org_id,
            recipient_user_id=user_id,
            type=type,
            request_id=request_id,
            title=title[:200],
            body=body[:500],
        )
    )


def notify_staff(
    db: Session,
    *,
    org_id: int,
    type: str,
    title: str,
    body: str = "",
    request_id: int | None = None,
    skip_user_id: int | None = None,
) -> None:
    """Tell every active dispatcher and administrator of the organization."""
    ids = db.scalars(
        select(OrganizationMembership.user_id).where(
            OrganizationMembership.organization_id == org_id,
            OrganizationMembership.role.in_([Role.DISPATCHER, Role.ADMIN]),
            OrganizationMembership.is_active.is_(True),
        )
    )
    for user_id in set(ids):
        if user_id != skip_user_id:
            notify(
                db,
                org_id=org_id,
                user_id=user_id,
                type=type,
                title=title,
                body=body,
                request_id=request_id,
            )


def list_mine(db: Session, ctx: OrgContext, unread_only: bool, limit: int) -> list[Notification]:
    """Only the caller's own notifications in the current organization (COMM-04)."""
    query = select(Notification).where(
        Notification.organization_id == ctx.org_id,
        Notification.recipient_user_id == ctx.user.id,
    )
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    return list(db.scalars(query.order_by(Notification.id.desc()).limit(limit)))


def mark_read(db: Session, ctx: OrgContext, notification_id: int) -> Notification:
    found = db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.organization_id == ctx.org_id,
            Notification.recipient_user_id == ctx.user.id,
        )
    )
    if found is None:
        raise AppError(404, "notification_not_found", "Notification not found")
    if found.read_at is None:
        found.read_at = datetime.now(UTC)
        db.commit()
    return found


def mark_all_read(db: Session, ctx: OrgContext) -> int:
    result = db.execute(
        update(Notification)
        .where(
            Notification.organization_id == ctx.org_id,
            Notification.recipient_user_id == ctx.user.id,
            Notification.read_at.is_(None),
        )
        .values(read_at=datetime.now(UTC))
        .returning(Notification.id)
    )
    updated = len(result.all())
    db.commit()
    return updated
