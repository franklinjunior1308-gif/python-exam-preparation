"""Inventory: non-negative stock, atomic idempotent write-off, races (PostgreSQL)."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest

from tests.conftest import monday_based

pytestmark = pytest.mark.integration


def cid() -> str:
    return uuid.uuid4().hex


def in_progress_request(world, make_client):
    """request1 of org A assigned, accepted and started by tech1."""
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
    for target in ("ACCEPTED", "IN_PROGRESS"):
        tech.post(f"/api/v1/requests/{world['request1_a']}/transitions", json={"to_status": target})
    return tech


def new_item(admin_client, code="FLT-1", stock="5", threshold="2", price=1050):
    res = admin_client.post(
        "/api/v1/inventory",
        json={
            "code": code,
            "name": "Filter",
            "unit": "pcs",
            "stock": stock,
            "reorder_threshold": threshold,
            "unit_price_cents": price,
        },
    )
    assert res.status_code == 201, res.text
    return res.json()


@pytest.fixture
def admin(world, make_client, engine):
    """An administrator of organization A (the base fixture only creates dispatchers/customers)."""
    from sqlalchemy import text

    with engine.begin() as conn:
        user_id = conn.execute(
            text(
                "INSERT INTO users "
                "(email, full_name, password_hash, is_active, created_at, updated_at) "
                "SELECT 'admin.a@t.test', 'admin a', password_hash, true, now(), now() "
                "FROM users WHERE email = 'dispatcher.a@t.test' RETURNING id"
            )
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO organization_memberships (organization_id, user_id, role, is_active, "
                "created_at, updated_at) VALUES (:o, :u, 'admin', true, now(), now())"
            ),
            {"o": world["org_a"], "u": user_id},
        )
    return make_client("admin.a@t.test", world["org_a"])


def test_admin_manages_items_and_stock_changes_are_recorded(world, admin):
    item = new_item(admin)
    assert Decimal(item["stock"]) == 5 and item["low_stock"] is False
    duplicate = admin.post("/api/v1/inventory", json={"code": "FLT-1", "name": "x", "unit": "pcs"})
    assert duplicate.status_code == 409 and duplicate.json()["error"]["code"] == "item_code_taken"

    more = admin.post(
        f"/api/v1/inventory/{item['id']}/replenish", json={"quantity": "10", "reason": "Delivery"}
    )
    assert more.status_code == 200 and Decimal(more.json()["stock"]) == 15
    assert (
        admin.post(
            f"/api/v1/inventory/{item['id']}/replenish", json={"quantity": "0", "reason": "x"}
        ).status_code
        == 422
    )
    assert (
        admin.post(
            f"/api/v1/inventory/{item['id']}/replenish", json={"quantity": "-3", "reason": "x"}
        ).status_code
        == 422
    )


def test_negative_stock_is_refused_by_the_database_itself(world, admin, engine):
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    item = new_item(admin)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text("UPDATE inventory_items SET stock = -1 WHERE id = :i"), {"i": item["id"]})


def test_low_stock_list_uses_the_threshold(world, admin):
    new_item(admin, code="A", stock="10", threshold="2")
    new_item(admin, code="B", stock="2", threshold="2")  # exactly at the threshold counts as low
    new_item(admin, code="C", stock="1", threshold="2")
    low = {i["code"] for i in admin.get("/api/v1/inventory", params={"low": True}).json()}
    assert low == {"B", "C"}


def test_materials_are_written_off_once_with_a_price_snapshot(world, make_client, admin):
    item = new_item(admin, stock="5", price=1050)
    tech = in_progress_request(world, make_client)
    command = cid()
    body = {"item_id": item["id"], "quantity": "2", "client_command_id": command}

    first = tech.post(f"/api/v1/requests/{world['request1_a']}/materials", json=body)
    assert first.status_code == 201
    assert first.json()["unit_price_cents"] == 1050 and first.json()["total_cents"] == 2100

    replay = tech.post(f"/api/v1/requests/{world['request1_a']}/materials", json=body)
    assert replay.status_code == 200 and replay.json()["id"] == first.json()["id"]
    stock = [i for i in admin.get("/api/v1/inventory").json() if i["id"] == item["id"]][0]
    assert Decimal(stock["stock"]) == 3  # reduced once, not twice

    usages = admin.get(f"/api/v1/requests/{world['request1_a']}/materials").json()
    assert len(usages) == 1 and usages[0]["unit_price_cents"] == 1050

    clash = tech.post(
        f"/api/v1/requests/{world['request1_a']}/materials", json={**body, "quantity": "1"}
    )
    assert clash.status_code == 409 and clash.json()["error"]["code"] == "idempotency_conflict"


def test_more_than_the_stock_is_a_conflict_without_any_change(world, make_client, admin):
    item = new_item(admin, stock="1")
    tech = in_progress_request(world, make_client)
    res = tech.post(
        f"/api/v1/requests/{world['request1_a']}/materials",
        json={"item_id": item["id"], "quantity": "1.5", "client_command_id": cid()},
    )
    assert res.status_code == 409 and res.json()["error"]["code"] == "insufficient_stock"
    stock = [i for i in admin.get("/api/v1/inventory").json() if i["id"] == item["id"]][0]
    assert Decimal(stock["stock"]) == 1  # untouched
    assert (
        admin.get(f"/api/v1/requests/{world['request1_a']}/materials").json() == []
    )  # no usage row


def test_parallel_write_offs_of_the_last_units_never_overdraw(world, make_client, admin):
    item = new_item(admin, stock="5")
    in_progress_request(world, make_client)

    def attempt(_: int) -> int:
        tech = make_client("tech1.a@t.test", world["org_a"])
        return tech.post(
            f"/api/v1/requests/{world['request1_a']}/materials",
            json={"item_id": item["id"], "quantity": "3", "client_command_id": cid()},
        ).status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        codes = sorted(pool.map(attempt, range(4)))
    assert codes == [201, 409, 409, 409]
    stock = [i for i in admin.get("/api/v1/inventory").json() if i["id"] == item["id"]][0]
    assert Decimal(stock["stock"]) == 2  # 5 - 3, never negative
    assert len(admin.get(f"/api/v1/requests/{world['request1_a']}/materials").json()) == 1


def test_same_command_sent_in_parallel_reduces_stock_once(world, make_client, admin):
    item = new_item(admin, stock="10")
    in_progress_request(world, make_client)
    command = cid()

    def attempt(_: int) -> int:
        tech = make_client("tech1.a@t.test", world["org_a"])
        return tech.post(
            f"/api/v1/requests/{world['request1_a']}/materials",
            json={"item_id": item["id"], "quantity": "4", "client_command_id": command},
        ).status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        codes = list(pool.map(attempt, range(4)))
    assert set(codes) <= {200, 201} and codes.count(201) == 1
    stock = [i for i in admin.get("/api/v1/inventory").json() if i["id"] == item["id"]][0]
    assert Decimal(stock["stock"]) == 6


def test_materials_only_while_in_progress_and_only_by_the_assigned_technician(
    world, make_client, admin
):
    item = new_item(admin)
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    dispatcher.post(
        f"/api/v1/requests/{world['request1_a']}/assignments",
        json={
            "technician_id": world["tech1_a"],
            "start_at": monday_based(1, 10).isoformat(),
            "end_at": monday_based(1, 12).isoformat(),
        },
    )
    body = {"item_id": item["id"], "quantity": "1", "client_command_id": cid()}
    tech = make_client("tech1.a@t.test", world["org_a"])
    early = tech.post(f"/api/v1/requests/{world['request1_a']}/materials", json=body)
    assert early.status_code == 409 and early.json()["error"]["code"] == "work_not_in_progress"

    for target in ("ACCEPTED", "IN_PROGRESS"):
        tech.post(f"/api/v1/requests/{world['request1_a']}/transitions", json={"to_status": target})
    other = make_client("tech2.a@t.test", world["org_a"])
    assert (
        other.post(
            f"/api/v1/requests/{world['request1_a']}/materials",
            json={**body, "client_command_id": cid()},
        ).status_code
        == 409
    )
    assert (
        dispatcher.post(
            f"/api/v1/requests/{world['request1_a']}/materials",
            json={**body, "client_command_id": cid()},
        ).status_code
        == 403
    )


def test_inventory_is_isolated_between_organizations(world, make_client, admin):
    item = new_item(admin)
    in_progress_request(world, make_client)
    outsider = make_client("dispatcher.b@t.test", world["org_b"])
    assert outsider.get("/api/v1/inventory").json() == []  # nothing of organization A is visible
    assert (
        outsider.post(
            f"/api/v1/inventory/{item['id']}/replenish", json={"quantity": "1", "reason": "x"}
        ).status_code
        == 403
    )
    customer = make_client("customer.a@t.test", world["org_a"])
    assert customer.get("/api/v1/inventory").status_code == 403
    assert customer.get(f"/api/v1/requests/{world['request1_a']}/materials").json() == []


def test_low_stock_after_a_write_off_notifies_the_staff(world, make_client, admin):
    item = new_item(admin, stock="3", threshold="2")
    tech = in_progress_request(world, make_client)
    tech.post(
        f"/api/v1/requests/{world['request1_a']}/materials",
        json={"item_id": item["id"], "quantity": "2", "client_command_id": cid()},
    )
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    assert "low_stock" in [n["type"] for n in dispatcher.get("/api/v1/notifications").json()]
