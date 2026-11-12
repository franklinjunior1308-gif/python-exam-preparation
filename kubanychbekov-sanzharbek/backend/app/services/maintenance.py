"""Preventive maintenance: plans and duplicate-free generation of requests (PM-01..05)."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.api.deps import OrgContext
from app.core.errors import AppError
from app.domain.enums import AssetStatus, RequestStatus, Role
from app.domain.maintenance import Frequency, next_occurrence, occurrences
from app.models import (
    Asset,
    MaintenancePlan,
    Organization,
    RequestStatusHistory,
    ServiceCategory,
    ServiceRequest,
)
from app.schemas.maintenance import GenerateOut, PlanIn, PlanOut, PlanRequestOut
from app.services.audit import record_audit
from app.services.notifications import notify_staff

STAFF = {Role.DISPATCHER, Role.ADMIN}
OPEN = [
    RequestStatus.SUBMITTED,
    RequestStatus.TRIAGED,
    RequestStatus.SCHEDULED,
    RequestStatus.ACCEPTED,
    RequestStatus.IN_PROGRESS,
    RequestStatus.BLOCKED,
    RequestStatus.REOPENED,
]


def _require_staff(ctx: OrgContext) -> None:
    if ctx.role not in STAFF:
        raise AppError(403, "forbidden", "Only dispatchers and administrators manage plans")


def _today(timezone: str) -> date:
    return datetime.now(ZoneInfo(timezone)).date()


def _plan_out(db: Session, plan: MaintenancePlan) -> PlanOut:
    asset = db.get(Asset, plan.asset_id)
    count = db.scalar(select(func.count()).where(ServiceRequest.plan_id == plan.id)) or 0
    last = db.scalar(
        select(func.max(ServiceRequest.plan_date)).where(ServiceRequest.plan_id == plan.id)
    )
    next_date = None
    if plan.is_active and asset is not None and asset.status != AssetStatus.RETIRED:
        # the next event after the latest generated one (or the first date if none yet)
        if last is None:
            next_date = plan.first_date
        else:
            next_date = next_occurrence(plan.first_date, Frequency(plan.frequency), last)
    return PlanOut(
        id=plan.id,
        asset_id=plan.asset_id,
        asset_name=asset.name if asset else "?",
        category_id=plan.category_id,
        title=plan.title,
        description=plan.description,
        priority=plan.priority,
        frequency=plan.frequency,
        first_date=plan.first_date,
        is_active=plan.is_active,
        next_date=next_date,
        generated_count=count,
        created_at=plan.created_at,
    )


def create_plan(db: Session, ctx: OrgContext, data: PlanIn) -> PlanOut:
    _require_staff(ctx)
    asset = db.scalar(
        select(Asset).where(Asset.id == data.asset_id, Asset.organization_id == ctx.org_id)
    )
    if asset is None:
        raise AppError(404, "asset_not_found", "Asset not found")
    if asset.status == AssetStatus.RETIRED:  # ASSET-04
        raise AppError(422, "asset_retired", "A retired asset cannot get a maintenance plan")
    category = db.scalar(
        select(ServiceCategory).where(
            ServiceCategory.id == data.category_id,
            ServiceCategory.organization_id == ctx.org_id,
            ServiceCategory.is_active.is_(True),
        )
    )
    if category is None:
        raise AppError(404, "category_not_found", "Category not found")
    plan = MaintenancePlan(
        organization_id=ctx.org_id,
        asset_id=asset.id,
        category_id=category.id,
        title=data.title.strip(),
        description=data.description.strip(),
        priority=data.priority,
        frequency=data.frequency,
        first_date=data.first_date,
        created_by_user_id=ctx.user.id,
    )
    db.add(plan)
    db.flush()
    record_audit(
        db,
        action="plan.created",
        object_type="maintenance_plan",
        object_id=plan.id,
        organization_id=ctx.org_id,
        actor_user_id=ctx.user.id,
        after={"asset_id": asset.id, "frequency": data.frequency},
    )
    db.commit()
    return _plan_out(db, plan)


def list_plans(db: Session, ctx: OrgContext) -> list[PlanOut]:
    _require_staff(ctx)
    plans = db.scalars(
        select(MaintenancePlan)
        .where(MaintenancePlan.organization_id == ctx.org_id)
        .order_by(MaintenancePlan.id.desc())
    )
    return [_plan_out(db, p) for p in plans]


def disable_plan(db: Session, ctx: OrgContext, plan_id: int) -> PlanOut:
    """Stops future generation; requests already created stay untouched (PM-04)."""
    _require_staff(ctx)
    plan = db.scalar(
        select(MaintenancePlan).where(
            MaintenancePlan.id == plan_id, MaintenancePlan.organization_id == ctx.org_id
        )
    )
    if plan is None:
        raise AppError(404, "plan_not_found", "Plan not found")
    if plan.is_active:
        plan.is_active = False
        plan.disabled_at = datetime.now(UTC)
        record_audit(
            db,
            action="plan.disabled",
            object_type="maintenance_plan",
            object_id=plan.id,
            organization_id=ctx.org_id,
            actor_user_id=ctx.user.id,
        )
        db.commit()
    return _plan_out(db, plan)


def _description(plan: MaintenancePlan, day: date) -> str:
    base = plan.description.strip()[:2800]
    note = f"Planned {plan.frequency.lower()} maintenance for {day.isoformat()}."
    return f"{base}\n\n{note}" if base else note


def generate(db: Session, org_id: int, as_of: date) -> tuple[int, int]:
    """Create one request per due event date of every active plan, up to and including `as_of`.

    Repeating or running it in parallel never duplicates an event: the database has a unique
    (plan, date) constraint and the insert silently skips existing rows (PM-02, PM-03).
    A retired asset stops its plan automatically (PM-04).
    """
    created = skipped = 0
    plans = list(
        db.scalars(
            select(MaintenancePlan).where(
                MaintenancePlan.organization_id == org_id, MaintenancePlan.is_active.is_(True)
            )
        )
    )
    for plan in plans:
        asset = db.get(Asset, plan.asset_id)
        if asset is None or asset.status == AssetStatus.RETIRED:
            continue
        for day in occurrences(plan.first_date, Frequency(plan.frequency), as_of):
            new_id = db.execute(
                insert(ServiceRequest)
                .values(
                    organization_id=org_id,
                    title=plan.title[:120],
                    description=_description(plan, day),
                    category_id=plan.category_id,
                    property_id=asset.property_id,
                    asset_id=asset.id,
                    priority=plan.priority,
                    status=RequestStatus.SUBMITTED,
                    created_by_user_id=plan.created_by_user_id,
                    plan_id=plan.id,
                    plan_date=day,
                )
                .on_conflict_do_nothing(index_elements=["plan_id", "plan_date"])
                .returning(ServiceRequest.id)
            ).scalar()
            if new_id is None:
                skipped += 1
                continue
            db.add(
                RequestStatusHistory(
                    organization_id=org_id,
                    request_id=new_id,
                    from_status=None,
                    to_status=RequestStatus.SUBMITTED,
                    actor_user_id=plan.created_by_user_id,
                    reason=f"Generated by plan #{plan.id}",
                )
            )
            record_audit(
                db,
                action="plan.request_generated",
                object_type="service_request",
                object_id=new_id,
                organization_id=org_id,
                after={"plan_id": plan.id, "plan_date": day.isoformat()},
            )
            notify_staff(
                db,
                org_id=org_id,
                type="maintenance_due",
                title=f"Planned maintenance: {plan.title}",
                body=day.isoformat(),
                request_id=new_id,
            )
            created += 1
        db.commit()
    return created, skipped


def generate_for_org(db: Session, ctx: OrgContext, as_of: date | None) -> GenerateOut:
    _require_staff(ctx)
    day = as_of or _today(ctx.organization.timezone)
    created, skipped = generate(db, ctx.org_id, day)
    return GenerateOut(as_of=day, created_requests=created, skipped_existing=skipped)


def generate_everywhere(db: Session, as_of: date | None) -> list[tuple[str, date, int, int]]:
    """Used by the local command: every active organization, today unless a date is given."""
    results = []
    for org in db.scalars(select(Organization).where(Organization.is_active.is_(True))):
        day = as_of or _today(org.timezone)
        created, skipped = generate(db, org.id, day)
        results.append((org.name, day, created, skipped))
    return results


def plan_requests(db: Session, ctx: OrgContext, plan_id: int) -> list[PlanRequestOut]:
    """History of what a plan has generated (PM-05)."""
    _require_staff(ctx)
    rows = db.execute(
        select(ServiceRequest.id, ServiceRequest.plan_date, ServiceRequest.status)
        .where(ServiceRequest.plan_id == plan_id, ServiceRequest.organization_id == ctx.org_id)
        .order_by(ServiceRequest.plan_date.desc())
    )
    return [
        PlanRequestOut(request_id=i, plan_date=d, status=s.value)
        for i, d, s in rows
        if d is not None
    ]


def asset_summary(db: Session, ctx: OrgContext, asset_id: int) -> dict[str, object]:
    """Open work, last completed service and the next planned maintenance (ASSET-05)."""
    _require_staff(ctx)
    asset = db.scalar(
        select(Asset).where(Asset.id == asset_id, Asset.organization_id == ctx.org_id)
    )
    if asset is None:
        raise AppError(404, "asset_not_found", "Asset not found")
    open_count = db.scalar(
        select(func.count()).where(
            ServiceRequest.asset_id == asset.id,
            ServiceRequest.organization_id == ctx.org_id,
            ServiceRequest.status.in_(OPEN),
        )
    )
    last_done = db.scalar(
        select(func.max(RequestStatusHistory.created_at))
        .join(ServiceRequest, ServiceRequest.id == RequestStatusHistory.request_id)
        .where(
            ServiceRequest.asset_id == asset.id,
            RequestStatusHistory.to_status == RequestStatus.COMPLETED,
        )
    )
    upcoming: list[date] = []
    if asset.status != AssetStatus.RETIRED:
        today = _today(ctx.organization.timezone)
        for plan in db.scalars(
            select(MaintenancePlan).where(
                MaintenancePlan.asset_id == asset.id,
                MaintenancePlan.organization_id == ctx.org_id,
                MaintenancePlan.is_active.is_(True),
            )
        ):
            upcoming.append(next_occurrence(plan.first_date, Frequency(plan.frequency), today))
    return {
        "asset_id": asset.id,
        "code": asset.code,
        "name": asset.name,
        "status": asset.status.value,
        "open_requests": open_count or 0,
        "last_completed_at": last_done,
        "next_planned": min(upcoming) if upcoming else None,
    }
