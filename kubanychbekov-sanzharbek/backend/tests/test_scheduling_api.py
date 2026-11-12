"""Scheduling, lifecycle races and tenant isolation against a real PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest

from tests.conftest import monday_based

pytestmark = pytest.mark.integration


def window(day: int, start_hour: int, end_hour: int) -> dict[str, str]:
    return {
        "start_at": monday_based(day, start_hour).isoformat(),
        "end_at": monday_based(day, end_hour).isoformat(),
    }


def assign(client, request_id: int, technician_id: int, **times):
    return client.post(
        f"/api/v1/requests/{request_id}/assignments",
        json={"technician_id": technician_id, **times},
    )


def test_login_me_and_org_header_required(world, make_client):
    client = make_client("dispatcher.a@t.test", None)
    me = client.get("/api/v1/me").json()
    assert [m["role"] for m in me["memberships"]] == ["dispatcher"]
    assert client.get("/api/v1/requests").json()["error"]["code"] == "organization_required"


def test_candidates_report_missing_skills(world, make_client):
    client = make_client("dispatcher.a@t.test", world["org_a"])
    res = client.get(f"/api/v1/requests/{world['request1_a']}/candidates", params=window(1, 10, 12))
    assert res.status_code == 200
    by_id = {c["technician_id"]: c for c in res.json()}
    assert by_id[world["tech1_a"]]["available"] is True
    plumber = by_id[world["tech2_a"]]
    assert plumber["available"] is False
    assert plumber["reasons"][0]["code"] == "missing_skills"


def test_smart_assign_suggests_only_suitable_technicians_and_the_suggestion_can_be_applied(
    world, make_client
):
    client = make_client("dispatcher.a@t.test", world["org_a"])
    res = client.get(f"/api/v1/requests/{world['request1_a']}/suggestions")
    assert res.status_code == 200
    proposals = res.json()
    # only the HVAC technician qualifies; the plumber lacks the required skill
    assert [p["technician_id"] for p in proposals] == [world["tech1_a"]]
    best = proposals[0]
    assert best["is_best"] is True and best["within_desired_window"] is None

    applied = assign(
        client,
        world["request1_a"],
        best["technician_id"],
        start_at=best["start_at"],
        end_at=best["end_at"],
    )
    assert applied.status_code == 201  # a suggestion is a normal, valid booking

    # the next request gets a later slot: the first one is now busy
    second = client.get(f"/api/v1/requests/{world['request2_a']}/suggestions").json()[0]
    assert second["start_at"] >= best["end_at"]
    assert (
        assign(
            client,
            world["request2_a"],
            second["technician_id"],
            start_at=second["start_at"],
            end_at=second["end_at"],
        ).status_code
        == 201
    )


def test_smart_assign_is_staff_only_and_empty_after_scheduling(world, make_client):
    customer = make_client("customer.a@t.test", world["org_a"])
    assert customer.get(f"/api/v1/requests/{world['request1_a']}/suggestions").status_code == 403

    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    assign(dispatcher, world["request1_a"], world["tech1_a"], **window(1, 10, 12))
    assert dispatcher.get(f"/api/v1/requests/{world['request1_a']}/suggestions").json() == []
    outsider = make_client("dispatcher.b@t.test", world["org_b"])
    assert outsider.get(f"/api/v1/requests/{world['request1_a']}/suggestions").status_code == 404


def test_assign_moves_request_to_scheduled_and_is_idempotent(world, make_client):
    client = make_client("dispatcher.a@t.test", world["org_a"])
    first = assign(client, world["request1_a"], world["tech1_a"], **window(1, 10, 12))
    assert first.status_code == 201
    assert first.json()["status"] == "SCHEDULED"
    assert client.get(f"/api/v1/requests/{world['request1_a']}").json()["status"] == "SCHEDULED"

    replay = assign(client, world["request1_a"], world["tech1_a"], **window(1, 10, 12))
    assert replay.status_code == 200
    assert replay.json()["id"] == first.json()["id"]

    other = assign(client, world["request1_a"], world["tech1_a"], **window(1, 14, 16))
    assert other.status_code == 409
    assert other.json()["error"]["code"] == "already_assigned"


def test_overlapping_booking_is_rejected_but_adjacent_is_allowed(world, make_client):
    client = make_client("dispatcher.a@t.test", world["org_a"])
    assert (
        assign(client, world["request1_a"], world["tech1_a"], **window(1, 11, 12)).status_code
        == 201
    )

    clash = assign(client, world["request2_a"], world["tech1_a"], **window(1, 11, 13))
    assert clash.status_code == 409
    assert clash.json()["error"]["code"] == "schedule_conflict"

    adjacent = assign(client, world["request2_a"], world["tech1_a"], **window(1, 12, 13))
    assert adjacent.status_code == 201  # [11,12) and [12,13) do not overlap


def test_concurrent_overlapping_assignments_exactly_one_wins(world, make_client):
    def attempt(request_key: str) -> int:
        client = make_client("dispatcher.a@t.test", world["org_a"])
        return assign(client, world[request_key], world["tech1_a"], **window(2, 10, 12)).status_code

    with ThreadPoolExecutor(max_workers=3) as pool:
        codes = sorted(pool.map(attempt, ["request1_a", "request2_a", "request3_a"]))
    assert codes == [201, 409, 409]


@pytest.mark.parametrize(
    ("times", "code"),
    [
        (window(1, 7, 9), "outside_availability"),
        (window(1, 17, 19), "outside_availability"),
        (window(5, 10, 12), "outside_availability"),  # Saturday
    ],
)
def test_visit_outside_working_hours_is_rejected(world, make_client, times, code):
    client = make_client("dispatcher.a@t.test", world["org_a"])
    res = assign(client, world["request1_a"], world["tech1_a"], **times)
    assert res.status_code == 422
    assert res.json()["error"]["code"] == code


def test_past_and_too_short_visits_are_rejected(world, make_client):
    client = make_client("dispatcher.a@t.test", world["org_a"])
    past = monday_based(1, 10) - timedelta(days=30)
    res = assign(
        client,
        world["request1_a"],
        world["tech1_a"],
        start_at=past.isoformat(),
        end_at=(past + timedelta(hours=2)).isoformat(),
    )
    assert res.json()["error"]["code"] == "in_past"
    short = monday_based(1, 10)
    res = assign(
        client,
        world["request1_a"],
        world["tech1_a"],
        start_at=short.isoformat(),
        end_at=(short + timedelta(minutes=10)).isoformat(),
    )
    assert res.json()["error"]["code"] == "too_short"


def test_technician_without_the_skill_cannot_be_assigned(world, make_client):
    client = make_client("dispatcher.a@t.test", world["org_a"])
    res = assign(client, world["request1_a"], world["tech2_a"], **window(1, 10, 12))
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "missing_skills"


def test_unassign_frees_the_slot_and_keeps_history(world, make_client):
    client = make_client("dispatcher.a@t.test", world["org_a"])
    created = assign(client, world["request1_a"], world["tech1_a"], **window(1, 10, 12)).json()
    res = client.post(f"/api/v1/assignments/{created['id']}/unassign", json={"reason": "no part"})
    assert res.status_code == 200 and res.json()["status"] == "CANCELED"
    assert client.get(f"/api/v1/requests/{world['request1_a']}").json()["status"] == "TRIAGED"

    history = client.get(f"/api/v1/requests/{world['request1_a']}/assignments").json()
    assert [a["status"] for a in history] == ["CANCELED"]  # the old row is kept

    again = assign(client, world["request2_a"], world["tech1_a"], **window(1, 10, 12))
    assert again.status_code == 201  # the freed slot is available again


def test_technician_accepts_starts_and_sees_only_own_work(world, make_client):
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    assign(dispatcher, world["request1_a"], world["tech1_a"], **window(1, 10, 12))

    tech = make_client("tech1.a@t.test", world["org_a"])
    mine = tech.get("/api/v1/requests").json()
    assert [r["id"] for r in mine["items"]] == [world["request1_a"]]

    other_tech = make_client("tech2.a@t.test", world["org_a"])
    assert other_tech.get("/api/v1/requests").json()["items"] == []

    accepted = tech.post(
        f"/api/v1/requests/{world['request1_a']}/transitions", json={"to_status": "ACCEPTED"}
    )
    assert accepted.status_code == 200
    started = tech.post(
        f"/api/v1/requests/{world['request1_a']}/transitions", json={"to_status": "IN_PROGRESS"}
    )
    assert started.status_code == 200

    # another technician may not start someone else's job
    forbidden = other_tech.post(
        f"/api/v1/requests/{world['request1_a']}/transitions", json={"to_status": "IN_PROGRESS"}
    )
    assert forbidden.status_code == 404  # not even visible to them


def test_technician_decline_returns_request_to_triage(world, make_client):
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    created = assign(dispatcher, world["request1_a"], world["tech1_a"], **window(1, 10, 12)).json()
    tech = make_client("tech1.a@t.test", world["org_a"])
    res = tech.post(f"/api/v1/assignments/{created['id']}/decline", json={"reason": "sick"})
    assert res.status_code == 200 and res.json()["status"] == "DECLINED"
    assert dispatcher.get(f"/api/v1/requests/{world['request1_a']}").json()["status"] == "TRIAGED"


def test_concurrent_status_changes_only_one_succeeds(world, make_client):
    def attempt(_: int) -> int:
        client = make_client("dispatcher.a@t.test", world["org_a"])
        return client.post(
            f"/api/v1/requests/{world['request1_a']}/transitions",
            json={"to_status": "CANCELED", "reason": "duplicate"},
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = sorted(pool.map(attempt, range(2)))
    assert codes[0] == 200 and codes[1] in {403, 409}  # the loser sees a terminal state


def test_other_organization_cannot_read_or_change_data(world, make_client):
    outsider = make_client("dispatcher.b@t.test", world["org_b"])
    request_id = world["request1_a"]
    assert outsider.get(f"/api/v1/requests/{request_id}").status_code == 404
    assert outsider.get(f"/api/v1/requests/{request_id}/history").status_code == 404
    assert (
        outsider.post(
            f"/api/v1/requests/{request_id}/transitions",
            json={"to_status": "CANCELED", "reason": "x"},
        ).status_code
        == 404
    )
    assert assign(outsider, request_id, world["tech1_b"], **window(1, 10, 12)).status_code == 404

    # a technician id from another organization is never accepted either
    inside = make_client("dispatcher.a@t.test", world["org_a"])
    cross = assign(inside, world["request1_a"], world["tech1_b"], **window(1, 10, 12))
    assert cross.status_code == 404
    assert cross.json()["error"]["code"] == "technician_not_found"


def test_user_cannot_use_an_organization_they_do_not_belong_to(world, make_client):
    client = make_client("dispatcher.b@t.test", None)
    client.headers["X-Organization-Id"] = str(world["org_a"])
    res = client.get("/api/v1/requests")
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "not_a_member"


def test_customer_sees_only_own_requests_and_no_planning(world, make_client):
    customer = make_client("customer.a@t.test", world["org_a"])
    assert customer.get("/api/v1/technicians").status_code == 403
    assert customer.get(f"/api/v1/requests/{world['request1_a']}/assignments").json() == []
    assert customer.get("/api/v1/requests").json()["total"] == 3
    assert customer.get("/api/v1/requests", params={"q": "nothing-matches"}).json()["total"] == 0


def test_invalid_and_missing_tokens_are_rejected(world, make_client):
    from fastapi.testclient import TestClient

    from app.main import app

    anonymous = TestClient(app)
    assert anonymous.get("/api/v1/me").status_code == 401
    anonymous.headers["Authorization"] = "Bearer not-a-real-token"
    assert anonymous.get("/api/v1/me").json()["error"]["code"] == "invalid_token"

    client = make_client("dispatcher.a@t.test", world["org_a"])
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/me").json()["error"]["code"] == "session_expired"  # revoked


def test_disabled_technician_cannot_receive_work(world, make_client, engine):
    from sqlalchemy import text

    with engine.begin() as conn:
        conn.execute(
            text("UPDATE technician_profiles SET is_active = false WHERE id = :i"),
            {"i": world["tech1_a"]},
        )
    client = make_client("dispatcher.a@t.test", world["org_a"])
    res = assign(client, world["request1_a"], world["tech1_a"], **window(1, 10, 12))
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "technician_inactive"


def test_failed_login_is_audited_without_the_password(world, engine):
    from fastapi.testclient import TestClient
    from sqlalchemy import text

    from app.main import app

    res = TestClient(app).post(
        "/api/v1/auth/login", json={"email": "dispatcher.a@t.test", "password": "wrong-password"}
    )
    assert res.status_code == 401
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT before, after FROM audit_events WHERE action = 'auth.login_failed'")
        ).all()
    assert len(rows) == 1
    assert "wrong-password" not in str(rows[0])
