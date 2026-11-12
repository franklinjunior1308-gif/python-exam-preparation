from fastapi import APIRouter, Response

from app.api.deps import DbDep, OrgDep
from app.schemas.inventory import ItemIn, ItemOut, ReplenishIn, UsageIn, UsageOut
from app.services import inventory as service

router = APIRouter(tags=["inventory"])


@router.get("/inventory", response_model=list[ItemOut])
def list_items(ctx: OrgDep, db: DbDep, low: bool = False) -> list[ItemOut]:
    """Items of the organization; `low=true` lists those at or below their reorder threshold."""
    return service.list_items(db, ctx, low)


@router.post("/inventory", response_model=ItemOut, status_code=201)
def create_item(data: ItemIn, ctx: OrgDep, db: DbDep) -> ItemOut:
    return service.create_item(db, ctx, data)


@router.post("/inventory/{item_id}/replenish", response_model=ItemOut)
def replenish(item_id: int, data: ReplenishIn, ctx: OrgDep, db: DbDep) -> ItemOut:
    return service.replenish(db, ctx, item_id, data)


@router.get("/requests/{request_id}/materials", response_model=list[UsageOut])
def list_usages(request_id: int, ctx: OrgDep, db: DbDep) -> list[UsageOut]:
    return service.list_usages(db, ctx, request_id)


@router.post("/requests/{request_id}/materials", response_model=UsageOut, status_code=201)
def use_material(
    request_id: int, data: UsageIn, ctx: OrgDep, db: DbDep, response: Response
) -> UsageOut:
    usage, created = service.use_material(db, ctx, request_id, data)
    if not created:
        response.status_code = 200  # same command repeated: stock was NOT reduced again
    return usage
