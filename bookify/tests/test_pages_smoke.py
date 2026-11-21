"""Every page renders (200) for the role that should see it, using realistic data."""
import pytest

from conftest import future_slot, login
from app.services.booking_manager import BookingManager

PUBLIC = ["/", "/businesses", "/businesses?q=alp", "/b/alpha", "/b/alpha/services", "/b/alpha/book",
          "/login", "/register", "/register-business"]
ADMIN = ["/admin", "/admin/services", "/admin/services/new", "/admin/staff", "/admin/staff/new",
         "/admin/settings", "/admin/calendar", "/admin/bookings", "/admin/bookings?status=cancelled",
         "/notifications"]
CUSTOMER = ["/dashboard", "/bookings", "/bookings?status=completed", "/notifications"]


@pytest.mark.parametrize("url", PUBLIC)
def test_public_pages(client, world, url):
    assert client.get(url).status_code == 200


def test_admin_pages(client, world):
    bk = BookingManager.create_booking(world.c1, world.a.business, world.a.long.id, world.a.staff.id, future_slot())
    login(client, "admin@alpha.test")
    for url in ADMIN + [f"/admin/services/{world.a.long.id}/edit", f"/admin/staff/{world.a.staff.id}/edit",
                        f"/admin/staff/{world.a.staff.id}/schedule",
                        "/admin/calendar?week=" + bk.start_time.date().isoformat()]:
        assert client.get(url).status_code == 200, url


def test_customer_and_staff_pages(client, world):
    bk = BookingManager.create_booking(world.c1, world.a.business, world.a.long.id, world.a.staff.id, future_slot())
    login(client, "c1@test.test")
    for url in CUSTOMER + [f"/bookings/{bk.id}/confirmation", "/b/alpha/book?service=1"]:
        assert client.get(url).status_code == 200, url
    client.post("/logout")
    login(client, world.a.staff_user.email)
    assert client.get("/staff").status_code == 200
    assert client.get("/notifications").status_code == 200


def test_schedule_save_and_notification_read(client, world):
    login(client, "admin@alpha.test")
    sid = world.a.staff.id
    r = client.post(f"/admin/staff/{sid}/schedule", data={"work_0": "1", "start_0": "08:00", "end_0": "12:00"},
                    follow_redirects=True)
    assert b"schedule saved" in r.data
    from app.models import WorkSchedule
    rows = WorkSchedule.query.filter_by(staff_id=sid).all()
    assert len(rows) == 1 and rows[0].weekday == 0
    r = client.post(f"/admin/staff/{sid}/schedule", data={"work_1": "1", "start_1": "12:00", "end_1": "08:00"},
                    follow_redirects=True)
    assert b"end time must be after" in r.data
    assert client.post("/notifications/read", follow_redirects=True).status_code == 200
