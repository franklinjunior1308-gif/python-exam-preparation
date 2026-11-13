"""Notes, photos, completion and the technician's task list (COMM-*, LIFE-05, MOB-*)."""

import hashlib
import io
import uuid
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import OrgContext
from app.core.config import get_settings
from app.core.errors import AppError
from app.domain.enums import (
    ACTIVE_ASSIGNMENT_STATUSES,
    AssignmentStatus,
    NoteVisibility,
    RequestStatus,
    Role,
)
from app.domain.lifecycle import TransitionError, allowed_targets, check_transition
from app.models import (
    Asset,
    Assignment,
    EvidenceFile,
    Property,
    RequestStatusHistory,
    ServiceCategory,
    ServiceRequest,
    TechnicianAbsence,
    TechnicianAvailability,
    TechnicianProfile,
    TechnicianSkill,
    User,
    WorkNote,
)
from app.schemas.work import (
    AbsenceOut,
    AvailabilitySpan,
    MyAvailabilityOut,
    MyTaskOut,
    NoteCreate,
    NoteOut,
    TaskHistoryItem,
)
from app.services import sla as sla_service
from app.services.audit import record_audit
from app.services.notifications import notify, notify_staff
from app.services.requests import assigned_set, get_request

MAX_BYTES = 10 * 1024 * 1024  # 10 MiB per image (COMM-05)
MAX_SIDE = 8000
MAX_PIXELS = 40_000_000
MIN_SUMMARY = 20  # LIFE-05
CUSTOMER_PHOTO_LIMIT = 3  # REQ-01
PURPOSES = {"before", "after", "evidence"}
FORMATS = {
    "JPEG": ("image/jpeg", "jpg"),
    "PNG": ("image/png", "png"),
    "WEBP": ("image/webp", "webp"),
}
CLOSED = {RequestStatus.CLOSED, RequestStatus.CANCELED}

Image.MAX_IMAGE_PIXELS = MAX_PIXELS  # decompression-bomb guard


def _writable_request(db: Session, ctx: OrgContext, request_id: int) -> ServiceRequest:
    """Load a request the caller may add notes or photos to.

    A technician whose assignment was taken away (e.g. while offline) gets a 409 conflict that
    the mobile app turns into a visible "conflict" entry (MOB-07), not a misleading 404.
    """
    if ctx.role == Role.TECHNICIAN:
        req = db.scalar(
            select(ServiceRequest).where(
                ServiceRequest.id == request_id, ServiceRequest.organization_id == ctx.org_id
            )
        )
        if req is None:
            raise AppError(404, "request_not_found", "Request not found")
        if req.status in CLOSED:
            raise AppError(409, "request_closed", "This request is closed")
        if req.id not in assigned_set(db, ctx, [req.id]):
            raise AppError(409, "assignment_changed", "This request is no longer assigned to you")
        return req
    req = get_request(db, ctx, request_id)
    if req.status in CLOSED:
        raise AppError(409, "request_closed", "This request is closed")
    return req


def _note_out(db: Session, note: WorkNote, author_name: str | None = None) -> NoteOut:
    if author_name is None:
        author = db.get(User, note.author_user_id)
        author_name = author.full_name if author else ""
    out = NoteOut.model_validate(note)
    out.author_name = author_name
    return out


# ---------------------------------------------------------------- notes
def add_note(
    db: Session, ctx: OrgContext, request_id: int, data: NoteCreate
) -> tuple[NoteOut, bool]:
    """Create a note. Repeating the same command id with the same content returns the original."""
    req = _writable_request(db, ctx, request_id)
    if ctx.role == Role.CUSTOMER and data.visibility != NoteVisibility.PUBLIC:
        raise AppError(403, "forbidden", "Customers can only write public notes")
    body = data.body.strip()
    if not body:
        raise AppError(422, "validation_error", "A note cannot be empty")

    existing = db.scalar(
        select(WorkNote).where(
            WorkNote.organization_id == ctx.org_id,
            WorkNote.client_command_id == data.client_command_id,
        )
    )
    if existing is not None:
        same = (
            existing.request_id == req.id
            and existing.author_user_id == ctx.user.id
            and existing.body == body
            and existing.visibility == data.visibility
        )
        if not same:
            raise AppError(409, "idempotency_conflict", "This command id was used for another note")
        return _note_out(db, existing, ctx.user.full_name), False

    note = WorkNote(
        organization_id=ctx.org_id,
        request_id=req.id,
        author_user_id=ctx.user.id,
        visibility=data.visibility,
        body=body,
        client_command_id=data.client_command_id,
    )
    db.add(note)
    try:
        db.flush()
    except IntegrityError:  # a parallel retry won the race: return what it stored
        db.rollback()
        return add_note(db, ctx, request_id, data)
    record_audit(
        db,
        action="note.created",
        object_type="work_note",
        object_id=note.id,
        organization_id=ctx.org_id,
        actor_user_id=ctx.user.id,
        after={"request_id": req.id, "visibility": data.visibility.value},
    )
    db.commit()
    return _note_out(db, note, ctx.user.full_name), True


def list_notes(db: Session, ctx: OrgContext, request_id: int) -> list[NoteOut]:
    req = get_request(db, ctx, request_id)
    query = (
        select(WorkNote, User.full_name)
        .join(User, User.id == WorkNote.author_user_id)
        .where(WorkNote.request_id == req.id, WorkNote.organization_id == ctx.org_id)
        .order_by(WorkNote.id)
    )
    if ctx.role == Role.CUSTOMER:  # customers never see internal notes (COMM-01)
        query = query.where(WorkNote.visibility == NoteVisibility.PUBLIC)
    return [_note_out(db, note, name) for note, name in db.execute(query)]


# ---------------------------------------------------------------- photos
def _inspect_image(data: bytes) -> tuple[str, str, int, int]:
    """Validate by decoding the bytes, never by trusting the filename or Content-Type."""
    try:
        with Image.open(io.BytesIO(data)) as probe:
            fmt = probe.format
            width, height = probe.size
            probe.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        raise AppError(422, "invalid_image", "The file is not a valid image") from None
    if fmt not in FORMATS:
        raise AppError(422, "unsupported_image_type", "Only JPEG, PNG and WebP images are accepted")
    if max(width, height) > MAX_SIDE or width * height > MAX_PIXELS:
        raise AppError(422, "image_dimensions_too_large", "The image dimensions are too large")
    content_type, extension = FORMATS[fmt]
    return content_type, extension, width, height


def _storage_root() -> Path:
    return Path(get_settings().upload_dir).resolve()


def add_attachment(
    db: Session,
    ctx: OrgContext,
    request_id: int,
    *,
    data: bytes,
    purpose: str,
    client_command_id: str,
    note_id: int | None,
) -> tuple[EvidenceFile, bool]:
    if len(data) > MAX_BYTES:
        raise AppError(413, "file_too_large", "Images can be at most 10 MiB")
    if purpose not in PURPOSES:
        raise AppError(422, "validation_error", "purpose must be before, after or evidence")
    req = _writable_request(db, ctx, request_id)
    digest = hashlib.sha256(data).hexdigest()

    existing = db.scalar(
        select(EvidenceFile).where(
            EvidenceFile.organization_id == ctx.org_id,
            EvidenceFile.client_command_id == client_command_id,
        )
    )
    if existing is not None:
        same = (
            existing.sha256 == digest
            and existing.request_id == req.id
            and existing.uploaded_by_user_id == ctx.user.id
        )
        if not same:
            raise AppError(409, "idempotency_conflict", "This command id was used for another file")
        return existing, False

    if ctx.role == Role.CUSTOMER:
        count = db.scalar(
            select(func.count())
            .select_from(EvidenceFile)
            .where(
                EvidenceFile.request_id == req.id, EvidenceFile.uploaded_by_user_id == ctx.user.id
            )
        )
        if (count or 0) >= CUSTOMER_PHOTO_LIMIT:
            raise AppError(422, "photo_limit", "At most 3 photos per request from a customer")
    if note_id is not None:
        linked = db.scalar(
            select(WorkNote.id).where(
                WorkNote.id == note_id,
                WorkNote.request_id == req.id,
                WorkNote.organization_id == ctx.org_id,
            )
        )
        if linked is None:
            raise AppError(404, "note_not_found", "Note not found on this request")

    content_type, extension, width, height = _inspect_image(data)

    # server-generated path: user-supplied names never reach the file system (COMM-05)
    key = f"{ctx.org_id}/{req.id}/{uuid.uuid4().hex}.{extension}"
    path = _storage_root() / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    try:
        record = EvidenceFile(
            organization_id=ctx.org_id,
            request_id=req.id,
            note_id=note_id,
            uploaded_by_user_id=ctx.user.id,
            purpose=purpose,
            content_type=content_type,
            size_bytes=len(data),
            sha256=digest,
            storage_key=key,
            width=width,
            height=height,
            client_command_id=client_command_id,
        )
        db.add(record)
        db.flush()
        record_audit(
            db,
            action="file.uploaded",
            object_type="evidence_file",
            object_id=record.id,
            organization_id=ctx.org_id,
            actor_user_id=ctx.user.id,
            after={"request_id": req.id, "purpose": purpose, "size_bytes": len(data)},
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        path.unlink(missing_ok=True)
        return add_attachment(
            db,
            ctx,
            request_id,
            data=data,
            purpose=purpose,
            client_command_id=client_command_id,
            note_id=note_id,
        )
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)  # a failed upload leaves nothing reachable behind
        raise
    return record, True


def _visible_files_query(ctx: OrgContext, request_id: int):
    query = select(EvidenceFile).where(
        EvidenceFile.request_id == request_id, EvidenceFile.organization_id == ctx.org_id
    )
    if ctx.role == Role.CUSTOMER:  # files attached to internal notes stay internal
        hidden = select(WorkNote.id).where(
            WorkNote.request_id == request_id, WorkNote.visibility == NoteVisibility.INTERNAL
        )
        query = query.where(EvidenceFile.note_id.is_(None) | EvidenceFile.note_id.not_in(hidden))
    return query.order_by(EvidenceFile.id)


def list_attachments(db: Session, ctx: OrgContext, request_id: int) -> list[EvidenceFile]:
    req = get_request(db, ctx, request_id)
    return list(db.scalars(_visible_files_query(ctx, req.id)))


def open_attachment(db: Session, ctx: OrgContext, attachment_id: int) -> tuple[Path, EvidenceFile]:
    """Resolve a file only if the caller may see its request, then confirm the path is inside the
    upload folder. 404 for everything else, so other organizations learn nothing."""
    record = db.scalar(
        select(EvidenceFile).where(
            EvidenceFile.id == attachment_id, EvidenceFile.organization_id == ctx.org_id
        )
    )
    if record is None:
        raise AppError(404, "file_not_found", "File not found")
    get_request(db, ctx, record.request_id)  # visibility of the parent request
    allowed = db.scalar(
        _visible_files_query(ctx, record.request_id).where(EvidenceFile.id == record.id)
    )
    if allowed is None:
        raise AppError(404, "file_not_found", "File not found")
    path = (_storage_root() / record.storage_key).resolve()
    if _storage_root() not in path.parents or not path.is_file():
        raise AppError(404, "file_not_found", "File not found")
    return path, record


# ---------------------------------------------------------------- completion
def complete_work(
    db: Session, ctx: OrgContext, request_id: int, summary: str, client_command_id: str
) -> ServiceRequest:
    """IN_PROGRESS -> COMPLETED with a final note of 20+ characters and at least one photo.

    (Materials will be checked here once inventory exists.) Repeating the command is safe.
    """
    if ctx.role != Role.TECHNICIAN:
        raise AppError(403, "forbidden", "Only the assigned technician completes work")
    # A replay must be answered BEFORE any "is this still your job?" check: after the first
    # success the assignment is already COMPLETED, and an offline retry must not see a conflict.
    done = db.scalar(
        select(WorkNote).where(
            WorkNote.organization_id == ctx.org_id,
            WorkNote.client_command_id == client_command_id,
            WorkNote.kind == "completion",
        )
    )
    if done is not None:
        if done.request_id != request_id or done.author_user_id != ctx.user.id:
            raise AppError(409, "idempotency_conflict", "This command id was used elsewhere")
        replayed = db.scalar(
            select(ServiceRequest).where(
                ServiceRequest.id == request_id, ServiceRequest.organization_id == ctx.org_id
            )
        )
        if replayed is not None:
            return replayed

    req = _writable_request(db, ctx, request_id)
    text = summary.strip()
    if len(text) < MIN_SUMMARY:
        raise AppError(
            422, "summary_too_short", f"The final note needs at least {MIN_SUMMARY} characters"
        )
    photos = db.scalar(
        select(func.count())
        .select_from(EvidenceFile)
        .where(EvidenceFile.request_id == req.id, EvidenceFile.uploaded_by_user_id == ctx.user.id)
    )
    if not photos:
        raise AppError(422, "photo_required", "Add at least one photo before completing")

    source = req.status
    try:
        check_transition(
            source, RequestStatus.COMPLETED, ctx.role, is_assignee=True, via_dedicated_endpoint=True
        )
    except TransitionError as err:
        raise AppError(409, err.code, str(err)) from err

    moved = db.execute(
        update(ServiceRequest)
        .where(
            ServiceRequest.id == req.id,
            ServiceRequest.organization_id == ctx.org_id,
            ServiceRequest.status == source,
        )
        .values(status=RequestStatus.COMPLETED)
        .returning(ServiceRequest.id)
    )
    if moved.first() is None:
        db.rollback()
        raise AppError(409, "state_conflict", "The request was changed by someone else; reload")

    db.execute(
        update(Assignment)
        .where(
            Assignment.request_id == req.id,
            Assignment.organization_id == ctx.org_id,
            Assignment.status.in_(ACTIVE_ASSIGNMENT_STATUSES),
        )
        .values(status=AssignmentStatus.COMPLETED)
    )
    db.add(
        WorkNote(
            organization_id=ctx.org_id,
            request_id=req.id,
            author_user_id=ctx.user.id,
            visibility=NoteVisibility.PUBLIC,
            kind="completion",
            body=text,
            client_command_id=client_command_id,
        )
    )
    db.add(
        RequestStatusHistory(
            organization_id=ctx.org_id,
            request_id=req.id,
            from_status=source,
            to_status=RequestStatus.COMPLETED,
            actor_user_id=ctx.user.id,
            reason=text[:1000],
        )
    )
    record_audit(
        db,
        action="request.completed",
        object_type="service_request",
        object_id=req.id,
        organization_id=ctx.org_id,
        actor_user_id=ctx.user.id,
        before={"status": source.value},
        after={"status": RequestStatus.COMPLETED.value},
    )
    notify(
        db,
        org_id=ctx.org_id,
        user_id=req.created_by_user_id,
        type="request_completed",
        title=f"Request #{req.id} was completed",
        body=req.title,
        request_id=req.id,
    )
    notify_staff(
        db,
        org_id=ctx.org_id,
        type="request_completed",
        title=f"Request #{req.id} was completed",
        body=req.title,
        request_id=req.id,
    )
    db.commit()
    db.refresh(req)
    return req


# ---------------------------------------------------------------- technician task list
def my_tasks(db: Session, ctx: OrgContext, days_back: int) -> list[MyTaskOut]:
    """Assignments of the signed-in technician with the request data needed to do the work."""
    from datetime import timedelta

    if ctx.role != Role.TECHNICIAN:
        raise AppError(403, "forbidden", "Only technicians have a task list")
    since = datetime.now(UTC) - timedelta(days=days_back)
    rows = db.execute(
        select(Assignment, ServiceRequest, ServiceCategory, Property, Asset, User)
        .join(TechnicianProfile, TechnicianProfile.id == Assignment.technician_id)
        .join(
            ServiceRequest,
            (ServiceRequest.id == Assignment.request_id)
            & (ServiceRequest.organization_id == Assignment.organization_id),
        )
        .join(
            ServiceCategory,
            (ServiceCategory.id == ServiceRequest.category_id)
            & (ServiceCategory.organization_id == ServiceRequest.organization_id),
        )
        .join(
            Property,
            (Property.id == ServiceRequest.property_id)
            & (Property.organization_id == ServiceRequest.organization_id),
        )
        .outerjoin(
            Asset,
            (Asset.id == ServiceRequest.asset_id)
            & (Asset.organization_id == ServiceRequest.organization_id),
        )
        .join(User, User.id == ServiceRequest.created_by_user_id)
        .where(
            Assignment.organization_id == ctx.org_id,
            TechnicianProfile.user_id == ctx.user.id,
            Assignment.status.notin_([AssignmentStatus.CANCELED, AssignmentStatus.DECLINED]),
            Assignment.end_at >= since,
        )
        .order_by(Assignment.start_at)
    ).all()

    slas = sla_service.sla_for(db, ctx.org_id, ctx.organization.timezone, [r[1] for r in rows])
    history = _asset_history_for_tasks(db, ctx.org_id, rows)

    tasks: list[MyTaskOut] = []
    for assignment, req, category, prop, asset, customer in rows:
        active = assignment.status in ACTIVE_ASSIGNMENT_STATUSES
        tasks.append(
            MyTaskOut(
                assignment_id=assignment.id,
                assignment_status=assignment.status,
                start_at=assignment.start_at,
                end_at=assignment.end_at,
                timezone=assignment.timezone,
                request_id=req.id,
                title=req.title,
                description=req.description,
                priority=req.priority,
                request_status=req.status,
                allowed_actions=allowed_targets(
                    req.status, ctx.role, is_owner=False, is_assignee=active
                ),
                category_name=category.name,
                property_name=prop.name,
                property_address=prop.address,
                contact_instructions=prop.contact_instructions,
                asset_label=f"{asset.name} ({asset.code})" if asset else None,
                customer_name=customer.full_name,
                updated_at=req.updated_at,
                sla=slas.get(req.id),
                asset_history=history.get(req.id, []),
            )
        )
    return tasks


def _asset_history_for_tasks(db: Session, org_id: int, rows) -> dict[int, list[TaskHistoryItem]]:
    """Up to five earlier finished jobs on the same equipment, newest first (MOB-02).

    Only titles, dates and the technician's closing note: no costs, customers or other staff.
    """
    by_asset: dict[int, list[int]] = {}
    for _a, req, _c, _p, asset, _u in rows:
        if asset is not None:
            by_asset.setdefault(asset.id, []).append(req.id)
    out: dict[int, list[TaskHistoryItem]] = {}
    for asset_id, task_request_ids in by_asset.items():
        finished = db.execute(
            select(
                ServiceRequest.id, ServiceRequest.title, func.max(RequestStatusHistory.created_at)
            )
            .join(RequestStatusHistory, RequestStatusHistory.request_id == ServiceRequest.id)
            .where(
                ServiceRequest.organization_id == org_id,
                ServiceRequest.asset_id == asset_id,
                RequestStatusHistory.to_status == RequestStatus.COMPLETED,
                ServiceRequest.id.notin_(task_request_ids),
            )
            .group_by(ServiceRequest.id, ServiceRequest.title)
            .order_by(func.max(RequestStatusHistory.created_at).desc())
            .limit(5)
        ).all()
        ids = [r[0] for r in finished]
        notes = {}
        if ids:
            for rid, body in db.execute(
                select(WorkNote.request_id, WorkNote.body)
                .where(WorkNote.request_id.in_(ids), WorkNote.kind == "completion")
                .order_by(WorkNote.id)
            ):
                notes[rid] = body
        items = [
            TaskHistoryItem(request_id=rid, title=title, completed_at=done, result=notes.get(rid))
            for rid, title, done in finished
        ]
        for rid in task_request_ids:
            out[rid] = items
    return out


def my_availability(db: Session, ctx: OrgContext) -> MyAvailabilityOut:
    """The technician's own skills, weekly hours and absences (MOB-01)."""
    if ctx.role != Role.TECHNICIAN:
        raise AppError(403, "forbidden", "Only technicians have an availability profile")
    profile = db.scalar(
        select(TechnicianProfile).where(
            TechnicianProfile.organization_id == ctx.org_id,
            TechnicianProfile.user_id == ctx.user.id,
        )
    )
    if profile is None:
        raise AppError(404, "technician_not_found", "No technician profile")
    skills = sorted(
        db.scalars(select(TechnicianSkill.skill).where(TechnicianSkill.technician_id == profile.id))
    )
    weekly = db.scalars(
        select(TechnicianAvailability)
        .where(TechnicianAvailability.technician_id == profile.id)
        .order_by(TechnicianAvailability.weekday, TechnicianAvailability.start_time)
    )
    absences = db.scalars(
        select(TechnicianAbsence)
        .where(
            TechnicianAbsence.technician_id == profile.id,
            TechnicianAbsence.end_at >= datetime.now(UTC),
        )
        .order_by(TechnicianAbsence.start_at)
    )
    return MyAvailabilityOut(
        technician_id=profile.id,
        is_active=profile.is_active,
        skills=skills,
        timezone=ctx.organization.timezone,
        weekly=[
            AvailabilitySpan(weekday=w.weekday, start_time=w.start_time, end_time=w.end_time)
            for w in weekly
        ],
        absences=[
            AbsenceOut(start_at=a.start_at, end_at=a.end_at, reason=a.reason) for a in absences
        ],
    )
