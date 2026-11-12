"""Deterministic demo data. Run: python -m app.seed   (safe to repeat: existing orgs are skipped).

All accounts share ONE throw-away demo password. It is for local demos only.
"""

import random
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import get_sessionmaker
from app.domain.enums import AssetStatus, AssignmentStatus, Priority, RequestStatus, Role
from app.models import (
    Asset,
    Assignment,
    InventoryItem,
    Organization,
    OrganizationMembership,
    Property,
    RequestStatusHistory,
    ServiceCategory,
    ServiceRequest,
    TechnicianAbsence,
    TechnicianAvailability,
    TechnicianProfile,
    TechnicianSkill,
    User,
)

DEMO_PASSWORD = "Demo-2345!"  # demo-only, never reuse
S = RequestStatus
TZ = ZoneInfo("Asia/Bishkek")
SLOT = timedelta(hours=2)

# Path of states a request went through to reach its current state.
PATHS: dict[RequestStatus, list[RequestStatus]] = {
    S.SUBMITTED: [S.SUBMITTED],
    S.TRIAGED: [S.SUBMITTED, S.TRIAGED],
    S.SCHEDULED: [S.SUBMITTED, S.TRIAGED, S.SCHEDULED],
    S.ACCEPTED: [S.SUBMITTED, S.TRIAGED, S.SCHEDULED, S.ACCEPTED],
    S.IN_PROGRESS: [S.SUBMITTED, S.TRIAGED, S.SCHEDULED, S.ACCEPTED, S.IN_PROGRESS],
    S.BLOCKED: [S.SUBMITTED, S.TRIAGED, S.SCHEDULED, S.ACCEPTED, S.IN_PROGRESS, S.BLOCKED],
    S.COMPLETED: [S.SUBMITTED, S.TRIAGED, S.SCHEDULED, S.ACCEPTED, S.IN_PROGRESS, S.COMPLETED],
    S.CLOSED: [
        S.SUBMITTED,
        S.TRIAGED,
        S.SCHEDULED,
        S.ACCEPTED,
        S.IN_PROGRESS,
        S.COMPLETED,
        S.CLOSED,
    ],
    S.CANCELED: [S.SUBMITTED, S.TRIAGED, S.CANCELED],
    S.REOPENED: [
        S.SUBMITTED,
        S.TRIAGED,
        S.SCHEDULED,
        S.ACCEPTED,
        S.IN_PROGRESS,
        S.COMPLETED,
        S.REOPENED,
    ],
}

# Requests in these states have (or had) a technician booked.
BOOKED_NOW = {S.SCHEDULED: AssignmentStatus.SCHEDULED, S.ACCEPTED: AssignmentStatus.ACCEPTED}
BOOKED_PAST = {
    S.IN_PROGRESS: AssignmentStatus.IN_PROGRESS,
    S.BLOCKED: AssignmentStatus.BLOCKED,
    S.COMPLETED: AssignmentStatus.COMPLETED,
    S.CLOSED: AssignmentStatus.COMPLETED,
}

STATUS_WEIGHTS: list[tuple[RequestStatus, int]] = [
    (S.SUBMITTED, 8),
    (S.TRIAGED, 7),
    (S.SCHEDULED, 6),
    (S.ACCEPTED, 4),
    (S.IN_PROGRESS, 8),
    (S.BLOCKED, 2),
    (S.COMPLETED, 7),
    (S.CLOSED, 6),
    (S.CANCELED, 3),
    (S.REOPENED, 3),
]

PROBLEMS = [
    ("Air conditioner is not cooling", "The unit runs but the room stays warm and makes noise."),
    ("Elevator stops between floors", "The elevator occasionally stops and needs a restart."),
    ("Water leak in the bathroom", "A leak under the sink floods the cabinet every morning."),
    ("Ventilation fan does not work", "The extractor fan makes no sound and no air flows out."),
    ("Generator fails to start", "The backup generator cranks but does not start on tests."),
    ("Boiler pressure keeps dropping", "Pressure falls below the safe level within a few hours."),
    ("Lighting flickers in the corridor", "Several lamps flicker and one circuit trips often."),
    ("Pump makes a loud grinding noise", "The circulation pump grinds and vibrates when running."),
]

ORGS = [
    {
        "key": "a",
        "name": "AIT Facility",
        "categories": [
            ("HVAC", ["hvac"]),
            ("Plumbing", ["plumbing"]),
            ("Electrical", ["electrical"]),
            ("Elevators", ["elevators"]),
        ],
        "properties": [
            ("Building A", "12 Chui Ave, Bishkek"),
            ("Building B", "14 Chui Ave, Bishkek"),
            ("Dormitory No. 2", "5 Toktogul St, Bishkek"),
            ("Server Building C", "8 Manas Ave, Bishkek"),
            ("Warehouse D", "22 Ankara St, Bishkek"),
        ],
        "customers": ["Aidar Sultanov", "Nurzat Bekova", "Timur Asanov"],
        "technicians": [
            ("Erlan Moldobekov", ["hvac", "electrical"]),
            ("Azamat Kenzhebaev", ["plumbing", "hvac"]),
            ("Timur Osmonov", ["elevators", "electrical"]),
            ("Aigul Seitova", ["plumbing", "electrical"]),
        ],
        "requests": 30,
    },
    {
        "key": "b",
        "name": "Nord Service",
        "categories": [
            ("Ventilation", ["ventilation"]),
            ("Heating", ["heating"]),
            ("Fire safety", ["fire safety"]),
            ("Cleaning equipment", ["cleaning equipment"]),
        ],
        "properties": [
            ("North Mall", "3 Sovetskaya St, Bishkek"),
            ("Office Park", "90 Kievskaya St, Bishkek"),
            ("Clinic No. 5", "17 Mira Ave, Bishkek"),
            ("School No. 61", "41 Frunze St, Bishkek"),
            ("Depot", "2 Industrial Rd, Bishkek"),
        ],
        "customers": ["Elena Petrova", "Bakyt Ismailov"],
        "technicians": [
            ("Marat Zhunusov", ["ventilation", "heating"]),
            ("Dinara Kurmanova", ["fire safety", "cleaning equipment", "ventilation"]),
        ],
        "requests": 24,
    },
]
INVENTORY = [
    # code, name, unit, stock, reorder threshold, price in tyiyn
    ("FLT-01", "Air filter", "pcs", "12", "5", 85_000),
    ("REF-410", "Refrigerant R410A", "kg", "4", "5", 420_000),  # low stock on purpose
    ("BLT-02", "Drive belt", "pcs", "18", "10", 120_000),
    ("CLN-03", "Cleaning agent", "l", "3", "5", 60_000),  # low stock on purpose
    ("TAP-04", "Sealing tape", "m", "50", "20", 1_500),
    ("PIP-05", "Copper pipe 1/2", "m", "30", "10", 35_000),
    ("BLB-06", "LED lamp", "pcs", "40", "15", 22_000),
    ("FUS-07", "Fuse 16A", "pcs", "25", "10", 9_000),
    ("GSK-08", "Gasket set", "set", "14", "6", 48_000),
    ("OIL-09", "Machine oil", "l", "20", "8", 55_000),
]

ASSET_TYPES = ["HVAC unit", "Elevator", "Pump", "Generator", "Boiler"]


def _user(db: Session, email: str, name: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, full_name=name, password_hash=hash_password(DEMO_PASSWORD))
        db.add(user)
        db.flush()
    return user


def _member(db: Session, org: Organization, user: User, role: Role) -> None:
    db.add(OrganizationMembership(organization_id=org.id, user_id=user.id, role=role))


def _next_start(cursor: datetime) -> datetime:
    """Move to the next free working slot (Mon-Fri 09:00-18:00, Asia/Bishkek)."""
    local = cursor.astimezone(TZ)
    while True:
        if local.weekday() >= 5 or local.hour >= 16:
            local = datetime.combine(local.date() + timedelta(days=1), time(9, 0), TZ)
            continue
        if local.hour < 9:
            local = datetime.combine(local.date(), time(9, 0), TZ)
        return local.astimezone(UTC)


def seed_org(db: Session, spec: dict, rng: random.Random, shared: User | None) -> User:
    org = Organization(name=spec["name"], timezone="Asia/Bishkek")
    db.add(org)
    db.flush()
    key = spec["key"]
    now = datetime.now(UTC)

    admin = _user(db, f"admin.{key}@fixflow.test", f"Admin {key.upper()}")
    dispatcher = _user(db, f"dispatcher.{key}@fixflow.test", f"Dispatcher {key.upper()}")
    _member(db, org, admin, Role.ADMIN)
    _member(db, org, dispatcher, Role.DISPATCHER)

    customers: list[User] = []
    for i, name in enumerate(spec["customers"], start=1):
        user = _user(db, f"customer{i}.{key}@fixflow.test", name)
        _member(db, org, user, Role.CUSTOMER)
        customers.append(user)
    if shared is not None:  # same person, different role in the second organization
        _member(db, org, shared, Role.CUSTOMER)
        customers.append(shared)

    categories = [
        ServiceCategory(
            organization_id=org.id,
            name=name,
            description=f"{name} service",
            default_duration_min=60 + 30 * i,
            required_skills=skills,
        )
        for i, (name, skills) in enumerate(spec["categories"])
    ]
    properties = [
        Property(organization_id=org.id, name=n, address=a) for n, a in spec["properties"]
    ]
    db.add_all([*categories, *properties])
    db.flush()

    # technicians: profile, skills, Mon-Fri 09:00-18:00; the last one is away next week
    technicians: list[tuple[TechnicianProfile, list[str]]] = []
    for i, (name, skills) in enumerate(spec["technicians"], start=1):
        user = _user(db, f"tech{i}.{key}@fixflow.test", name)
        _member(db, org, user, Role.TECHNICIAN)
        profile = TechnicianProfile(organization_id=org.id, user_id=user.id)
        db.add(profile)
        db.flush()
        for skill in skills:
            db.add(TechnicianSkill(organization_id=org.id, technician_id=profile.id, skill=skill))
        for weekday in range(5):
            db.add(
                TechnicianAvailability(
                    organization_id=org.id,
                    technician_id=profile.id,
                    weekday=weekday,
                    start_time=time(9, 0),
                    end_time=time(18, 0),
                )
            )
        technicians.append((profile, skills))
    away = technicians[-1][0]
    monday_next = datetime.combine(
        datetime.now(TZ).date() + timedelta(days=7 - datetime.now(TZ).weekday()), time(0, 0), TZ
    )
    db.add(
        TechnicianAbsence(
            organization_id=org.id,
            technician_id=away.id,
            start_at=monday_next.astimezone(UTC),
            end_at=(monday_next + timedelta(days=3)).astimezone(UTC),
            reason="Annual leave",
        )
    )

    for code, name, unit, stock, threshold, price in INVENTORY:
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

    assets: list[Asset] = []
    for i in range(1, 8):
        prop = properties[i % len(properties)]
        kind = ASSET_TYPES[i % len(ASSET_TYPES)]
        assets.append(
            Asset(
                organization_id=org.id,
                property_id=prop.id,
                code=f"{key.upper()}-{i:03d}",
                name=f"{kind} {i}",
                asset_type=kind,
                status=AssetStatus.ACTIVE if i != 4 else AssetStatus.OUT_OF_SERVICE,
            )
        )
    db.add_all(assets)
    db.flush()

    all_statuses = list(RequestStatus)
    pool = [s for s, n in STATUS_WEIGHTS for _ in range(n)]
    past_cursor: dict[int, datetime] = {p.id: now - timedelta(days=13) for p, _ in technicians}
    future_cursor: dict[int, datetime] = {p.id: now + timedelta(hours=14) for p, _ in technicians}

    for index in range(spec["requests"]):
        # the first requests walk through every status, so each one is always represented
        status = all_statuses[index] if index < len(all_statuses) else rng.choice(pool)
        title, description = PROBLEMS[rng.randrange(len(PROBLEMS))]
        prop = rng.choice(properties)
        prop_assets = [a for a in assets if a.property_id == prop.id]
        category = rng.choice(categories)
        created = now - timedelta(
            days=rng.randrange(14), hours=rng.randrange(1, 12), minutes=rng.randrange(60)
        )
        author = rng.choice(customers)
        req = ServiceRequest(
            organization_id=org.id,
            title=title,
            description=description,
            category_id=category.id,
            property_id=prop.id,
            asset_id=rng.choice(prop_assets).id if prop_assets and rng.random() < 0.6 else None,
            priority=rng.choice([Priority.LOW, Priority.NORMAL, Priority.NORMAL, Priority.HIGH]),
            status=status,
            created_by_user_id=author.id,
            created_at=created,
            updated_at=created,
        )
        db.add(req)
        db.flush()

        moment = created
        previous = None
        for step in PATHS[status]:
            actor = author if step in {S.SUBMITTED, S.CLOSED, S.REOPENED} else dispatcher
            reason = "Demo data" if step in {S.CANCELED, S.BLOCKED, S.REOPENED} else None
            db.add(
                RequestStatusHistory(
                    organization_id=org.id,
                    request_id=req.id,
                    from_status=previous,
                    to_status=step,
                    actor_user_id=actor.id,
                    reason=reason,
                    created_at=moment,
                )
            )
            previous = step
            moment = min(now, moment + timedelta(hours=rng.randrange(1, 20)))
        req.updated_at = moment

        # a booking that matches the request's state, never overlapping another one
        if status in BOOKED_NOW or status in BOOKED_PAST or status == S.REOPENED:
            capable = [
                p
                for p, skills in technicians
                if set(category.required_skills) <= set(skills) and p is not away
            ]
            if capable:
                tech = rng.choice(capable)
                if status in BOOKED_NOW:
                    cursors, assign_status = future_cursor, BOOKED_NOW[status]
                else:
                    cursors = past_cursor
                    assign_status = BOOKED_PAST.get(status, AssignmentStatus.COMPLETED)
                start = _next_start(max(cursors[tech.id], created + timedelta(hours=2)))
                if status in BOOKED_PAST or status == S.REOPENED:
                    if start + SLOT > now:  # past work must have happened already
                        continue
                cursors[tech.id] = start + SLOT + timedelta(hours=1)
                db.add(
                    Assignment(
                        organization_id=org.id,
                        request_id=req.id,
                        technician_id=tech.id,
                        start_at=start,
                        end_at=start + SLOT,
                        timezone="Asia/Bishkek",
                        status=assign_status,
                        created_by_user_id=dispatcher.id,
                    )
                )
    return dispatcher


def main() -> None:
    rng = random.Random(1308)  # fixed seed -> same data shape every run
    with get_sessionmaker()() as db:
        shared = None
        for spec in ORGS:
            if db.scalar(select(Organization).where(Organization.name == spec["name"])):
                print(f"skip {spec['name']} (already seeded)")
                continue
            dispatcher = seed_org(db, spec, rng, shared)
            if spec["key"] == "a":
                shared = dispatcher  # dispatcher in A becomes a customer in B
            db.commit()
            print(f"seeded {spec['name']}")
    print(f"demo password for every seeded account: {DEMO_PASSWORD} (demo-only)")


if __name__ == "__main__":
    main()
