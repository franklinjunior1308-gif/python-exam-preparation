import threading
from datetime import datetime, time, timedelta

import pytest

from app import create_app
from app.extensions import db
from app.models import Booking, Notification, User, WorkSchedule, utcnow
from app.services.availability import AvailabilityService
from app.services.booking_manager import BookingError, BookingManager, BookingPermissionError

from conftest import future_slot, login, make_business, make_user


def book(world, customer=None, svc=None, start=None, biz=None):
    biz = biz or world.a
    return BookingManager.create_booking(customer or world.c1, biz.business, (svc or biz.long).id,
                                         biz.staff.id, start or future_slot())


# ---- availability ----------------------------------------------------------------------
def test_slot_calculation_respects_duration(world):
    day = future_slot().date()
    short = AvailabilityService.get_slots(world.a.business, world.a.short, day)
    long_ = AvailabilityService.get_slots(world.a.business, world.a.long, day)
    assert len(short) == 16 and short[0]["start"].hour == 9 and short[-1]["start"] == datetime(day.year, day.month, day.day, 16, 30)
    assert len(long_) == 15 and long_[-1]["start"] == datetime(day.year, day.month, day.day, 16, 0)


def test_booked_time_removed_from_slots_and_cancel_frees_it(world):
    day = future_slot().date()
    bk = book(world)  # 10:00-11:00
    starts = [s["start"].strftime("%H:%M") for s in AvailabilityService.get_slots(world.a.business, world.a.long, day)]
    assert not {"09:30", "10:00", "10:30"} & set(starts)  # 09:30 long would overlap 10:00
    assert "09:00" in starts and "11:00" in starts
    BookingManager.cancel_booking(world.c1, bk)
    starts = [s["start"].strftime("%H:%M") for s in AvailabilityService.get_slots(world.a.business, world.a.long, day)]
    assert {"09:30", "10:00", "10:30"} <= set(starts)


def test_no_slots_on_day_off_or_for_unqualified_staff(world):
    day = future_slot().date()
    WorkSchedule.query.filter_by(staff_id=world.a.staff.id, weekday=day.weekday()).delete()
    db.session.commit()
    assert AvailabilityService.get_slots(world.a.business, world.a.long, day) == []
    # staff of business B is not qualified for A's service
    assert AvailabilityService.get_slots(world.a.business, world.a.long, future_slot().date(), staff=world.b.staff) == []


def test_slots_in_business_timezone(app):
    w = make_business("tokyo", "admin@tokyo.test", tz="Asia/Tokyo")
    day = future_slot().date()
    first = AvailabilityService.get_slots(w.business, w.short, day)[0]["start"]
    assert first.hour == 0  # 09:00 JST == 00:00 UTC


def test_past_slots_not_offered(world):
    now = datetime(2030, 1, 1, 12, 0)
    slots = AvailabilityService.get_slots(world.a.business, world.a.short, now.date(), now=now)
    assert all(s["start"] > now for s in slots) and len(slots) == 9  # 12:30 .. 16:30


def test_slots_api(client, world):
    day = future_slot().date().isoformat()
    r = client.get(f"/api/b/alpha/slots?service_id={world.a.long.id}&date={day}")
    assert r.status_code == 200 and len(r.get_json()["slots"]) == 15
    assert client.get("/api/b/alpha/slots?service_id=999&date=" + day).status_code == 400
    assert client.get(f"/api/b/alpha/slots?service_id={world.b.long.id}&date={day}").status_code == 400  # other business


# ---- creation rules --------------------------------------------------------------------
def test_create_booking_snapshots_price(world):
    bk = book(world)
    world.a.long.price_cents = 9900
    db.session.commit()
    assert Booking.query.get(bk.id).price_cents == 4000 and bk.duration_minutes == 60
    assert bk.end_time - bk.start_time == timedelta(minutes=60)
    assert Notification.query.filter_by(user_id=world.c1.id).count() == 1
    assert Notification.query.filter_by(user_id=world.a.admin.id).count() == 1


def test_overlapping_bookings_forbidden(world):
    book(world, start=future_slot(hour=10))  # 10:00-11:00
    for hour, minute in ((10, 0), (10, 30), (9, 30)):
        with pytest.raises(BookingError):
            book(world, customer=world.c2, start=future_slot(hour=hour, minute=minute))
    # adjacent bookings are fine
    book(world, customer=world.c2, start=future_slot(hour=11))
    book(world, customer=world.c2, svc=world.a.short, start=future_slot(hour=9))
    assert Booking.query.filter_by(business_id=world.a.business.id).count() == 3


def test_past_date_rejected(world):
    with pytest.raises(BookingError, match="future"):
        book(world, start=utcnow() - timedelta(days=1))
    with pytest.raises(BookingError, match="future"):
        book(world, start=utcnow() - timedelta(minutes=1))
    assert Booking.query.count() == 0


def test_outside_working_hours_and_misaligned_rejected(world):
    with pytest.raises(BookingError):
        book(world, start=future_slot(hour=7))
    with pytest.raises(BookingError):
        book(world, start=future_slot(hour=16, minute=30))  # 60 min would end 17:30
    with pytest.raises(BookingError):
        book(world, start=future_slot(hour=10, minute=15))


def test_unqualified_staff_or_foreign_service_rejected(world):
    world.a.staff.services.remove(world.a.long)
    db.session.commit()
    with pytest.raises(BookingError, match="qualified"):
        book(world)
    with pytest.raises(BookingError):  # service of another business
        BookingManager.create_booking(world.c1, world.a.business, world.b.long.id, world.a.staff.id, future_slot())


def test_inactive_service_rejected(world):
    world.a.long.is_active = False
    db.session.commit()
    with pytest.raises(BookingError):
        book(world)


def test_any_staff_picks_free_staff(world):
    book(world)
    # only one staff member exists and is busy -> "anyone" must fail
    with pytest.raises(BookingError):
        BookingManager.create_booking(world.c2, world.a.business, world.a.long.id, None, future_slot())
    # add a second qualified staff member: "anyone" now lands on them
    from app.models import StaffMember
    u2 = make_user("Second", "second@alpha.test", "staff")
    sm2 = StaffMember(business_id=world.a.business.id, user_id=u2.id)
    sm2.services = [world.a.long]
    db.session.add(sm2)
    db.session.flush()
    for d in range(7):
        db.session.add(WorkSchedule(staff_id=sm2.id, weekday=d, start_time=time(9), end_time=time(17)))
    db.session.commit()
    other = BookingManager.create_booking(world.c2, world.a.business, world.a.long.id, None, future_slot())
    assert other.staff_id == sm2.id


def test_booking_via_route_end_to_end(client, world):
    login(client, "c1@test.test")
    start = future_slot().strftime("%Y-%m-%dT%H:%M")
    r = client.post("/b/alpha/book", data={"service_id": world.a.long.id, "staff_id": world.a.staff.id, "start": start},
                    follow_redirects=True)
    assert b"You&#39;re booked" in r.data or b"You're booked" in r.data
    assert Booking.query.count() == 1
    # same slot again -> error flash, no second booking
    client.post("/b/alpha/book", data={"service_id": world.a.long.id, "staff_id": world.a.staff.id, "start": start})
    assert Booking.query.count() == 1


def test_non_customers_and_anonymous_cannot_book(client, world):
    start = future_slot().strftime("%Y-%m-%dT%H:%M")
    data = {"service_id": world.a.long.id, "staff_id": world.a.staff.id, "start": start}
    assert client.post("/b/alpha/book", data=data).status_code == 302
    login(client, "admin@alpha.test")
    client.post("/b/alpha/book", data=data)
    assert Booking.query.count() == 0


# ---- cancellation ----------------------------------------------------------------------
def test_customer_cancel_cutoff(world):
    now = utcnow()
    far = book(world, start=future_slot(hour=10))
    BookingManager.cancel_booking(world.c1, far)
    assert far.status == "cancelled" and far.cancelled_by_id == world.c1.id

    soon = book(world, start=future_slot(hour=12))
    with pytest.raises(BookingError, match="2 hours"):
        BookingManager.cancel_booking(world.c1, soon, now=soon.start_time - timedelta(hours=1, minutes=59))
    BookingManager.cancel_booking(world.c1, soon, now=soon.start_time - timedelta(hours=2))
    assert soon.status == "cancelled"
    assert now  # silence linter


def test_admin_can_cancel_inside_cutoff(world):
    bk = book(world)
    BookingManager.cancel_booking(world.a.admin, bk, now=bk.start_time - timedelta(minutes=30))
    assert bk.status == "cancelled"
    assert Notification.query.filter_by(user_id=world.c1.id).count() == 2  # created + cancelled


def test_completed_cannot_be_cancelled(world):
    bk = book(world)
    bk.status = "completed"
    db.session.commit()
    with pytest.raises(BookingError, match="Completed"):
        BookingManager.cancel_booking(world.c1, bk)
    with pytest.raises(BookingError, match="Completed"):
        BookingManager.cancel_booking(world.a.admin, bk)


def test_cannot_cancel_other_customers_or_other_business_booking(client, world):
    bk = book(world)
    with pytest.raises(BookingPermissionError):
        BookingManager.cancel_booking(world.c2, bk)
    with pytest.raises(BookingPermissionError):
        BookingManager.cancel_booking(world.b.admin, bk)
    login(client, "c2@test.test")
    assert client.post(f"/bookings/{bk.id}/cancel").status_code == 404
    assert client.get(f"/bookings/{bk.id}/confirmation").status_code == 404
    assert Booking.query.get(bk.id).status == "confirmed"


def test_cancel_via_route(client, world):
    bk = book(world)
    login(client, "c1@test.test")
    client.post(f"/bookings/{bk.id}/cancel", follow_redirects=True)
    assert Booking.query.get(bk.id).status == "cancelled"


# ---- history ---------------------------------------------------------------------------
def test_booking_history_only_shows_own(client, world):
    book(world, customer=world.c1, start=future_slot(hour=9))
    book(world, customer=world.c2, start=future_slot(hour=14))
    old = book(world, customer=world.c1, svc=world.a.short, start=future_slot(hour=16))
    old.status = "completed"
    db.session.commit()
    login(client, "c1@test.test")
    page = client.get("/bookings").data
    assert page.count(b"Details") == 2
    assert client.get("/bookings?status=completed").data.count(b"Details") == 1
    assert b"Cust Two" not in page


# ---- concurrency -----------------------------------------------------------------------
def _run_concurrently(app, jobs):
    barrier = threading.Barrier(len(jobs))
    results = [None] * len(jobs)

    def worker(i, customer_id, business_id, service_id, staff_id, start):
        with app.app_context():
            customer = db.session.get(User, customer_id)
            from app.models import Business
            business = db.session.get(Business, business_id)
            barrier.wait()
            try:
                BookingManager.create_booking(customer, business, service_id, staff_id, start)
                results[i] = "ok"
            except BookingError:
                results[i] = "rejected"
            except Exception as e:  # any other failure is a test failure
                results[i] = f"error: {e!r}"
            finally:
                db.session.remove()

    threads = [threading.Thread(target=worker, args=(i, *j)) for i, j in enumerate(jobs)]
    [t.start() for t in threads]
    [t.join(60) for t in threads]
    return results


@pytest.fixture()
def file_app(tmp_path):
    app = create_app("testing", {"SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'c.sqlite'}"})
    with app.app_context():
        db.create_all()
        w = make_business("alpha", "admin@alpha.test")
        customers = [make_user(f"C{i}", f"c{i}@t.test", "customer") for i in range(8)]
        db.session.commit()
        yield app, w, [c.id for c in customers]
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


def test_concurrent_same_slot_only_one_wins(file_app):
    app, w, cust_ids = file_app
    start = future_slot()
    jobs = [(cid, w.business.id, w.long.id, w.staff.id, start) for cid in cust_ids]
    results = _run_concurrently(app, jobs)
    assert results.count("ok") == 1, results
    assert results.count("rejected") == 7, results
    assert Booking.query.filter_by(staff_id=w.staff.id).count() == 1


def test_concurrent_overlapping_slots_only_one_wins(file_app):
    app, w, cust_ids = file_app
    # 60-minute bookings starting at 10:00 / 10:30 / 11:00 -> 10:00 overlaps 10:30, 10:30 overlaps 11:00
    starts = [future_slot(hour=10), future_slot(hour=10, minute=30)]
    jobs = [(cid, w.business.id, w.long.id, w.staff.id, starts[i % 2]) for i, cid in enumerate(cust_ids)]
    results = _run_concurrently(app, jobs)
    assert results.count("ok") == 1, results
    assert Booking.query.filter(Booking.status != "cancelled").count() == 1


def test_db_unique_index_blocks_duplicate_start(app, world):
    """Defence in depth: even a buggy code path cannot insert two active bookings at one start."""
    from sqlalchemy.exc import IntegrityError
    bk = book(world)
    dup = Booking(business_id=bk.business_id, customer_id=world.c2.id, service_id=bk.service_id,
                  staff_id=bk.staff_id, start_time=bk.start_time, end_time=bk.end_time, price_cents=1,
                  duration_minutes=60)
    db.session.add(dup)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
