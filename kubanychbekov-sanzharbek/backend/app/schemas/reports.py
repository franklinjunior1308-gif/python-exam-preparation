from datetime import date, datetime

from pydantic import BaseModel


class DailyPoint(BaseModel):
    date: date
    created: int
    completed: int


class CategoryCount(BaseModel):
    category_id: int
    name: str
    count: int


class UpcomingVisit(BaseModel):
    request_id: int
    title: str
    technician: str
    start_at: datetime
    end_at: datetime


class TechnicianLoad(BaseModel):
    """REPORT-03: scheduled minutes / available working minutes of the active technicians."""

    percent: int  # capped at 100, see `method`
    scheduled_minutes: int
    available_minutes: int
    technicians: int  # active technicians counted in the denominator
    method: str


class SummaryOut(BaseModel):
    total: int
    open: int
    in_progress: int
    completed_in_period: int
    period_days: int
    timezone: str
    by_status: dict[str, int]
    by_priority: dict[str, int]
    by_category: list[CategoryCount]
    daily: list[DailyPoint]
    date_from: date
    date_to: date
    overdue: int | None = None  # open requests past their SLA (staff only)
    upcoming_visits: list[UpcomingVisit] = []
    technician_load: TechnicianLoad | None = None  # staff only
    # approved estimates are quotes, not revenue (REPORT-04)
    approved_estimates_cents: int = 0
    approved_estimates_count: int = 0
    materials_cost_cents: int | None = None  # staff only
