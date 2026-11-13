"""Properties and equipment (ASSET-01..04) on PostgreSQL."""

import io
import uuid

import pytest
from PIL import Image

from tests.conftest import monday_based

pytestmark = pytest.mark.integration

PROPERTY = {"name": "Annex", "address": "5 Lenin St", "contact_instructions": " Ask the guard "}


def asset_body(world, **over):
    body = {
        "property_id": world["property_a"],
        "code": "PMP-77",
        "name": "Booster pump",
        "asset_type": "Pump",
        "serial_number": "SN-1",
        "installed_on": "2024-05-01",
        "status": "ACTIVE",
        "notes": "Basement",
    }
    return {**body, **over}


def test_staff_manage_properties_and_everyone_else_is_refused(world, make_client):
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    created = dispatcher.post("/api/v1/properties", json=PROPERTY)
    assert created.status_code == 201, created.text
    assert created.json()["contact_instructions"] == "Ask the guard"
    pid = created.json()["id"]
    off = dispatcher.put(f"/api/v1/properties/{pid}", json={**PROPERTY, "is_active": False})
    assert off.status_code == 200 and off.json()["is_active"] is False
    # a deactivated property leaves the pick list but stays available to staff with the flag
    assert pid not in [p["id"] for p in dispatcher.get("/api/v1/properties").json()]
    listed = dispatcher.get("/api/v1/properties", params={"include_inactive": True}).json()
    assert pid in [p["id"] for p in listed]
    for who in ("customer.a@t.test", "tech1.a@t.test"):
        client = make_client(who, world["org_a"])
        assert client.post("/api/v1/properties", json=PROPERTY).status_code == 403
    assert (
        dispatcher.put(f"/api/v1/properties/{world['property_b']}", json=PROPERTY).status_code
        == 404
    )
    assert dispatcher.post("/api/v1/properties", json={**PROPERTY, "name": " "}).status_code == 422


def test_equipment_code_is_unique_and_property_must_be_own(world, make_client):
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    first = dispatcher.post("/api/v1/assets", json=asset_body(world))
    assert first.status_code == 201, first.text
    assert first.json()["serial_number"] == "SN-1" and first.json()["installed_on"] == "2024-05-01"
    dup = dispatcher.post("/api/v1/assets", json=asset_body(world))
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "asset_code_taken"
    foreign = dispatcher.post(
        "/api/v1/assets", json=asset_body(world, code="X-1", property_id=world["property_b"])
    )
    assert foreign.status_code == 404
    bad = dispatcher.post("/api/v1/assets", json=asset_body(world, code="X-2", status="BROKEN"))
    assert bad.status_code == 422


def test_editing_equipment_keeps_its_code_and_audits_changes(world, make_client, admin):
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    aid = dispatcher.post("/api/v1/assets", json=asset_body(world)).json()["id"]
    body = {
        k: v
        for k, v in asset_body(world, name="Booster pump 2", status="OUT_OF_SERVICE").items()
        if k != "code"
    }
    res = dispatcher.put(f"/api/v1/assets/{aid}", json=body)
    assert res.status_code == 200 and res.json()["code"] == "PMP-77"
    assert res.json()["status"] == "OUT_OF_SERVICE"
    feed = admin.get("/api/v1/audit", params={"action": "asset."}).json()["items"]
    assert [e["action"] for e in feed] == ["asset.updated", "asset.created"]


def test_retired_equipment_stays_retired_and_blocks_new_plans(world, make_client):
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    aid = dispatcher.post("/api/v1/assets", json=asset_body(world)).json()["id"]
    body = {k: v for k, v in asset_body(world, status="RETIRED").items() if k != "code"}
    assert dispatcher.put(f"/api/v1/assets/{aid}", json=body).status_code == 200
    back = dispatcher.put(f"/api/v1/assets/{aid}", json={**body, "status": "ACTIVE"})
    assert back.status_code == 409 and back.json()["error"]["code"] == "asset_retired"
    plan = dispatcher.post(
        "/api/v1/maintenance-plans",
        json={
            "asset_id": aid,
            "category_id": world["category_a"],
            "title": "Yearly check",
            "description": "Check everything on the unit.",
            "priority": "NORMAL",
            "frequency": "MONTHLY",
            "first_date": "2030-01-01",
        },
    )
    assert plan.status_code in (409, 422)  # ASSET-04: no new plans for retired equipment


def png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 10, 10)).save(buf, format="PNG")
    return buf.getvalue()


def test_history_lists_jobs_with_technician_result_materials_and_photos(world, make_client, admin):
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    customer = make_client("customer.a@t.test", world["org_a"])
    aid = dispatcher.post("/api/v1/assets", json=asset_body(world)).json()["id"]

    made = customer.post(
        "/api/v1/requests",
        json={
            "title": "Pump is noisy",
            "description": "The booster pump makes a loud noise at night.",
            "category_id": world["category_a"],
            "property_id": world["property_a"],
            "asset_id": aid,
            "priority": "NORMAL",
        },
    )
    assert made.status_code == 201, made.text
    rid = made.json()["id"]
    assert dispatcher.get(f"/api/v1/assets/{aid}/history").json()[0]["technicians"] == []

    dispatcher.post(f"/api/v1/requests/{rid}/transitions", json={"to_status": "TRIAGED"})
    dispatcher.post(
        f"/api/v1/requests/{rid}/assignments",
        json={
            "technician_id": world["tech1_a"],
            "start_at": monday_based(1, 10).isoformat(),
            "end_at": monday_based(1, 12).isoformat(),
        },
    )
    tech = make_client("tech1.a@t.test", world["org_a"])
    for target in ("ACCEPTED", "IN_PROGRESS"):
        assert (
            tech.post(f"/api/v1/requests/{rid}/transitions", json={"to_status": target}).status_code
            == 200
        )
    item = admin.post(
        "/api/v1/inventory",
        json={
            "code": "BRG-1",
            "name": "Bearing",
            "unit": "pcs",
            "stock": "5",
            "unit_price_cents": 2500,
        },
    ).json()
    used = tech.post(
        f"/api/v1/requests/{rid}/materials",
        json={"item_id": item["id"], "quantity": "2", "client_command_id": uuid.uuid4().hex},
    )
    assert used.status_code == 201, used.text
    up = tech.post(
        f"/api/v1/requests/{rid}/attachments",
        data={"purpose": "after", "client_command_id": uuid.uuid4().hex},
        files={"file": ("a.png", png(), "image/png")},
    )
    assert up.status_code == 201, up.text
    done = tech.post(
        f"/api/v1/requests/{rid}/complete",
        json={
            "summary": "Replaced the bearing and tested the pump.",
            "client_command_id": uuid.uuid4().hex,
        },
    )
    assert done.status_code == 200, done.text

    (entry,) = dispatcher.get(f"/api/v1/assets/{aid}/history").json()
    assert entry["request_id"] == rid and entry["status"] == "COMPLETED"
    assert entry["technicians"] == ["tech1 a"]
    assert entry["result"] == "Replaced the bearing and tested the pump."
    assert entry["completed_at"] is not None
    assert [(m["item_name"], m["total_cents"]) for m in entry["materials"]] == [("Bearing", 5000)]
    assert [f["purpose"] for f in entry["attachments"]] == ["after"]


def test_history_is_staff_only_and_organization_scoped(world, make_client):
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    aid = dispatcher.post("/api/v1/assets", json=asset_body(world)).json()["id"]
    assert dispatcher.get(f"/api/v1/assets/{aid}/history").json() == []
    for who in ("customer.a@t.test", "tech1.a@t.test"):
        assert (
            make_client(who, world["org_a"]).get(f"/api/v1/assets/{aid}/history").status_code == 403
        )
    other = make_client("dispatcher.b@t.test", world["org_b"])
    assert other.get(f"/api/v1/assets/{aid}/history").status_code == 404
