"""Customer feedback (COMM-07) and the audit feed (ORG-05) on PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration


def set_status(engine, request_id: int, status: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE service_requests SET status = :s WHERE id = :i"),
            {"s": status, "i": request_id},
        )


def test_customer_rates_finished_work_once(world, make_client, engine):
    customer = make_client("customer.a@t.test", world["org_a"])
    url = f"/api/v1/requests/{world['request1_a']}/feedback"

    assert customer.get(url).json() is None  # not rated yet
    early = customer.post(url, json={"rating": 5})
    assert early.status_code == 409 and early.json()["error"]["code"] == "request_not_finished"

    set_status(engine, world["request1_a"], "COMPLETED")
    created = customer.post(url, json={"rating": 4, "comment": "  Fast and tidy  "})
    assert created.status_code == 201, created.text
    assert created.json()["rating"] == 4 and created.json()["comment"] == "Fast and tidy"
    assert customer.get(url).json()["rating"] == 4

    again = customer.post(url, json={"rating": 1})
    assert again.status_code == 409 and again.json()["error"]["code"] == "feedback_exists"
    assert customer.get(url).json()["rating"] == 4  # the first rating stands


@pytest.mark.parametrize("rating", [0, 6, -1])
def test_rating_must_be_between_1_and_5(world, make_client, engine, rating):
    set_status(engine, world["request1_a"], "COMPLETED")
    customer = make_client("customer.a@t.test", world["org_a"])
    res = customer.post(f"/api/v1/requests/{world['request1_a']}/feedback", json={"rating": rating})
    assert res.status_code == 422


def test_only_the_owner_customer_can_rate_and_others_see_it(world, make_client, engine):
    set_status(engine, world["request1_a"], "COMPLETED")
    url = f"/api/v1/requests/{world['request1_a']}/feedback"

    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    assert dispatcher.post(url, json={"rating": 5}).status_code == 403

    other_org = make_client("customer.b@t.test", world["org_b"])
    assert other_org.post(url, json={"rating": 5}).status_code == 404  # no existence leak
    assert other_org.get(url).status_code == 404

    make_client("customer.a@t.test", world["org_a"]).post(url, json={"rating": 5})
    assert dispatcher.get(url).json()["rating"] == 5  # staff can read it


def test_two_simultaneous_ratings_store_exactly_one(world, make_client, engine):
    set_status(engine, world["request1_a"], "CLOSED")
    url = f"/api/v1/requests/{world['request1_a']}/feedback"
    clients = [make_client("customer.a@t.test", world["org_a"]) for _ in range(4)]
    with ThreadPoolExecutor(4) as pool:
        codes = sorted(pool.map(lambda c: c.post(url, json={"rating": 3}).status_code, clients))
    assert codes == [201, 409, 409, 409]
    with engine.connect() as conn:
        count = conn.scalar(text("SELECT count(*) FROM request_feedback"))
    assert count == 1


def test_audit_feed_is_admin_only_scoped_and_paged(world, make_client, admin, engine):
    admin.post("/api/v1/inventory", json={"code": "A-1", "name": "One", "unit": "pcs"})
    admin.post("/api/v1/inventory", json={"code": "A-2", "name": "Two", "unit": "pcs"})
    set_status(engine, world["request1_a"], "COMPLETED")
    make_client("customer.a@t.test", world["org_a"]).post(
        f"/api/v1/requests/{world['request1_a']}/feedback", json={"rating": 5}
    )

    feed = admin.get("/api/v1/audit").json()
    actions = [e["action"] for e in feed["items"]]
    assert actions[0] == "request.feedback_left"  # newest first
    assert actions.count("inventory.item_created") == 2
    assert feed["items"][0]["actor_name"] == "customer a"

    only_inventory = admin.get("/api/v1/audit", params={"action": "inventory."}).json()
    assert only_inventory["total"] == 2
    page = admin.get("/api/v1/audit", params={"limit": 1, "offset": 1}).json()
    assert len(page["items"]) == 1 and page["total"] == feed["total"]

    for who in ("dispatcher.a@t.test", "customer.a@t.test", "tech1.a@t.test"):
        assert make_client(who, world["org_a"]).get("/api/v1/audit").status_code == 403
    assert admin.get("/api/v1/audit", params={"limit": 0}).status_code == 422
    assert admin.get("/api/v1/audit", params={"limit": 1000}).status_code == 422


def test_audit_feed_never_shows_another_organization(world, make_client, admin, engine):
    admin.post("/api/v1/inventory", json={"code": "A-1", "name": "One", "unit": "pcs"})
    with engine.begin() as conn:
        user_id = conn.scalar(text("SELECT id FROM users WHERE email = 'admin.a@t.test'"))
        conn.execute(
            text(
                "INSERT INTO organization_memberships (organization_id, user_id, role, is_active, "
                "created_at, updated_at) VALUES (:o, :u, 'admin', true, now(), now())"
            ),
            {"o": world["org_b"], "u": user_id},
        )
    admin_b = make_client("admin.a@t.test", world["org_b"])
    assert admin_b.get("/api/v1/audit").json()["total"] == 0
