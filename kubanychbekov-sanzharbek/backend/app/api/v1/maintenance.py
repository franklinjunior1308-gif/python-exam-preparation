from fastapi import APIRouter

from app.api.deps import DbDep, OrgDep
from app.schemas.maintenance import GenerateIn, GenerateOut, PlanIn, PlanOut, PlanRequestOut
from app.services import maintenance as service

router = APIRouter(tags=["maintenance"])


@router.get("/maintenance-plans", response_model=list[PlanOut])
def list_plans(ctx: OrgDep, db: DbDep) -> list[PlanOut]:
    return service.list_plans(db, ctx)


@router.post("/maintenance-plans", response_model=PlanOut, status_code=201)
def create_plan(data: PlanIn, ctx: OrgDep, db: DbDep) -> PlanOut:
    return service.create_plan(db, ctx, data)


@router.post("/maintenance-plans/{plan_id}/disable", response_model=PlanOut)
def disable_plan(plan_id: int, ctx: OrgDep, db: DbDep) -> PlanOut:
    return service.disable_plan(db, ctx, plan_id)


@router.get("/maintenance-plans/{plan_id}/requests", response_model=list[PlanRequestOut])
def plan_requests(plan_id: int, ctx: OrgDep, db: DbDep) -> list[PlanRequestOut]:
    return service.plan_requests(db, ctx, plan_id)


@router.post("/maintenance/generate", response_model=GenerateOut)
def generate(data: GenerateIn, ctx: OrgDep, db: DbDep) -> GenerateOut:
    """Create the requests of every event up to `as_of` (default: today). Safe to repeat."""
    return service.generate_for_org(db, ctx, data.as_of)


@router.get("/assets/{asset_id}/summary")
def asset_summary(asset_id: int, ctx: OrgDep, db: DbDep) -> dict[str, object]:
    return service.asset_summary(db, ctx, asset_id)
