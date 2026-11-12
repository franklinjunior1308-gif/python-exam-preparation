from sqlalchemy import String, case, cast, func, or_, select, update
from sqlalchemy.orm import Session

from app.api.deps import OrgContext
from app.core.errors import AppError
from app.domain.enums import (
    ACTIVE_ASSIGNMENT_STATUSES,
    AssetStatus,
    AssignmentStatus,
    EstimateStatus,
    Priority,
    RequestStatus,
    Role,
)
from app.domain.lifecycle import TransitionError, allowed_targets, check_transition
from app.models import (
    Asset,
    Assignment,
    Estimate,
    Property,
    RequestStatusHistory,
    ServiceCategory,
    ServiceRequest,
    TechnicianProfile,
)
from app.schemas.request import RequestCreate, RequestOut, TriageIn
from app.services.audit import record_audit

MAX_PAGE_SIZE = 100

_PRIORITY_RANK = case(
    (ServiceRequest.priority == Priority.HIGH, 3),
    (ServiceRequest.priority == Priority.NORMAL, 2),
    else_=1,
)
_SORT_COLUMNS = {
    "created_at": ServiceRequest.created_at,
    "id": ServiceRequest.id,
    "priority": _PRIORITY_RANK,
}


_ASSIGNMENT_FOLLOWS = {
    RequestStatus.ACCEPTED: AssignmentStatus.ACCEPTED,
    RequestStatus.IN_PROGRESS: AssignmentStatus.IN_PROGRESS,
    RequestStatus.BLOCKED: AssignmentStatus.BLOCKED,
    RequestStatus.COMPLETED: AssignmentStatus.COMPLETED,
}


def assigned_set(db: Session, ctx: OrgContext, request_ids: list[int]) -> set[int]:
    """Requests (among the given ids) where the current user is the active technician."""
    if ctx.role != Role.TECHNICIAN or not request_ids:
        return set()
    rows = db.scalars(
        select(Assignment.request_id)
        .join(TechnicianProfile, TechnicianProfile.id == Assignment.technician_id)
        .where(
            Assignment.organization_id == ctx.org_id,
            Assignment.request_id.in_(request_ids),
            Assignment.status.in_(ACTIVE_ASSIGNMENT_STATUSES),
            TechnicianProfile.user_id == ctx.user.id,
        )
    )
    return set(rows)


def to_out(req: ServiceRequest, ctx: OrgContext, assigned: set[int] | None = None) -> RequestOut:
    """Serialize and attach the actions the current user may take (REQ-05)."""
    out = RequestOut.model_validate(req)
    out.allowed_actions = allowed_targets(
        req.status,
        ctx.role,
        is_owner=req.created_by_user_id == ctx.user.id,
        is_assignee=req.id in (assigned or set()),
    )
    return out


def visible_conditions(ctx: OrgContext):
    """Row-level visibility (ROLE-03). Always scoped to the organization."""
    conditions = [ServiceRequest.organization_id == ctx.org_id]
    if ctx.role == Role.CUSTOMER:
        conditions.append(ServiceRequest.created_by_user_id == ctx.user.id)
    elif ctx.role == Role.TECHNICIAN:
        # technicians see only requests they are (or were) booked on, never released ones
        mine = (
            select(Assignment.request_id)
            .join(TechnicianProfile, TechnicianProfile.id == Assignment.technician_id)
            .where(
                Assignment.organization_id == ctx.org_id,
                TechnicianProfile.user_id == ctx.user.id,
                Assignment.status.notin_([AssignmentStatus.CANCELED, AssignmentStatus.DECLINED]),
            )
        )
        conditions.append(ServiceRequest.id.in_(mine))
    return conditions


def create_request(db: Session, ctx: OrgContext, data: RequestCreate) -> ServiceRequest:
    if ctx.role != Role.CUSTOMER:
        raise AppError(403, "forbidden", "Only customers create requests")

    category = db.scalar(
        select(ServiceCategory).where(
            ServiceCategory.id == data.category_id,
            ServiceCategory.organization_id == ctx.org_id,
        )
    )
    if category is None:
        raise AppError(404, "category_not_found", "Category not found")
    if not category.is_active:
        raise AppError(422, "category_inactive", "Category is not available for new requests")

    prop = db.scalar(
        select(Property).where(
            Property.id == data.property_id, Property.organization_id == ctx.org_id
        )
    )
    if prop is None or not prop.is_active:
        raise AppError(404, "property_not_found", "Property not found")

    if data.asset_id is not None:
        asset = db.scalar(
            select(Asset).where(Asset.id == data.asset_id, Asset.organization_id == ctx.org_id)
        )
        if asset is None or asset.property_id != prop.id:
            raise AppError(404, "asset_not_found", "Asset not found on this property")
        if asset.status == AssetStatus.RETIRED:
            raise AppError(422, "asset_retired", "Asset is retired")

    req = ServiceRequest(
        organization_id=ctx.org_id,
        title=data.title.strip(),
        description=data.description.strip(),
        category_id=data.category_id,
        property_id=data.property_id,
        asset_id=data.asset_id,
        priority=data.priority,
        status=RequestStatus.SUBMITTED,
        desired_start=data.desired_start,
        desired_end=data.desired_end,
        created_by_user_id=ctx.user.id,
    )
    db.add(req)
    db.flush()  # assigns the id inside the transaction
    db.add(
        RequestStatusHistory(
            organization_id=ctx.org_id,
            request_id=req.id,
            from_status=None,
            to_status=RequestStatus.SUBMITTED,
            actor_user_id=ctx.user.id,
        )
    )
    record_audit(
        db,
        action="request.created",
        object_type="service_request",
        object_id=req.id,
        organization_id=ctx.org_id,
        actor_user_id=ctx.user.id,
        after={"status": RequestStatus.SUBMITTED.value, "priority": data.priority.value},
    )
    db.commit()
    return req


def get_request(db: Session, ctx: OrgContext, request_id: int) -> ServiceRequest:
    """404 (not 403) for other organizations / other customers: no existence leak (SEC-01)."""
    req = db.scalar(
        select(ServiceRequest).where(ServiceRequest.id == request_id, *visible_conditions(ctx))
    )
    if req is None:
        raise AppError(404, "request_not_found", "Request not found")
    return req


def list_requests(
    db: Session,
    ctx: OrgContext,
    *,
    page: int,
    page_size: int,
    status: RequestStatus | None,
    priority: Priority | None,
    category_id: int | None,
    property_id: int | None,
    q: str | None,
    sort_by: str,
    descending: bool,
    unpaged: bool = False,
) -> tuple[list[ServiceRequest], int]:
    conditions = visible_conditions(ctx)
    if status:
        conditions.append(ServiceRequest.status == status)
    if priority:
        conditions.append(ServiceRequest.priority == priority)
    if category_id:
        conditions.append(ServiceRequest.category_id == category_id)
    if property_id:
        conditions.append(ServiceRequest.property_id == property_id)

    base = select(ServiceRequest).join(
        Property,
        (Property.id == ServiceRequest.property_id)
        & (Property.organization_id == ServiceRequest.organization_id),
    )
    if q:
        term = f"%{q.strip()}%"
        conditions.append(
            or_(
                ServiceRequest.title.ilike(term),
                Property.address.ilike(term),
                cast(ServiceRequest.id, String) == q.strip(),
            )
        )
    base = base.where(*conditions)

    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    column = _SORT_COLUMNS.get(sort_by, ServiceRequest.created_at)
    ordering = column.desc() if descending else column.asc()
    ordered = base.order_by(ordering, ServiceRequest.id.desc())
    if not unpaged:
        ordered = ordered.limit(min(page_size, MAX_PAGE_SIZE)).offset((page - 1) * page_size)
    rows = db.scalars(ordered).all()
    return list(rows), total


def transition_request(
    db: Session,
    ctx: OrgContext,
    request_id: int,
    target: RequestStatus,
    reason: str | None,
) -> ServiceRequest:
    req = get_request(db, ctx, request_id)
    source = req.status
    try:
        check_transition(
            source,
            target,
            ctx.role,
            is_owner=req.created_by_user_id == ctx.user.id,
            is_assignee=req.id in assigned_set(db, ctx, [req.id]),
            reason=reason,
        )
    except TransitionError as err:
        status = {
            "invalid_transition": 409,
            "requires_dedicated_endpoint": 409,
            "reason_required": 422,
        }.get(err.code, 403)
        raise AppError(status, err.code, str(err)) from err

    # EST-04: once an estimate was sent to the customer, work cannot start until it is approved.
    # (No submitted estimate = work may start. A rejected one must be replaced or withdrawn first.)
    if source == RequestStatus.ACCEPTED and target == RequestStatus.IN_PROGRESS:
        newest = db.scalar(
            select(Estimate.status)
            .where(
                Estimate.organization_id == ctx.org_id,
                Estimate.request_id == req.id,
                Estimate.status.in_(
                    [
                        EstimateStatus.AWAITING_APPROVAL,
                        EstimateStatus.APPROVED,
                        EstimateStatus.REJECTED,
                    ]
                ),
            )
            .order_by(Estimate.version.desc())
            .limit(1)
        )
        if newest is not None and newest != EstimateStatus.APPROVED:
            raise AppError(
                409, "estimate_not_approved", "The estimate must be approved before work starts"
            )

    # Compare-and-set: the UPDATE only matches if nobody changed the status meanwhile, so two
    # concurrent transitions cannot both succeed (LIFE-08).
    result = db.execute(
        update(ServiceRequest)
        .where(
            ServiceRequest.id == req.id,
            ServiceRequest.organization_id == ctx.org_id,
            ServiceRequest.status == source,
        )
        .values(status=target)
        .returning(ServiceRequest.id)
    )
    if result.first() is None:
        db.rollback()
        raise AppError(409, "state_conflict", "The request was changed by someone else; reload")

    # keep the booking in step with the work (assignment statuses follow the request)
    mirrored = _ASSIGNMENT_FOLLOWS.get(target)
    if mirrored is not None:
        db.execute(
            update(Assignment)
            .where(
                Assignment.request_id == req.id,
                Assignment.organization_id == ctx.org_id,
                Assignment.status.in_(ACTIVE_ASSIGNMENT_STATUSES),
            )
            .values(status=mirrored)
        )

    db.add(
        RequestStatusHistory(
            organization_id=ctx.org_id,
            request_id=req.id,
            from_status=source,
            to_status=target,
            actor_user_id=ctx.user.id,
            reason=reason.strip() if reason else None,
        )
    )
    record_audit(
        db,
        action="request.status_changed",
        object_type="service_request",
        object_id=req.id,
        organization_id=ctx.org_id,
        actor_user_id=ctx.user.id,
        before={"status": source.value},
        after={"status": target.value, "reason": reason},
    )
    db.commit()
    db.refresh(req)
    return req


def update_triage(db: Session, ctx: OrgContext, request_id: int, data: TriageIn) -> ServiceRequest:
    """Change priority/category with a reason; the SLA follows the new priority at once (SLA-05)."""
    if ctx.role not in {Role.DISPATCHER, Role.ADMIN}:
        raise AppError(403, "forbidden", "Only dispatchers and administrators change these fields")
    req = get_request(db, ctx, request_id)
    if req.status in {RequestStatus.CLOSED, RequestStatus.CANCELED}:
        raise AppError(409, "request_closed", "A closed request cannot be changed")
    before = {"priority": req.priority.value, "category_id": req.category_id}
    if data.category_id is not None:
        category = db.scalar(
            select(ServiceCategory).where(
                ServiceCategory.id == data.category_id,
                ServiceCategory.organization_id == ctx.org_id,
                ServiceCategory.is_active.is_(True),
            )
        )
        if category is None:
            raise AppError(404, "category_not_found", "Category not found")
        req.category_id = data.category_id
    if data.priority is not None:
        req.priority = data.priority
    record_audit(
        db,
        action="request.triage_changed",
        object_type="service_request",
        object_id=req.id,
        organization_id=ctx.org_id,
        actor_user_id=ctx.user.id,
        before=before,
        after={
            "priority": req.priority.value,
            "category_id": req.category_id,
            "reason": data.reason.strip(),
        },
    )
    db.commit()
    db.refresh(req)
    return req
