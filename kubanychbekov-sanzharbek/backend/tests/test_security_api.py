"""Login rate limit (SEC-03) and request IDs with structured logs (SEC-08)."""

import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import PASSWORD


def test_every_response_has_a_request_id_and_a_good_caller_id_is_kept() -> None:
    client = TestClient(app)
    generated = client.get("/api/v1/health/live").headers["x-request-id"]
    assert len(generated) == 32
    kept = client.get("/api/v1/health/live", headers={"X-Request-ID": "trace-abc-12345"})
    assert kept.headers["x-request-id"] == "trace-abc-12345"
    # a hostile or oversized value is replaced, never echoed into logs or headers
    for bad in ("short", "x" * 200, "bad id with spaces", "a/b\\c;d"):
        got = client.get("/api/v1/health/live", headers={"X-Request-ID": bad})
        assert got.headers["x-request-id"] != bad


def test_error_bodies_carry_the_request_id() -> None:
    res = TestClient(app).get("/api/v1/requests", headers={"X-Request-ID": "report-from-user-1"})
    body = res.json()
    assert res.status_code == 401
    assert body["error"]["request_id"] == "report-from-user-1"
    assert res.headers["x-request-id"] == "report-from-user-1"


def test_access_log_is_one_json_line_without_secrets(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("fixflow.access")
    records: list[logging.LogRecord] = []

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = Capture()
    logger.addHandler(handler)
    try:
        TestClient(app).post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "Sup3r-Secret-Value!"},
            headers={"X-Request-ID": "log-check-123456"},
        )
    finally:
        logger.removeHandler(handler)
    line = next(
        r for r in records if getattr(r, "fields", {}).get("request_id") == "log-check-123456"
    )
    fields = line.fields  # ty: ignore[missing-attribute]
    assert fields["method"] == "POST" and fields["path"] == "/api/v1/auth/login"
    assert fields["status"] in (401, 500)  # 500 only when no database is configured for the run
    assert "duration_ms" in fields
    from app.core.request_context import JsonFormatter

    text = JsonFormatter().format(line)
    assert json.loads(text)["request_id"] == "log-check-123456"
    assert "Sup3r-Secret-Value" not in text and "nobody@example.com" not in text


@pytest.mark.integration
def test_five_wrong_passwords_lock_the_account_for_the_window(world, make_client):
    client = TestClient(app)
    login = {"email": "dispatcher.a@t.test"}
    for _ in range(5):
        res = client.post("/api/v1/auth/login", json={**login, "password": "wrong-password"})
        assert res.status_code == 401
    locked = client.post("/api/v1/auth/login", json={**login, "password": "wrong-password"})
    assert locked.status_code == 429 and locked.json()["error"]["code"] == "too_many_attempts"
    # the right password does not bypass the pause...
    right = client.post("/api/v1/auth/login", json={**login, "password": PASSWORD})
    assert right.status_code == 429
    # ...but other accounts are not affected
    assert make_client("customer.a@t.test", world["org_a"]) is not None


@pytest.mark.integration
def test_old_failures_do_not_count_and_the_case_of_the_email_is_ignored(world, engine):
    from sqlalchemy import text

    client = TestClient(app)
    email = "dispatcher.a@t.test"
    for _ in range(5):
        client.post("/api/v1/auth/login", json={"email": email, "password": "nope-nope"})
    shouted = client.post("/api/v1/auth/login", json={"email": email.upper(), "password": PASSWORD})
    assert shouted.status_code == 429
    with engine.begin() as conn:  # time passes: the failures leave the window
        conn.execute(text("UPDATE audit_events SET created_at = now() - interval '20 minutes'"))
    ok = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert ok.status_code == 200
