from typing import Annotated

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
)
from app.services import requests as service

router = APIRouter(prefix="/requests", tags=["requests"])


@router.post("", response_model=RequestOut, status_code=201)
def create(data: RequestCreate, ctx: OrgDep, db: DbDep) -> RequestOut:
    return service.to_out(service.create_request(db, ctx, data), ctx)


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
    q: Annotated[str | None, Query(max_length=200)] = None,
    sort_by: Annotated[str, Query(pattern="^(created_at|priority|id)$")] = "created_at",
    descending: bool = True,
) -> RequestPage:
    rows, total = service.list_requests(
        db,
        ctx,
        page=page,
        page_size=page_size,
        status=status,
        priority=priority,
        category_id=category_id,
        property_id=property_id,
        q=q,
        sort_by=sort_by,
        descending=descending,
    )
    assigned = service.assigned_set(db, ctx, [r.id for r in rows])
    return RequestPage(
        items=[service.to_out(r, ctx, assigned) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{request_id}", response_model=RequestOut)
def detail(request_id: int, ctx: OrgDep, db: DbDep) -> RequestOut:
    req = service.get_request(db, ctx, request_id)
    return service.to_out(req, ctx, service.assigned_set(db, ctx, [req.id]))


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
    return service.to_out(req, ctx, service.assigned_set(db, ctx, [req.id]))
