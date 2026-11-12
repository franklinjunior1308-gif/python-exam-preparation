from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.api.deps import DbDep, OrgDep
from app.schemas.scheduling import (
    AssignmentCreate,
    AssignmentOut,
    AssignmentReason,
    AssignmentReschedule,
    CandidateOut,
    ScheduleOut,
    SuggestionOut,
    TechnicianOut,
)
from app.services import scheduling as service

router = APIRouter(tags=["scheduling"])


@router.get("/technicians", response_model=list[TechnicianOut])
def technicians(ctx: OrgDep, db: DbDep) -> list[TechnicianOut]:
    return service.technician_list(db, ctx)


@router.get("/schedule", response_model=ScheduleOut)
def schedule(
    ctx: OrgDep,
    db: DbDep,
    start: Annotated[datetime, Query(alias="from")],
    end: Annotated[datetime, Query(alias="to")],
) -> ScheduleOut:
    return service.schedule(db, ctx, start, end)


@router.get("/requests/{request_id}/candidates", response_model=list[CandidateOut])
def candidates(
    request_id: int,
    ctx: OrgDep,
    db: DbDep,
    start_at: datetime,
    end_at: datetime,
) -> list[CandidateOut]:
    return service.candidates(db, ctx, request_id, start_at, end_at)


@router.get("/requests/{request_id}/suggestions", response_model=list[SuggestionOut])
def suggestions(request_id: int, ctx: OrgDep, db: DbDep) -> list[SuggestionOut]:
    """Smart Assign: ready-to-apply technician + time proposals for a triaged request."""
    return service.suggestions(db, ctx, request_id)


@router.get("/requests/{request_id}/assignments", response_model=list[AssignmentOut])
def request_assignments(request_id: int, ctx: OrgDep, db: DbDep) -> list[AssignmentOut]:
    return service.assignments_for_request(db, ctx, request_id)


@router.post("/requests/{request_id}/assignments", response_model=AssignmentOut, status_code=201)
def assign(
    request_id: int, data: AssignmentCreate, ctx: OrgDep, db: DbDep, response: Response
) -> AssignmentOut:
    out, created = service.assign(db, ctx, request_id, data)
    if not created:
        response.status_code = 200  # identical command replayed: same result, nothing new made
    return out


@router.patch("/assignments/{assignment_id}", response_model=AssignmentOut)
def reschedule(
    assignment_id: int, data: AssignmentReschedule, ctx: OrgDep, db: DbDep
) -> AssignmentOut:
    return service.reschedule(db, ctx, assignment_id, data)


@router.post("/assignments/{assignment_id}/unassign", response_model=AssignmentOut)
def unassign(assignment_id: int, data: AssignmentReason, ctx: OrgDep, db: DbDep) -> AssignmentOut:
    return service.unassign(db, ctx, assignment_id, data.reason)


@router.post("/assignments/{assignment_id}/decline", response_model=AssignmentOut)
def decline(assignment_id: int, data: AssignmentReason, ctx: OrgDep, db: DbDep) -> AssignmentOut:
    return service.decline(db, ctx, assignment_id, data.reason)
