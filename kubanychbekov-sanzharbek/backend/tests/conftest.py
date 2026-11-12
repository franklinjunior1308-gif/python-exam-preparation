"""Integration fixtures. They need PostgreSQL: set TEST_DATABASE_URL (see docs/VERIFICATION.md).

The URL is exported as DATABASE_URL *before* the app is imported, so the app and the tests share
one throw-away database. Nothing here ever touches the development database.
"""

import os
import tempfile
from collections.abc import Iterator
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

TEST_URL = os.environ.get("TEST_DATABASE_URL")
if TEST_URL:
    os.environ["DATABASE_URL"] = TEST_URL
# uploaded test photos go to a throw-away folder, never to the real upload volume
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="fixflow-test-uploads-")

TZ = ZoneInfo("Asia/Bishkek")
PASSWORD = "Test-Pass-1!"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if TEST_URL:
        return
    skip = pytest.mark.skip(reason="TEST_DATABASE_URL is not set (needs PostgreSQL)")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


def _ensure_database(url: str) -> None:
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    target = make_url(url)
    admin = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": target.database}
        )
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    admin.dispose()


@pytest.fixture(scope="session")
def engine():
    if not TEST_URL:
        pytest.skip("TEST_DATABASE_URL is not set")
    from sqlalchemy import text

    from app import models  # noqa: F401  (register every table)
    from app.db.base import Base
    from app.db.session import get_engine

    _ensure_database(TEST_URL)
    eng = get_engine()
    with eng.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    return eng


class World:
    """Two organizations with one user per role, built fresh for every test."""

    def __init__(self) -> None:
        self.ids: dict[str, int] = {}

    def __getitem__(self, key: str) -> int:
        return self.ids[key]


def monday_based(day_offset: int, hour: int, minute: int = 0) -> datetime:
    """A future working-day time in Bishkek: next Monday + offset days, as UTC."""
    today = datetime.now(TZ).date()
    monday = today + timedelta(days=7 - today.weekday())
    local = datetime.combine(monday + timedelta(days=day_offset), time(hour, minute), TZ)
    return local.astimezone(UTC)


@pytest.fixture
def world(engine) -> Iterator[World]:
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    from app.core.security import hash_password
    from app.domain.enums import Priority, RequestStatus, Role
    from app.models import (
        Organization,
        OrganizationMembership,
        Property,
        ServiceCategory,
        ServiceRequest,
        TechnicianAvailability,
        TechnicianProfile,
        TechnicianSkill,
        User,
    )

    with engine.begin() as conn:  # clean slate for every test
        conn.execute(text("TRUNCATE organizations RESTART IDENTITY CASCADE"))
        conn.execute(text("TRUNCATE users RESTART IDENTITY CASCADE"))

    w = World()
    with Session(engine) as db:
        password_hash = hash_password(PASSWORD)

        def user(email: str, name: str) -> User:
            row = User(email=email, full_name=name, password_hash=password_hash)
            db.add(row)
            db.flush()
            return row

        for key, name in (("a", "Org A"), ("b", "Org B")):
            org = Organization(name=name, timezone="Asia/Bishkek")
            db.add(org)
            db.flush()
            w.ids[f"org_{key}"] = org.id
            category = ServiceCategory(
                organization_id=org.id, name="HVAC", required_skills=["hvac"]
            )
            prop = Property(organization_id=org.id, name="Main", address="1 Test St")
            db.add_all([category, prop])
            db.flush()
            w.ids[f"category_{key}"] = category.id
            w.ids[f"property_{key}"] = prop.id

            for role in ("dispatcher", "customer"):
                u = user(f"{role}.{key}@t.test", f"{role} {key}")
                db.add(
                    OrganizationMembership(organization_id=org.id, user_id=u.id, role=Role(role))
                )
                w.ids[f"{role}_{key}"] = u.id

            for tech_no, skills in ((1, ["hvac"]), (2, ["plumbing"])):
                u = user(f"tech{tech_no}.{key}@t.test", f"tech{tech_no} {key}")
                db.add(
                    OrganizationMembership(
                        organization_id=org.id, user_id=u.id, role=Role.TECHNICIAN
                    )
                )
                profile = TechnicianProfile(organization_id=org.id, user_id=u.id)
                db.add(profile)
                db.flush()
                for skill in skills:
                    db.add(
                        TechnicianSkill(
                            organization_id=org.id, technician_id=profile.id, skill=skill
                        )
                    )
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
                w.ids[f"tech{tech_no}_{key}"] = profile.id
                w.ids[f"tech{tech_no}_user_{key}"] = u.id

            for number in range(1, 4):
                req = ServiceRequest(
                    organization_id=org.id,
                    title=f"Request {number} of {name}",
                    description="A sufficiently long description of the problem.",
                    category_id=category.id,
                    property_id=prop.id,
                    priority=Priority.NORMAL,
                    status=RequestStatus.TRIAGED,
                    created_by_user_id=w.ids[f"customer_{key}"],
                )
                db.add(req)
                db.flush()
                w.ids[f"request{number}_{key}"] = req.id
        db.commit()
    yield w


@pytest.fixture
def make_client():
    """Factory for an authenticated API client acting in one organization."""
    from fastapi.testclient import TestClient

    from app.main import app

    def build(email: str, org_id: int | None) -> TestClient:
        client = TestClient(app)
        res = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        assert res.status_code == 200, res.text
        client.headers["Authorization"] = f"Bearer {res.json()['access_token']}"
        if org_id is not None:
            client.headers["X-Organization-Id"] = str(org_id)
        return client

    return build
