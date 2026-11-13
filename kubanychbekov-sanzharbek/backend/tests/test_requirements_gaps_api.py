"""Gaps found in the final audit: list filters and sorting, rework notification, report
filters and money, organization settings, session revocation audit, request body limit."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from tests.conftest import monday_based

pytestmark = pytest.mark.integration


def assign(client, world, request_key="request1_a", tech="tech1_a", day=1, hour=10):
    res = client.post(
        f"/api/v1/requests/{world[request_key]}/assignments",
        json={
            "technician_id": world[tech],
            "start_at": monday_based(day, hour).isoformat(),
            "end_at": monday_based(day, hour + 2).isoformat(),
        },
    )
    assert res.status_code == 201, res.text


def test_request_list_filters_by_technician_and_dates_and_sorts_by_due(world, make_client):
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    assign(dispatcher, world)
    by_tech = dispatcher.get("/api/v1/requests", params={"technician_id": world["tech1_a"]}).json()
    assert [r["id"] for r in by_tech["items"]] == [world["request1_a"]] and by_tech["total"] == 1
    other = dispatcher.get("/api/v1/requests", params={"technician_id": world["tech2_a"]}).json()
    assert other["total"] == 0

    today = datetime.now(UTC).date()
    inside = dispatcher.get(
        "/api/v1/requests", params={"created_from": str(today), "created_to": str(today)}
    ).json()
    assert inside["total"] == 3
    outside = dispatcher.get(
        "/api/v1/requests", params={"created_to": str(today - timedelta(days=2))}
    ).json()
    assert outside["total"] == 0

    due = dispatcher.get("/api/v1/requests", params={"sort_by": "due_at", "descending": False})
    assert due.status_code == 200 and due.json()["total"] == 3
    deadlines = [r["sla"]["due_at"] for r in due.json()["items"]]
    assert deadlines == sorted(deadlines)  # earliest deadline first
    assert dispatcher.get("/api/v1/requests", params={"sort_by": "nope"}).status_code == 422


def test_rework_request_notifies_staff_and_the_technician(world, make_client, engine):
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    customer = make_client("customer.a@t.test", world["org_a"])
    assign(dispatcher, world)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE service_requests SET status = 'COMPLETED' WHERE id = :i"),
            {"i": world["request1_a"]},
        )
        conn.execute(text("UPDATE assignments SET status = 'COMPLETED'"))
    res = customer.post(
        f"/api/v1/requests/{world['request1_a']}/transitions",
        json={"to_status": "REOPENED", "reason": "The noise is back after two days."},
    )
    assert res.status_code == 200, res.text
    staff = dispatcher.get("/api/v1/notifications").json()
    tech = make_client("tech1.a@t.test", world["org_a"]).get("/api/v1/notifications").json()
    for feed in (staff, tech):
        assert any(n["type"] == "request_reopened" for n in feed)
    other_tech = make_client("tech2.a@t.test", world["org_a"]).get("/api/v1/notifications").json()
    assert not any(n["type"] == "request_reopened" for n in other_tech)


def test_report_filters_load_estimates_and_materials(world, make_client):
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    assign(dispatcher, world)
    today = datetime.now(UTC).date()
    window = {
        "date_from": str(today - timedelta(days=3)),
        "date_to": str(today + timedelta(days=14)),
    }
    report = dispatcher.get("/api/v1/reports/summary", params=window).json()
    load = report["technician_load"]
    assert load["scheduled_minutes"] == 120 and load["available_minutes"] > 0
    assert 0 < load["percent"] <= 100 and load["technicians"] == 2
    assert "Inactive technicians are excluded" in load["method"]
    assert report["upcoming_visits"][0]["request_id"] == world["request1_a"]
    assert report["overdue"] == 0 and report["materials_cost_cents"] == 0

    only_other = dispatcher.get(
        "/api/v1/reports/summary", params={**window, "technician_id": world["tech2_a"]}
    ).json()
    assert only_other["technician_load"]["scheduled_minutes"] == 0
    assert only_other["total"] == 0  # no request is booked on technician 2
    wrong_category = dispatcher.get(
        "/api/v1/reports/summary", params={**window, "category_id": 999999}
    ).json()
    assert wrong_category["total"] == 0

    customer = make_client("customer.a@t.test", world["org_a"])
    mine = customer.get("/api/v1/reports/summary", params=window).json()
    assert mine["technician_load"] is None and mine["materials_cost_cents"] is None
    assert mine["overdue"] is None


def test_report_period_is_validated(world, make_client):
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    bad = dispatcher.get(
        "/api/v1/reports/summary", params={"date_from": "2026-02-01", "date_to": "2026-01-01"}
    )
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "invalid_period"
    long = dispatcher.get(
        "/api/v1/reports/summary", params={"date_from": "2026-01-01", "date_to": "2026-12-31"}
    )
    assert long.status_code == 422 and long.json()["error"]["code"] == "period_too_long"


def test_organization_settings_admin_only_with_validation_and_audit(world, make_client, admin):
    assert admin.get("/api/v1/settings/organization").json()["timezone"] == "Asia/Bishkek"
    ok = admin.put(
        "/api/v1/settings/organization", json={"name": "Org A Ltd", "timezone": "Asia/Tashkent"}
    )
    assert ok.status_code == 200 and ok.json()["timezone"] == "Asia/Tashkent"
    for bad in (
        {"name": "x", "timezone": "Asia/Bishkek"},
        {"name": "Org", "timezone": "Mars/Base"},
    ):
        assert admin.put("/api/v1/settings/organization", json=bad).status_code == 422
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    forbidden = dispatcher.put(
        "/api/v1/settings/organization", json={"name": "Hacked", "timezone": "Asia/Bishkek"}
    )
    assert forbidden.status_code == 403
    feed = admin.get("/api/v1/audit", params={"action": "organization."}).json()["items"]
    assert feed[0]["before"]["timezone"] == "Asia/Bishkek"
    assert feed[0]["after"]["timezone"] == "Asia/Tashkent"


def test_logout_and_deactivation_audit_session_revocation(world, make_client, admin):
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    assert dispatcher.post("/api/v1/auth/logout").status_code == 204
    customer = make_client("customer.a@t.test", world["org_a"])
    assert customer.get("/api/v1/requests").status_code == 200
    admin.put(f"/api/v1/users/{world['customer_a']}", json={"is_active": False})
    assert customer.get("/api/v1/requests").status_code == 401
    feed = admin.get("/api/v1/audit", params={"action": "auth."}).json()["items"]
    assert "auth.sessions_revoked" in [e["action"] for e in feed]
    dump = str(feed)
    assert "Bearer" not in dump and "eyJ" not in dump  # no tokens in the audit feed


def test_oversized_json_body_is_refused_before_it_is_read(world, make_client):
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    big = {"title": "x" * (1024 * 1024 + 10), "description": "y"}
    res = dispatcher.post("/api/v1/requests", json=big)
    assert res.status_code == 413 and res.json()["error"]["code"] == "body_too_large"
    assert "request_id" in res.json()["error"]
    login = TestClient(app).post(
        "/api/v1/auth/login", json={"email": "a@b.c", "password": "z" * 2_000_000}
    )
    assert login.status_code == 413
