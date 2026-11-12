"""Estimate versions, customer decision and the start-of-work gate (EST-01..06)."""

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import OrgContext
from app.core.errors import AppError
from app.domain.enums import EstimateStatus as ES
from app.domain.enums import Role
from app.domain.money import CURRENCY, estimate_total_cents, line_total_cents
from app.models import Estimate, EstimateLine
from app.schemas.estimate import DecisionIn, EstimateIn, EstimateOut, LineOut
from app.services.audit import record_audit
from app.services.notifications import notify, notify_staff
from app.services.requests import get_request

STAFF = {Role.DISPATCHER, Role.ADMIN}
# once the customer has to look at an estimate, it can no longer be edited
SUBMITTED = (ES.AWAITING_APPROVAL, ES.APPROVED, ES.REJECTED)


def _require_staff(ctx: OrgContext) -> None:
    if ctx.role not in STAFF:
        raise AppError(403, "forbidden", "Only dispatchers and administrators manage estimates")


def _out(db: Session, est: Estimate) -> EstimateOut:
    lines = list(
        db.scalars(
            select(EstimateLine).where(EstimateLine.estimate_id == est.id).order_by(EstimateLine.id)
        )
    )
    labor, materials, total = estimate_total_cents(
        est.labor_minutes,
        est.labor_rate_cents,
        [(ln.quantity, ln.unit_price_cents) for ln in lines],
    )
    return EstimateOut(
        id=est.id,
        request_id=est.request_id,
        version=est.version,
        status=est.status,
        currency=CURRENCY,
        labor_minutes=est.labor_minutes,
        labor_rate_cents=est.labor_rate_cents,
        labor_cents=labor,
        materials_cents=materials,
        total_cents=total,
        lines=[
            LineOut(
                id=ln.id,
                description=ln.description,
                quantity=ln.quantity,
                unit_price_cents=ln.unit_price_cents,
                line_total_cents=line_total_cents(ln.quantity, ln.unit_price_cents),
            )
            for ln in lines
        ],
        created_by_user_id=est.created_by_user_id,
        submitted_at=est.submitted_at,
        decided_by_user_id=est.decided_by_user_id,
        decided_at=est.decided_at,
        decision_reason=est.decision_reason,
        created_at=est.created_at,
    )


def _load(db: Session, ctx: OrgContext, estimate_id: int) -> Estimate:
    """An estimate is reachable only through a request the caller may see (tenant + ownership)."""
    est = db.scalar(
        select(Estimate).where(Estimate.id == estimate_id, Estimate.organization_id == ctx.org_id)
    )
    if est is None:
        raise AppError(404, "estimate_not_found", "Estimate not found")
    get_request(db, ctx, est.request_id)  # 404 for other customers / other organizations
    if ctx.role == Role.CUSTOMER and est.status == ES.DRAFT:
        raise AppError(404, "estimate_not_found", "Estimate not found")
    return est


def _replace_lines(db: Session, ctx: OrgContext, est: Estimate, data: EstimateIn) -> None:
    for old in db.scalars(select(EstimateLine).where(EstimateLine.estimate_id == est.id)):
        db.delete(old)
    db.flush()
    for ln in data.lines:
        db.add(
            EstimateLine(
                organization_id=ctx.org_id,
                estimate_id=est.id,
                description=ln.description.strip(),
                quantity=ln.quantity,
                unit_price_cents=ln.unit_price_cents,
            )
        )


def create(db: Session, ctx: OrgContext, request_id: int, data: EstimateIn) -> EstimateOut:
    _require_staff(ctx)
    req = get_request(db, ctx, request_id)
    latest = db.scalar(
        select(Estimate).where(Estimate.request_id == req.id).order_by(Estimate.version.desc())
    )
    if latest is not None and latest.status in (ES.DRAFT, ES.AWAITING_APPROVAL):
        raise AppError(409, "estimate_open", "Finish or withdraw the current estimate first")

    est = Estimate(
        organization_id=ctx.org_id,
        request_id=req.id,
        version=(latest.version + 1) if latest else 1,
        labor_minutes=data.labor_minutes,
        labor_rate_cents=data.labor_rate_cents,
        created_by_user_id=ctx.user.id,
    )
    db.add(est)
    try:
        db.flush()
    except IntegrityError as err:  # two dispatchers created the same version at once
        db.rollback()
        raise AppError(409, "estimate_open", "Another estimate was just created") from err
    _replace_lines(db, ctx, est, data)
    record_audit(
        db,
        action="estimate.created",
        object_type="estimate",
        object_id=est.id,
        organization_id=ctx.org_id,
        actor_user_id=ctx.user.id,
        after={"request_id": req.id, "version": est.version},
    )
    db.commit()
    return _out(db, est)


def update_draft(db: Session, ctx: OrgContext, estimate_id: int, data: EstimateIn) -> EstimateOut:
    _require_staff(ctx)
    est = _load(db, ctx, estimate_id)
    if est.status != ES.DRAFT:
        raise AppError(
            409, "estimate_immutable", "A submitted estimate cannot be edited; make a new version"
        )
    est.labor_minutes = data.labor_minutes
    est.labor_rate_cents = data.labor_rate_cents
    _replace_lines(db, ctx, est, data)
    record_audit(
        db,
        action="estimate.updated",
        object_type="estimate",
        object_id=est.id,
        organization_id=ctx.org_id,
        actor_user_id=ctx.user.id,
        after={"version": est.version},
    )
    db.commit()
    return _out(db, est)


def submit(db: Session, ctx: OrgContext, estimate_id: int) -> EstimateOut:
    _require_staff(ctx)
    est = _load(db, ctx, estimate_id)
    req = get_request(db, ctx, est.request_id)
    moved = db.execute(
        update(Estimate)
        .where(Estimate.id == est.id, Estimate.status == ES.DRAFT)
        .values(status=ES.AWAITING_APPROVAL, submitted_at=datetime.now(UTC))
        .returning(Estimate.id)
    )
    if moved.first() is None:
        db.rollback()
        raise AppError(409, "estimate_immutable", "Only a draft can be submitted")
    # the previous submitted version is replaced by this one (EST-02, EST-06)
    db.execute(
        update(Estimate)
        .where(
            Estimate.request_id == est.request_id,
            Estimate.id != est.id,
            Estimate.status.in_(SUBMITTED),
        )
        .values(status=ES.SUPERSEDED)
    )
    record_audit(
        db,
        action="estimate.submitted",
        object_type="estimate",
        object_id=est.id,
        organization_id=ctx.org_id,
        actor_user_id=ctx.user.id,
        after={"version": est.version, "request_id": est.request_id},
    )
    notify(
        db,
        org_id=ctx.org_id,
        user_id=req.created_by_user_id,
        type="estimate_submitted",
        title=f"Estimate for request #{req.id} awaits your decision",
        body=req.title,
        request_id=req.id,
    )
    db.commit()
    db.refresh(est)
    return _out(db, est)


def decide(db: Session, ctx: OrgContext, estimate_id: int, data: DecisionIn) -> EstimateOut:
    """Only the request's own customer decides, once. Two parallel decisions cannot both win."""
    if ctx.role != Role.CUSTOMER:
        raise AppError(403, "forbidden", "Only the customer decides on an estimate")
    est = _load(db, ctx, estimate_id)
    req = get_request(db, ctx, est.request_id)
    if req.created_by_user_id != ctx.user.id:  # defense in depth; get_request already filters
        raise AppError(404, "estimate_not_found", "Estimate not found")
    reason = (data.reason or "").strip()
    if not data.approve and not reason:
        raise AppError(422, "reason_required", "A reason is required to reject an estimate")

    new_status = ES.APPROVED if data.approve else ES.REJECTED
    moved = db.execute(
        update(Estimate)
        .where(Estimate.id == est.id, Estimate.status == ES.AWAITING_APPROVAL)
        .values(
            status=new_status,
            decided_by_user_id=ctx.user.id,
            decided_at=datetime.now(UTC),
            decision_reason=reason or None,
        )
        .returning(Estimate.id)
    )
    if moved.first() is None:
        db.rollback()
        raise AppError(
            409, "estimate_not_pending", "This estimate is no longer awaiting a decision"
        )
    record_audit(
        db,
        action="estimate.approved" if data.approve else "estimate.rejected",
        object_type="estimate",
        object_id=est.id,
        organization_id=ctx.org_id,
        actor_user_id=ctx.user.id,
        before={"status": ES.AWAITING_APPROVAL.value},
        after={"status": new_status.value, "version": est.version, "reason": reason or None},
    )
    notify_staff(
        db,
        org_id=ctx.org_id,
        type="estimate_decision",
        title=f"Estimate v{est.version} for request #{req.id} was "
        f"{'approved' if data.approve else 'rejected'}",
        body=reason or req.title,
        request_id=req.id,
    )
    db.commit()
    db.refresh(est)
    return _out(db, est)


def withdraw(db: Session, ctx: OrgContext, estimate_id: int) -> EstimateOut:
    """Dispatcher replaces/withdraws an estimate (EST-04): a draft, pending or rejected one."""
    _require_staff(ctx)
    est = _load(db, ctx, estimate_id)
    moved = db.execute(
        update(Estimate)
        .where(
            Estimate.id == est.id,
            Estimate.status.in_([ES.DRAFT, ES.AWAITING_APPROVAL, ES.REJECTED]),
        )
        .values(status=ES.SUPERSEDED)
        .returning(Estimate.id)
    )
    if moved.first() is None:
        db.rollback()
        raise AppError(409, "estimate_immutable", "An approved estimate cannot be withdrawn")
    record_audit(
        db,
        action="estimate.withdrawn",
        object_type="estimate",
        object_id=est.id,
        organization_id=ctx.org_id,
        actor_user_id=ctx.user.id,
        after={"version": est.version},
    )
    db.commit()
    db.refresh(est)
    return _out(db, est)


def list_for_request(db: Session, ctx: OrgContext, request_id: int) -> list[EstimateOut]:
    req = get_request(db, ctx, request_id)
    if ctx.role == Role.TECHNICIAN:
        # technicians only need to know the approved total, not internal drafts
        statuses = [ES.APPROVED]
    elif ctx.role == Role.CUSTOMER:
        statuses = [ES.AWAITING_APPROVAL, ES.APPROVED, ES.REJECTED, ES.SUPERSEDED]
    else:
        statuses = list(ES)
    rows = db.scalars(
        select(Estimate)
        .where(Estimate.request_id == req.id, Estimate.status.in_(statuses))
        .order_by(Estimate.version.desc())
    )
    return [_out(db, est) for est in rows]
