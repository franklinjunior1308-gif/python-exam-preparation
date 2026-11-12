from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.domain.enums import Priority


class PlanIn(BaseModel):
    asset_id: int
    category_id: int
    title: str = Field(min_length=5, max_length=120)
    description: str = Field(default="", max_length=2000)
    priority: Priority = Priority.NORMAL
    frequency: Literal["WEEKLY", "MONTHLY"]
    first_date: date


class PlanOut(BaseModel):
    id: int
    asset_id: int
    asset_name: str
    category_id: int
    title: str
    description: str
    priority: Priority
    frequency: str
    first_date: date
    is_active: bool
    next_date: date | None  # the next event that has not been generated yet
    generated_count: int
    created_at: datetime


class GenerateIn(BaseModel):
    as_of: date | None = None  # defaults to today in the organization's timezone


class GenerateOut(BaseModel):
    as_of: date
    created_requests: int
    skipped_existing: int


class PlanRequestOut(BaseModel):
    request_id: int
    plan_date: date
    status: str
