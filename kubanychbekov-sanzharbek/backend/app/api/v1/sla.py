from fastapi import APIRouter

from app.api.deps import DbDep, OrgDep
from app.schemas.sla import HolidayIn, OverdueOut, WorkingHoursIn, WorkingHoursOut
from app.services import sla as service

router = APIRouter(tags=["sla"])


@router.get("/sla/overdue", response_model=list[OverdueOut])
def overdue(ctx: OrgDep, db: DbDep) -> list[OverdueOut]:
    """Open requests past their SLA, most overdue first."""
    return service.overdue_queue(db, ctx)


@router.get("/settings/working-hours", response_model=WorkingHoursOut)
def get_hours(ctx: OrgDep, db: DbDep) -> WorkingHoursOut:
    return service.get_hours(db, ctx)


@router.put("/settings/working-hours", response_model=WorkingHoursOut)
def set_hours(data: WorkingHoursIn, ctx: OrgDep, db: DbDep) -> WorkingHoursOut:
    return service.set_hours(db, ctx, data)


@router.post("/settings/holidays", response_model=WorkingHoursOut, status_code=201)
def add_holiday(data: HolidayIn, ctx: OrgDep, db: DbDep) -> WorkingHoursOut:
    return service.add_holiday(db, ctx, data)


@router.delete("/settings/holidays/{holiday_id}", response_model=WorkingHoursOut)
def remove_holiday(holiday_id: int, ctx: OrgDep, db: DbDep) -> WorkingHoursOut:
    return service.remove_holiday(db, ctx, holiday_id)
