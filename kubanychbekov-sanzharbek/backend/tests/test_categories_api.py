"""Service categories admin (ORG-03)."""

import pytest

pytestmark = pytest.mark.integration

BODY = {
    "name": "Plumbing",
    "description": "Pipes and taps",
    "default_duration_min": 90,
    "required_skills": [" Plumbing ", "plumbing", "Water"],
}


def test_admin_creates_and_edits_a_category(world, admin):
    res = admin.post("/api/v1/categories", json=BODY)
    assert res.status_code == 201, res.text
    created = res.json()
    assert created["required_skills"] == ["plumbing", "water"] and created["is_active"] is True

    upd = admin.put(
        f"/api/v1/categories/{created['id']}",
        json={**BODY, "name": "Plumbing & water", "default_duration_min": 120},
    )
    assert upd.status_code == 200 and upd.json()["default_duration_min"] == 120
    feed = admin.get("/api/v1/audit", params={"action": "category."}).json()["items"]
    actions = [e["action"] for e in feed]
    assert actions == ["category.updated", "category.created"]


@pytest.mark.parametrize("minutes", [4, 481])
def test_duration_range_is_validated(world, admin, minutes):
    res = admin.post("/api/v1/categories", json={**BODY, "default_duration_min": minutes})
    assert res.status_code == 422


def test_name_is_unique_per_organization_only(world, admin):
    assert admin.post("/api/v1/categories", json=BODY).status_code == 201
    dup = admin.post("/api/v1/categories", json=BODY)
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "category_name_taken"
    other = admin.post("/api/v1/categories", json={**BODY, "name": "HVAC"})  # exists in org A
    assert other.status_code == 409
    existing = admin.get("/api/v1/categories").json()[0]
    clash = admin.put(f"/api/v1/categories/{existing['id']}", json={**BODY, "name": "Plumbing"})
    assert clash.status_code == 409


def test_disabled_category_keeps_history_and_blocks_new_requests(world, admin, make_client):
    cat = world["category_a"]
    customer = make_client("customer.a@t.test", world["org_a"])
    off = admin.put(
        f"/api/v1/categories/{cat}",
        json={"name": "HVAC", "description": "", "default_duration_min": 60, "is_active": False},
    )
    assert off.status_code == 200 and off.json()["is_active"] is False
    assert cat not in [c["id"] for c in customer.get("/api/v1/categories").json()]
    listed = admin.get("/api/v1/categories", params={"include_inactive": True}).json()
    assert cat in [c["id"] for c in listed]
    created = customer.post(
        "/api/v1/requests",
        json={
            "title": "Fan broken",
            "description": "The fan makes no sound and does not blow.",
            "category_id": cat,
            "property_id": world["property_a"],
            "priority": "NORMAL",
        },
    )
    assert created.status_code == 422 and created.json()["error"]["code"] == "category_inactive"
    # the existing request still shows its category: history is kept
    assert customer.get(f"/api/v1/requests/{world['request1_a']}").status_code == 200


def test_only_admins_and_own_organization(world, admin, make_client):
    for who in ("dispatcher.a@t.test", "customer.a@t.test", "tech1.a@t.test"):
        client = make_client(who, world["org_a"])
        assert client.post("/api/v1/categories", json=BODY).status_code == 403
        assert client.put(f"/api/v1/categories/{world['category_a']}", json=BODY).status_code == 403
    assert admin.put(f"/api/v1/categories/{world['category_b']}", json=BODY).status_code == 404
