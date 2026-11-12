from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DbDep, OrgDep
from app.schemas.feedback import AuditPage, FeedbackIn, FeedbackOut
from app.services import feedback as service

router = APIRouter(tags=["feedback"])


@router.get("/requests/{request_id}/feedback", response_model=FeedbackOut | None)
def get_feedback(request_id: int, ctx: OrgDep, db: DbDep) -> FeedbackOut | None:
    """The rating of a request, or `null` when it has not been rated yet."""
    row = service.get_feedback(db, ctx, request_id)
    return FeedbackOut.model_validate(row) if row else None


@router.post("/requests/{request_id}/feedback", response_model=FeedbackOut, status_code=201)
def leave_feedback(request_id: int, data: FeedbackIn, ctx: OrgDep, db: DbDep) -> FeedbackOut:
    return FeedbackOut.model_validate(service.leave_feedback(db, ctx, request_id, data))


@router.get("/audit", response_model=AuditPage)
def audit_feed(
    ctx: OrgDep,
    db: DbDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    action: Annotated[str | None, Query(max_length=100)] = None,
    object_type: Annotated[str | None, Query(max_length=60)] = None,
) -> AuditPage:
    """Newest first. `action` is a prefix filter (e.g. `inventory.`). Administrators only."""
    return service.list_audit(
        db, ctx, limit=limit, offset=offset, action=action, object_type=object_type
    )
