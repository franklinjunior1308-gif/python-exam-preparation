from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, ForeignKeyConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.enums import Priority
from app.models.base import TimestampMixin, enum_column


class MaintenancePlan(TimestampMixin, Base):
    """A recurring preventive job for one asset (PM-01)."""

    __tablename__ = "maintenance_plans"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "asset_id"], ["assets.organization_id", "assets.id"]
        ),
        ForeignKeyConstraint(
            ["organization_id", "category_id"],
            ["service_categories.organization_id", "service_categories.id"],
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    asset_id: Mapped[int] = mapped_column()
    category_id: Mapped[int] = mapped_column()
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[Priority] = mapped_column(enum_column(Priority), default=Priority.NORMAL)
    frequency: Mapped[str] = mapped_column(String(10))  # WEEKLY | MONTHLY
    first_date: Mapped[date] = mapped_column(Date)  # first event, in the organization's calendar
    is_active: Mapped[bool] = mapped_column(default=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
