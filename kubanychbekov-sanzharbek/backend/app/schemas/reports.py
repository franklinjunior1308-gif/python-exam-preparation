from datetime import date

from pydantic import BaseModel


class DailyPoint(BaseModel):
    date: date
    created: int
    completed: int


class CategoryCount(BaseModel):
    category_id: int
    name: str
    count: int


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
