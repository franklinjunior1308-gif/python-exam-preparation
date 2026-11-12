from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import Priority, RequestStatus
from app.schemas.sla import SlaOut


class RequestCreate(BaseModel):
    title: str = Field(min_length=5, max_length=120)
    description: str = Field(min_length=20, max_length=3000)
    category_id: int
    property_id: int
    asset_id: int | None = None
    priority: Priority = Priority.NORMAL
    desired_start: datetime | None = None
    desired_end: datetime | None = None

    @model_validator(mode="after")
    def _check_window(self) -> Self:
        if self.desired_start and self.desired_end and self.desired_end <= self.desired_start:
            raise ValueError("desired_end must be later than desired_start")
        return self


class RequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    title: str
    description: str
    category_id: int
    property_id: int
    asset_id: int | None
    priority: Priority
    status: RequestStatus
    desired_start: datetime | None
    desired_end: datetime | None
    created_by_user_id: int
    created_at: datetime
    updated_at: datetime
    allowed_actions: list[RequestStatus] = []
    sla: SlaOut | None = None


class RequestPage(BaseModel):
    items: list[RequestOut]
    total: int
    page: int
    page_size: int


class TransitionIn(BaseModel):
    to_status: RequestStatus
    reason: str | None = Field(default=None, max_length=1000)


class HistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    from_status: RequestStatus | None
    to_status: RequestStatus
    actor_user_id: int
    reason: str | None
    created_at: datetime


class TriageIn(BaseModel):
    """Dispatcher changes priority and/or category, with a mandatory reason (REQ-03)."""

    priority: Priority | None = None
    category_id: int | None = None
    reason: str = Field(min_length=3, max_length=1000)

    @model_validator(mode="after")
    def _something_to_change(self) -> Self:
        if self.priority is None and self.category_id is None:
            raise ValueError("priority or category_id is required")
        return self
