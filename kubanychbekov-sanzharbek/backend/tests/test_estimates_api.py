"""Estimate versions, decisions, concurrency and the start gate (PostgreSQL)."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from tests.conftest import monday_based

pytestmark = pytest.mark.integration

BODY = {
    "labor_minutes": 90,
    "labor_rate_cents": 120_000,
    "lines": [
        {"description": "Filter", "quantity": "2", "unit_price_cents": 1050},
        {"description": "Refrigerant", "quantity": "0.5", "unit_price_cents": 333},
    ],
}


def accepted_request(world, make_client):
    """request1 of org A assigned to tech1 and accepted, ready to start."""
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    dispatcher.post(
        f"/api/v1/requests/{world['request1_a']}/assignments",
        json={
            "technician_id": world["tech1_a"],
            "start_at": monday_based(1, 10).isoformat(),
            "end_at": monday_based(1, 12).isoformat(),
        },
    )
    tech = make_client("tech1.a@t.test", world["org_a"])
    tech.post(f"/api/v1/requests/{world['request1_a']}/transitions", json={"to_status": "ACCEPTED"})
    return dispatcher, tech


def start(tech, world):
    return tech.post(
        f"/api/v1/requests/{world['request1_a']}/transitions", json={"to_status": "IN_PROGRESS"}
    )


def test_totals_are_computed_in_whole_tyiyn(world, make_client):
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    est = dispatcher.post(f"/api/v1/requests/{world['request1_a']}/estimates", json=BODY).json()
    assert est["status"] == "DRAFT" and est["version"] == 1 and est["currency"] == "KGS"
    assert est["labor_cents"] == 180_000
    assert est["materials_cents"] == 2100 + 167  # 0.5 x 333 = 166.5 -> 167 (half-up)
    assert est["total_cents"] == 180_000 + 2100 + 167
    assert [ln["line_total_cents"] for ln in est["lines"]] == [2100, 167]


@pytest.mark.parametrize(
    "patch",
    [
        {"labor_minutes": -1},
        {"labor_rate_cents": -5},
        {"lines": [{"description": "x", "quantity": "0", "unit_price_cents": 10}]},
        {"lines": [{"description": "x", "quantity": "-1", "unit_price_cents": 10}]},
        {"lines": [{"description": "x", "quantity": "1", "unit_price_cents": -10}]},
    ],
)
def test_negative_costs_and_non_positive_quantities_are_rejected(world, make_client, patch):
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    res = dispatcher.post(
        f"/api/v1/requests/{world['request1_a']}/estimates", json={**BODY, **patch}
    )
    assert res.status_code == 422


def test_submitted_estimate_is_immutable_and_customer_decides(world, make_client):
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    customer = make_client("customer.a@t.test", world["org_a"])
    rid = world["request1_a"]
    est = dispatcher.post(f"/api/v1/requests/{rid}/estimates", json=BODY).json()

    assert customer.get(f"/api/v1/requests/{rid}/estimates").json() == []  # drafts are private
    assert (
        dispatcher.put(
            f"/api/v1/estimates/{est['id']}", json={**BODY, "labor_minutes": 30}
        ).status_code
        == 200
    )

    sent = dispatcher.post(f"/api/v1/estimates/{est['id']}/submit").json()
    assert sent["status"] == "AWAITING_APPROVAL"
    edit = dispatcher.put(f"/api/v1/estimates/{est['id']}", json=BODY)
    assert edit.status_code == 409 and edit.json()["error"]["code"] == "estimate_immutable"

    seen = customer.get(f"/api/v1/requests/{rid}/estimates").json()
    assert [e["status"] for e in seen] == ["AWAITING_APPROVAL"]

    approved = customer.post(
        f"/api/v1/estimates/{est['id']}/decision", json={"approve": True}
    ).json()
    assert approved["status"] == "APPROVED"
    assert approved["decided_by_user_id"] == world["customer_a"] and approved["decided_at"]
    again = customer.post(
        f"/api/v1/estimates/{est['id']}/decision", json={"approve": False, "reason": "no"}
    )
    assert again.status_code == 409 and again.json()["error"]["code"] == "estimate_not_pending"


def test_rejection_needs_a_reason_and_only_the_owner_can_decide(world, make_client):
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    rid = world["request1_a"]
    est = dispatcher.post(f"/api/v1/requests/{rid}/estimates", json=BODY).json()
    dispatcher.post(f"/api/v1/estimates/{est['id']}/submit")

    customer = make_client("customer.a@t.test", world["org_a"])
    assert (
        customer.post(
            f"/api/v1/estimates/{est['id']}/decision", json={"approve": False}
        ).status_code
        == 422
    )
    assert (
        dispatcher.post(
            f"/api/v1/estimates/{est['id']}/decision", json={"approve": True}
        ).status_code
        == 403
    )
    outsider = make_client("customer.b@t.test", world["org_b"])
    assert (
        outsider.post(f"/api/v1/estimates/{est['id']}/decision", json={"approve": True}).status_code
        == 404
    )

    rejected = customer.post(
        f"/api/v1/estimates/{est['id']}/decision",
        json={"approve": False, "reason": "too expensive"},
    )
    assert (
        rejected.json()["status"] == "REJECTED"
        and rejected.json()["decision_reason"] == "too expensive"
    )


def test_two_parallel_decisions_cannot_both_succeed(world, make_client):
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    est = dispatcher.post(f"/api/v1/requests/{world['request1_a']}/estimates", json=BODY).json()
    dispatcher.post(f"/api/v1/estimates/{est['id']}/submit")

    def decide(approve: bool) -> int:
        client = make_client("customer.a@t.test", world["org_a"])
        body = {"approve": approve, "reason": "changed my mind"}
        return client.post(f"/api/v1/estimates/{est['id']}/decision", json=body).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = sorted(pool.map(decide, [True, False]))
    assert codes == [200, 409]
    final = dispatcher.get(f"/api/v1/requests/{world['request1_a']}/estimates").json()[0]
    assert final["status"] in {"APPROVED", "REJECTED"}  # exactly one decision was recorded


def test_start_is_blocked_while_awaiting_or_rejected_and_allowed_after_approval(world, make_client):
    dispatcher, tech = accepted_request(world, make_client)
    rid = world["request1_a"]
    customer = make_client("customer.a@t.test", world["org_a"])
    est = dispatcher.post(f"/api/v1/requests/{rid}/estimates", json=BODY).json()
    dispatcher.post(f"/api/v1/estimates/{est['id']}/submit")

    blocked = start(tech, world)
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "estimate_not_approved"

    customer.post(
        f"/api/v1/estimates/{est['id']}/decision", json={"approve": False, "reason": "too high"}
    )
    assert start(tech, world).status_code == 409  # a rejected estimate still blocks

    # dispatcher replaces it with version 2, customer approves it, work starts
    v2 = dispatcher.post(
        f"/api/v1/requests/{rid}/estimates", json={**BODY, "labor_minutes": 60}
    ).json()
    assert v2["version"] == 2
    dispatcher.post(f"/api/v1/estimates/{v2['id']}/submit")
    versions = {
        e["version"]: e["status"]
        for e in dispatcher.get(f"/api/v1/requests/{rid}/estimates").json()
    }
    assert versions == {1: "SUPERSEDED", 2: "AWAITING_APPROVAL"}  # v1 history is kept

    customer.post(f"/api/v1/estimates/{v2['id']}/decision", json={"approve": True})
    assert start(tech, world).status_code == 200


def test_work_may_start_when_no_estimate_was_ever_submitted(world, make_client):
    dispatcher, tech = accepted_request(world, make_client)
    rid = world["request1_a"]
    dispatcher.post(f"/api/v1/requests/{rid}/estimates", json=BODY)  # only a draft
    assert start(tech, world).status_code == 200


def test_approval_of_one_version_does_not_cover_another(world, make_client):
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    customer = make_client("customer.a@t.test", world["org_a"])
    rid = world["request1_a"]
    v1 = dispatcher.post(f"/api/v1/requests/{rid}/estimates", json=BODY).json()
    dispatcher.post(f"/api/v1/estimates/{v1['id']}/submit")
    customer.post(f"/api/v1/estimates/{v1['id']}/decision", json={"approve": True})

    v2 = dispatcher.post(
        f"/api/v1/requests/{rid}/estimates", json={**BODY, "labor_minutes": 600}
    ).json()
    assert v2["status"] == "DRAFT" and v2["version"] == 2
    dispatcher.post(f"/api/v1/estimates/{v2['id']}/submit")
    statuses = {
        e["version"]: e["status"]
        for e in dispatcher.get(f"/api/v1/requests/{rid}/estimates").json()
    }
    assert statuses == {
        1: "SUPERSEDED",
        2: "AWAITING_APPROVAL",
    }  # the old approval no longer applies


def test_only_one_open_estimate_and_withdrawal(world, make_client):
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    rid = world["request1_a"]
    first = dispatcher.post(f"/api/v1/requests/{rid}/estimates", json=BODY).json()
    second = dispatcher.post(f"/api/v1/requests/{rid}/estimates", json=BODY)
    assert second.status_code == 409 and second.json()["error"]["code"] == "estimate_open"
    assert (
        dispatcher.post(f"/api/v1/estimates/{first['id']}/withdraw").json()["status"]
        == "SUPERSEDED"
    )
    assert dispatcher.post(f"/api/v1/requests/{rid}/estimates", json=BODY).json()["version"] == 2


def test_estimates_are_isolated_between_organizations_and_roles(world, make_client):
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    est = dispatcher.post(f"/api/v1/requests/{world['request1_a']}/estimates", json=BODY).json()
    outsider = make_client("dispatcher.b@t.test", world["org_b"])
    assert outsider.get(f"/api/v1/requests/{world['request1_a']}/estimates").status_code == 404
    assert outsider.put(f"/api/v1/estimates/{est['id']}", json=BODY).status_code == 404
    assert outsider.post(f"/api/v1/estimates/{est['id']}/submit").status_code == 404
    customer = make_client("customer.a@t.test", world["org_a"])
    assert (
        customer.post(f"/api/v1/requests/{world['request1_a']}/estimates", json=BODY).status_code
        == 403
    )
