from fastapi import APIRouter

from app.api.deps import DbDep, OrgDep
from app.schemas.estimate import DecisionIn, EstimateIn, EstimateOut
from app.services import estimates as service

router = APIRouter(tags=["estimates"])


@router.get("/requests/{request_id}/estimates", response_model=list[EstimateOut])
def list_estimates(request_id: int, ctx: OrgDep, db: DbDep) -> list[EstimateOut]:
    return service.list_for_request(db, ctx, request_id)


@router.post("/requests/{request_id}/estimates", response_model=EstimateOut, status_code=201)
def create_estimate(request_id: int, data: EstimateIn, ctx: OrgDep, db: DbDep) -> EstimateOut:
    return service.create(db, ctx, request_id, data)


@router.put("/estimates/{estimate_id}", response_model=EstimateOut)
def update_estimate(estimate_id: int, data: EstimateIn, ctx: OrgDep, db: DbDep) -> EstimateOut:
    return service.update_draft(db, ctx, estimate_id, data)


@router.post("/estimates/{estimate_id}/submit", response_model=EstimateOut)
def submit_estimate(estimate_id: int, ctx: OrgDep, db: DbDep) -> EstimateOut:
    return service.submit(db, ctx, estimate_id)


@router.post("/estimates/{estimate_id}/decision", response_model=EstimateOut)
def decide_estimate(estimate_id: int, data: DecisionIn, ctx: OrgDep, db: DbDep) -> EstimateOut:
    return service.decide(db, ctx, estimate_id, data)


@router.post("/estimates/{estimate_id}/withdraw", response_model=EstimateOut)
def withdraw_estimate(estimate_id: int, ctx: OrgDep, db: DbDep) -> EstimateOut:
    return service.withdraw(db, ctx, estimate_id)
