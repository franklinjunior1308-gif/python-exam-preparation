from datetime import date, datetime, time

from pydantic import BaseModel, Field, model_validator


class SlaOut(BaseModel):
    """SLA of one request in working time (SLA-02..05)."""

    budget_minutes: int
    used_minutes: int
    remaining_minutes: int  # negative once overdue
    state: str  # ON_TRACK | AT_RISK | OVERDUE
    due_at: datetime | None  # None while the clock is paused or after completion
    paused: bool  # an estimate is waiting for the customer
    finished: bool  # completed: the result is fixed at the moment of completion


class OverdueOut(BaseModel):
    request_id: int
    title: str
    priority: str
    status: str
    overdue_minutes: int
    escalated: bool


class IntervalIn(BaseModel):
    weekday: int = Field(ge=0, le=6)
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def _ordered(self) -> "IntervalIn":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be later than start_time")
        return self


class WorkingHoursIn(BaseModel):
    intervals: list[IntervalIn] = Field(max_length=70)


class HolidayIn(BaseModel):
    day: date
    name: str = Field(default="", max_length=120)


class HolidayOut(HolidayIn):
    id: int


class WorkingHoursOut(BaseModel):
    timezone: str
    intervals: list[IntervalIn]
    holidays: list[HolidayOut]
    is_default: bool
