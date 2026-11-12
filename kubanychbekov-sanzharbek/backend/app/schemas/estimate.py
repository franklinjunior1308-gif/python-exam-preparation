from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.domain.enums import EstimateStatus


class LineIn(BaseModel):
    description: str = Field(min_length=1, max_length=200)
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    unit_price_cents: int = Field(ge=0, le=10**12)


class EstimateIn(BaseModel):
    labor_minutes: int = Field(ge=0, le=100_000)
    labor_rate_cents: int = Field(ge=0, le=10**10)
    lines: list[LineIn] = Field(default_factory=list, max_length=100)


class LineOut(LineIn):
    id: int
    line_total_cents: int


class EstimateOut(BaseModel):
    id: int
    request_id: int
    version: int
    status: EstimateStatus
    currency: str = "KGS"
    labor_minutes: int
    labor_rate_cents: int
    labor_cents: int
    materials_cents: int
    total_cents: int
    lines: list[LineOut]
    created_by_user_id: int
    submitted_at: datetime | None
    decided_by_user_id: int | None
    decided_at: datetime | None
    decision_reason: str | None
    created_at: datetime


class DecisionIn(BaseModel):
    approve: bool
    reason: str | None = Field(default=None, max_length=1000)
