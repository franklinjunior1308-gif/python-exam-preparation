from datetime import datetime, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import DbDep, OrgDep
from app.domain.enums import RequestStatus
from app.models import RequestStatusHistory, ServiceCategory, ServiceRequest
from app.schemas.reports import CategoryCount, DailyPoint, SummaryOut
from app.services.requests import visible_conditions

router = APIRouter(prefix="/reports", tags=["reports"])

_CLOSED = {RequestStatus.CLOSED, RequestStatus.CANCELED}


@router.get("/summary", response_model=SummaryOut)
def summary(ctx: OrgDep, db: DbDep, days: Annotated[int, Query(ge=1, le=90)] = 14) -> SummaryOut:
    """Dashboard numbers computed from the database (REPORT-05), in the organization's timezone.

    Scoped like the request list: customers only see aggregates of their own requests.
    """
    conds = visible_conditions(ctx)
    tz = ZoneInfo(ctx.organization.timezone)
    today = datetime.now(tz).date()
    first_day = today - timedelta(days=days - 1)
    since = datetime.combine(first_day, datetime.min.time(), tzinfo=tz)

    status_rows = db.execute(
        select(ServiceRequest.status, func.count()).where(*conds).group_by(ServiceRequest.status)
    ).all()
    by_status = {s.value: 0 for s in RequestStatus}
    for status, count in status_rows:
        by_status[status.value] = count

    priority_rows = db.execute(
        select(ServiceRequest.priority, func.count())
        .where(*conds)
        .group_by(ServiceRequest.priority)
    ).all()
    by_priority = {p.value: c for p, c in priority_rows}

    category_rows = db.execute(
        select(ServiceCategory.id, ServiceCategory.name, func.count(ServiceRequest.id))
        .join(
            ServiceRequest,
            (ServiceRequest.category_id == ServiceCategory.id)
            & (ServiceRequest.organization_id == ServiceCategory.organization_id),
        )
        .where(*conds)
        .group_by(ServiceCategory.id, ServiceCategory.name)
        .order_by(func.count(ServiceRequest.id).desc(), ServiceCategory.name)
    ).all()

    local_created = func.date(func.timezone(ctx.organization.timezone, ServiceRequest.created_at))
    created_rows = dict(
        db.execute(
            select(local_created, func.count())
            .where(*conds, ServiceRequest.created_at >= since)
            .group_by(local_created)
        ).all()
    )

    local_done = func.date(
        func.timezone(ctx.organization.timezone, RequestStatusHistory.created_at)
    )
    completed_rows = dict(
        db.execute(
            select(local_done, func.count(func.distinct(RequestStatusHistory.request_id)))
            .join(ServiceRequest, ServiceRequest.id == RequestStatusHistory.request_id)
            .where(
                *conds,
                RequestStatusHistory.to_status == RequestStatus.COMPLETED,
                RequestStatusHistory.created_at >= since,
            )
            .group_by(local_done)
        ).all()
    )

    daily = [
        DailyPoint(
            date=day,
            created=created_rows.get(day, 0),
            completed=completed_rows.get(day, 0),
        )
        for day in (first_day + timedelta(days=i) for i in range(days))
    ]

    total = sum(by_status.values())
    open_count = sum(
        count for status, count in by_status.items() if status not in {s.value for s in _CLOSED}
    )
    return SummaryOut(
        total=total,
        open=open_count,
        in_progress=by_status[RequestStatus.IN_PROGRESS.value],
        completed_in_period=sum(p.completed for p in daily),
        period_days=days,
        timezone=ctx.organization.timezone,
        by_status=by_status,
        by_priority=by_priority,
        by_category=[CategoryCount(category_id=i, name=n, count=c) for i, n, c in category_rows],
        daily=daily,
    )
