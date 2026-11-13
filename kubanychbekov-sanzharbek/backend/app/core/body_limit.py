"""Request body size limit (SEC-04): JSON calls are small, photo uploads may be up to 10 MiB.

Requests that declare a larger Content-Length are refused before the body is read. The photo
endpoint additionally checks the real size while reading (see `services/work.py`).
"""

import json
import re

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.errors import _body

JSON_LIMIT = 1 * 1024 * 1024
UPLOAD_LIMIT = 11 * 1024 * 1024  # 10 MiB image + multipart overhead
_UPLOAD_PATH = re.compile(r"^/api/v1/requests/\d+/attachments$")


class BodyLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = UPLOAD_LIMIT if _UPLOAD_PATH.match(scope["path"]) else JSON_LIMIT
        declared = next((v for k, v in scope["headers"] if k == b"content-length"), b"")
        if declared.isdigit() and int(declared) > limit:
            payload = json.dumps(
                _body("body_too_large", f"The request body is larger than {limit // 1024} KiB")
            ).encode()
            await send(
                {
                    "type": "http.response.start",
                    "status": 413,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(payload)).encode()),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": payload})
            return
        await self.app(scope, receive, send)
