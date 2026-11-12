"""Preventive maintenance: plans, duplicate-free generation, stopping rules (PostgreSQL)."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


@pytest.fixture
def asset_id(world, engine) -> int:
    from app.models import Asset

    with Session(engine) as db:
        asset = Asset(
            organization_id=world["org_a"],
            property_id=world["property_a"],
            code="AC-001",
            name="Chiller",
            asset_type="HVAC unit",
        )
        db.add(asset)
        db.commit()
        return asset.id


def plan_body(world, asset_id, **overrides):
    body = {
        "asset_id": asset_id,
        "category_id": world["category_a"],
        "title": "Quarterly filter check",
        "description": "Replace filters and test airflow.",
        "priority": "NORMAL",
        "frequency": "WEEKLY",
        "first_date": "2026-11-02",
    }
    body.update(overrides)
    return body


def count_requests(engine, plan_id) -> int:
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT count(*) FROM service_requests WHERE plan_id = :p"), {"p": plan_id}
        ).scalar_one()


def test_generation_creates_one_request_per_due_date_with_the_plan_link(
    world, make_client, asset_id, engine
):
    admin = make_client("dispatcher.a@t.test", world["org_a"])
    plan = admin.post("/api/v1/maintenance-plans", json=plan_body(world, asset_id)).json()
    assert plan["next_date"] == "2026-11-02" and plan["generated_count"] == 0

    result = admin.post("/api/v1/maintenance/generate", json={"as_of": "2026-11-16"}).json()
    assert (result["created_requests"], result["skipped_existing"]) == (3, 0)  # 2, 9 and 16 Nov
    assert count_requests(engine, plan["id"]) == 3

    listing = admin.get(f"/api/v1/maintenance-plans/{plan['id']}/requests").json()
    assert [r["plan_date"] for r in listing] == ["2026-11-16", "2026-11-09", "2026-11-02"]
    request = admin.get(f"/api/v1/requests/{listing[0]['request_id']}").json()
    assert request["status"] == "SUBMITTED" and request["asset_id"] == asset_id
    assert request["title"] == "Quarterly filter check" and "2026-11-16" in request["description"]

    after = admin.get("/api/v1/maintenance-plans").json()[0]
    assert after["generated_count"] == 3 and after["next_date"] == "2026-11-23"


def test_repeating_generation_never_duplicates(world, make_client, asset_id, engine):
    admin = make_client("dispatcher.a@t.test", world["org_a"])
    plan = admin.post("/api/v1/maintenance-plans", json=plan_body(world, asset_id)).json()
    first = admin.post("/api/v1/maintenance/generate", json={"as_of": "2026-11-16"}).json()
    again = admin.post("/api/v1/maintenance/generate", json={"as_of": "2026-11-16"}).json()
    assert first["created_requests"] == 3
    assert (again["created_requests"], again["skipped_existing"]) == (0, 3)
    later = admin.post("/api/v1/maintenance/generate", json={"as_of": "2026-11-23"}).json()
    assert (later["created_requests"], later["skipped_existing"]) == (1, 3)  # only the new date
    assert count_requests(engine, plan["id"]) == 4


def test_parallel_generation_creates_each_event_exactly_once(world, make_client, asset_id, engine):
    admin = make_client("dispatcher.a@t.test", world["org_a"])
    plan = admin.post("/api/v1/maintenance-plans", json=plan_body(world, asset_id)).json()

    def run(_: int) -> int:
        client = make_client("dispatcher.a@t.test", world["org_a"])
        return client.post("/api/v1/maintenance/generate", json={"as_of": "2026-12-28"}).json()[
            "created_requests"
        ]

    with ThreadPoolExecutor(max_workers=4) as pool:
        created = sum(pool.map(run, range(4)))
    assert created == 9  # 2 Nov ... 28 Dec weekly, no matter how many runs raced
    assert count_requests(engine, plan["id"]) == 9
    with engine.connect() as conn:
        distinct = conn.execute(
            text("SELECT count(DISTINCT plan_date) FROM service_requests WHERE plan_id = :p"),
            {"p": plan["id"]},
        ).scalar_one()
    assert distinct == 9


def test_the_database_itself_refuses_a_duplicate_event(world, make_client, asset_id, engine):
    from sqlalchemy.exc import IntegrityError

    admin = make_client("dispatcher.a@t.test", world["org_a"])
    plan = admin.post("/api/v1/maintenance-plans", json=plan_body(world, asset_id)).json()
    admin.post("/api/v1/maintenance/generate", json={"as_of": "2026-11-02"})
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO service_requests (organization_id, title, description, category_id, "
                "property_id, priority, status, created_by_user_id, plan_id, plan_date, "
                "created_at, updated_at) SELECT organization_id, title, description, category_id, "
                "property_id, priority, status, created_by_user_id, plan_id, plan_date, "
                "now(), now() "
                "FROM service_requests WHERE plan_id = :p"
            ),
            {"p": plan["id"]},
        )


def test_monthly_plan_follows_the_calendar_and_future_events_wait(world, make_client, asset_id):
    admin = make_client("dispatcher.a@t.test", world["org_a"])
    admin.post(
        "/api/v1/maintenance-plans",
        json=plan_body(world, asset_id, frequency="MONTHLY", first_date="2026-01-31"),
    )
    result = admin.post("/api/v1/maintenance/generate", json={"as_of": "2026-03-31"}).json()
    assert result["created_requests"] == 3  # 31 Jan, 28 Feb, 31 Mar
    nothing = admin.post("/api/v1/maintenance/generate", json={"as_of": "2026-04-29"}).json()
    assert nothing["created_requests"] == 0  # 30 April is still in the future


def test_a_plan_with_a_start_date_in_the_future_generates_nothing_yet(world, make_client, asset_id):
    admin = make_client("dispatcher.a@t.test", world["org_a"])
    admin.post(
        "/api/v1/maintenance-plans", json=plan_body(world, asset_id, first_date="2030-01-01")
    )
    assert (
        admin.post("/api/v1/maintenance/generate", json={"as_of": "2026-11-12"}).json()[
            "created_requests"
        ]
        == 0
    )


def test_disabling_a_plan_stops_future_generation_and_keeps_the_past(
    world, make_client, asset_id, engine
):
    admin = make_client("dispatcher.a@t.test", world["org_a"])
    plan = admin.post("/api/v1/maintenance-plans", json=plan_body(world, asset_id)).json()
    admin.post("/api/v1/maintenance/generate", json={"as_of": "2026-11-09"})
    off = admin.post(f"/api/v1/maintenance-plans/{plan['id']}/disable").json()
    assert off["is_active"] is False and off["next_date"] is None

    after = admin.post("/api/v1/maintenance/generate", json={"as_of": "2026-12-31"}).json()
    assert after["created_requests"] == 0
    assert count_requests(engine, plan["id"]) == 2  # the earlier requests are untouched


def test_a_retired_asset_stops_its_plan_and_cannot_get_a_new_one(
    world, make_client, asset_id, engine
):
    admin = make_client("dispatcher.a@t.test", world["org_a"])
    plan = admin.post("/api/v1/maintenance-plans", json=plan_body(world, asset_id)).json()
    admin.post("/api/v1/maintenance/generate", json={"as_of": "2026-11-02"})
    with engine.begin() as conn:
        conn.execute(text("UPDATE assets SET status = 'RETIRED' WHERE id = :a"), {"a": asset_id})

    assert (
        admin.post("/api/v1/maintenance/generate", json={"as_of": "2026-12-31"}).json()[
            "created_requests"
        ]
        == 0
    )
    assert count_requests(engine, plan["id"]) == 1
    refused = admin.post(
        "/api/v1/maintenance-plans", json=plan_body(world, asset_id, title="Another plan")
    )
    assert refused.status_code == 422 and refused.json()["error"]["code"] == "asset_retired"


def test_generated_requests_use_the_normal_lifecycle(world, make_client, asset_id):
    admin = make_client("dispatcher.a@t.test", world["org_a"])
    admin.post("/api/v1/maintenance-plans", json=plan_body(world, asset_id))
    admin.post("/api/v1/maintenance/generate", json={"as_of": "2026-11-02"})
    request = admin.get("/api/v1/requests").json()["items"][0]
    assert request["allowed_actions"] == ["TRIAGED", "CANCELED"]
    done = admin.post(
        f"/api/v1/requests/{request['id']}/transitions", json={"to_status": "TRIAGED"}
    )
    assert done.status_code == 200 and done.json()["status"] == "TRIAGED"
    notified = [n["type"] for n in admin.get("/api/v1/notifications").json()]
    assert "maintenance_due" in notified


def test_asset_summary_shows_open_work_and_the_next_planned_event(world, make_client, asset_id):
    admin = make_client("dispatcher.a@t.test", world["org_a"])
    admin.post(
        "/api/v1/maintenance-plans", json=plan_body(world, asset_id, first_date="2026-11-02")
    )
    admin.post("/api/v1/maintenance/generate", json={"as_of": "2026-11-09"})
    summary = admin.get(f"/api/v1/assets/{asset_id}/summary").json()
    assert summary["open_requests"] == 2 and summary["last_completed_at"] is None
    assert date.fromisoformat(summary["next_planned"]) > date(2026, 11, 2)


def test_plans_are_for_staff_of_the_same_organization_only(world, make_client, asset_id):
    admin = make_client("dispatcher.a@t.test", world["org_a"])
    plan = admin.post("/api/v1/maintenance-plans", json=plan_body(world, asset_id)).json()

    customer = make_client("customer.a@t.test", world["org_a"])
    assert customer.get("/api/v1/maintenance-plans").status_code == 403
    assert (
        customer.post("/api/v1/maintenance-plans", json=plan_body(world, asset_id)).status_code
        == 403
    )
    assert customer.post("/api/v1/maintenance/generate", json={}).status_code == 403

    outsider = make_client("dispatcher.b@t.test", world["org_b"])
    assert outsider.get("/api/v1/maintenance-plans").json() == []
    assert outsider.post(f"/api/v1/maintenance-plans/{plan['id']}/disable").status_code == 404
    assert outsider.get(f"/api/v1/assets/{asset_id}/summary").status_code == 404
    foreign = outsider.post("/api/v1/maintenance-plans", json=plan_body(world, asset_id))
    assert foreign.status_code == 404  # another organization's asset is not even visible


def test_plan_input_is_validated(world, make_client, asset_id):
    admin = make_client("dispatcher.a@t.test", world["org_a"])
    assert (
        admin.post(
            "/api/v1/maintenance-plans", json=plan_body(world, asset_id, frequency="DAILY")
        ).status_code
        == 422
    )
    assert (
        admin.post(
            "/api/v1/maintenance-plans", json=plan_body(world, asset_id, title="abc")
        ).status_code
        == 422
    )
