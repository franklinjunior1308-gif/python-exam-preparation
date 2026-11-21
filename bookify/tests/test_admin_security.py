from datetime import timedelta

from app.models import Booking, Service, utcnow
from app.services.booking_manager import BookingManager

from conftest import PW, future_slot, login


def test_service_validation(client, world):
    login(client, "admin@alpha.test")
    for data in ({"name": "", "price": "10", "duration": "30"},
                 {"name": "Cut", "price": "-5", "duration": "30"},
                 {"name": "Cut", "price": "abc", "duration": "30"},
                 {"name": "Cut", "price": "10", "duration": "0"},
                 {"name": "Cut", "price": "10", "duration": "9999"}):
        before = Service.query.count()
        client.post("/admin/services/new", data=data)
        assert Service.query.count() == before, data


def test_service_crud_and_deactivate(client, world):
    login(client, "admin@alpha.test")
    client.post("/admin/services/new", data={"name": "Trim", "price": "12.50", "duration": "15"})
    s = Service.query.filter_by(name="Trim").one()
    assert s.price_cents == 1250 and s.business_id == world.a.business.id
    client.post(f"/admin/services/{s.id}/edit", data={"name": "Trim+", "price": "15", "duration": "20"})
    assert Service.query.get(s.id).name == "Trim+"
    client.post(f"/admin/services/{s.id}/toggle")
    assert Service.query.get(s.id).is_active is False
    assert b"Trim+" not in client.get("/b/alpha/services").data


def test_business_isolation_services(client, world):
    login(client, "admin@alpha.test")
    other = world.b.long
    assert client.get(f"/admin/services/{other.id}/edit").status_code == 404
    assert client.post(f"/admin/services/{other.id}/edit",
                       data={"name": "Hacked", "price": "1", "duration": "5"}).status_code == 404
    assert client.post(f"/admin/services/{other.id}/toggle").status_code == 404
    assert Service.query.get(other.id).name == "Long"


def test_business_isolation_bookings_and_staff(client, world, app):
    bk = BookingManager.create_booking(world.c1, world.b.business, world.b.long.id, world.b.staff.id, future_slot())
    login(client, "admin@alpha.test")
    assert client.post(f"/admin/bookings/{bk.id}/cancel").status_code == 404
    assert client.post(f"/admin/bookings/{bk.id}/complete").status_code == 404
    assert client.get(f"/admin/staff/{world.b.staff.id}/edit").status_code == 404
    assert client.get(f"/admin/staff/{world.b.staff.id}/schedule").status_code == 404
    assert Booking.query.get(bk.id).status == "confirmed"
    # the other business's bookings never appear in this admin's list
    assert b"Cust One" not in client.get("/admin/bookings").data
    assert b"Cust One" not in client.get("/admin/calendar?week=" + future_slot().date().isoformat()).data


def test_role_based_access(client, world):
    # anonymous -> redirect to login
    assert client.get("/admin").status_code == 302
    login(client, "c1@test.test")
    assert client.get("/admin").status_code == 403
    assert client.get("/staff").status_code == 403
    client.post("/logout")
    login(client, world.a.staff_user.email)
    assert client.get("/admin").status_code == 403
    assert client.get("/dashboard").status_code == 403
    assert client.get("/staff").status_code == 200
    client.post("/logout")
    login(client, "admin@alpha.test")
    assert client.get("/dashboard").status_code == 403
    assert client.get("/admin").status_code == 200


def test_staff_only_sees_and_finishes_own_appointments(client, world, app):
    # second staff member in business alpha
    from conftest import make_user
    from app.models import StaffMember, WorkSchedule
    from app.extensions import db
    from datetime import time
    u2 = make_user("Other Staff", "other@alpha.test", "staff")
    sm2 = StaffMember(business_id=world.a.business.id, user_id=u2.id)
    sm2.services = [world.a.long]
    db.session.add(sm2)
    db.session.flush()
    for d in range(7):
        db.session.add(WorkSchedule(staff_id=sm2.id, weekday=d, start_time=time(9), end_time=time(17)))
    db.session.commit()

    now = utcnow()
    start = future_slot(days=2)
    mine = BookingManager.create_booking(world.c1, world.a.business, world.a.long.id, world.a.staff.id, start)
    theirs = BookingManager.create_booking(world.c1, world.a.business, world.a.long.id, sm2.id, start)
    login(client, world.a.staff_user.email)
    page = client.get("/staff").data
    assert page.count(b"Mark finished") == 0  # future appointments cannot be finished yet
    assert client.post(f"/staff/bookings/{theirs.id}/complete").status_code == 404
    # past appointment of mine can be finished
    mine.start_time = now - timedelta(hours=3)
    mine.end_time = now - timedelta(hours=2)
    db.session.commit()
    assert b"Mark finished" in client.get("/staff").data
    client.post(f"/staff/bookings/{mine.id}/complete", follow_redirects=True)
    assert Booking.query.get(mine.id).status == "completed"
    assert Booking.query.get(theirs.id).status == "confirmed"


def test_customer_cannot_use_admin_booking_actions(client, world):
    bk = BookingManager.create_booking(world.c1, world.a.business, world.a.long.id, world.a.staff.id, future_slot())
    login(client, "c2@test.test")
    assert client.post(f"/admin/bookings/{bk.id}/cancel").status_code == 403
    assert Booking.query.get(bk.id).status == "confirmed"


def test_custom_error_pages(client):
    r = client.get("/nope")
    assert r.status_code == 404 and b"Page not found" in r.data


def test_csrf_enforced_when_enabled():
    from app import create_app
    from app.extensions import db
    app = create_app("testing", {"WTF_CSRF_ENABLED": True})
    with app.app_context():
        db.create_all()
        r = app.test_client().post("/login", data={"email": "a@b.co", "password": "x"})
        assert r.status_code == 400
