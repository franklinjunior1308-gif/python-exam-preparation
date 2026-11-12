from typing import Annotated

from fastapi import APIRouter, Form, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse

from app.api.deps import DbDep, OrgDep
from app.core.errors import AppError
from app.schemas.request import RequestOut
from app.schemas.work import (
    AttachmentOut,
    CommandId,
    CompleteIn,
    MyTaskOut,
    NoteCreate,
    NoteOut,
    NotificationOut,
)
from app.services import notifications as notification_service
from app.services import requests as request_service
from app.services import work as service

router = APIRouter(tags=["work"])

_BODY_SLACK = 1024 * 1024  # multipart framing around a 10 MiB image


@router.get("/my/tasks", response_model=list[MyTaskOut])
def my_tasks(
    ctx: OrgDep, db: DbDep, days_back: Annotated[int, Query(ge=0, le=60)] = 14
) -> list[MyTaskOut]:
    return service.my_tasks(db, ctx, days_back)


@router.get("/requests/{request_id}/notes", response_model=list[NoteOut])
def list_notes(request_id: int, ctx: OrgDep, db: DbDep) -> list[NoteOut]:
    return service.list_notes(db, ctx, request_id)


@router.post("/requests/{request_id}/notes", response_model=NoteOut, status_code=201)
def add_note(
    request_id: int, data: NoteCreate, ctx: OrgDep, db: DbDep, response: Response
) -> NoteOut:
    note, created = service.add_note(db, ctx, request_id, data)
    if not created:
        response.status_code = 200  # same command repeated: nothing new was made
    return note


@router.get("/requests/{request_id}/attachments", response_model=list[AttachmentOut])
def list_attachments(request_id: int, ctx: OrgDep, db: DbDep):
    return service.list_attachments(db, ctx, request_id)


@router.post("/requests/{request_id}/attachments", response_model=AttachmentOut, status_code=201)
def add_attachment(
    request_id: int,
    request: Request,
    file: UploadFile,
    client_command_id: Annotated[CommandId, Form()],
    ctx: OrgDep,
    db: DbDep,
    response: Response,
    purpose: Annotated[str, Form()] = "evidence",
    note_id: Annotated[int | None, Form()] = None,
):
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > service.MAX_BYTES + _BODY_SLACK:
        raise AppError(413, "file_too_large", "Images can be at most 10 MiB")
    data = file.file.read(service.MAX_BYTES + 1)
    record, created = service.add_attachment(
        db,
        ctx,
        request_id,
        data=data,
        purpose=purpose,
        client_command_id=client_command_id,
        note_id=note_id,
    )
    if not created:
        response.status_code = 200
    return record


@router.get("/attachments/{attachment_id}/file")
def download_attachment(attachment_id: int, ctx: OrgDep, db: DbDep) -> FileResponse:
    """Authenticated, authorized download; the bytes are never reachable by a public URL."""
    path, record = service.open_attachment(db, ctx, attachment_id)
    return FileResponse(
        path,
        media_type=record.content_type,
        headers={
            "Cache-Control": "private, max-age=600",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "inline",
        },
    )


@router.post("/requests/{request_id}/complete", response_model=RequestOut)
def complete(request_id: int, data: CompleteIn, ctx: OrgDep, db: DbDep) -> RequestOut:
    req = service.complete_work(db, ctx, request_id, data.summary, data.client_command_id)
    return request_service.to_out(req, ctx, request_service.assigned_set(db, ctx, [req.id]))


@router.get("/notifications", response_model=list[NotificationOut])
def notifications(
    ctx: OrgDep,
    db: DbDep,
    unread: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return notification_service.list_mine(db, ctx, unread, limit)


@router.post("/notifications/read-all")
def read_all(ctx: OrgDep, db: DbDep) -> dict[str, int]:
    return {"updated": notification_service.mark_all_read(db, ctx)}


@router.post("/notifications/{notification_id}/read", response_model=NotificationOut)
def read_one(notification_id: int, ctx: OrgDep, db: DbDep):
    return notification_service.mark_read(db, ctx, notification_id)
