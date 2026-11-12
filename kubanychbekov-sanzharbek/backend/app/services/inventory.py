"""Inventory: items, replenishment, idempotent atomic write-off of materials (INV-01..06)."""

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import OrgContext
from app.core.errors import AppError
from app.domain.enums import RequestStatus, Role
from app.domain.money import line_total_cents
from app.models import InventoryItem, MaterialUsage, ServiceRequest, StockReplenishment
from app.schemas.inventory import ItemIn, ItemOut, ReplenishIn, UsageIn, UsageOut
from app.services.audit import record_audit
from app.services.notifications import notify_staff
from app.services.requests import assigned_set, get_request


def _item_out(item: InventoryItem) -> ItemOut:
    out = ItemOut.model_validate(item)
    out.low_stock = item.stock <= item.reorder_threshold  # INV-06: at or below the threshold
    return out


def _require_admin(ctx: OrgContext) -> None:
    if ctx.role != Role.ADMIN:
        raise AppError(403, "forbidden", "Only administrators manage inventory")


def list_items(db: Session, ctx: OrgContext, low_only: bool) -> list[ItemOut]:
    if ctx.role == Role.CUSTOMER:
        raise AppError(403, "forbidden", "Inventory is not available to customers")
    query = select(InventoryItem).where(
        InventoryItem.organization_id == ctx.org_id, InventoryItem.is_active.is_(True)
    )
    items = [_item_out(i) for i in db.scalars(query.order_by(InventoryItem.name))]
    return [i for i in items if i.low_stock] if low_only else items


def create_item(db: Session, ctx: OrgContext, data: ItemIn) -> ItemOut:
    _require_admin(ctx)
    item = InventoryItem(
        organization_id=ctx.org_id,
        code=data.code.strip(),
        name=data.name.strip(),
        unit=data.unit.strip(),
        stock=data.stock,
        reorder_threshold=data.reorder_threshold,
        unit_price_cents=data.unit_price_cents,
    )
    db.add(item)
    try:
        db.flush()
    except IntegrityError as err:  # unique (organization, code)
        db.rollback()
        raise AppError(409, "item_code_taken", "An item with this code already exists") from err
    record_audit(
        db,
        action="inventory.item_created",
        object_type="inventory_item",
        object_id=item.id,
        organization_id=ctx.org_id,
        actor_user_id=ctx.user.id,
        after={"code": item.code},
    )
    db.commit()
    return _item_out(item)


def replenish(db: Session, ctx: OrgContext, item_id: int, data: ReplenishIn) -> ItemOut:
    _require_admin(ctx)
    moved = db.execute(
        update(InventoryItem)
        .where(InventoryItem.id == item_id, InventoryItem.organization_id == ctx.org_id)
        .values(stock=InventoryItem.stock + data.quantity)
        .returning(InventoryItem.id)
    )
    if moved.first() is None:
        db.rollback()
        raise AppError(404, "item_not_found", "Item not found")
    db.add(
        StockReplenishment(
            organization_id=ctx.org_id,
            item_id=item_id,
            quantity=data.quantity,
            reason=data.reason.strip(),
            user_id=ctx.user.id,
        )
    )
    record_audit(
        db,
        action="inventory.replenished",
        object_type="inventory_item",
        object_id=item_id,
        organization_id=ctx.org_id,
        actor_user_id=ctx.user.id,
        after={"quantity": str(data.quantity), "reason": data.reason.strip()},
    )
    db.commit()
    refreshed = db.get(InventoryItem, item_id)
    if refreshed is None:  # cannot happen: the UPDATE above matched
        raise AppError(404, "item_not_found", "Item not found")
    return _item_out(refreshed)


def _usage_out(usage: MaterialUsage, item_name: str) -> UsageOut:
    out = UsageOut.model_validate(usage)
    out.item_name = item_name
    out.total_cents = line_total_cents(usage.quantity, usage.unit_price_cents)
    return out


def use_material(
    db: Session, ctx: OrgContext, request_id: int, data: UsageIn
) -> tuple[UsageOut, bool]:
    """Write material off a request in ONE transaction: stock decreases and the usage row exists
    together, or neither happens. Repeating the same command id never decreases stock twice."""
    if ctx.role != Role.TECHNICIAN:
        raise AppError(403, "forbidden", "Only the assigned technician writes off materials")

    # replay first: after the first success the assignment may already look different (INV-05)
    existing = db.scalar(
        select(MaterialUsage).where(
            MaterialUsage.organization_id == ctx.org_id,
            MaterialUsage.client_command_id == data.client_command_id,
        )
    )
    if existing is not None:
        same = (
            existing.request_id == request_id
            and existing.item_id == data.item_id
            and existing.quantity == data.quantity
            and existing.used_by_user_id == ctx.user.id
        )
        if not same:
            raise AppError(409, "idempotency_conflict", "This command id was used elsewhere")
        item = db.get(InventoryItem, existing.item_id)
        return _usage_out(existing, item.name if item else ""), False

    req = db.scalar(
        select(ServiceRequest).where(
            ServiceRequest.id == request_id, ServiceRequest.organization_id == ctx.org_id
        )
    )
    if req is None:
        raise AppError(404, "request_not_found", "Request not found")
    if req.id not in assigned_set(db, ctx, [req.id]):
        raise AppError(409, "assignment_changed", "This request is no longer assigned to you")
    if req.status != RequestStatus.IN_PROGRESS:  # INV-03: only while the work is in progress
        raise AppError(
            409, "work_not_in_progress", "Materials can be used only while work is in progress"
        )

    item = db.scalar(
        select(InventoryItem).where(
            InventoryItem.id == data.item_id,
            InventoryItem.organization_id == ctx.org_id,
            InventoryItem.is_active.is_(True),
        )
    )
    if item is None:
        raise AppError(404, "item_not_found", "Item not found")

    # The guarded UPDATE is the concurrency control: of two parallel calls for the last units,
    # only the one that still finds enough stock matches the WHERE clause (INV-04).
    taken = db.execute(
        update(InventoryItem)
        .where(
            InventoryItem.id == item.id,
            InventoryItem.organization_id == ctx.org_id,
            InventoryItem.stock >= data.quantity,
        )
        .values(stock=InventoryItem.stock - data.quantity)
        .returning(InventoryItem.stock, InventoryItem.reorder_threshold)
    ).first()
    if taken is None:
        db.rollback()
        raise AppError(409, "insufficient_stock", "Not enough of this material in stock")

    usage = MaterialUsage(
        organization_id=ctx.org_id,
        request_id=req.id,
        item_id=item.id,
        quantity=data.quantity,
        unit_price_cents=item.unit_price_cents,  # price snapshot
        used_by_user_id=ctx.user.id,
        client_command_id=data.client_command_id,
    )
    db.add(usage)
    try:
        db.flush()
    except IntegrityError:  # the same command arrived twice at once: undo and return the first
        db.rollback()
        return use_material(db, ctx, request_id, data)

    record_audit(
        db,
        action="inventory.used",
        object_type="material_usage",
        object_id=usage.id,
        organization_id=ctx.org_id,
        actor_user_id=ctx.user.id,
        after={"request_id": req.id, "item_id": item.id, "quantity": str(data.quantity)},
    )
    new_stock, threshold = taken
    if new_stock <= threshold:
        notify_staff(
            db,
            org_id=ctx.org_id,
            type="low_stock",
            title=f"Low stock: {item.name}",
            body=f"{new_stock} {item.unit} left",
        )
    db.commit()
    return _usage_out(usage, item.name), True


def list_usages(db: Session, ctx: OrgContext, request_id: int) -> list[UsageOut]:
    req = get_request(db, ctx, request_id)
    if ctx.role == Role.CUSTOMER:
        return []  # internal cost accounting
    rows = db.execute(
        select(MaterialUsage, InventoryItem.name)
        .join(
            InventoryItem,
            (InventoryItem.id == MaterialUsage.item_id)
            & (InventoryItem.organization_id == MaterialUsage.organization_id),
        )
        .where(MaterialUsage.request_id == req.id, MaterialUsage.organization_id == ctx.org_id)
        .order_by(MaterialUsage.id)
    )
    return [_usage_out(usage, name) for usage, name in rows]
