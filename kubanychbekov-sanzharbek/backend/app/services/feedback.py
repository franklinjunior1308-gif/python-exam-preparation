"""Customer feedback (COMM-07) and the administrator's audit feed (ORG-05)."""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import OrgContext
from app.core.errors import AppError
from app.domain.enums import RequestStatus, Role
from app.models import AuditEvent, RequestFeedback, User
from app.schemas.feedback import AuditEventOut, AuditPage, FeedbackIn
from app.services.audit import record_audit
from app.services.requests import get_request

_RATEABLE = {RequestStatus.COMPLETED, RequestStatus.CLOSED}


def get_feedback(db: Session, ctx: OrgContext, request_id: int) -> RequestFeedback | None:
    request = get_request(db, ctx, request_id)  # 404 when the caller cannot see the request
    return db.scalar(
        select(RequestFeedback).where(
            RequestFeedback.request_id == request.id,
            RequestFeedback.organization_id == ctx.org_id,
        )
    )


def leave_feedback(
    db: Session, ctx: OrgContext, request_id: int, data: FeedbackIn
) -> RequestFeedback:
    request = get_request(db, ctx, request_id)
    if ctx.role != Role.CUSTOMER or request.created_by_user_id != ctx.user.id:
        raise AppError(403, "forbidden", "Only the customer who created the request can rate it")
    if request.status not in _RATEABLE:
        raise AppError(409, "request_not_finished", "Work can be rated only after it is completed")
    comment = data.comment.strip() if data.comment else None
    row = RequestFeedback(
        organization_id=ctx.org_id,
        request_id=request.id,
        author_user_id=ctx.user.id,
        rating=data.rating,
        comment=comment or None,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError as err:  # unique (request): a second rating, also from a double click
        db.rollback()
        raise AppError(409, "feedback_exists", "This request has already been rated") from err
    record_audit(
        db,
        action="request.feedback_left",
        object_type="service_request",
        object_id=request.id,
        organization_id=ctx.org_id,
        actor_user_id=ctx.user.id,
        after={"rating": row.rating},
    )
    db.commit()
    return row


def list_audit(
    db: Session,
    ctx: OrgContext,
    *,
    limit: int,
    offset: int,
    action: str | None,
    object_type: str | None,
) -> AuditPage:
    if ctx.role != Role.ADMIN:
        raise AppError(403, "forbidden", "Only administrators can read the audit feed")
    conditions = [AuditEvent.organization_id == ctx.org_id]
    if action:
        conditions.append(AuditEvent.action.startswith(action))
    if object_type:
        conditions.append(AuditEvent.object_type == object_type)
    total = db.scalar(select(func.count()).select_from(AuditEvent).where(*conditions)) or 0
    rows = db.execute(
        select(AuditEvent, User.full_name)
        .join(User, User.id == AuditEvent.actor_user_id, isouter=True)
        .where(*conditions)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    items = [
        AuditEventOut(
            id=e.id,
            created_at=e.created_at,
            actor_user_id=e.actor_user_id,
            actor_name=name,
            action=e.action,
            object_type=e.object_type,
            object_id=e.object_id,
            before=e.before,
            after=e.after,
        )
        for e, name in rows
    ]
    return AuditPage(items=items, total=total, limit=limit, offset=offset)
