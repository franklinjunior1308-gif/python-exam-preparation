"""Live updates (API-06): hints only, scoped to what the viewer may see."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.security import decode_access_token
from app.domain.enums import Role
from app.main import app
from app.services import events
from tests.conftest import monday_based

pytestmark = pytest.mark.integration


def viewer_of(client, world, org_key, user_key, role) -> events.Viewer:
    token = client.headers["Authorization"].removeprefix("Bearer ")
    session_id = decode_access_token(token)
    assert session_id is not None
    return events.Viewer(
        user_id=world[user_key],
        org_id=world[org_key],
        role=role,
        session_id=session_id,
    )


async def collect(viewer, trigger, seconds=1.5):
    """Open the stream, run `trigger` in a thread, return everything received meanwhile."""
    gen = events.stream(viewer, poll_seconds=0.1, keepalive_seconds=0.4)
    chunks = [await gen.__anext__()]  # preamble: the cursor is set before the change happens
    await asyncio.to_thread(trigger)
    try:
        async with asyncio.timeout(seconds):
            while True:
                chunks.append(await gen.__anext__())
    except TimeoutError:
        pass
    finally:
        await gen.aclose()
    return chunks


def changed(chunks):
    out = []
    for chunk in chunks:
        if chunk.startswith("event: changed"):
            out.append(json.loads(chunk.split("data: ", 1)[1]))
    return out


def assign(world, make_client):
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


def test_stream_needs_a_token_and_an_organization(world, make_client):
    assert TestClient(app).get("/api/v1/events").status_code == 401
    token_only = make_client("dispatcher.a@t.test", None)
    assert token_only.get("/api/v1/events").status_code == 400


def test_staff_receive_a_hint_with_ids_only(world, make_client):
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    viewer = viewer_of(dispatcher, world, "org_a", "dispatcher_a", Role.DISPATCHER)
    chunks = asyncio.run(collect(viewer, lambda: assign(world, make_client)))
    hints = changed(chunks)
    assert "assignments" in {h["scope"] for h in hints}
    assert all(set(h) == {"scope", "request_id", "at"} for h in hints)  # no data beyond ids
    assert any(h["request_id"] == world["request1_a"] for h in hints)
    assert any(c.startswith(": keepalive") for c in chunks)


def test_a_technician_hears_only_about_own_jobs(world, make_client):
    assigned = make_client("tech1.a@t.test", world["org_a"])
    other = make_client("tech2.a@t.test", world["org_a"])
    mine = viewer_of(assigned, world, "org_a", "tech1_user_a", Role.TECHNICIAN)
    stranger = viewer_of(other, world, "org_a", "tech2_user_a", Role.TECHNICIAN)

    async def both():
        return await asyncio.gather(
            collect(mine, lambda: assign(world, make_client)),
            collect(stranger, lambda: None),
        )

    # the change happens once, inside the first collector's trigger; both streams watch it
    got_mine, got_stranger = asyncio.run(both())
    assert any(h["request_id"] == world["request1_a"] for h in changed(got_mine))
    assert changed(got_stranger) == []


def test_customer_hears_only_about_own_requests(world, make_client, engine):
    customer = make_client("customer.a@t.test", world["org_a"])
    viewer = viewer_of(customer, world, "org_a", "customer_a", Role.CUSTOMER)

    def foreign_change():
        with engine.begin() as conn:  # a request of organization B changes
            conn.execute(
                text(
                    "INSERT INTO audit_events (organization_id, action, object_type, object_id, "
                    "created_at) VALUES "
                    "(:o, 'request.status_changed', 'service_request', :r, now())"
                ),
                {"o": world["org_b"], "r": str(world["request1_b"])},
            )

    chunks = asyncio.run(collect(viewer, foreign_change))
    assert changed(chunks) == []
    own = asyncio.run(collect(viewer, lambda: assign(world, make_client)))
    assert any(h["request_id"] == world["request1_a"] for h in changed(own))


def test_notifications_reach_only_their_recipient(world, make_client):
    tech = make_client("tech1.a@t.test", world["org_a"])
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    mine = viewer_of(tech, world, "org_a", "tech1_user_a", Role.TECHNICIAN)
    theirs = viewer_of(dispatcher, world, "org_a", "dispatcher_a", Role.DISPATCHER)

    async def both():
        return await asyncio.gather(
            collect(mine, lambda: assign(world, make_client)),
            collect(theirs, lambda: None),
        )

    got_tech, got_dispatcher = asyncio.run(both())
    assert any(h["scope"] == "notifications" for h in changed(got_tech))
    assert not any(h["scope"] == "notifications" for h in changed(got_dispatcher))


def test_stream_ends_when_the_session_is_revoked(world, make_client):
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    viewer = viewer_of(dispatcher, world, "org_a", "dispatcher_a", Role.DISPATCHER)

    async def run():
        gen = events.stream(viewer, poll_seconds=0.1, keepalive_seconds=5)
        await gen.__anext__()
        await asyncio.to_thread(dispatcher.post, "/api/v1/auth/logout")
        async with asyncio.timeout(5):
            async for _ in gen:
                pass
        return True

    assert asyncio.run(run())
