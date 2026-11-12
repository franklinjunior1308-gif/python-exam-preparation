from collections.abc import Iterator

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app


class _FailingSession:
    def execute(self, *_args: object, **_kwargs: object) -> None:
        raise RuntimeError("database is down")


def _failing_db() -> Iterator[_FailingSession]:
    yield _FailingSession()


def test_live_is_ok() -> None:
    response = TestClient(app).get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_fails_when_database_is_down() -> None:
    app.dependency_overrides[get_db] = _failing_db
    try:
        response = TestClient(app).get("/api/v1/health/ready")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503
