from datetime import date, datetime, time

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WorkingInterval(Base):
    """Organization working hours: one row per interval and weekday (0 = Monday), ORG-02."""

    __tablename__ = "working_intervals"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_working_weekday"),
        CheckConstraint("end_time > start_time", name="ck_working_order"),
        Index("ix_working_org", "organization_id", "weekday"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    weekday: Mapped[int] = mapped_column(SmallInteger)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)


class Holiday(Base):
    """A date excluded from the SLA clock (ORG-02, SLA-01)."""

    __tablename__ = "holidays"
    __table_args__ = (UniqueConstraint("organization_id", "day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    day: Mapped[date] = mapped_column(Date)
    name: Mapped[str] = mapped_column(String(120), default="")


class SlaEscalation(Base):
    """At most one escalation per request, enforced by the database (SLA-06)."""

    __tablename__ = "sla_escalations"
    __table_args__ = (UniqueConstraint("request_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("service_requests.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
