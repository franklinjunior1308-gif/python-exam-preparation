"""Administrator edits of technician skills and availability (ORG-01)."""

import pytest

pytestmark = pytest.mark.integration

WEEK = [{"weekday": d, "start_time": "08:00:00", "end_time": "17:00:00"} for d in range(5)]


def url(world, key="tech1_a"):
    return f"/api/v1/technicians/{world[key]}/profile"


def test_admin_replaces_skills_and_hours(world, admin, make_client):
    body = {"skills": ["  Electrical ", "hvac", "HVAC", ""], "availability": WEEK}
    res = admin.put(url(world), json=body)
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["skills"] == ["electrical", "hvac"]  # trimmed, lower-cased, de-duplicated
    assert len(out["availability"]) == 5 and out["availability"][0]["start_time"] == "08:00:00"

    listed = make_client("dispatcher.a@t.test", world["org_a"]).get("/api/v1/technicians").json()
    mine = next(t for t in listed if t["id"] == world["tech1_a"])
    assert mine["skills"] == ["electrical", "hvac"]
    other = next(t for t in listed if t["id"] == world["tech2_a"])
    assert other["skills"] == ["plumbing"]  # nobody else was touched


def test_hours_can_be_cleared_and_technician_deactivated(world, admin):
    res = admin.put(url(world), json={"skills": [], "availability": [], "is_active": False})
    assert res.status_code == 200
    assert res.json()["skills"] == [] and res.json()["availability"] == []
    assert res.json()["is_active"] is False


@pytest.mark.parametrize(
    "availability",
    [
        [{"weekday": 7, "start_time": "08:00:00", "end_time": "17:00:00"}],
        [{"weekday": 1, "start_time": "17:00:00", "end_time": "08:00:00"}],
        [
            {"weekday": 1, "start_time": "08:00:00", "end_time": "12:00:00"},
            {"weekday": 1, "start_time": "11:00:00", "end_time": "15:00:00"},
        ],
    ],
)
def test_invalid_hours_are_refused_and_nothing_changes(world, admin, availability):
    before = admin.get("/api/v1/technicians").json()
    res = admin.put(url(world), json={"skills": ["hvac"], "availability": availability})
    assert res.status_code == 422
    assert admin.get("/api/v1/technicians").json() == before


def test_only_admins_and_only_inside_the_organization(world, admin, make_client):
    body = {"skills": ["hvac"], "availability": WEEK}
    for who in ("dispatcher.a@t.test", "customer.a@t.test", "tech1.a@t.test"):
        assert make_client(who, world["org_a"]).put(url(world), json=body).status_code == 403
    # a technician profile of organization B is invisible to administrator A
    assert admin.put(url(world, "tech1_b"), json=body).status_code == 404


def test_change_is_written_to_the_audit_feed(world, admin):
    admin.put(url(world), json={"skills": ["welding"], "availability": WEEK})
    feed = admin.get("/api/v1/audit", params={"action": "technician."}).json()
    assert feed["total"] == 1
    event = feed["items"][0]
    assert event["after"]["skills"] == ["welding"] and event["before"]["skills"] == ["hvac"]
