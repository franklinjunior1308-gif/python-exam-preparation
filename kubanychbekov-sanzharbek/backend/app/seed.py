"""Deterministic demo data. Run: python -m app.seed   (safe to repeat: existing orgs are skipped).

All accounts share ONE throw-away demo password. It is for local demos only.
"""

import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import get_sessionmaker
from app.domain.enums import AssetStatus, Priority, RequestStatus, Role
from app.models import (
    Asset,
    Organization,
    OrganizationMembership,
    Property,
    RequestStatusHistory,
    ServiceCategory,
    ServiceRequest,
    User,
)

DEMO_PASSWORD = "Demo-2345!"  # demo-only, never reuse
S = RequestStatus

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

# How many demo requests end in each state (sums to 54 across both organizations).
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
        "categories": ["HVAC", "Plumbing", "Electrical", "Elevators"],
        "properties": [
            ("Building A", "12 Chui Ave, Bishkek"),
            ("Building B", "14 Chui Ave, Bishkek"),
            ("Dormitory No. 2", "5 Toktogul St, Bishkek"),
            ("Server Building C", "8 Manas Ave, Bishkek"),
            ("Warehouse D", "22 Ankara St, Bishkek"),
        ],
        "customers": ["Aidar Sultanov", "Nurzat Bekova", "Timur Asanov"],
        "technicians": ["Erlan Moldobekov", "Azamat Kenzhebaev", "Timur Osmonov", "Aigul Seitova"],
        "requests": 30,
    },
    {
        "key": "b",
        "name": "Nord Service",
        "categories": ["Ventilation", "Heating", "Fire safety", "Cleaning equipment"],
        "properties": [
            ("North Mall", "3 Sovetskaya St, Bishkek"),
            ("Office Park", "90 Kievskaya St, Bishkek"),
            ("Clinic No. 5", "17 Mira Ave, Bishkek"),
            ("School No. 61", "41 Frunze St, Bishkek"),
            ("Depot", "2 Industrial Rd, Bishkek"),
        ],
        "customers": ["Elena Petrova", "Bakyt Ismailov"],
        "technicians": ["Marat Zhunusov", "Dinara Kurmanova"],
        "requests": 24,
    },
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


def seed_org(db: Session, spec: dict, rng: random.Random, shared: User | None) -> User:
    org = Organization(name=spec["name"], timezone="Asia/Bishkek")
    db.add(org)
    db.flush()
    key = spec["key"]

    admin = _user(db, f"admin.{key}@fixflow.test", f"Admin {key.upper()}")
    dispatcher = _user(db, f"dispatcher.{key}@fixflow.test", f"Dispatcher {key.upper()}")
    _member(db, org, admin, Role.ADMIN)
    _member(db, org, dispatcher, Role.DISPATCHER)

    customers: list[User] = []
    for i, name in enumerate(spec["customers"], start=1):
        user = _user(db, f"customer{i}.{key}@fixflow.test", name)
        _member(db, org, user, Role.CUSTOMER)
        customers.append(user)
    for i, name in enumerate(spec["technicians"], start=1):
        _member(db, org, _user(db, f"tech{i}.{key}@fixflow.test", name), Role.TECHNICIAN)

    if shared is not None:  # same person, different role in the second organization
        _member(db, org, shared, Role.CUSTOMER)
        customers.append(shared)

    categories = [
        ServiceCategory(
            organization_id=org.id,
            name=n,
            description=f"{n} service",
            default_duration_min=60 + 30 * i,
        )
        for i, n in enumerate(spec["categories"])
    ]
    properties = [
        Property(organization_id=org.id, name=n, address=a) for n, a in spec["properties"]
    ]
    db.add_all([*categories, *properties])
    db.flush()

    assets: list[Asset] = []
    for i in range(1, 8 if key == "a" else 8):
        prop = properties[i % len(properties)]
        assets.append(
            Asset(
                organization_id=org.id,
                property_id=prop.id,
                code=f"{key.upper()}-{i:03d}",
                name=f"{ASSET_TYPES[i % len(ASSET_TYPES)]} {i}",
                asset_type=ASSET_TYPES[i % len(ASSET_TYPES)],
                status=AssetStatus.ACTIVE if i != 4 else AssetStatus.OUT_OF_SERVICE,
            )
        )
    db.add_all(assets)
    db.flush()

    pool = [s for s, n in STATUS_WEIGHTS for _ in range(n)]
    now = datetime.now(UTC)
    for index in range(spec["requests"]):
        # the first requests walk through every status, so each one is always represented
        status = list(RequestStatus)[index] if index < len(RequestStatus) else rng.choice(pool)
        title, description = PROBLEMS[rng.randrange(len(PROBLEMS))]
        prop = rng.choice(properties)
        prop_assets = [a for a in assets if a.property_id == prop.id]
        created = now - timedelta(
            days=rng.randrange(14), hours=rng.randrange(1, 12), minutes=rng.randrange(60)
        )
        author = rng.choice(customers)
        req = ServiceRequest(
            organization_id=org.id,
            title=title,
            description=description,
            category_id=rng.choice(categories).id,
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
