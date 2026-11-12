"""Notes, photos, completion, notifications and the technician task list (PostgreSQL)."""

import io
import os
import uuid
from pathlib import Path

import pytest
from PIL import Image

from tests.conftest import monday_based

pytestmark = pytest.mark.integration


def png_bytes(size=(40, 30), color=(30, 120, 220)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def cid() -> str:
    return uuid.uuid4().hex


def booked_request(world, make_client, *, start: bool = False):
    """request1 of org A assigned to tech1; optionally accepted and started."""
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    res = dispatcher.post(
        f"/api/v1/requests/{world['request1_a']}/assignments",
        json={
            "technician_id": world["tech1_a"],
            "start_at": monday_based(1, 10).isoformat(),
            "end_at": monday_based(1, 12).isoformat(),
        },
    )
    assert res.status_code == 201, res.text
    tech = make_client("tech1.a@t.test", world["org_a"])
    if start:
        for target in ("ACCEPTED", "IN_PROGRESS"):
            r = tech.post(
                f"/api/v1/requests/{world['request1_a']}/transitions", json={"to_status": target}
            )
            assert r.status_code == 200, r.text
    return dispatcher, tech


def upload(
    client, request_id, *, data=None, name="photo.png", command=None, purpose="after", **extra
):
    return client.post(
        f"/api/v1/requests/{request_id}/attachments",
        files={"file": (name, data if data is not None else png_bytes(), "image/png")},
        data={"client_command_id": command or cid(), "purpose": purpose, **extra},
    )


# ------------------------------------------------------------------ notes
def test_note_is_idempotent_and_conflicts_on_different_content(world, make_client):
    _, tech = booked_request(world, make_client)
    rid = world["request1_a"]
    command = cid()
    body = {
        "body": "Checked the unit, pressure is low.",
        "visibility": "internal",
        "client_command_id": command,
    }

    first = tech.post(f"/api/v1/requests/{rid}/notes", json=body)
    assert first.status_code == 201
    replay = tech.post(f"/api/v1/requests/{rid}/notes", json=body)
    assert replay.status_code == 200 and replay.json()["id"] == first.json()["id"]
    assert len(tech.get(f"/api/v1/requests/{rid}/notes").json()) == 1  # exactly one note

    different = tech.post(f"/api/v1/requests/{rid}/notes", json={**body, "body": "Something else"})
    assert different.status_code == 409
    assert different.json()["error"]["code"] == "idempotency_conflict"


def test_customer_never_sees_internal_notes_and_cannot_write_them(world, make_client):
    dispatcher, _ = booked_request(world, make_client)
    rid = world["request1_a"]
    dispatcher.post(
        f"/api/v1/requests/{rid}/notes",
        json={"body": "Public update", "visibility": "public", "client_command_id": cid()},
    )
    dispatcher.post(
        f"/api/v1/requests/{rid}/notes",
        json={"body": "Internal only", "visibility": "internal", "client_command_id": cid()},
    )

    customer = make_client("customer.a@t.test", world["org_a"])
    bodies = [n["body"] for n in customer.get(f"/api/v1/requests/{rid}/notes").json()]
    assert bodies == ["Public update"]
    forbidden = customer.post(
        f"/api/v1/requests/{rid}/notes",
        json={"body": "x", "visibility": "internal", "client_command_id": cid()},
    )
    assert forbidden.status_code == 403


def test_note_command_id_must_be_well_formed(world, make_client):
    _, tech = booked_request(world, make_client)
    res = tech.post(
        f"/api/v1/requests/{world['request1_a']}/notes",
        json={"body": "hi", "client_command_id": "short"},
    )
    assert res.status_code == 422


def test_reassigned_technician_gets_a_conflict_not_a_silent_success(world, make_client):
    dispatcher, tech = booked_request(world, make_client)
    rid = world["request1_a"]
    assignment = dispatcher.get(f"/api/v1/requests/{rid}/assignments").json()[0]
    dispatcher.post(f"/api/v1/assignments/{assignment['id']}/unassign", json={"reason": "swap"})

    late_note = tech.post(
        f"/api/v1/requests/{rid}/notes",
        json={"body": "Written while offline", "client_command_id": cid()},
    )
    assert late_note.status_code == 409
    assert late_note.json()["error"]["code"] == "assignment_changed"
    late_photo = upload(tech, rid)
    assert late_photo.status_code == 409


def test_other_organization_cannot_write_notes(world, make_client):
    booked_request(world, make_client)
    outsider = make_client("dispatcher.b@t.test", world["org_b"])
    res = outsider.post(
        f"/api/v1/requests/{world['request1_a']}/notes",
        json={"body": "hi there", "client_command_id": cid()},
    )
    assert res.status_code == 404


# ------------------------------------------------------------------ photos
def test_photo_upload_is_idempotent_and_downloadable_only_when_authorized(world, make_client):
    dispatcher, tech = booked_request(world, make_client)
    rid = world["request1_a"]
    command = cid()
    data = png_bytes()

    first = upload(tech, rid, data=data, command=command)
    assert first.status_code == 201
    meta = first.json()
    assert meta["content_type"] == "image/png" and meta["width"] == 40 and meta["height"] == 30
    replay = upload(tech, rid, data=data, command=command)
    assert replay.status_code == 200 and replay.json()["id"] == meta["id"]
    assert len(tech.get(f"/api/v1/requests/{rid}/attachments").json()) == 1  # one file only

    clash = upload(tech, rid, data=png_bytes(color=(1, 2, 3)), command=command)
    assert clash.status_code == 409 and clash.json()["error"]["code"] == "idempotency_conflict"

    ok = tech.get(f"/api/v1/attachments/{meta['id']}/file")
    assert ok.status_code == 200 and ok.content == data
    assert ok.headers["content-type"] == "image/png"
    assert ok.headers["x-content-type-options"] == "nosniff"

    outsider = make_client("dispatcher.b@t.test", world["org_b"])
    assert outsider.get(f"/api/v1/attachments/{meta['id']}/file").status_code == 404
    other_tech = make_client("tech2.a@t.test", world["org_a"])
    assert other_tech.get(f"/api/v1/attachments/{meta['id']}/file").status_code == 404
    assert dispatcher.get(f"/api/v1/attachments/{meta['id']}/file").status_code == 200


def test_customer_cannot_download_photos_attached_to_internal_notes(world, make_client):
    dispatcher, tech = booked_request(world, make_client)
    rid = world["request1_a"]
    note = tech.post(
        f"/api/v1/requests/{rid}/notes",
        json={"body": "Internal finding", "visibility": "internal", "client_command_id": cid()},
    ).json()
    photo = upload(tech, rid, note_id=str(note["id"])).json()
    open_photo = upload(tech, rid).json()

    customer = make_client("customer.a@t.test", world["org_a"])
    assert customer.get(f"/api/v1/attachments/{photo['id']}/file").status_code == 404
    assert customer.get(f"/api/v1/attachments/{open_photo['id']}/file").status_code == 200
    ids = [a["id"] for a in customer.get(f"/api/v1/requests/{rid}/attachments").json()]
    assert ids == [open_photo["id"]]


@pytest.mark.parametrize(
    ("payload", "name", "status", "code"),
    [
        (b"this is plain text, not an image", "photo.png", 422, "invalid_image"),
        (
            b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
            "photo.png",
            422,
            "unsupported_image_type",
        ),
        (b"", "empty.png", 422, "invalid_image"),
    ],
)
def test_invalid_or_unsupported_files_are_rejected(world, make_client, payload, name, status, code):
    _, tech = booked_request(world, make_client)
    res = upload(tech, world["request1_a"], data=payload, name=name)
    assert res.status_code == status
    assert res.json()["error"]["code"] == code


def test_oversized_file_is_rejected_and_nothing_is_stored(world, make_client):
    _, tech = booked_request(world, make_client)
    res = upload(tech, world["request1_a"], data=b"\x00" * (10 * 1024 * 1024 + 10))
    assert res.status_code == 413
    assert res.json()["error"]["code"] == "file_too_large"
    assert tech.get(f"/api/v1/requests/{world['request1_a']}/attachments").json() == []


def test_user_supplied_file_name_never_reaches_the_file_system(world, make_client):
    _, tech = booked_request(world, make_client)
    res = upload(tech, world["request1_a"], name="../../../../etc/passwd.png")
    assert res.status_code == 201
    root = Path(os.environ["UPLOAD_DIR"]).resolve()
    stored = [p for p in root.rglob("*") if p.is_file()]
    assert stored and all(root in p.resolve().parents for p in stored)
    assert all("passwd" not in p.name for p in stored)


def test_customer_photo_limit_is_three(world, make_client):
    customer = make_client("customer.a@t.test", world["org_a"])
    rid = world["request1_a"]
    for i in range(3):
        assert (
            upload(customer, rid, data=png_bytes(color=(i, i, i)), purpose="evidence").status_code
            == 201
        )
    fourth = upload(customer, rid, data=png_bytes(color=(9, 9, 9)), purpose="evidence")
    assert fourth.status_code == 422 and fourth.json()["error"]["code"] == "photo_limit"


# ------------------------------------------------------------------ completion
def test_completion_needs_a_summary_and_a_photo(world, make_client):
    _, tech = booked_request(world, make_client, start=True)
    rid = world["request1_a"]
    short = tech.post(
        f"/api/v1/requests/{rid}/complete", json={"summary": "done", "client_command_id": cid()}
    )
    assert short.status_code == 422 and short.json()["error"]["code"] == "summary_too_short"

    no_photo = tech.post(
        f"/api/v1/requests/{rid}/complete",
        json={"summary": "Replaced the filter and tested the unit.", "client_command_id": cid()},
    )
    assert no_photo.status_code == 422 and no_photo.json()["error"]["code"] == "photo_required"
    assert tech.get(f"/api/v1/requests/{rid}").json()["status"] == "IN_PROGRESS"  # nothing changed


def test_completion_succeeds_once_and_a_replay_does_nothing_more(world, make_client):
    dispatcher, tech = booked_request(world, make_client, start=True)
    rid = world["request1_a"]
    assert upload(tech, rid).status_code == 201
    command = cid()
    body = {"summary": "Replaced the filter and tested the unit.", "client_command_id": command}

    done = tech.post(f"/api/v1/requests/{rid}/complete", json=body)
    assert done.status_code == 200 and done.json()["status"] == "COMPLETED"
    replay = tech.post(f"/api/v1/requests/{rid}/complete", json=body)
    assert replay.status_code == 200 and replay.json()["status"] == "COMPLETED"

    history = [h["to_status"] for h in dispatcher.get(f"/api/v1/requests/{rid}/history").json()]
    assert history.count("COMPLETED") == 1  # one transition, not two
    notes = dispatcher.get(f"/api/v1/requests/{rid}/notes").json()
    assert [n["kind"] for n in notes] == ["completion"]
    assignment = dispatcher.get(f"/api/v1/requests/{rid}/assignments").json()[0]
    assert assignment["status"] == "COMPLETED"


def test_only_the_assigned_technician_can_complete(world, make_client):
    dispatcher, tech = booked_request(world, make_client, start=True)
    rid = world["request1_a"]
    upload(tech, rid)
    body = {"summary": "Replaced the filter and tested the unit.", "client_command_id": cid()}
    assert dispatcher.post(f"/api/v1/requests/{rid}/complete", json=body).status_code == 403
    other = make_client("tech2.a@t.test", world["org_a"])
    assert (
        other.post(
            f"/api/v1/requests/{rid}/complete", json={**body, "client_command_id": cid()}
        ).status_code
        == 409
    )


def test_cannot_complete_work_that_was_not_started(world, make_client):
    _, tech = booked_request(world, make_client)  # only SCHEDULED
    rid = world["request1_a"]
    upload(tech, rid)
    res = tech.post(
        f"/api/v1/requests/{rid}/complete",
        json={"summary": "Replaced the filter and tested the unit.", "client_command_id": cid()},
    )
    assert res.status_code == 409


# ------------------------------------------------------------------ notifications and tasks
def test_assignment_creates_a_private_notification_for_the_technician(world, make_client):
    dispatcher, tech = booked_request(world, make_client)
    mine = tech.get("/api/v1/notifications").json()
    assert [n["type"] for n in mine] == ["assignment_created"]
    assert mine[0]["read_at"] is None

    assert (
        dispatcher.get("/api/v1/notifications", params={"unread": True}).json() == []
    )  # not theirs
    other_tech = make_client("tech2.a@t.test", world["org_a"])
    assert other_tech.get("/api/v1/notifications").json() == []
    assert other_tech.post(f"/api/v1/notifications/{mine[0]['id']}/read").status_code == 404

    read = tech.post(f"/api/v1/notifications/{mine[0]['id']}/read")
    assert read.status_code == 200 and read.json()["read_at"] is not None
    assert tech.get("/api/v1/notifications", params={"unread": True}).json() == []


def test_technician_decline_notifies_the_dispatchers(world, make_client):
    dispatcher, tech = booked_request(world, make_client)
    assignment = dispatcher.get(f"/api/v1/requests/{world['request1_a']}/assignments").json()[0]
    tech.post(f"/api/v1/assignments/{assignment['id']}/decline", json={"reason": "sick"})
    types = [n["type"] for n in dispatcher.get("/api/v1/notifications").json()]
    assert "assignment_declined" in types


def test_my_tasks_lists_only_own_assignments_with_needed_data(world, make_client):
    dispatcher, tech = booked_request(world, make_client)
    tasks = tech.get("/api/v1/my/tasks").json()
    assert len(tasks) == 1
    task = tasks[0]
    assert task["request_id"] == world["request1_a"]
    assert task["assignment_status"] == "SCHEDULED"
    assert (
        task["allowed_actions"] == ["ACCEPTED", "TRIAGED"] or "ACCEPTED" in task["allowed_actions"]
    )
    assert task["property_address"] == "1 Test St" and task["customer_name"]

    other = make_client("tech2.a@t.test", world["org_a"])
    assert other.get("/api/v1/my/tasks").json() == []
    assert dispatcher.get("/api/v1/my/tasks").status_code == 403
