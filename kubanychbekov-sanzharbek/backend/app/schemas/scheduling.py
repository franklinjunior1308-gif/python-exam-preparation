from datetime import datetime, time
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import AssignmentStatus


class AvailabilityOut(BaseModel):
    weekday: int
    start_time: time
    end_time: time


class TechnicianOut(BaseModel):
    id: int
    user_id: int
    full_name: str
    email: str
    is_active: bool
    skills: list[str]
    availability: list[AvailabilityOut]
    load_percent: int  # scheduled / available working minutes in the chosen week


class Reason(BaseModel):
    code: str
    detail: str | None = None


class CandidateOut(BaseModel):
    technician_id: int
    full_name: str
    skills: list[str]
    available: bool
    load_percent: int
    reasons: list[Reason]
    conflicting_assignment_ids: list[int]


class SuggestionOut(BaseModel):
    """One ready-to-apply booking proposed by Smart Assign."""

    technician_id: int
    full_name: str
    skills: list[str]
    start_at: datetime
    end_at: datetime
    load_percent: int
    within_desired_window: bool | None  # None when the customer gave no preferred window
    is_best: bool


class VisitWindow(BaseModel):
    start_at: datetime
    end_at: datetime

    @model_validator(mode="after")
    def _aware(self) -> Self:
        if self.start_at.tzinfo is None or self.end_at.tzinfo is None:
            raise ValueError("start_at and end_at must include a timezone offset")
        return self


class AssignmentCreate(VisitWindow):
    technician_id: int


class AssignmentReschedule(BaseModel):
    start_at: datetime
    end_at: datetime
    technician_id: int | None = None  # keep the current technician when omitted
    reason: str | None = Field(default=None, max_length=1000)


class AssignmentReason(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class AssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_id: int
    request_title: str
    technician_id: int
    technician_name: str
    start_at: datetime
    end_at: datetime
    timezone: str
    status: AssignmentStatus


class AbsenceOut(BaseModel):
    technician_id: int
    start_at: datetime
    end_at: datetime
    reason: str | None


class ScheduleOut(BaseModel):
    timezone: str
    technicians: list[TechnicianOut]
    assignments: list[AssignmentOut]
    absences: list[AbsenceOut]
