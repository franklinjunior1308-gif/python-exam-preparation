"""Properties and equipment (ASSET-01..04): staff manage them, the history keeps every job."""

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import OrgContext
from app.core.errors import AppError
from app.domain.enums import AssetStatus, AssignmentStatus, RequestStatus, Role
from app.models import (
    Asset,
    Assignment,
    EvidenceFile,
    InventoryItem,
    MaterialUsage,
    Property,
    RequestStatusHistory,
    ServiceRequest,
    TechnicianProfile,
    User,
    WorkNote,
)
from app.schemas.catalog import (
    AssetIn,
    AssetUpdate,
    HistoryEntry,
    HistoryFile,
    HistoryMaterial,
    PropertyIn,
)
from app.services.audit import record_audit

STAFF = {Role.ADMIN, Role.DISPATCHER}
HISTORY_LIMIT = 100


def _require_staff(ctx: OrgContext) -> None:
    if ctx.role not in STAFF:
        raise AppError(403, "forbidden", "Only dispatchers and administrators manage this")


def create_property(db: Session, ctx: OrgContext, data: PropertyIn) -> Property:
    _require_staff(ctx)
    row = Property(
        organization_id=ctx.org_id,
        name=data.name,
        address=data.address,
        contact_instructions=(data.contact_instructions or "").strip() or None,
        is_active=data.is_active,
    )
    db.add(row)
    db.flush()
    record_audit(
        db,
        action="property.created",
        object_type="property",
        object_id=row.id,
        organization_id=ctx.org_id,
        actor_user_id=ctx.user.id,
        after={"name": row.name},
    )
    db.commit()
    return row


def update_property(db: Session, ctx: OrgContext, property_id: int, data: PropertyIn) -> Property:
    _require_staff(ctx)
    row = db.scalar(
        select(Property)
        .where(Property.id == property_id, Property.organization_id == ctx.org_id)
        .with_for_update()
    )
    if row is None:
        raise AppError(404, "property_not_found", "Property not found")
    before = {"name": row.name, "address": row.address, "is_active": row.is_active}
    row.name = data.name
    row.address = data.address
    row.contact_instructions = (data.contact_instructions or "").strip() or None
    row.is_active = data.is_active  # deactivating keeps history and old requests (DATA-06)
    record_audit(
        db,
        action="property.updated",
        object_type="property",
        object_id=row.id,
        organization_id=ctx.org_id,
        actor_user_id=ctx.user.id,
        before=before,
        after={"name": row.name, "address": row.address, "is_active": row.is_active},
    )
    db.commit()
    return row


def _own_property(db: Session, ctx: OrgContext, property_id: int) -> Property:
    row = db.scalar(
        select(Property).where(Property.id == property_id, Property.organization_id == ctx.org_id)
    )
    if row is None:
        raise AppError(404, "property_not_found", "Property not found")
    return row


def create_asset(db: Session, ctx: OrgContext, data: AssetIn) -> Asset:
    _require_staff(ctx)
    _own_property(db, ctx, data.property_id)
    row = Asset(
        organization_id=ctx.org_id,
        property_id=data.property_id,
        code=data.code,
        name=data.name,
        asset_type=data.asset_type,
        serial_number=(data.serial_number or "").strip() or None,
        installed_on=data.installed_on,
        status=data.status,
        notes=(data.notes or "").strip() or None,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError as err:  # unique (organization, code)
        db.rollback()
        raise AppError(409, "asset_code_taken", "Equipment with this code already exists") from err
    record_audit(
        db,
        action="asset.created",
        object_type="asset",
        object_id=row.id,
        organization_id=ctx.org_id,
        actor_user_id=ctx.user.id,
        after={"code": row.code, "status": row.status.value},
    )
    db.commit()
    return row


def update_asset(db: Session, ctx: OrgContext, asset_id: int, data: AssetUpdate) -> Asset:
    _require_staff(ctx)
    row = db.scalar(
        select(Asset)
        .where(Asset.id == asset_id, Asset.organization_id == ctx.org_id)
        .with_for_update()
    )
    if row is None:
        raise AppError(404, "asset_not_found", "Equipment not found")
    _own_property(db, ctx, data.property_id)
    if row.status == AssetStatus.RETIRED and data.status != AssetStatus.RETIRED:
        # a retired unit stays retired: its history and the ban on new plans must not be undone
        raise AppError(409, "asset_retired", "Retired equipment cannot be brought back")
    before = {"status": row.status.value, "name": row.name, "property_id": row.property_id}
    row.property_id = data.property_id
    row.name = data.name
    row.asset_type = data.asset_type
    row.serial_number = (data.serial_number or "").strip() or None
    row.installed_on = data.installed_on
    row.status = data.status
    row.notes = (data.notes or "").strip() or None
    record_audit(
        db,
        action="asset.retired" if data.status == AssetStatus.RETIRED else "asset.updated",
        object_type="asset",
        object_id=row.id,
        organization_id=ctx.org_id,
        actor_user_id=ctx.user.id,
        before=before,
        after={"status": row.status.value, "name": row.name, "property_id": row.property_id},
    )
    db.commit()
    return row


def asset_history(db: Session, ctx: OrgContext, asset_id: int) -> list[HistoryEntry]:
    """Requests on this equipment, newest first, with technicians, result, materials, photos."""
    _require_staff(ctx)
    asset = db.scalar(
        select(Asset.id).where(Asset.id == asset_id, Asset.organization_id == ctx.org_id)
    )
    if asset is None:
        raise AppError(404, "asset_not_found", "Equipment not found")
    requests = list(
        db.scalars(
            select(ServiceRequest)
            .where(ServiceRequest.organization_id == ctx.org_id, ServiceRequest.asset_id == asset)
            .order_by(ServiceRequest.created_at.desc(), ServiceRequest.id.desc())
            .limit(HISTORY_LIMIT)
        )
    )
    ids = [r.id for r in requests]
    if not ids:
        return []

    completed: dict[int, object] = {}
    for rid, moment in db.execute(
        select(RequestStatusHistory.request_id, RequestStatusHistory.created_at)
        .where(
            RequestStatusHistory.request_id.in_(ids),
            RequestStatusHistory.to_status == RequestStatus.COMPLETED,
        )
        .order_by(RequestStatusHistory.id)
    ):
        completed[rid] = moment  # the latest completion wins (after a rework)

    technicians: dict[int, list[str]] = defaultdict(list)
    for rid, name in db.execute(
        select(Assignment.request_id, User.full_name)
        .join(TechnicianProfile, TechnicianProfile.id == Assignment.technician_id)
        .join(User, User.id == TechnicianProfile.user_id)
        .where(
            Assignment.request_id.in_(ids),
            Assignment.status.notin_([AssignmentStatus.CANCELED, AssignmentStatus.DECLINED]),
        )
        .order_by(Assignment.id)
    ):
        if name not in technicians[rid]:
            technicians[rid].append(name)

    results: dict[int, str] = {}
    for rid, body in db.execute(
        select(WorkNote.request_id, WorkNote.body)
        .where(WorkNote.request_id.in_(ids), WorkNote.kind == "completion")
        .order_by(WorkNote.id)
    ):
        results[rid] = body

    materials: dict[int, list[HistoryMaterial]] = defaultdict(list)
    for usage, item_name in db.execute(
        select(MaterialUsage, InventoryItem.name)
        .join(InventoryItem, InventoryItem.id == MaterialUsage.item_id)
        .where(MaterialUsage.request_id.in_(ids))
        .order_by(MaterialUsage.id)
    ):
        total = round(usage.quantity * usage.unit_price_cents)
        materials[usage.request_id].append(
            HistoryMaterial(item_name=item_name, quantity=usage.quantity, total_cents=int(total))
        )

    files: dict[int, list[HistoryFile]] = defaultdict(list)
    for fid, rid, purpose in db.execute(
        select(EvidenceFile.id, EvidenceFile.request_id, EvidenceFile.purpose)
        .where(EvidenceFile.request_id.in_(ids))
        .order_by(EvidenceFile.id)
    ):
        files[rid].append(HistoryFile(id=fid, purpose=purpose))

    return [
        HistoryEntry(
            request_id=r.id,
            title=r.title,
            status=r.status.value,
            priority=r.priority.value,
            created_at=r.created_at,
            completed_at=completed.get(r.id),  # ty: ignore[invalid-argument-type]
            technicians=technicians.get(r.id, []),
            result=results.get(r.id),
            materials=materials.get(r.id, []),
            attachments=files.get(r.id, []),
        )
        for r in requests
    ]
