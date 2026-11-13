"""Service categories admin (ORG-03). Disabling keeps history, hides it from new requests."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import OrgContext
from app.core.errors import AppError
from app.domain.enums import Role
from app.models import ServiceCategory
from app.schemas.catalog import CategoryIn, CategoryUpdate
from app.services.audit import record_audit


def _require_admin(ctx: OrgContext) -> None:
    if ctx.role != Role.ADMIN:
        raise AppError(403, "forbidden", "Only administrators manage categories")


def _snapshot(c: ServiceCategory) -> dict[str, object]:
    return {
        "name": c.name,
        "default_duration_min": c.default_duration_min,
        "required_skills": list(c.required_skills),
        "is_active": c.is_active,
    }


def create_category(db: Session, ctx: OrgContext, data: CategoryIn) -> ServiceCategory:
    _require_admin(ctx)
    category = ServiceCategory(
        organization_id=ctx.org_id,
        name=data.name,
        description=data.description,
        default_duration_min=data.default_duration_min,
        required_skills=data.required_skills,
    )
    db.add(category)
    try:
        db.flush()
    except IntegrityError as err:  # unique (organization, name)
        db.rollback()
        raise AppError(409, "category_name_taken", "A category with this name exists") from err
    record_audit(
        db,
        action="category.created",
        object_type="service_category",
        object_id=category.id,
        organization_id=ctx.org_id,
        actor_user_id=ctx.user.id,
        after=_snapshot(category),
    )
    db.commit()
    return category


def update_category(
    db: Session, ctx: OrgContext, category_id: int, data: CategoryUpdate
) -> ServiceCategory:
    _require_admin(ctx)
    category = db.scalar(
        select(ServiceCategory)
        .where(ServiceCategory.id == category_id, ServiceCategory.organization_id == ctx.org_id)
        .with_for_update()
    )
    if category is None:
        raise AppError(404, "category_not_found", "Category not found")
    before = _snapshot(category)
    category.name = data.name
    category.description = data.description
    category.default_duration_min = data.default_duration_min
    category.required_skills = data.required_skills
    if data.is_active is not None:
        category.is_active = data.is_active
    try:
        db.flush()
    except IntegrityError as err:
        db.rollback()
        raise AppError(409, "category_name_taken", "A category with this name exists") from err
    record_audit(
        db,
        action="category.updated",
        object_type="service_category",
        object_id=category.id,
        organization_id=ctx.org_id,
        actor_user_id=ctx.user.id,
        before=before,
        after=_snapshot(category),
    )
    db.commit()
    return category
