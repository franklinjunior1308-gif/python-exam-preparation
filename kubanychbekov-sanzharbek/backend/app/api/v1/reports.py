from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import DbDep, OrgDep
from app.core.errors import AppError
from app.domain.enums import (
    AssignmentStatus,
    EstimateStatus,
    RequestStatus,
    Role,
)
from app.domain.money import estimate_total_cents, line_total_cents
from app.domain.scheduling import available_minutes
from app.models import (
    Assignment,
    Estimate,
    EstimateLine,
    MaterialUsage,
    RequestStatusHistory,
    ServiceCategory,
    ServiceRequest,
    TechnicianProfile,
    User,
)
from app.schemas.reports import (
    CategoryCount,
    DailyPoint,
    SummaryOut,
    TechnicianLoad,
    UpcomingVisit,
)
from app.services import scheduling as scheduling_service
from app.services import sla as sla_service
from app.services.requests import visible_conditions

router = APIRouter(prefix="/reports", tags=["reports"])

_CLOSED = {RequestStatus.CLOSED, RequestStatus.CANCELED}
_STAFF = {Role.ADMIN, Role.DISPATCHER}
MAX_PERIOD_DAYS = 90
LOAD_METHOD = (
    "Scheduled assignment minutes in the period divided by the working minutes of all active "
    "technicians (weekly availability minus absences, in the organization time zone). "
    "Inactive technicians are excluded from the denominator. The percentage is capped at 100 "
    "because a visit may sit partly outside normal hours."
)


def _period(
    tz: ZoneInfo, days: int, date_from: date | None, date_to: date | None
) -> tuple[date, date]:
    today = datetime.now(tz).date()
    last = date_to or today
    first = date_from or last - timedelta(days=days - 1)
    if first > last:
        raise AppError(422, "invalid_period", "date_from must not be after date_to")
    if (last - first).days + 1 > MAX_PERIOD_DAYS:
        raise AppError(422, "period_too_long", f"The period is at most {MAX_PERIOD_DAYS} days")
    return first, last


@router.get("/summary", response_model=SummaryOut)
def summary(
    ctx: OrgDep,
    db: DbDep,
    days: Annotated[int, Query(ge=1, le=MAX_PERIOD_DAYS)] = 14,
    date_from: date | None = None,
    date_to: date | None = None,
    category_id: int | None = None,
    technician_id: int | None = None,
) -> SummaryOut:
    """Dashboard numbers computed from the database (REPORT-05), in the organization time zone.

    The period is the last `days` days or `date_from`..`date_to` (local days, at most 90).
    Scoped like the request list: customers only see aggregates of their own requests.
    Optional filters: `category_id`, `technician_id` (requests booked on that technician).
    """
    conds = visible_conditions(ctx)
    if category_id is not None:
        conds.append(ServiceRequest.category_id == category_id)
    if technician_id is not None:
        booked = select(Assignment.request_id).where(
            Assignment.organization_id == ctx.org_id,
            Assignment.technician_id == technician_id,
            Assignment.status.notin_([AssignmentStatus.CANCELED, AssignmentStatus.DECLINED]),
        )
        conds.append(ServiceRequest.id.in_(booked))

    tz = ZoneInfo(ctx.organization.timezone)
    first_day, last_day = _period(tz, days, date_from, date_to)
    period_days = (last_day - first_day).days + 1
    since = datetime.combine(first_day, time.min, tzinfo=tz)
    until = datetime.combine(last_day + timedelta(days=1), time.min, tzinfo=tz)

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
            .where(*conds, ServiceRequest.created_at >= since, ServiceRequest.created_at < until)
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
                RequestStatusHistory.created_at < until,
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
        for day in (first_day + timedelta(days=i) for i in range(period_days))
    ]

    total = sum(by_status.values())
    open_count = sum(
        count for status, count in by_status.items() if status not in {s.value for s in _CLOSED}
    )

    # approved estimates decided in the period, for requests the viewer may see (REPORT-04)
    estimates = list(
        db.scalars(
            select(Estimate)
            .join(
                ServiceRequest,
                (ServiceRequest.id == Estimate.request_id)
                & (ServiceRequest.organization_id == Estimate.organization_id),
            )
            .where(
                *conds,
                Estimate.status == EstimateStatus.APPROVED,
                Estimate.decided_at >= since,
                Estimate.decided_at < until,
            )
        )
    )
    approved_cents = 0
    if estimates:
        lines: dict[int, list[tuple[Decimal, int]]] = {e.id: [] for e in estimates}
        for line in db.scalars(
            select(EstimateLine).where(EstimateLine.estimate_id.in_(list(lines)))
        ):
            lines[line.estimate_id].append((line.quantity, line.unit_price_cents))
        for est in estimates:
            approved_cents += estimate_total_cents(
                est.labor_minutes, est.labor_rate_cents, lines[est.id]
            )[2]

    out = SummaryOut(
        total=total,
        open=open_count,
        in_progress=by_status[RequestStatus.IN_PROGRESS.value],
        completed_in_period=sum(p.completed for p in daily),
        period_days=period_days,
        timezone=ctx.organization.timezone,
        by_status=by_status,
        by_priority=by_priority,
        by_category=[CategoryCount(category_id=i, name=n, count=c) for i, n, c in category_rows],
        daily=daily,
        date_from=first_day,
        date_to=last_day,
        approved_estimates_cents=approved_cents,
        approved_estimates_count=len(estimates),
    )

    now = datetime.now(UTC)
    visits = db.execute(
        select(Assignment, ServiceRequest.title, User.full_name)
        .join(
            ServiceRequest,
            (ServiceRequest.id == Assignment.request_id)
            & (ServiceRequest.organization_id == Assignment.organization_id),
        )
        .join(TechnicianProfile, TechnicianProfile.id == Assignment.technician_id)
        .join(User, User.id == TechnicianProfile.user_id)
        .where(
            *conds,
            Assignment.status.in_(
                [AssignmentStatus.SCHEDULED, AssignmentStatus.ACCEPTED, AssignmentStatus.BLOCKED]
            ),
            Assignment.start_at >= now,
        )
        .order_by(Assignment.start_at)
        .limit(5)
    ).all()
    out.upcoming_visits = [
        UpcomingVisit(
            request_id=a.request_id,
            title=title,
            technician=name,
            start_at=a.start_at,
            end_at=a.end_at,
        )
        for a, title, name in visits
    ]

    if ctx.role in _STAFF:
        out.overdue = len(sla_service.overdue_queue(db, ctx))

        used = db.execute(
            select(MaterialUsage.quantity, MaterialUsage.unit_price_cents)
            .join(
                ServiceRequest,
                (ServiceRequest.id == MaterialUsage.request_id)
                & (ServiceRequest.organization_id == MaterialUsage.organization_id),
            )
            .where(
                *conds,
                MaterialUsage.created_at >= since,
                MaterialUsage.created_at < until,
            )
        ).all()
        out.materials_cost_cents = sum(line_total_cents(q, price) for q, price in used)

        techs = scheduling_service.load_technicians(db, ctx.org_id)
        counted = [
            t
            for t in techs.values()
            if t.usable and (technician_id is None or t.profile.id == technician_id)
        ]
        available = sum(
            available_minutes(since, until, tz=tz, weekly=t.weekly, absences=t.absences)
            for t in counted
        )
        extra = [ServiceRequest.category_id == category_id] if category_id is not None else []
        booked_rows = db.execute(
            select(Assignment.start_at, Assignment.end_at)
            .join(
                ServiceRequest,
                (ServiceRequest.id == Assignment.request_id)
                & (ServiceRequest.organization_id == Assignment.organization_id),
            )
            .where(
                Assignment.organization_id == ctx.org_id,
                Assignment.technician_id.in_([t.profile.id for t in counted] or [0]),
                Assignment.status.notin_([AssignmentStatus.CANCELED, AssignmentStatus.DECLINED]),
                Assignment.start_at < until,
                Assignment.end_at > since,
                *extra,
            )
        ).all()
        scheduled = 0
        for start, end in booked_rows:
            scheduled += round((min(end, until) - max(start, since)).total_seconds() / 60)
        out.technician_load = TechnicianLoad(
            percent=0 if available <= 0 else min(100, round(scheduled * 100 / available)),
            scheduled_minutes=scheduled,
            available_minutes=available,
            technicians=len(counted),
            method=LOAD_METHOD,
        )
    return out
