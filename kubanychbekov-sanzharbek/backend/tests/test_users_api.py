"""Staff and roles (ORG-04, AUTH-05) on PostgreSQL."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import monday_based

pytestmark = pytest.mark.integration

NEW = {
    "email": "  New.Person@T.test ",
    "full_name": "New Person",
    "role": "dispatcher",
    "password": "Start-Pass-12",
}


def users_by_email(admin):
    return {u["email"]: u for u in admin.get("/api/v1/users").json()}


def test_only_admins_manage_staff(world, admin, make_client):
    for who in ("dispatcher.a@t.test", "customer.a@t.test", "tech1.a@t.test"):
        client = make_client(who, world["org_a"])
        assert client.get("/api/v1/users").status_code == 403
        assert client.post("/api/v1/users", json=NEW).status_code == 403
        target = f"/api/v1/users/{world['dispatcher_a']}"
        assert client.put(target, json={"role": "admin"}).status_code == 403
    assert "dispatcher.a@t.test" in users_by_email(admin)


def test_admin_creates_a_member_who_can_sign_in(world, admin):
    res = admin.post("/api/v1/users", json=NEW)
    assert res.status_code == 201, res.text
    assert res.json()["email"] == "new.person@t.test" and res.json()["role"] == "dispatcher"
    login = TestClient(app).post(
        "/api/v1/auth/login", json={"email": "new.person@t.test", "password": "Start-Pass-12"}
    )
    assert login.status_code == 200
    again = admin.post("/api/v1/users", json=NEW)
    assert again.status_code == 409 and again.json()["error"]["code"] == "already_member"


@pytest.mark.parametrize("password", ["short1", "onlyletterslong", "1234567890123"])
def test_weak_initial_passwords_are_refused(world, admin, password):
    assert admin.post("/api/v1/users", json={**NEW, "password": password}).status_code == 422


def test_new_technician_gets_a_schedulable_profile(world, admin):
    res = admin.post("/api/v1/users", json={**NEW, "role": "technician"})
    assert res.status_code == 201 and res.json()["technician_id"] is not None
    techs = {t["id"] for t in admin.get("/api/v1/technicians").json()}
    assert res.json()["technician_id"] in techs


def test_role_change_is_audited_and_never_touches_other_orgs(world, admin):
    res = admin.put(f"/api/v1/users/{world['dispatcher_a']}", json={"role": "customer"})
    assert res.status_code == 200 and res.json()["role"] == "customer"
    event = admin.get("/api/v1/audit", params={"action": "user.role_changed"}).json()["items"][0]
    assert event["before"] == {"role": "dispatcher"} and event["after"] == {"role": "customer"}
    foreign = admin.put(f"/api/v1/users/{world['dispatcher_b']}", json={"role": "admin"})
    assert foreign.status_code == 404
    assert all(u["email"].endswith("@t.test") for u in admin.get("/api/v1/users").json())
    assert "dispatcher.b@t.test" not in users_by_email(admin)


def test_the_last_administrator_cannot_be_removed(world, admin):
    me = users_by_email(admin)["admin.a@t.test"]["id"]
    for body in ({"role": "dispatcher"}, {"is_active": False}):
        res = admin.put(f"/api/v1/users/{me}", json=body)
        assert res.status_code == 409 and res.json()["error"]["code"] == "last_admin"
    # with a second administrator the first may step down
    other = admin.post("/api/v1/users", json={**NEW, "role": "admin"}).json()["id"]
    assert admin.put(f"/api/v1/users/{me}", json={"role": "dispatcher"}).status_code == 200
    assert other


def test_deactivation_revokes_sessions_and_blocks_access(world, admin, make_client):
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    assert dispatcher.get("/api/v1/requests").status_code == 200
    res = admin.put(f"/api/v1/users/{world['dispatcher_a']}", json={"is_active": False})
    assert res.status_code == 200 and res.json()["is_active"] is False
    assert dispatcher.get("/api/v1/requests").status_code == 401  # session revoked at once
    assert admin.get("/api/v1/audit", params={"action": "user.deactivated"}).json()["total"] == 1
    back = admin.put(f"/api/v1/users/{world['dispatcher_a']}", json={"is_active": True})
    assert back.json()["is_active"] is True


def test_technician_with_active_jobs_cannot_be_deactivated(world, admin, make_client):
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    dispatcher.post(
        f"/api/v1/requests/{world['request1_a']}/assignments",
        json={
            "technician_id": world["tech1_a"],
            "start_at": monday_based(1, 10).isoformat(),
            "end_at": monday_based(1, 12).isoformat(),
        },
    )
    res = admin.put(f"/api/v1/users/{world['tech1_user_a']}", json={"is_active": False})
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "technician_has_active_assignments"
