from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.enums import EstimateStatus
from app.models.base import TimestampMixin, enum_column


class Estimate(TimestampMixin, Base):
    """One version of the cost estimate of a request (EST-02, EST-06)."""

    __tablename__ = "estimates"
    __table_args__ = (
        UniqueConstraint("request_id", "version"),
        UniqueConstraint("organization_id", "id"),
        ForeignKeyConstraint(
            ["organization_id", "request_id"],
            ["service_requests.organization_id", "service_requests.id"],
        ),
        CheckConstraint("labor_minutes >= 0 AND labor_rate_cents >= 0", name="ck_estimate_labor"),
        Index("ix_estimates_request", "request_id", "version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    request_id: Mapped[int] = mapped_column()
    version: Mapped[int] = mapped_column()
    status: Mapped[EstimateStatus] = mapped_column(
        enum_column(EstimateStatus, 20), default=EstimateStatus.DRAFT
    )
    labor_minutes: Mapped[int] = mapped_column(default=0)
    labor_rate_cents: Mapped[int] = mapped_column(default=0)  # per hour, in tyiyn
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    decided_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    decision_reason: Mapped[str | None] = mapped_column(String(1000), default=None)


class EstimateLine(Base):
    __tablename__ = "estimate_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_line_quantity"),
        CheckConstraint("unit_price_cents >= 0", name="ck_line_price"),
        ForeignKeyConstraint(
            ["organization_id", "estimate_id"], ["estimates.organization_id", "estimates.id"]
        ),
        Index("ix_estimate_lines_estimate", "estimate_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    estimate_id: Mapped[int] = mapped_column()
    description: Mapped[str] = mapped_column(String(200))
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    unit_price_cents: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
