"""SLA for requests: working-time clock, pauses, overdue queue, one-time escalation."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.api.deps import OrgContext
from app.core.errors import AppError
from app.domain.enums import EstimateStatus, Priority, RequestStatus, Role
from app.domain.sla import (
    DEFAULT_WEEKLY,
    Interval,
    Weekly,
    budget_minutes,
    deadline,
    sla_state,
    working_minutes,
)
from app.models import (
    Estimate,
    Holiday,
    Organization,
    RequestStatusHistory,
    ServiceRequest,
    SlaEscalation,
    WorkingInterval,
)
from app.schemas.request import RequestOut
from app.schemas.sla import (
    HolidayIn,
    HolidayOut,
    IntervalIn,
    OverdueOut,
    PriorityRow,
    SlaOut,
    SlaReportOut,
    WorkingHoursIn,
    WorkingHoursOut,
)
from app.services.audit import record_audit
from app.services.notifications import notify_staff
from app.services.requests import visible_conditions

OPEN_FOR_SLA = {
    RequestStatus.SUBMITTED,
    RequestStatus.TRIAGED,
    RequestStatus.SCHEDULED,
    RequestStatus.ACCEPTED,
    RequestStatus.IN_PROGRESS,
    RequestStatus.BLOCKED,
    RequestStatus.REOPENED,
}
FINISHED = {RequestStatus.COMPLETED, RequestStatus.CLOSED}
SUBMITTED_ESTIMATES = [
    EstimateStatus.AWAITING_APPROVAL,
    EstimateStatus.APPROVED,
    EstimateStatus.REJECTED,
    EstimateStatus.SUPERSEDED,
]


@dataclass(frozen=True)
class Calendar:
    tz: ZoneInfo
    weekly: Weekly
    holidays: frozenset[date]
    is_default: bool


def load_calendar(db: Session, org_id: int, timezone: str) -> Calendar:
    rows = db.scalars(select(WorkingInterval).where(WorkingInterval.organization_id == org_id))
    weekly: Weekly = {}
    for row in rows:
        weekly.setdefault(row.weekday, []).append((row.start_time, row.end_time))
    holidays = frozenset(db.scalars(select(Holiday.day).where(Holiday.organization_id == org_id)))
    return Calendar(ZoneInfo(timezone), weekly or DEFAULT_WEEKLY, holidays, not weekly)


def _pauses(db: Session, request_ids: list[int], now: datetime) -> dict[int, list[Interval]]:
    """Time spent waiting for the customer's decision on an estimate (SLA-03).

    Derived from the estimate rows themselves (submitted -> decided/replaced), so the history
    needed for an exact recalculation is never lost.
    """
    result: dict[int, list[Interval]] = {rid: [] for rid in request_ids}
    if not request_ids:
        return result
    rows = db.execute(
        select(
            Estimate.request_id,
            Estimate.submitted_at,
            Estimate.decided_at,
            Estimate.updated_at,
            Estimate.status,
        ).where(
            Estimate.request_id.in_(request_ids),
            Estimate.submitted_at.is_not(None),
            Estimate.status.in_(SUBMITTED_ESTIMATES),
        )
    )
    for request_id, submitted, decided, updated, status in rows:
        if decided is not None:
            end = decided
        elif status == EstimateStatus.SUPERSEDED:
            end = updated  # replaced or withdrawn while pending
        else:
            end = now  # still waiting: the clock is paused right now
        if submitted is not None and end > submitted:
            result[request_id].append((submitted, end))
    return result


def _completed_at(db: Session, request_ids: list[int]) -> dict[int, datetime]:
    rows = db.execute(
        select(RequestStatusHistory.request_id, RequestStatusHistory.created_at)
        .where(
            RequestStatusHistory.request_id.in_(request_ids),
            RequestStatusHistory.to_status == RequestStatus.COMPLETED,
        )
        .order_by(RequestStatusHistory.id)
    )
    found: dict[int, datetime] = {}
    for request_id, moment in rows:
        found[request_id] = moment  # the latest completion wins (after a rework)
    return found


def compute(
    req: ServiceRequest,
    calendar: Calendar,
    pauses: list[Interval],
    completed_at: datetime | None,
    now: datetime,
) -> SlaOut:
    finished = req.status in FINISHED and completed_at is not None
    end = completed_at if finished and completed_at else now
    budget = budget_minutes(Priority(req.priority))
    used = working_minutes(
        req.created_at,
        end,
        tz=calendar.tz,
        weekly=calendar.weekly,
        holidays=calendar.holidays,
        pauses=pauses,
    )
    state, remaining = sla_state(budget, used)
    paused = any(p_end >= now and p_start <= now for p_start, p_end in pauses) and not finished
    due = None
    if not finished and not paused:
        due = deadline(
            req.created_at,
            budget,
            tz=calendar.tz,
            weekly=calendar.weekly,
            holidays=calendar.holidays,
            pauses=pauses,
        )
    return SlaOut(
        budget_minutes=budget,
        used_minutes=used,
        remaining_minutes=remaining,
        state=state,
        due_at=due,
        paused=paused,
        finished=finished,
    )


def attach(db: Session, ctx: OrgContext, outs: list[RequestOut]) -> None:
    """Add the SLA block to request payloads (REQ-05). One calendar, two queries per page."""
    if not outs:
        return
    now = datetime.now(UTC)
    calendar = load_calendar(db, ctx.org_id, ctx.organization.timezone)
    ids = [o.id for o in outs]
    pauses = _pauses(db, ids, now)
    done = _completed_at(db, ids)
    for out in outs:
        shim = ServiceRequest(
            id=out.id, priority=out.priority, status=out.status, created_at=out.created_at
        )
        out.sla = compute(shim, calendar, pauses[out.id], done.get(out.id), now)


def overdue_queue(db: Session, ctx: OrgContext) -> list[OverdueOut]:
    """Open requests past their SLA, most overdue first (SLA-06)."""
    if ctx.role not in {Role.DISPATCHER, Role.ADMIN}:
        raise AppError(403, "forbidden", "Only dispatchers and administrators see the SLA queue")
    return _overdue(db, ctx.org_id, ctx.organization.timezone)


def _overdue(db: Session, org_id: int, timezone: str) -> list[OverdueOut]:
    now = datetime.now(UTC)
    calendar = load_calendar(db, org_id, timezone)
    open_requests = list(
        db.scalars(
            select(ServiceRequest).where(
                ServiceRequest.organization_id == org_id,
                ServiceRequest.status.in_(OPEN_FOR_SLA),
            )
        )
    )
    pauses = _pauses(db, [r.id for r in open_requests], now)
    escalated = set(
        db.scalars(select(SlaEscalation.request_id).where(SlaEscalation.organization_id == org_id))
    )
    items: list[OverdueOut] = []
    for req in open_requests:
        info = compute(req, calendar, pauses[req.id], None, now)
        if info.state == "OVERDUE":
            items.append(
                OverdueOut(
                    request_id=req.id,
                    title=req.title,
                    priority=req.priority.value,
                    status=req.status.value,
                    overdue_minutes=-info.remaining_minutes,
                    escalated=req.id in escalated,
                )
            )
    return sorted(items, key=lambda i: -i.overdue_minutes)


def filter_ids_by_state(
    db: Session, ctx: OrgContext, wanted: str, candidate_ids: list[int]
) -> set[int]:
    """Request ids (among candidates) whose SLA state equals `wanted` (REQ-04 SLA filter)."""
    now = datetime.now(UTC)
    calendar = load_calendar(db, ctx.org_id, ctx.organization.timezone)
    rows = list(
        db.scalars(
            select(ServiceRequest).where(
                ServiceRequest.id.in_(candidate_ids), *visible_conditions(ctx)
            )
        )
    )
    ids = [r.id for r in rows]
    pauses = _pauses(db, ids, now)
    done = _completed_at(db, ids)
    return {
        r.id
        for r in rows
        if compute(r, calendar, pauses[r.id], done.get(r.id), now).state == wanted
    }


def scan_and_escalate(db: Session) -> int:
    """Create ONE escalation notification per newly overdue request. Safe to run repeatedly
    and in parallel: the unique constraint decides who creates it (SLA-06, SLA-07)."""
    created = 0
    for org in db.scalars(select(Organization).where(Organization.is_active.is_(True))):
        for item in _overdue(db, org.id, org.timezone):
            inserted = db.execute(
                insert(SlaEscalation)
                .values(organization_id=org.id, request_id=item.request_id)
                .on_conflict_do_nothing(index_elements=["request_id"])
                .returning(SlaEscalation.id)
            ).first()
            if inserted is None:
                continue  # already escalated earlier (or by a parallel scan)
            notify_staff(
                db,
                org_id=org.id,
                type="sla_overdue",
                title=f"Request #{item.request_id} is past its SLA",
                body=f"{item.title} ({item.overdue_minutes} working minutes overdue)",
                request_id=item.request_id,
            )
            record_audit(
                db,
                action="sla.escalated",
                object_type="service_request",
                object_id=item.request_id,
                organization_id=org.id,
                after={"overdue_minutes": item.overdue_minutes},
            )
            db.commit()
            created += 1
    return created


# ------------------------------------------------------------------ settings (ORG-02)
def _require_admin(ctx: OrgContext) -> None:
    if ctx.role != Role.ADMIN:
        raise AppError(403, "forbidden", "Only administrators change working hours")


def get_hours(db: Session, ctx: OrgContext) -> WorkingHoursOut:
    if ctx.role not in {Role.ADMIN, Role.DISPATCHER}:
        raise AppError(403, "forbidden", "Not available for your role")
    calendar = load_calendar(db, ctx.org_id, ctx.organization.timezone)
    holidays = db.scalars(
        select(Holiday).where(Holiday.organization_id == ctx.org_id).order_by(Holiday.day)
    )
    return WorkingHoursOut(
        timezone=ctx.organization.timezone,
        intervals=[
            IntervalIn(weekday=d, start_time=s, end_time=e)
            for d, spans in sorted(calendar.weekly.items())
            for s, e in sorted(spans)
        ],
        holidays=[HolidayOut(id=h.id, day=h.day, name=h.name) for h in holidays],
        is_default=calendar.is_default,
    )


def set_hours(db: Session, ctx: OrgContext, data: WorkingHoursIn) -> WorkingHoursOut:
    _require_admin(ctx)
    by_day: dict[int, list[IntervalIn]] = {}
    for interval in data.intervals:
        by_day.setdefault(interval.weekday, []).append(interval)
    for spans in by_day.values():  # intervals of one day must not overlap
        spans.sort(key=lambda i: i.start_time)
        for a, b in zip(spans, spans[1:], strict=False):
            if b.start_time < a.end_time:
                raise AppError(422, "overlapping_intervals", "Working intervals overlap")
    for old in db.scalars(
        select(WorkingInterval).where(WorkingInterval.organization_id == ctx.org_id)
    ):
        db.delete(old)
    db.flush()
    for i in data.intervals:
        db.add(
            WorkingInterval(
                organization_id=ctx.org_id,
                weekday=i.weekday,
                start_time=i.start_time,
                end_time=i.end_time,
            )
        )
    record_audit(
        db,
        action="org.working_hours_changed",
        object_type="organization",
        object_id=ctx.org_id,
        organization_id=ctx.org_id,
        actor_user_id=ctx.user.id,
        after={"intervals": len(data.intervals)},
    )
    db.commit()
    return get_hours(db, ctx)


def add_holiday(db: Session, ctx: OrgContext, data: HolidayIn) -> WorkingHoursOut:
    _require_admin(ctx)
    exists = db.scalar(
        select(Holiday.id).where(Holiday.organization_id == ctx.org_id, Holiday.day == data.day)
    )
    if exists is None:
        db.add(Holiday(organization_id=ctx.org_id, day=data.day, name=data.name.strip()))
        record_audit(
            db,
            action="org.holiday_added",
            object_type="organization",
            object_id=ctx.org_id,
            organization_id=ctx.org_id,
            actor_user_id=ctx.user.id,
            after={"day": data.day.isoformat()},
        )
        db.commit()
    return get_hours(db, ctx)


def remove_holiday(db: Session, ctx: OrgContext, holiday_id: int) -> WorkingHoursOut:
    _require_admin(ctx)
    holiday = db.scalar(
        select(Holiday).where(Holiday.id == holiday_id, Holiday.organization_id == ctx.org_id)
    )
    if holiday is None:
        raise AppError(404, "holiday_not_found", "Holiday not found")
    db.delete(holiday)
    record_audit(
        db,
        action="org.holiday_removed",
        object_type="organization",
        object_id=ctx.org_id,
        organization_id=ctx.org_id,
        actor_user_id=ctx.user.id,
        after={"day": holiday.day.isoformat()},
    )
    db.commit()
    return get_hours(db, ctx)


def report(db: Session, ctx: OrgContext, days: int) -> SlaReportOut:
    """SLA outcome of requests completed in the last `days` days (WEB-04)."""
    if ctx.role not in {Role.DISPATCHER, Role.ADMIN}:
        raise AppError(403, "forbidden", "Only dispatchers and administrators see the SLA report")
    now = datetime.now(UTC)
    since = now - timedelta(days=days)
    completed = {
        rid: moment
        for rid, moment in _completed_at(
            db,
            list(
                db.scalars(
                    select(ServiceRequest.id).where(
                        ServiceRequest.organization_id == ctx.org_id,
                        ServiceRequest.status.in_(FINISHED),
                    )
                )
            ),
        ).items()
        if moment >= since
    }
    calendar = load_calendar(db, ctx.org_id, ctx.organization.timezone)
    requests = (
        list(
            db.scalars(
                select(ServiceRequest).where(
                    ServiceRequest.organization_id == ctx.org_id,
                    ServiceRequest.id.in_(list(completed)),
                )
            )
        )
        if completed
        else []
    )
    pauses = _pauses(db, [r.id for r in requests], now)
    per_priority: dict[str, list[int]] = {}
    used_total = late_total = 0
    for req in requests:
        info = compute(req, calendar, pauses[req.id], completed[req.id], now)
        late = info.state == "OVERDUE"
        used_total += info.used_minutes
        late_total += int(late)
        row = per_priority.setdefault(req.priority.value, [0, 0])
        row[0] += 1
        row[1] += int(late)
    escalated = (
        db.scalar(
            select(func.count())
            .select_from(SlaEscalation)
            .where(SlaEscalation.organization_id == ctx.org_id, SlaEscalation.created_at >= since)
        )
        or 0
    )
    total = len(requests)
    return SlaReportOut(
        period_days=days,
        total=total,
        on_time=total - late_total,
        late=late_total,
        avg_resolution_minutes=round(used_total / total) if total else None,
        escalated=escalated,
        by_priority=[
            PriorityRow(priority=name, total=row[0], late=row[1])
            for name, row in sorted(per_priority.items())
        ],
    )
