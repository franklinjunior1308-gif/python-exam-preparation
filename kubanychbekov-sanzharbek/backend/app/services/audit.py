from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditEvent


def record_audit(
    db: Session,
    *,
    action: str,
    object_type: str,
    object_id: int | str,
    organization_id: int | None = None,
    actor_user_id: int | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    """Add an audit row to the current transaction (committed or rolled back with the change)."""
    db.add(
        AuditEvent(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action=action,
            object_type=object_type,
            object_id=str(object_id),
            before=before,
            after=after,
        )
    )
