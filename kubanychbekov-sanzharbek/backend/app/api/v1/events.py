from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.deps import AuthDep, OrgDep
from app.core.config import get_settings
from app.services import events as service

router = APIRouter(tags=["events"])


@router.get("/events")
async def events(ctx: OrgDep, auth: AuthDep) -> StreamingResponse:
    """Server-Sent Events: `event: changed` hints (scope + request id, no data) for this user.

    Send the same Bearer token and X-Organization-Id as for any call; refetch after each hint.
    """
    settings = get_settings()
    viewer = service.Viewer(
        user_id=ctx.user.id, org_id=ctx.org_id, role=ctx.role, session_id=auth.session.id
    )
    return StreamingResponse(
        service.stream(
            viewer,
            poll_seconds=settings.events_poll_seconds,
            keepalive_seconds=settings.events_keepalive_seconds,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
