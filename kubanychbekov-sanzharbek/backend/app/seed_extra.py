"""Extra demo data (SEED-02/03): maintenance plans, estimates in several states, SLA cases and a
scheduling-conflict candidate. INSERT-ONLY and idempotent: each organization is marked with an audit
event, so running it again changes nothing, and nothing existing is modified or deleted.

Run:  python -m app.seed_extra
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_sessionmaker
from app.domain.enums import (
    ACTIVE_ASSIGNMENT_STATUSES,
    AssetStatus,
    EstimateStatus,
    Priority,
    RequestStatus,
)
from app.domain.maintenance import Frequency
from app.domain.sla import budget_minutes, sla_state, working_minutes
from app.models import (
    Asset,
    Assignment,
    AuditEvent,
    Estimate,
    EstimateLine,
    InventoryItem,
    Organization,
    OrganizationMembership,
    RequestStatusHistory,
    ServiceCategory,
    ServiceRequest,
    TechnicianSkill,
)
from app.services.maintenance import generate
from app.services.sla import load_calendar

MARKER = "seed.extra"
INVENTORY_MARKER = "seed.extra.inventory"
PARTS = [
    ("FLT-01", "Air filter", "pcs", "12", "5", 85_000),
    ("TPE-02", "Sealing tape", "m", "40", "10", 1_500),
    ("PMP-03", "Circulation pump", "pcs", "2", "3", 640_000),  # below its level: low stock
    ("CAP-04", "Capacitor 40uF", "pcs", "3", "3", 32_000),  # exactly at its level: low stock
    ("GAS-05", "Refrigerant R410A", "kg", "18.5", "6", 210_000),
]


# SEED-01: with the base seed this brings the demo to 20 stock items and 16 pieces of equipment
EXTRA_PARTS = [
    ("FAN-06", "Fan motor 120W", "pcs", "6", "2", 450_000),
    ("BLT-07", "Drive belt B-52", "pcs", "15", "4", 18_000),
    ("OIL-08", "Machine oil 1L", "l", "30", "8", 12_000),
    ("LMP-09", "LED panel 40W", "pcs", "25", "6", 28_000),
    ("FUS-10", "Fuse 16A", "pcs", "100", "20", 800),
]


def seed_top_up(db: Session) -> None:
    """Idempotent: adds missing extra stock items and one more asset per organization."""
    for org in db.scalars(select(Organization)):
        for code, name, unit, stock, threshold, price in EXTRA_PARTS:
            exists = db.scalar(
                select(InventoryItem.id).where(
                    InventoryItem.organization_id == org.id, InventoryItem.code == code
                )
            )
            if exists is None:
                db.add(
                    InventoryItem(
                        organization_id=org.id,
                        code=code,
                        name=name,
                        unit=unit,
                        stock=Decimal(stock),
                        reorder_threshold=Decimal(threshold),
                        unit_price_cents=price,
                    )
                )
        template = db.scalars(
            select(Asset).where(Asset.organization_id == org.id).order_by(Asset.id)
        ).first()
        if template is not None:
            code = f"{template.code.split('-')[0]}-008"
            has = db.scalar(
                select(Asset.id).where(Asset.organization_id == org.id, Asset.code == code)
            )
            if has is None:
                db.add(
                    Asset(
                        organization_id=org.id,
                        property_id=template.property_id,
                        code=code,
                        name="Air handling unit 8",
                        asset_type="HVAC unit",
                        status=AssetStatus.ACTIVE,
                    )
                )
        db.commit()


def _staff_id(db: Session, org_id: int) -> int:
    return (
        db.scalars(
            select(OrganizationMembership.user_id).where(
                OrganizationMembership.organization_id == org_id,
                OrganizationMembership.role == "dispatcher",
            )
        ).first()
        or 0
    )


def _customer_id(db: Session, org_id: int) -> int:
    return (
        db.scalars(
            select(OrganizationMembership.user_id).where(
                OrganizationMembership.organization_id == org_id,
                OrganizationMembership.role == "customer",
            )
        ).first()
        or 0
    )


def _new_request(
    db, org_id, *, category, prop_id, asset_id, title, priority, status, created, author
):
    req = ServiceRequest(
        organization_id=org_id,
        title=title,
        description="Demo request created by the extra seed for the acceptance scenarios.",
        category_id=category.id,
        property_id=prop_id,
        asset_id=asset_id,
        priority=priority,
        status=status,
        created_by_user_id=author,
        created_at=created,
        updated_at=created,
    )
    db.add(req)
    db.flush()
    db.add(
        RequestStatusHistory(
            organization_id=org_id,
            request_id=req.id,
            from_status=None,
            to_status=RequestStatus.SUBMITTED,
            actor_user_id=author,
            created_at=created,
        )
    )
    return req


def _estimate(
    db,
    org_id,
    request_id,
    *,
    version,
    status,
    staff,
    submitted=None,
    decided=None,
    reason=None,
    minutes=90,
    rate=120_000,
    lines=(),
):
    est = Estimate(
        organization_id=org_id,
        request_id=request_id,
        version=version,
        status=status,
        labor_minutes=minutes,
        labor_rate_cents=rate,
        created_by_user_id=staff,
        submitted_at=submitted,
        decided_at=decided,
        decision_reason=reason,
        decided_by_user_id=None,
    )
    db.add(est)
    db.flush()
    for description, quantity, price in lines:
        db.add(
            EstimateLine(
                organization_id=org_id,
                estimate_id=est.id,
                description=description,
                quantity=Decimal(quantity),
                unit_price_cents=price,
            )
        )


def _at_risk_creation_time(calendar, priority: Priority, now: datetime) -> datetime:
    """A creation time for which 75%-100% of the SLA budget is used right now."""
    budget = budget_minutes(priority)
    candidate = now
    for _ in range(60 * 24 * 14 // 30):  # walk back in 30-minute steps for up to two weeks
        candidate -= timedelta(minutes=30)
        used = working_minutes(
            candidate, now, tz=calendar.tz, weekly=calendar.weekly, holidays=calendar.holidays
        )
        if sla_state(budget, used)[0] == "AT_RISK":
            return candidate
    return now - timedelta(days=1)


def seed_org(db: Session, org: Organization) -> list[str]:
    done: list[str] = []
    now = datetime.now(UTC)
    staff, customer = _staff_id(db, org.id), _customer_id(db, org.id)
    category = db.scalars(
        select(ServiceCategory).where(ServiceCategory.organization_id == org.id)
    ).first()
    assets = list(
        db.scalars(select(Asset).where(Asset.organization_id == org.id).order_by(Asset.id))
    )
    if category is None or len(assets) < 3 or not staff or not customer:
        return ["skipped: missing base data"]

    # --- maintenance plans (one is already due and gets generated)
    from app.models import MaintenancePlan

    plans = [
        (
            "Weekly filter inspection",
            assets[0],
            Frequency.WEEKLY,
            (now - timedelta(days=15)).date(),
        ),
        ("Monthly safety check", assets[1], Frequency.MONTHLY, (now - timedelta(days=40)).date()),
        ("Quarterly deep service", assets[2], Frequency.MONTHLY, (now + timedelta(days=20)).date()),
    ]
    for title, asset, frequency, first in plans:
        db.add(
            MaintenancePlan(
                organization_id=org.id,
                asset_id=asset.id,
                category_id=category.id,
                title=title,
                description="Standard preventive routine.",
                priority=Priority.NORMAL,
                frequency=frequency.value,
                first_date=first,
                created_by_user_id=staff,
            )
        )
    db.flush()
    created, _ = generate(db, org.id, now.date())
    done.append(f"{len(plans)} plans, {created} generated requests")

    # --- estimates in several states (EST-*), each on its own accepted request
    for index, (state, version_note) in enumerate(
        [
            (EstimateStatus.APPROVED, "approved"),
            (EstimateStatus.AWAITING_APPROVAL, "awaiting"),
            (EstimateStatus.REJECTED, "rejected + replaced by v2"),
        ]
    ):
        asset = assets[index]
        req = _new_request(
            db,
            org.id,
            category=category,
            prop_id=asset.property_id,
            asset_id=asset.id,
            title=f"Estimate demo: {version_note}",
            priority=Priority.NORMAL,
            status=RequestStatus.ACCEPTED,
            created=now - timedelta(hours=30 + index),
            author=customer,
        )
        submitted = now - timedelta(hours=20)
        lines = [("Air filter", "2", 85_000), ("Sealing tape", "3.5", 1_500)]
        if state == EstimateStatus.REJECTED:
            _estimate(
                db,
                org.id,
                req.id,
                version=1,
                status=EstimateStatus.SUPERSEDED,
                staff=staff,
                submitted=submitted,
                decided=now - timedelta(hours=10),
                reason="Too expensive",
                lines=lines,
            )
            _estimate(
                db,
                org.id,
                req.id,
                version=2,
                status=EstimateStatus.AWAITING_APPROVAL,
                staff=staff,
                submitted=now - timedelta(hours=2),
                minutes=60,
                lines=lines[:1],
            )
        else:
            _estimate(
                db,
                org.id,
                req.id,
                version=1,
                status=state,
                staff=staff,
                submitted=submitted,
                decided=now - timedelta(hours=10) if state == EstimateStatus.APPROVED else None,
                lines=lines,
            )
    done.append("3 requests with estimates (approved / awaiting / rejected+v2)")

    # --- SLA cases: an at-risk request (the base seed already has on-track and overdue ones)
    calendar = load_calendar(db, org.id, org.timezone)
    created_at = _at_risk_creation_time(calendar, Priority.HIGH, now)
    _new_request(
        db,
        org.id,
        category=category,
        prop_id=assets[0].property_id,
        asset_id=None,
        title="SLA demo: at risk",
        priority=Priority.HIGH,
        status=RequestStatus.TRIAGED,
        created=created_at,
        author=customer,
    )
    done.append("1 at-risk SLA request")

    # --- a conflict candidate: a triaged request wanting the time a technician is already booked
    booked = db.scalar(
        select(Assignment)
        .where(
            Assignment.organization_id == org.id,
            Assignment.status.in_(ACTIVE_ASSIGNMENT_STATUSES),
            Assignment.start_at > now,
        )
        .order_by(Assignment.start_at)
    )
    if booked is not None:
        skills = set(
            db.scalars(
                select(TechnicianSkill.skill).where(
                    TechnicianSkill.technician_id == booked.technician_id
                )
            )
        )
        match = next(
            (
                c
                for c in db.scalars(
                    select(ServiceCategory).where(ServiceCategory.organization_id == org.id)
                )
                if set(c.required_skills) <= skills
            ),
            category,
        )
        req = _new_request(
            db,
            org.id,
            category=match,
            prop_id=assets[0].property_id,
            asset_id=None,
            title="Scheduling demo: wants an already booked slot",
            priority=Priority.NORMAL,
            status=RequestStatus.TRIAGED,
            created=now - timedelta(hours=1),
            author=customer,
        )
        req.desired_start, req.desired_end = booked.start_at, booked.end_at
        done.append("1 conflict-candidate request")
    return done


def seed_inventory(db: Session) -> None:
    for org in db.scalars(select(Organization)):
        marker = db.scalar(
            select(AuditEvent.id).where(
                AuditEvent.organization_id == org.id, AuditEvent.action == INVENTORY_MARKER
            )
        )
        if marker is not None:
            continue
        for code, name, unit, stock, threshold, price in PARTS:
            exists = db.scalar(
                select(InventoryItem.id).where(
                    InventoryItem.organization_id == org.id, InventoryItem.code == code
                )
            )
            if exists is None:
                db.add(
                    InventoryItem(
                        organization_id=org.id,
                        code=code,
                        name=name,
                        unit=unit,
                        stock=Decimal(stock),
                        reorder_threshold=Decimal(threshold),
                        unit_price_cents=price,
                    )
                )
        db.add(
            AuditEvent(
                organization_id=org.id,
                action=INVENTORY_MARKER,
                object_type="organization",
                object_id=str(org.id),
                after={"items": len(PARTS)},
            )
        )
        db.commit()
        print(f"inventory for {org.name}: {len(PARTS)} items")


def main() -> None:
    with get_sessionmaker()() as db:
        seed_inventory(db)
        seed_top_up(db)
        for org in db.scalars(select(Organization)):
            marker = db.scalar(
                select(AuditEvent.id).where(
                    AuditEvent.organization_id == org.id, AuditEvent.action == MARKER
                )
            )
            if marker is not None:
                print(f"skip {org.name} (extra data already present)")
                continue
            summary = seed_org(db, org)
            db.add(
                AuditEvent(
                    organization_id=org.id,
                    action=MARKER,
                    object_type="organization",
                    object_id=str(org.id),
                    after={"summary": summary},
                )
            )
            db.commit()
            print(f"extra data for {org.name}: " + "; ".join(summary))


if __name__ == "__main__":
    main()
