from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import DbDep, OrgDep
from app.domain.enums import Role
from app.models import Asset, Property, ServiceCategory
from app.schemas.catalog import (
    AssetIn,
    AssetOut,
    AssetUpdate,
    CategoryIn,
    CategoryOut,
    CategoryUpdate,
    HistoryEntry,
    PropertyIn,
    PropertyOut,
)
from app.services import assets as asset_service
from app.services import categories

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


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(data: CategoryIn, ctx: OrgDep, db: DbDep) -> ServiceCategory:
    return categories.create_category(db, ctx, data)


@router.put("/categories/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: int, data: CategoryUpdate, ctx: OrgDep, db: DbDep
) -> ServiceCategory:
    return categories.update_category(db, ctx, category_id, data)


@router.get("/properties", response_model=list[PropertyOut])
def list_properties(ctx: OrgDep, db: DbDep, include_inactive: bool = False) -> list[Property]:
    query = select(Property).where(Property.organization_id == ctx.org_id)
    if not include_inactive or ctx.role not in {Role.ADMIN, Role.DISPATCHER}:
        query = query.where(Property.is_active.is_(True))
    return list(db.scalars(query.order_by(Property.name)))


@router.post("/properties", response_model=PropertyOut, status_code=201)
def create_property(data: PropertyIn, ctx: OrgDep, db: DbDep) -> Property:
    return asset_service.create_property(db, ctx, data)


@router.put("/properties/{property_id}", response_model=PropertyOut)
def update_property(property_id: int, data: PropertyIn, ctx: OrgDep, db: DbDep) -> Property:
    return asset_service.update_property(db, ctx, property_id, data)


@router.get("/assets", response_model=list[AssetOut])
def list_assets(
    ctx: OrgDep, db: DbDep, property_id: Annotated[int | None, Query()] = None
) -> list[Asset]:
    query = select(Asset).where(Asset.organization_id == ctx.org_id)
    if property_id is not None:
        query = query.where(Asset.property_id == property_id)
    return list(db.scalars(query.order_by(Asset.code)))


@router.post("/assets", response_model=AssetOut, status_code=201)
def create_asset(data: AssetIn, ctx: OrgDep, db: DbDep) -> Asset:
    return asset_service.create_asset(db, ctx, data)


@router.put("/assets/{asset_id}", response_model=AssetOut)
def update_asset(asset_id: int, data: AssetUpdate, ctx: OrgDep, db: DbDep) -> Asset:
    return asset_service.update_asset(db, ctx, asset_id, data)


@router.get("/assets/{asset_id}/history", response_model=list[HistoryEntry])
def asset_history(asset_id: int, ctx: OrgDep, db: DbDep) -> list[HistoryEntry]:
    """Requests, technicians, dates, results, materials and photos of one piece of equipment."""
    return asset_service.asset_history(db, ctx, asset_id)
