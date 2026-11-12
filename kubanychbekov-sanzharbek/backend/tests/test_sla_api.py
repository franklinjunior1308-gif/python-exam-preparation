"""SLA in working time, pauses, holidays, overdue queue and one-time escalation (PostgreSQL)."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

TZ = ZoneInfo("Asia/Bishkek")


def local(year, month, day, hour, minute=0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=TZ).astimezone(UTC)


def make_request(
    engine,
    world,
    *,
    created,
    priority="NORMAL",
    status="TRIAGED",
    org="a",
    completed=None,
    estimate=None,
):
    """Insert a request with an explicit creation time, optional completion and estimate wait."""
    from app.domain.enums import EstimateStatus, Priority, RequestStatus
    from app.models import Estimate, RequestStatusHistory, ServiceRequest

    with Session(engine) as db:
        req = ServiceRequest(
            organization_id=world[f"org_{org}"],
            title="SLA test request",
            description="A sufficiently long description of the problem.",
            category_id=world[f"category_{org}"],
            property_id=world[f"property_{org}"],
            priority=Priority(priority),
            status=RequestStatus(status),
            created_by_user_id=world[f"customer_{org}"],
            created_at=created,
            updated_at=created,
        )
        db.add(req)
        db.flush()
        if completed is not None:
            db.add(
                RequestStatusHistory(
                    organization_id=req.organization_id,
                    request_id=req.id,
                    from_status=RequestStatus.IN_PROGRESS,
                    to_status=RequestStatus.COMPLETED,
                    actor_user_id=world[f"dispatcher_{org}"],
                    created_at=completed,
                )
            )
        if estimate is not None:
            submitted, decided = estimate
            db.add(
                Estimate(
                    organization_id=req.organization_id,
                    request_id=req.id,
                    version=1,
                    status=EstimateStatus.APPROVED,
                    submitted_at=submitted,
                    decided_at=decided,
                    created_by_user_id=world[f"dispatcher_{org}"],
                )
            )
        db.commit()
        return req.id


def sla_of(client, request_id):
    return client.get(f"/api/v1/requests/{request_id}").json()["sla"]


def test_a_fresh_request_is_on_track_and_an_old_one_is_overdue(world, make_client, engine):
    now = datetime.now(UTC)
    fresh = make_request(engine, world, created=now)
    old = make_request(engine, world, created=now - timedelta(days=30))
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])

    assert sla_of(dispatcher, fresh)["state"] == "ON_TRACK"
    overdue = sla_of(dispatcher, old)
    assert overdue["state"] == "OVERDUE" and overdue["remaining_minutes"] < 0
    assert overdue["budget_minutes"] == 24 * 60  # NORMAL = 24 working hours


def test_overdue_queue_is_for_staff_and_sorted_most_overdue_first(world, make_client, engine):
    now = datetime.now(UTC)
    a = make_request(engine, world, created=now - timedelta(days=10))
    b = make_request(engine, world, created=now - timedelta(days=30))
    make_request(engine, world, created=now)  # not overdue
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    queue = dispatcher.get("/api/v1/sla/overdue").json()
    assert [i["request_id"] for i in queue][:2] == [b, a]
    assert all(i["overdue_minutes"] > 0 and i["escalated"] is False for i in queue)

    customer = make_client("customer.a@t.test", world["org_a"])
    assert customer.get("/api/v1/sla/overdue").status_code == 403
    outsider = make_client("dispatcher.b@t.test", world["org_b"])
    assert outsider.get("/api/v1/sla/overdue").json() == []  # other organizations see nothing


def test_the_request_list_can_be_filtered_by_sla_state(world, make_client, engine):
    now = datetime.now(UTC)
    fresh = make_request(engine, world, created=now)
    old = make_request(engine, world, created=now - timedelta(days=30))
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    overdue = dispatcher.get("/api/v1/requests", params={"sla": "OVERDUE"}).json()
    assert [r["id"] for r in overdue["items"]] == [old] and overdue["total"] == 1
    on_track = dispatcher.get("/api/v1/requests", params={"sla": "ON_TRACK"}).json()
    assert fresh in [r["id"] for r in on_track["items"]] and old not in [
        r["id"] for r in on_track["items"]
    ]
    assert all(r["sla"]["state"] == "OVERDUE" for r in overdue["items"])


def test_completed_request_keeps_the_result_from_the_moment_of_completion(
    world, make_client, engine
):
    # Tuesday 10:00 -> completed 11:00: one working hour of eight, however late we look
    request_id = make_request(
        engine,
        world,
        created=local(2026, 11, 3, 10),
        priority="HIGH",
        status="COMPLETED",
        completed=local(2026, 11, 3, 11),
    )
    sla = sla_of(make_client("dispatcher.a@t.test", world["org_a"]), request_id)
    assert sla["finished"] is True and sla["state"] == "ON_TRACK"
    assert (sla["used_minutes"], sla["remaining_minutes"]) == (60, 420)
    assert sla["due_at"] is None


def test_waiting_for_the_customer_pauses_the_clock(world, make_client, engine):
    created, done = local(2026, 11, 3, 10), local(2026, 11, 4, 10)
    with_estimate = make_request(
        engine,
        world,
        created=created,
        priority="HIGH",
        status="COMPLETED",
        completed=done,
        estimate=(local(2026, 11, 3, 10, 30), local(2026, 11, 4, 9)),
    )
    without = make_request(
        engine, world, created=created, priority="HIGH", status="COMPLETED", completed=done
    )
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    paused = sla_of(dispatcher, with_estimate)
    assert (paused["used_minutes"], paused["state"]) == (
        30 + 60,
        "ON_TRACK",
    )  # 10:00-10:30 + 09:00-10:00
    plain = sla_of(dispatcher, without)
    assert (plain["used_minutes"], plain["state"]) == (480 + 60, "OVERDUE")  # no pause: 9 h used


def test_priority_change_recomputes_from_the_used_time_and_is_audited(world, make_client, engine):
    created = datetime.now(UTC) - timedelta(days=3)
    request_id = make_request(engine, world, created=created, priority="LOW")
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    before = sla_of(dispatcher, request_id)
    assert before["budget_minutes"] == 48 * 60

    bad = dispatcher.patch(f"/api/v1/requests/{request_id}", json={"priority": "HIGH"})
    assert bad.status_code == 422  # a reason is mandatory
    changed = dispatcher.patch(
        f"/api/v1/requests/{request_id}",
        json={"priority": "HIGH", "reason": "Customer called, urgent"},
    ).json()
    assert changed["priority"] == "HIGH" and changed["sla"]["budget_minutes"] == 8 * 60
    assert (
        changed["sla"]["used_minutes"] == before["used_minutes"]
    )  # same time used, smaller budget
    assert changed["sla"]["remaining_minutes"] == 8 * 60 - before["used_minutes"]

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT before, after FROM audit_events WHERE action = 'request.triage_changed'")
        ).one()
    assert row.before["priority"] == "LOW" and row.after["priority"] == "HIGH"
    assert row.after["reason"] == "Customer called, urgent"

    customer = make_client("customer.a@t.test", world["org_a"])
    assert (
        customer.patch(
            f"/api/v1/requests/{request_id}", json={"priority": "LOW", "reason": "I want it lower"}
        ).status_code
        == 403
    )


def test_escalation_is_created_once_even_when_the_scan_runs_twice_and_in_parallel(
    world, make_client, engine
):
    from app.db.session import get_sessionmaker
    from app.services.sla import scan_and_escalate

    make_request(engine, world, created=datetime.now(UTC) - timedelta(days=30))

    def scan(_: int) -> int:
        with get_sessionmaker()() as db:
            return scan_and_escalate(db)

    with ThreadPoolExecutor(max_workers=4) as pool:
        created = sum(pool.map(scan, range(4)))
    assert created == 1  # exactly one scan created it
    assert scan(0) == 0  # a later run creates nothing new

    with engine.connect() as conn:
        escalations = conn.execute(text("SELECT count(*) FROM sla_escalations")).scalar_one()
        notified = conn.execute(
            text(
                "SELECT count(*) FROM notifications "
                "WHERE type = 'sla_overdue' AND recipient_user_id = :u"
            ),
            {"u": world["dispatcher_a"]},
        ).scalar_one()
    assert (escalations, notified) == (1, 1)
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    assert dispatcher.get("/api/v1/sla/overdue").json()[0]["escalated"] is True


def test_working_hours_and_holidays_are_managed_by_the_admin_only(world, make_client, admin):
    hours = admin.get("/api/v1/settings/working-hours").json()
    assert hours["is_default"] is True and len(hours["intervals"]) == 5  # Mon-Fri 09-18

    new = {
        "intervals": [
            {"weekday": 0, "start_time": "08:00:00", "end_time": "12:00:00"},
            {"weekday": 0, "start_time": "13:00:00", "end_time": "17:00:00"},
        ]
    }
    saved = admin.put("/api/v1/settings/working-hours", json=new).json()
    assert saved["is_default"] is False and len(saved["intervals"]) == 2

    overlapping = {
        "intervals": [
            {"weekday": 1, "start_time": "08:00:00", "end_time": "12:00:00"},
            {"weekday": 1, "start_time": "11:00:00", "end_time": "14:00:00"},
        ]
    }
    assert (
        admin.put("/api/v1/settings/working-hours", json=overlapping).json()["error"]["code"]
        == "overlapping_intervals"
    )
    backwards = {"intervals": [{"weekday": 1, "start_time": "12:00:00", "end_time": "09:00:00"}]}
    assert admin.put("/api/v1/settings/working-hours", json=backwards).status_code == 422

    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    assert dispatcher.get("/api/v1/settings/working-hours").status_code == 200
    assert dispatcher.put("/api/v1/settings/working-hours", json=new).status_code == 403
    customer = make_client("customer.a@t.test", world["org_a"])
    assert customer.get("/api/v1/settings/working-hours").status_code == 403

    holiday = admin.post(
        "/api/v1/settings/holidays", json={"day": "2026-11-20", "name": "Day off"}
    ).json()
    assert [h["day"] for h in holiday["holidays"]] == ["2026-11-20"]
    again = admin.post("/api/v1/settings/holidays", json={"day": "2026-11-20"}).json()
    assert len(again["holidays"]) == 1  # no duplicate
    removed = admin.delete(f"/api/v1/settings/holidays/{again['holidays'][0]['id']}").json()
    assert removed["holidays"] == []


def test_a_holiday_removes_that_day_from_the_clock(world, make_client, engine, admin):
    request_id = make_request(
        engine,
        world,
        created=local(2026, 11, 3, 10),
        priority="HIGH",
        status="COMPLETED",
        completed=local(2026, 11, 4, 10),
    )
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    assert sla_of(dispatcher, request_id)["used_minutes"] == 540  # Tuesday 10-18 + Wednesday 09-10

    admin.post("/api/v1/settings/holidays", json={"day": "2026-11-03", "name": "Holiday"})
    after = sla_of(dispatcher, request_id)
    assert after["used_minutes"] == 60 and after["state"] == "ON_TRACK"  # only Wednesday counts


def test_settings_are_isolated_between_organizations(world, make_client, admin):
    admin.post("/api/v1/settings/holidays", json={"day": "2026-12-31", "name": "New Year"})
    outsider = make_client("dispatcher.b@t.test", world["org_b"])
    assert outsider.get("/api/v1/settings/working-hours").json()["holidays"] == []
