"""What the technician app needs on a task: SLA, earlier jobs on the equipment, own availability
(MOB-01, MOB-02)."""

import pytest
from sqlalchemy import text

from tests.conftest import monday_based

pytestmark = pytest.mark.integration


def make_asset(dispatcher, world):
    res = dispatcher.post(
        "/api/v1/assets",
        json={
            "property_id": world["property_a"],
            "code": "AHU-1",
            "name": "Air handling unit",
            "asset_type": "HVAC unit",
        },
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def test_task_carries_sla_and_earlier_jobs_on_the_same_equipment(world, make_client, engine):
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    asset_id = make_asset(dispatcher, world)
    first, second = world["request1_a"], world["request2_a"]
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE service_requests SET asset_id = :a WHERE id IN (:x, :y)"),
            {"a": asset_id, "x": first, "y": second},
        )
        # the first job is already done, with the technician's closing note
        conn.execute(
            text("UPDATE service_requests SET status = 'COMPLETED' WHERE id = :x"), {"x": first}
        )
        conn.execute(
            text(
                "INSERT INTO request_status_history (organization_id, request_id, from_status, "
                "to_status, actor_user_id, created_at) VALUES (:o, :r, 'IN_PROGRESS', 'COMPLETED', "
                ":u, now())"
            ),
            {"o": world["org_a"], "r": first, "u": world["dispatcher_a"]},
        )
        conn.execute(
            text(
                "INSERT INTO work_notes (organization_id, request_id, author_user_id, visibility, "
                "kind, body, client_command_id, created_at) VALUES (:o, :r, :u, 'public', "
                "'completion', 'Replaced the belt and cleaned the filter.', 'cmd-hist-0001', now())"
            ),
            {"o": world["org_a"], "r": first, "u": world["tech1_user_a"]},
        )
    res = dispatcher.post(
        f"/api/v1/requests/{second}/assignments",
        json={
            "technician_id": world["tech1_a"],
            "start_at": monday_based(1, 10).isoformat(),
            "end_at": monday_based(1, 12).isoformat(),
        },
    )
    assert res.status_code == 201, res.text

    tech = make_client("tech1.a@t.test", world["org_a"])
    (task,) = tech.get("/api/v1/my/tasks").json()
    assert task["request_id"] == second
    assert task["sla"]["state"] in {"ON_TRACK", "AT_RISK", "OVERDUE"}
    assert task["sla"]["budget_minutes"] > 0
    (earlier,) = task["asset_history"]
    assert earlier["request_id"] == first
    assert earlier["result"] == "Replaced the belt and cleaned the filter."
    # nothing about money, customers or other staff leaks into the history
    assert set(earlier) == {"request_id", "title", "completed_at", "result"}


def test_technician_sees_own_availability_and_nobody_else_does(world, make_client):
    tech = make_client("tech1.a@t.test", world["org_a"])
    me = tech.get("/api/v1/my/availability")
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["skills"] == ["hvac"] and body["is_active"] is True
    assert [w["weekday"] for w in body["weekly"]] == [0, 1, 2, 3, 4]
    assert body["timezone"] == "Asia/Bishkek" and body["absences"] == []
    other = make_client("tech2.a@t.test", world["org_a"]).get("/api/v1/my/availability").json()
    assert other["skills"] == ["plumbing"]  # each technician only gets their own profile
    for who in ("dispatcher.a@t.test", "customer.a@t.test"):
        assert make_client(who, world["org_a"]).get("/api/v1/my/availability").status_code == 403
