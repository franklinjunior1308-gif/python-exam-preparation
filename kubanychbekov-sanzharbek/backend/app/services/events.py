"""Live updates over Server-Sent Events (API-06).

The stream carries only *hints*: a scope and a request id, never data. The client refetches the
canonical state through the normal, permission-checked endpoints, so nothing can leak through here.
Changes are found by polling the audit, assignment and notification tables by increasing id.
"""

import asyncio
import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import UTC, datetime

from anyio import to_thread
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_sessionmaker
from app.domain.enums import AssignmentStatus, Role
from app.models import (
    Assignment,
    AuditEvent,
    Notification,
    ServiceRequest,
    TechnicianProfile,
    UserSession,
)

MAX_EVENTS_PER_POLL = 50

Hint = dict[str, str | int | None]


@dataclass(frozen=True)
class Viewer:
    """Plain values copied out of the request-scoped objects (the stream outlives that session)."""

    user_id: int
    org_id: int
    role: Role
    session_id: str


@dataclass
class _Cursor:
    audit: int
    notification: int


def _max_id(db: Session, column, *conditions) -> int:
    return db.scalar(select(func.coalesce(func.max(column), 0)).where(*conditions)) or 0


def start_cursor(db: Session, viewer: Viewer) -> _Cursor:
    return _Cursor(
        audit=_max_id(db, AuditEvent.id, AuditEvent.organization_id == viewer.org_id),
        notification=_max_id(
            db,
            Notification.id,
            Notification.organization_id == viewer.org_id,
            Notification.recipient_user_id == viewer.user_id,
        ),
    )


def _visible(db: Session, viewer: Viewer, request_ids: set[int]) -> set[int]:
    """Which of these requests the viewer may see (same rules as the request list, ROLE-03)."""
    if not request_ids:
        return set()
    query = select(ServiceRequest.id).where(
        ServiceRequest.organization_id == viewer.org_id, ServiceRequest.id.in_(request_ids)
    )
    if viewer.role == Role.CUSTOMER:
        query = query.where(ServiceRequest.created_by_user_id == viewer.user_id)
    elif viewer.role == Role.TECHNICIAN:
        mine = (
            select(Assignment.request_id)
            .join(TechnicianProfile, TechnicianProfile.id == Assignment.technician_id)
            .where(
                Assignment.organization_id == viewer.org_id,
                TechnicianProfile.user_id == viewer.user_id,
                Assignment.status.notin_([AssignmentStatus.CANCELED, AssignmentStatus.DECLINED]),
            )
        )
        query = query.where(ServiceRequest.id.in_(mine))
    return set(db.scalars(query))


def session_alive(db: Session, viewer: Viewer) -> bool:
    row = db.get(UserSession, viewer.session_id)
    return row is not None and row.revoked_at is None and row.expires_at > datetime.now(UTC)


def poll(db: Session, viewer: Viewer, cursor: _Cursor) -> list[Hint]:
    """New change hints since the cursor; advances the cursor."""
    hints: dict[tuple[str, int | None], None] = {}

    audit_rows = db.execute(
        select(AuditEvent.id, AuditEvent.action, AuditEvent.object_type, AuditEvent.object_id)
        .where(AuditEvent.organization_id == viewer.org_id, AuditEvent.id > cursor.audit)
        .order_by(AuditEvent.id)
        .limit(200)
    ).all()
    request_rows: list[tuple[str, int]] = []
    for row in audit_rows:
        cursor.audit = row.id
        if row.object_type == "service_request" and row.object_id.isdigit():
            scope = "assignments" if row.action.startswith("assignment.") else "requests"
            request_rows.append((scope, int(row.object_id)))
    allowed = _visible(db, viewer, {rid for _, rid in request_rows})
    for scope, rid in request_rows:
        if rid in allowed:
            hints[(scope, rid)] = None

    for note in db.execute(
        select(Notification.id, Notification.request_id)
        .where(
            Notification.organization_id == viewer.org_id,
            Notification.recipient_user_id == viewer.user_id,
            Notification.id > cursor.notification,
        )
        .order_by(Notification.id)
        .limit(200)
    ):
        cursor.notification = note.id
        hints[("notifications", note.request_id)] = None

    at = datetime.now(UTC).isoformat()
    return [{"scope": s, "request_id": r, "at": at} for s, r in list(hints)][:MAX_EVENTS_PER_POLL]


def _sync_step(viewer: Viewer, cursor: _Cursor | None) -> tuple[_Cursor, list[Hint], bool]:
    with get_sessionmaker()() as db:
        if not session_alive(db, viewer):
            return cursor or _Cursor(0, 0), [], False
        if cursor is None:
            return start_cursor(db, viewer), [], True
        return cursor, poll(db, viewer, cursor), True


def format_event(payload: Hint) -> str:
    return f"event: changed\ndata: {json.dumps(payload)}\n\n"


async def stream(
    viewer: Viewer, *, poll_seconds: float, keepalive_seconds: float
) -> AsyncGenerator[str]:
    """Yields SSE text. Ends when the session is revoked or expires; cancelled on disconnect."""
    cursor, _, alive = await to_thread.run_sync(_sync_step, viewer, None)
    yield "retry: 3000\n: connected\n\n"
    idle = 0.0
    while alive:
        await asyncio.sleep(poll_seconds)
        cursor, events, alive = await to_thread.run_sync(_sync_step, viewer, cursor)
        for event in events:
            yield format_event(event)
        idle = 0.0 if events else idle + poll_seconds
        if idle >= keepalive_seconds and alive:
            idle = 0.0
            yield ": keepalive\n\n"
