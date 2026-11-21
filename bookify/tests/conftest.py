import sys
from datetime import datetime, time, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Business, Service, StaffMember, User, WorkSchedule, utcnow  # noqa: E402

PW = "Password123!"


def make_user(name, email, role):
    u = User(name=name, email=email, role=role)
    u.set_password(PW)
    db.session.add(u)
    db.session.flush()
    return u


def make_business(slug, admin_email, tz="UTC", staff_email=None):
    """A business with one service (60 min / $40), 30-min service, and one staff member working every day 09-17."""
    admin = make_user(f"Admin {slug}", admin_email, "admin")
    biz = Business(owner_id=admin.id, name=slug.title(), slug=slug, timezone=tz, slot_interval_minutes=30)
    db.session.add(biz)
    db.session.flush()
    long_svc = Service(business_id=biz.id, name="Long", price_cents=4000, duration_minutes=60)
    short_svc = Service(business_id=biz.id, name="Short", price_cents=2000, duration_minutes=30)
    db.session.add_all([long_svc, short_svc])
    su = make_user(f"Staff {slug}", staff_email or f"staff@{slug}.test", "staff")
    sm = StaffMember(business_id=biz.id, user_id=su.id)
    sm.services = [long_svc, short_svc]
    db.session.add(sm)
    db.session.flush()
    for d in range(7):
        db.session.add(WorkSchedule(staff_id=sm.id, weekday=d, start_time=time(9), end_time=time(17)))
    db.session.commit()
    return SimpleNamespace(admin=admin, business=biz, long=long_svc, short=short_svc, staff=sm, staff_user=su)


def future_slot(days=3, hour=10, minute=0):
    d = (utcnow() + timedelta(days=days)).date()
    return datetime(d.year, d.month, d.day, hour, minute)


@pytest.fixture()
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def world(app):
    """Two isolated businesses plus two customers."""
    w = SimpleNamespace()
    w.a = make_business("alpha", "admin@alpha.test")
    w.b = make_business("beta", "admin@beta.test")
    w.c1 = make_user("Cust One", "c1@test.test", "customer")
    w.c2 = make_user("Cust Two", "c2@test.test", "customer")
    db.session.commit()
    return w


def login(client, email, password=PW):
    return client.post("/login", data={"email": email, "password": password}, follow_redirects=True)
