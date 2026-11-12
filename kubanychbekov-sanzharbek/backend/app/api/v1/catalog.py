from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import DbDep, OrgDep
from app.domain.enums import Role
from app.models import Asset, Property, ServiceCategory
from app.schemas.catalog import AssetOut, CategoryOut, PropertyOut

router = APIRouter(tags=["catalog"])


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(
    ctx: OrgDep, db: DbDep, include_inactive: bool = False
) -> list[ServiceCategory]:
    """Inactive categories stay in history but are hidden from new requests (ORG-03)."""
    query = select(ServiceCategory).where(ServiceCategory.organization_id == ctx.org_id)
    if not include_inactive or ctx.role not in {Role.ADMIN, Role.DISPATCHER}:
        query = query.where(ServiceCategory.is_active.is_(True))
    return list(db.scalars(query.order_by(ServiceCategory.name)))


@router.get("/properties", response_model=list[PropertyOut])
def list_properties(ctx: OrgDep, db: DbDep) -> list[Property]:
    query = (
        select(Property)
        .where(Property.organization_id == ctx.org_id, Property.is_active.is_(True))
        .order_by(Property.name)
    )
    return list(db.scalars(query))


@router.get("/assets", response_model=list[AssetOut])
def list_assets(
    ctx: OrgDep, db: DbDep, property_id: Annotated[int | None, Query()] = None
) -> list[Asset]:
    query = select(Asset).where(Asset.organization_id == ctx.org_id)
    if property_id is not None:
        query = query.where(Asset.property_id == property_id)
    return list(db.scalars(query.order_by(Asset.code)))
