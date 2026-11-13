"""Technician scheduling: candidates, assign, reschedule, unassign, decline, schedule view."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import OrgContext
from app.core.errors import AppError
from app.domain.enums import (
    ACTIVE_ASSIGNMENT_STATUSES,
    AssignmentStatus,
    RequestStatus,
    Role,
)
from app.domain.lifecycle import TransitionError, check_transition
from app.domain.scheduling import (
    Weekly,
    available_minutes,
    earliest_slot,
    load_percent,
    missing_skills,
    overlaps,
    window_problems,
)
from app.models import (
    Assignment,
    OrganizationMembership,
    RequestStatusHistory,
    ServiceCategory,
    ServiceRequest,
    TechnicianAbsence,
    TechnicianAvailability,
    TechnicianProfile,
    TechnicianSkill,
    User,
)
from app.schemas.scheduling import (
    AbsenceOut,
    AssignmentCreate,
    AssignmentOut,
    AssignmentReschedule,
    AvailabilityOut,
    CandidateOut,
    Reason,
    ScheduleOut,
    SuggestionOut,
    TechnicianOut,
)
from app.services.audit import record_audit
from app.services.notifications import notify, notify_staff
from app.services.requests import get_request

STAFF = {Role.DISPATCHER, Role.ADMIN}

# Order matters: the first problem becomes the error code returned to the client.
_STATUS_FOR_REASON = {
    "technician_inactive": 409,
    "schedule_conflict": 409,
}


def _require_staff(ctx: OrgContext) -> None:
    if ctx.role not in STAFF:
        raise AppError(403, "forbidden", "Only dispatchers and administrators can do this")


def _now() -> datetime:
    return datetime.now(UTC)


class _TechData:
    """Everything needed to judge one technician, loaded in a handful of queries."""

    def __init__(self) -> None:
        self.profile: TechnicianProfile
        self.user: User
        self.membership_active = True
        self.skills: list[str] = []
        self.weekly: Weekly = {}
        self.absences: list[tuple[datetime, datetime]] = []

    @property
    def usable(self) -> bool:
        return self.profile.is_active and self.user.is_active and self.membership_active


def load_technicians(
    db: Session, org_id: int, technician_ids: list[int] | None = None
) -> dict[int, _TechData]:
    query = (
        select(TechnicianProfile, User, OrganizationMembership)
        .join(User, User.id == TechnicianProfile.user_id)
        .join(
            OrganizationMembership,
            (OrganizationMembership.user_id == User.id)
            & (OrganizationMembership.organization_id == TechnicianProfile.organization_id),
        )
        .where(TechnicianProfile.organization_id == org_id)
        .order_by(User.full_name)
    )
    if technician_ids is not None:
        query = query.where(TechnicianProfile.id.in_(technician_ids))

    data: dict[int, _TechData] = {}
    for profile, user, membership in db.execute(query):
        item = _TechData()
        item.profile, item.user = profile, user
        item.membership_active = membership.is_active
        data[profile.id] = item
    if not data:
        return data

    ids = list(data)
    for skill in db.scalars(select(TechnicianSkill).where(TechnicianSkill.technician_id.in_(ids))):
        data[skill.technician_id].skills.append(skill.skill)
    for row in db.scalars(
        select(TechnicianAvailability).where(TechnicianAvailability.technician_id.in_(ids))
    ):
        data[row.technician_id].weekly.setdefault(row.weekday, []).append(
            (row.start_time, row.end_time)
        )
    for absence in db.scalars(
        select(TechnicianAbsence).where(TechnicianAbsence.technician_id.in_(ids))
    ):
        data[absence.technician_id].absences.append((absence.start_at, absence.end_at))
    return data


def _active_assignments(
    db: Session,
    org_id: int,
    technician_ids: list[int],
    start: datetime,
    end: datetime,
    exclude_id: int | None = None,
) -> list[Assignment]:
    query = select(Assignment).where(
        Assignment.organization_id == org_id,
        Assignment.technician_id.in_(technician_ids),
        Assignment.status.in_(ACTIVE_ASSIGNMENT_STATUSES),
        Assignment.start_at < end,
        Assignment.end_at > start,
    )
    if exclude_id is not None:
        query = query.where(Assignment.id != exclude_id)
    return list(db.scalars(query))


def _week_bounds(moment: datetime, tz: ZoneInfo) -> tuple[datetime, datetime]:
    local = moment.astimezone(tz)
    monday = datetime.combine(
        local.date() - timedelta(days=local.weekday()), datetime.min.time(), tz
    )
    return monday, monday + timedelta(days=7)


def _week_load(db: Session, org_id: int, tech: _TechData, moment: datetime, tz: ZoneInfo) -> int:
    start, end = _week_bounds(moment, tz)
    assigned = 0.0
    for a in _active_assignments(db, org_id, [tech.profile.id], start, end):
        lo, hi = max(a.start_at, start), min(a.end_at, end)
        assigned += (hi - lo).total_seconds() / 60
    available = available_minutes(start, end, tz=tz, weekly=tech.weekly, absences=tech.absences)
    return load_percent(round(assigned), available)


def evaluate(
    db: Session,
    ctx: OrgContext,
    category: ServiceCategory,
    tech: _TechData,
    start: datetime,
    end: datetime,
    exclude_assignment_id: int | None = None,
) -> CandidateOut:
    tz = ZoneInfo(ctx.organization.timezone)
    reasons: list[Reason] = []

    if not tech.usable:
        reasons.append(Reason(code="technician_inactive"))
    lacking = missing_skills(category.required_skills, tech.skills)
    if lacking:
        reasons.append(Reason(code="missing_skills", detail=", ".join(lacking)))
    for code in window_problems(
        start, end, now=_now(), tz=tz, weekly=tech.weekly, absences=tech.absences
    ):
        reasons.append(Reason(code=code))

    conflicts: list[int] = []
    if end > start:
        conflicts = [
            a.id
            for a in _active_assignments(
                db, ctx.org_id, [tech.profile.id], start, end, exclude_assignment_id
            )
        ]
    if conflicts:
        reasons.append(Reason(code="schedule_conflict", detail=",".join(map(str, conflicts))))

    return CandidateOut(
        technician_id=tech.profile.id,
        full_name=tech.user.full_name,
        skills=sorted(tech.skills),
        available=not reasons,
        load_percent=_week_load(db, ctx.org_id, tech, start, tz),
        reasons=reasons,
        conflicting_assignment_ids=conflicts,
    )


def _category_of(db: Session, req: ServiceRequest) -> ServiceCategory:
    category = db.get(ServiceCategory, req.category_id)
    if category is None:  # cannot happen: composite FK
        raise AppError(404, "category_not_found", "Category not found")
    return category


def candidates(
    db: Session, ctx: OrgContext, request_id: int, start: datetime, end: datetime
) -> list[CandidateOut]:
    _require_staff(ctx)
    req = get_request(db, ctx, request_id)
    category = _category_of(db, req)
    result = [
        evaluate(db, ctx, category, tech, start, end)
        for tech in load_technicians(db, ctx.org_id).values()
    ]
    # available first, then lighter load, then name
    return sorted(result, key=lambda c: (not c.available, c.load_percent, c.full_name))


SUGGESTION_HORIZON_DAYS = 14
MAX_SUGGESTIONS = 3


def suggestions(db: Session, ctx: OrgContext, request_id: int) -> list[SuggestionOut]:
    """Smart Assign: the earliest free, valid visit for every suitable technician.

    "Suitable" means active and holding all skills of the request's category. The visit uses the
    category's standard duration and, when the customer named a preferred window, is placed
    inside it if at all possible. Results are ranked by start time, then by lighter weekly load.
    Every suggestion is a normal booking proposal: applying it goes through `assign`, so all
    rules and the database overlap guard still apply.
    """
    _require_staff(ctx)
    req = get_request(db, ctx, request_id)
    if req.status != RequestStatus.TRIAGED:
        return []
    category = _category_of(db, req)
    tz = ZoneInfo(ctx.organization.timezone)
    duration = timedelta(minutes=category.default_duration_min)
    now = _now()
    not_before = now + timedelta(hours=1)  # leave time to notify and travel
    horizon_end = now + timedelta(days=SUGGESTION_HORIZON_DAYS + 1)

    suitable = {
        tid: tech
        for tid, tech in load_technicians(db, ctx.org_id).items()
        if tech.usable and not missing_skills(category.required_skills, tech.skills)
    }
    if not suitable:
        return []

    busy: dict[int, list[tuple[datetime, datetime]]] = {tid: [] for tid in suitable}
    for booking in _active_assignments(db, ctx.org_id, list(suitable), now, horizon_end):
        busy[booking.technician_id].append((booking.start_at, booking.end_at))

    has_preference = req.desired_start is not None or req.desired_end is not None
    found: list[tuple[datetime, datetime, int, bool | None, _TechData]] = []
    for tid, tech in suitable.items():

        def find(
            start_from: datetime,
            deadline: datetime | None = None,
            tech: _TechData = tech,
            tid: int = tid,
        ) -> tuple[datetime, datetime] | None:
            return earliest_slot(
                duration=duration,
                not_before=start_from,
                horizon_days=SUGGESTION_HORIZON_DAYS,
                tz=tz,
                weekly=tech.weekly,
                absences=tech.absences,
                busy=busy[tid],
                must_end_by=deadline,
            )

        slot = None
        within: bool | None = None
        if has_preference:
            preferred_from = max(not_before, req.desired_start or not_before)
            slot = find(preferred_from, req.desired_end)
            within = slot is not None
        if slot is None:
            slot = find(not_before)
            within = False if has_preference else None
        if slot is not None:
            found.append(
                (slot[0], slot[1], _week_load(db, ctx.org_id, tech, slot[0], tz), within, tech)
            )

    found.sort(key=lambda item: (item[3] is not True, item[0], item[2], item[4].user.full_name))
    return [
        SuggestionOut(
            technician_id=tech.profile.id,
            full_name=tech.user.full_name,
            skills=sorted(tech.skills),
            start_at=start,
            end_at=end,
            load_percent=load,
            within_desired_window=within,
            is_best=index == 0,
        )
        for index, (start, end, load, within, tech) in enumerate(found[:MAX_SUGGESTIONS])
    ]


def _history_and_audit(
    db: Session,
    ctx: OrgContext,
    req: ServiceRequest,
    source: RequestStatus,
    target: RequestStatus,
    reason: str | None,
    action: str,
    extra: dict[str, object],
) -> None:
    db.add(
        RequestStatusHistory(
            organization_id=ctx.org_id,
            request_id=req.id,
            from_status=source,
            to_status=target,
            actor_user_id=ctx.user.id,
            reason=reason,
        )
    )
    record_audit(
        db,
        action=action,
        object_type="service_request",
        object_id=req.id,
        organization_id=ctx.org_id,
        actor_user_id=ctx.user.id,
        before={"status": source.value},
        after={"status": target.value, **extra},
    )


def _move_request(
    db: Session, ctx: OrgContext, req_id: int, source: RequestStatus, target: RequestStatus
) -> None:
    """Compare-and-set the request status; a lost race becomes a 409 and rolls everything back."""
    result = db.execute(
        update(ServiceRequest)
        .where(
            ServiceRequest.id == req_id,
            ServiceRequest.organization_id == ctx.org_id,
            ServiceRequest.status == source,
        )
        .values(status=target)
        .returning(ServiceRequest.id)
    )
    if result.first() is None:
        db.rollback()
        raise AppError(409, "state_conflict", "The request was changed by someone else; reload")


def _raise_for(candidate: CandidateOut) -> None:
    first = candidate.reasons[0]
    status = _STATUS_FOR_REASON.get(first.code, 422)
    text = "; ".join(f"{r.code}{': ' + r.detail if r.detail else ''}" for r in candidate.reasons)
    raise AppError(status, first.code, text)


def _to_out(
    db: Session, a: Assignment, req_title: str | None = None, tech_name: str | None = None
) -> AssignmentOut:
    if tech_name is None:
        profile = db.get(TechnicianProfile, a.technician_id)
        user = db.get(User, profile.user_id) if profile else None
        tech_name = user.full_name if user else "?"
    if req_title is None:
        found = db.get(ServiceRequest, a.request_id)
        req_title = found.title if found else "?"
    return AssignmentOut(
        id=a.id,
        request_id=a.request_id,
        request_title=req_title,
        technician_id=a.technician_id,
        technician_name=tech_name,
        start_at=a.start_at,
        end_at=a.end_at,
        timezone=a.timezone,
        status=a.status,
        created_at=a.created_at,
    )


def assign(
    db: Session, ctx: OrgContext, request_id: int, data: AssignmentCreate
) -> tuple[AssignmentOut, bool]:
    """Create the booking. Returns (assignment, created). Repeating the same command is safe."""
    _require_staff(ctx)
    req = get_request(db, ctx, request_id)

    existing = db.scalar(
        select(Assignment).where(
            Assignment.request_id == req.id, Assignment.status.in_(ACTIVE_ASSIGNMENT_STATUSES)
        )
    )
    if existing is not None:
        same = (
            existing.technician_id == data.technician_id
            and existing.start_at == data.start_at
            and existing.end_at == data.end_at
        )
        if same:  # idempotent replay: same command, same effect (API-03)
            return _to_out(db, existing, req.title), False
        raise AppError(409, "already_assigned", "The request already has an active assignment")

    try:
        check_transition(req.status, RequestStatus.SCHEDULED, ctx.role, via_dedicated_endpoint=True)
    except TransitionError as err:
        raise AppError(409, err.code, str(err)) from err

    techs = load_technicians(db, ctx.org_id, [data.technician_id])
    tech = techs.get(data.technician_id)
    if tech is None:
        raise AppError(404, "technician_not_found", "Technician not found")

    verdict = evaluate(db, ctx, _category_of(db, req), tech, data.start_at, data.end_at)
    if not verdict.available:
        _raise_for(verdict)

    source = req.status
    assignment = Assignment(
        organization_id=ctx.org_id,
        request_id=req.id,
        technician_id=tech.profile.id,
        start_at=data.start_at,
        end_at=data.end_at,
        timezone=ctx.organization.timezone,
        status=AssignmentStatus.SCHEDULED,
        created_by_user_id=ctx.user.id,
    )
    try:
        db.add(assignment)
        db.flush()  # the exclusion constraint fires here if someone else just took the slot
    except IntegrityError as err:
        db.rollback()
        raise AppError(409, "schedule_conflict", "The technician is already booked then") from err

    _move_request(db, ctx, req.id, source, RequestStatus.SCHEDULED)
    _history_and_audit(
        db,
        ctx,
        req,
        source,
        RequestStatus.SCHEDULED,
        None,
        "assignment.created",
        {"technician_id": tech.profile.id, "start_at": data.start_at.isoformat()},
    )
    notify(
        db,
        org_id=ctx.org_id,
        user_id=tech.user.id,
        type="assignment_created",
        title=f"New task: request #{req.id}",
        body=req.title,
        request_id=req.id,
    )
    db.commit()
    return _to_out(db, assignment, req.title), True


def _get_assignment(db: Session, ctx: OrgContext, assignment_id: int) -> Assignment:
    found = db.scalar(
        select(Assignment).where(
            Assignment.id == assignment_id, Assignment.organization_id == ctx.org_id
        )
    )
    if found is None:
        raise AppError(404, "assignment_not_found", "Assignment not found")
    return found


_BEFORE_WORK = {AssignmentStatus.SCHEDULED, AssignmentStatus.ACCEPTED}


def reschedule(
    db: Session, ctx: OrgContext, assignment_id: int, data: AssignmentReschedule
) -> AssignmentOut:
    _require_staff(ctx)
    current = _get_assignment(db, ctx, assignment_id)
    if current.status not in _BEFORE_WORK:
        raise AppError(409, "work_started", "Only assignments that have not started can be changed")
    req = get_request(db, ctx, current.request_id)

    tech_id = data.technician_id or current.technician_id
    tech = load_technicians(db, ctx.org_id, [tech_id]).get(tech_id)
    if tech is None:
        raise AppError(404, "technician_not_found", "Technician not found")
    verdict = evaluate(
        db,
        ctx,
        _category_of(db, req),
        tech,
        data.start_at,
        data.end_at,
        exclude_assignment_id=current.id,
    )
    if not verdict.available:
        _raise_for(verdict)

    before = {
        "technician_id": current.technician_id,
        "start_at": current.start_at.isoformat(),
        "end_at": current.end_at.isoformat(),
    }
    source = req.status
    current.technician_id = tech_id
    current.start_at = data.start_at
    current.end_at = data.end_at
    current.timezone = ctx.organization.timezone
    current.status = AssignmentStatus.SCHEDULED  # a changed booking needs a fresh acceptance
    try:
        db.flush()
    except IntegrityError as err:
        db.rollback()
        raise AppError(409, "schedule_conflict", "The technician is already booked then") from err

    if source != RequestStatus.SCHEDULED:
        _move_request(db, ctx, req.id, source, RequestStatus.SCHEDULED)
        _history_and_audit(
            db,
            ctx,
            req,
            source,
            RequestStatus.SCHEDULED,
            data.reason,
            "assignment.rescheduled",
            {"technician_id": tech_id},
        )
    else:
        record_audit(
            db,
            action="assignment.rescheduled",
            object_type="assignment",
            object_id=current.id,
            organization_id=ctx.org_id,
            actor_user_id=ctx.user.id,
            before=before,
            after={
                "technician_id": tech_id,
                "start_at": data.start_at.isoformat(),
                "end_at": data.end_at.isoformat(),
            },
        )
    notify(
        db,
        org_id=ctx.org_id,
        user_id=tech.user.id,
        type="assignment_rescheduled",
        title=f"Task changed: request #{req.id}",
        body=req.title,
        request_id=req.id,
    )
    db.commit()
    return _to_out(db, current, req.title)


def _release(
    db: Session,
    ctx: OrgContext,
    assignment: Assignment,
    new_status: AssignmentStatus,
    reason: str | None,
    action: str,
) -> AssignmentOut:
    """Free the slot and send the request back to TRIAGED. History keeps the old row."""
    if assignment.status not in _BEFORE_WORK:
        raise AppError(
            409, "work_started", "Only assignments that have not started can be released"
        )
    # authorization was already decided by the caller (staff, or the assigned technician)
    req = db.scalar(
        select(ServiceRequest).where(
            ServiceRequest.id == assignment.request_id,
            ServiceRequest.organization_id == ctx.org_id,
        )
    )
    if req is None:
        raise AppError(404, "request_not_found", "Request not found")
    source = req.status
    assignment.status = new_status
    db.flush()
    _move_request(db, ctx, req.id, source, RequestStatus.TRIAGED)
    _history_and_audit(
        db,
        ctx,
        req,
        source,
        RequestStatus.TRIAGED,
        reason,
        action,
        {"assignment_id": assignment.id},
    )
    tech_user_id = db.scalar(
        select(TechnicianProfile.user_id).where(TechnicianProfile.id == assignment.technician_id)
    )
    if new_status == AssignmentStatus.DECLINED:  # the technician refused: tell the dispatchers
        notify_staff(
            db,
            org_id=ctx.org_id,
            type="assignment_declined",
            title=f"Technician declined request #{req.id}",
            body=reason or req.title,
            request_id=req.id,
        )
    elif tech_user_id is not None:  # a dispatcher removed the task: tell the technician
        notify(
            db,
            org_id=ctx.org_id,
            user_id=tech_user_id,
            type="assignment_canceled",
            title=f"Task removed: request #{req.id}",
            body=req.title,
            request_id=req.id,
        )
    db.commit()
    return _to_out(db, assignment, req.title)


def unassign(db: Session, ctx: OrgContext, assignment_id: int, reason: str | None) -> AssignmentOut:
    _require_staff(ctx)
    return _release(
        db,
        ctx,
        _get_assignment(db, ctx, assignment_id),
        AssignmentStatus.CANCELED,
        reason,
        "assignment.canceled",
    )


def _own_assignment(db: Session, ctx: OrgContext, assignment_id: int) -> Assignment:
    assignment = _get_assignment(db, ctx, assignment_id)
    owner = db.scalar(
        select(TechnicianProfile.user_id).where(TechnicianProfile.id == assignment.technician_id)
    )
    if ctx.role != Role.TECHNICIAN or owner != ctx.user.id:
        raise AppError(403, "forbidden", "This assignment belongs to another technician")
    return assignment


def decline(db: Session, ctx: OrgContext, assignment_id: int, reason: str | None) -> AssignmentOut:
    return _release(
        db,
        ctx,
        _own_assignment(db, ctx, assignment_id),
        AssignmentStatus.DECLINED,
        reason,
        "assignment.declined",
    )


def assignments_for_request(db: Session, ctx: OrgContext, request_id: int) -> list[AssignmentOut]:
    req = get_request(db, ctx, request_id)
    if ctx.role == Role.CUSTOMER:
        return []  # customers do not see internal planning
    rows = db.scalars(
        select(Assignment).where(Assignment.request_id == req.id).order_by(Assignment.id)
    )
    return [_to_out(db, a, req.title) for a in rows]


def technician_list(
    db: Session, ctx: OrgContext, week_of: datetime | None = None
) -> list[TechnicianOut]:
    _require_staff(ctx)
    tz = ZoneInfo(ctx.organization.timezone)
    moment = week_of or _now()
    out: list[TechnicianOut] = []
    for tech in load_technicians(db, ctx.org_id).values():
        out.append(
            TechnicianOut(
                id=tech.profile.id,
                user_id=tech.user.id,
                full_name=tech.user.full_name,
                email=tech.user.email,
                is_active=tech.usable,
                skills=sorted(tech.skills),
                availability=[
                    AvailabilityOut(weekday=d, start_time=s, end_time=e)
                    for d, spans in sorted(tech.weekly.items())
                    for s, e in spans
                ],
                load_percent=_week_load(db, ctx.org_id, tech, moment, tz),
            )
        )
    return out


def schedule(db: Session, ctx: OrgContext, start: datetime, end: datetime) -> ScheduleOut:
    """Bookings and absences between start and end (SCHED-07). Technicians see only their own."""
    if end <= start or end - start > timedelta(days=42):
        raise AppError(422, "invalid_range", "Choose a range of at most 42 days")
    techs = load_technicians(db, ctx.org_id)
    visible_ids = list(techs)
    if ctx.role == Role.TECHNICIAN:
        visible_ids = [i for i, t in techs.items() if t.user.id == ctx.user.id]
    elif ctx.role not in STAFF:
        raise AppError(403, "forbidden", "Not available for your role")

    rows = db.execute(
        select(Assignment, ServiceRequest.title)
        .join(
            ServiceRequest,
            (ServiceRequest.id == Assignment.request_id)
            & (ServiceRequest.organization_id == Assignment.organization_id),
        )
        .where(
            Assignment.organization_id == ctx.org_id,
            Assignment.technician_id.in_(visible_ids),
            Assignment.status.in_([*ACTIVE_ASSIGNMENT_STATUSES, AssignmentStatus.COMPLETED]),
            Assignment.start_at < end,
            Assignment.end_at > start,
        )
        .order_by(Assignment.start_at)
    ).all()

    absences = [
        AbsenceOut(technician_id=tid, start_at=s, end_at=e, reason=None)
        for tid, t in techs.items()
        if tid in visible_ids
        for s, e in t.absences
        if overlaps(s, e, start, end)
    ]
    tz = ZoneInfo(ctx.organization.timezone)
    technicians = [
        TechnicianOut(
            id=t.profile.id,
            user_id=t.user.id,
            full_name=t.user.full_name,
            email=t.user.email,
            is_active=t.usable,
            skills=sorted(t.skills),
            availability=[
                AvailabilityOut(weekday=d, start_time=s, end_time=e)
                for d, spans in sorted(t.weekly.items())
                for s, e in spans
            ],
            load_percent=_week_load(db, ctx.org_id, t, start, tz),
        )
        for i, t in techs.items()
        if i in visible_ids
    ]
    return ScheduleOut(
        timezone=ctx.organization.timezone,
        technicians=technicians,
        assignments=[
            _to_out(db, a, title, techs[a.technician_id].user.full_name) for a, title in rows
        ],
        absences=absences,
    )
