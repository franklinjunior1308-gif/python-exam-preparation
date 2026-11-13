from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import DbDep, OrgDep
from app.domain.enums import Priority, RequestStatus
from app.models import RequestStatusHistory
from app.schemas.request import (
    HistoryOut,
    RequestCreate,
    RequestOut,
    RequestPage,
    TransitionIn,
    TriageIn,
)
from app.services import requests as service
from app.services import sla as sla_service

router = APIRouter(prefix="/requests", tags=["requests"])


@router.post("", response_model=RequestOut, status_code=201)
def create(data: RequestCreate, ctx: OrgDep, db: DbDep) -> RequestOut:
    out = service.to_out(service.create_request(db, ctx, data), ctx)
    sla_service.attach(db, ctx, [out])
    return out


@router.get("", response_model=RequestPage)
def list_(
    ctx: OrgDep,
    db: DbDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=service.MAX_PAGE_SIZE)] = 20,
    status: RequestStatus | None = None,
    priority: Priority | None = None,
    category_id: int | None = None,
    property_id: int | None = None,
    sla: Literal["ON_TRACK", "AT_RISK", "OVERDUE"] | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    technician_id: int | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    sort_by: Annotated[str, Query(pattern="^(created_at|priority|id|due_at)$")] = "created_at",
    descending: bool = True,
) -> RequestPage:
    def fetch(page_no: int, size: int, unpaged: bool = False):
        return service.list_requests(
            db,
            ctx,
            page=page_no,
            page_size=size,
            status=status,
            priority=priority,
            category_id=category_id,
            property_id=property_id,
            technician_id=technician_id,
            created_from=created_from,
            created_to=created_to,
            q=q,
            sort_by=sort_by,
            descending=descending,
            unpaged=unpaged,
        )

    if sla is None and sort_by != "due_at":
        rows, total = fetch(page, page_size)
    else:
        # the SLA state and deadline are computed in working time, not stored: filter and sort
        # over every match first, then page
        every, _ = fetch(1, 1, unpaged=True)
        matching = every
        if sla is not None:
            wanted = sla_service.filter_ids_by_state(db, ctx, sla, [r.id for r in every])
            matching = [r for r in every if r.id in wanted]
        if sort_by == "due_at":
            matching = sla_service.sort_by_due(db, ctx, matching, descending)
        total = len(matching)
        first = (page - 1) * page_size
        rows = matching[first : first + page_size]
    assigned = service.assigned_set(db, ctx, [r.id for r in rows])
    items = [service.to_out(r, ctx, assigned) for r in rows]
    sla_service.attach(db, ctx, items)
    return RequestPage(items=items, total=total, page=page, page_size=page_size)


@router.get("/{request_id}", response_model=RequestOut)
def detail(request_id: int, ctx: OrgDep, db: DbDep) -> RequestOut:
    req = service.get_request(db, ctx, request_id)
    out = service.to_out(req, ctx, service.assigned_set(db, ctx, [req.id]))
    sla_service.attach(db, ctx, [out])
    return out


@router.get("/{request_id}/history", response_model=list[HistoryOut])
def history(request_id: int, ctx: OrgDep, db: DbDep) -> list[RequestStatusHistory]:
    req = service.get_request(db, ctx, request_id)  # also enforces visibility
    rows = db.scalars(
        select(RequestStatusHistory)
        .where(
            RequestStatusHistory.request_id == req.id,
            RequestStatusHistory.organization_id == ctx.org_id,
        )
        .order_by(RequestStatusHistory.id)
    )
    return list(rows)


@router.post("/{request_id}/transitions", response_model=RequestOut)
def transition(request_id: int, data: TransitionIn, ctx: OrgDep, db: DbDep) -> RequestOut:
    req = service.transition_request(db, ctx, request_id, data.to_status, data.reason)
    out = service.to_out(req, ctx, service.assigned_set(db, ctx, [req.id]))
    sla_service.attach(db, ctx, [out])
    return out


@router.patch("/{request_id}", response_model=RequestOut)
def triage(request_id: int, data: TriageIn, ctx: OrgDep, db: DbDep) -> RequestOut:
    req = service.update_triage(db, ctx, request_id, data)
    out = service.to_out(req, ctx, service.assigned_set(db, ctx, [req.id]))
    sla_service.attach(db, ctx, [out])
    return out
