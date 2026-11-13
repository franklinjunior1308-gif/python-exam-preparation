"""SLA report (WEB-04): on-time vs late completions per period."""

from datetime import UTC, datetime, timedelta

import pytest

from tests.test_sla_api import make_request

pytestmark = pytest.mark.integration


def test_report_counts_on_time_late_and_ignores_old_or_open_requests(world, make_client, engine):
    now = datetime.now(UTC)
    # finished within a minute: on time
    quick = now - timedelta(days=3)
    make_request(
        engine, world, created=quick - timedelta(minutes=1), status="COMPLETED", completed=quick
    )
    # twenty days of waiting before completion: late for any priority
    make_request(
        engine,
        world,
        created=now - timedelta(days=20),
        priority="HIGH",
        status="CLOSED",
        completed=now - timedelta(days=1),
    )
    # completed long before the period, and one still open: neither is counted
    make_request(
        engine,
        world,
        created=now - timedelta(days=80),
        status="COMPLETED",
        completed=now - timedelta(days=60),
    )
    make_request(engine, world, created=now - timedelta(days=2), status="IN_PROGRESS")
    # another organization is never mixed in
    make_request(
        engine, world, created=now - timedelta(days=5), status="COMPLETED", completed=now, org="b"
    )

    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    report = dispatcher.get("/api/v1/reports/sla", params={"days": 30}).json()
    assert (report["total"], report["on_time"], report["late"]) == (2, 1, 1)
    by_priority = {row["priority"]: row for row in report["by_priority"]}
    assert by_priority["HIGH"] == {"priority": "HIGH", "total": 1, "late": 1}
    assert by_priority["NORMAL"] == {"priority": "NORMAL", "total": 1, "late": 0}
    assert report["avg_resolution_minutes"] > 0 and report["escalated"] == 0

    wide = dispatcher.get("/api/v1/reports/sla", params={"days": 90}).json()
    assert wide["total"] == 3
    short = dispatcher.get("/api/v1/reports/sla", params={"days": 2}).json()
    assert short["total"] == 1


def test_empty_period_and_access_rules(world, make_client):
    dispatcher = make_client("dispatcher.a@t.test", world["org_a"])
    empty = dispatcher.get("/api/v1/reports/sla").json()
    assert empty["total"] == 0 and empty["avg_resolution_minutes"] is None
    assert empty["by_priority"] == []
    for who in ("customer.a@t.test", "tech1.a@t.test"):
        assert make_client(who, world["org_a"]).get("/api/v1/reports/sla").status_code == 403
    assert dispatcher.get("/api/v1/reports/sla", params={"days": 0}).status_code == 422
    assert dispatcher.get("/api/v1/reports/sla", params={"days": 400}).status_code == 422
