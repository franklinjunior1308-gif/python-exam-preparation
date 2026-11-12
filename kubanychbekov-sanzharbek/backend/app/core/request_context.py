"""Request ID and structured access log (SEC-08).

Every request gets an id (the caller's `X-Request-ID` when it looks sane, otherwise a new one).
The id is returned in the response header, copied into error bodies and written to one JSON log
line, so a user report can be matched to the server log. Passwords, tokens and request bodies are
never logged.
"""

import json
import logging
import re
import time
import uuid
from contextvars import ContextVar

from starlette.types import ASGIApp, Message, Receive, Scope, Send

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
access_log = logging.getLogger("fixflow.access")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"), "level": record.levelname}
        extra = getattr(record, "fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        else:
            payload["message"] = record.getMessage()
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging() -> None:
    """Idempotent: JSON lines on stdout for the access log."""
    if access_log.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    access_log.addHandler(handler)
    access_log.setLevel(logging.INFO)
    access_log.propagate = False


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = next(
            (v.decode("latin-1") for k, v in scope["headers"] if k == b"x-request-id"), ""
        )
        rid = incoming if _SAFE_ID.match(incoming) else uuid.uuid4().hex
        token = request_id_var.set(rid)
        started = time.perf_counter()
        status = 500

        async def send_with_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message.setdefault("headers", []).append((b"x-request-id", rid.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        except Exception:
            access_log.exception("unhandled error", extra={"fields": {"request_id": rid}})
            raise
        finally:
            access_log.info(
                "request",
                extra={
                    "fields": {
                        "request_id": rid,
                        "method": scope["method"],
                        "path": scope["path"],
                        "status": status,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                    }
                },
            )
            request_id_var.reset(token)
