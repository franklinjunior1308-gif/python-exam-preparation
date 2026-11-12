from datetime import datetime, time

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    SmallInteger,
    String,
    Time,
    UniqueConstraint,
    literal_column,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.enums import ACTIVE_ASSIGNMENT_STATUSES, AssignmentStatus
from app.models.base import TimestampMixin, enum_column

_ACTIVE_SQL = "status IN ({})".format(", ".join(f"'{s.value}'" for s in ACTIVE_ASSIGNMENT_STATUSES))


class TechnicianProfile(TimestampMixin, Base):
    __tablename__ = "technician_profiles"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id"),
        UniqueConstraint("organization_id", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    is_active: Mapped[bool] = mapped_column(default=True)


class TechnicianSkill(Base):
    __tablename__ = "technician_skills"
    __table_args__ = (
        UniqueConstraint("organization_id", "technician_id", "skill"),
        ForeignKeyConstraint(
            ["organization_id", "technician_id"],
            ["technician_profiles.organization_id", "technician_profiles.id"],
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    technician_id: Mapped[int] = mapped_column()
    skill: Mapped[str] = mapped_column(String(60))


class TechnicianAvailability(Base):
    """Weekly working interval in the organization's timezone (weekday 0 = Monday)."""

    __tablename__ = "technician_availability"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_availability_weekday"),
        CheckConstraint("end_time > start_time", name="ck_availability_order"),
        ForeignKeyConstraint(
            ["organization_id", "technician_id"],
            ["technician_profiles.organization_id", "technician_profiles.id"],
        ),
        Index("ix_availability_tech", "technician_id", "weekday"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    technician_id: Mapped[int] = mapped_column()
    weekday: Mapped[int] = mapped_column(SmallInteger)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)


class TechnicianAbsence(Base):
    """Vacation / day off, stored in UTC."""

    __tablename__ = "technician_absences"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="ck_absence_order"),
        ForeignKeyConstraint(
            ["organization_id", "technician_id"],
            ["technician_profiles.organization_id", "technician_profiles.id"],
        ),
        Index("ix_absence_tech", "technician_id", "start_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    technician_id: Mapped[int] = mapped_column()
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(String(200), default=None)


class Assignment(TimestampMixin, Base):
    """A technician booked for a request. History is kept: rows are never deleted (SCHED-06)."""

    __tablename__ = "assignments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "request_id"],
            ["service_requests.organization_id", "service_requests.id"],
        ),
        ForeignKeyConstraint(
            ["organization_id", "technician_id"],
            ["technician_profiles.organization_id", "technician_profiles.id"],
        ),
        CheckConstraint(
            "end_at >= start_at + interval '30 minutes'", name="ck_assignment_min_duration"
        ),
        # The database itself refuses two active bookings of one technician whose half-open
        # intervals [start_at, end_at) overlap, so two concurrent requests cannot both win
        # (SCHED-03/04). 11:00-12:00 and 12:00-13:00 do not overlap.
        ExcludeConstraint(
            ("technician_id", "="),
            (literal_column("tstzrange(start_at, end_at, '[)')"), "&&"),
            where=text(_ACTIVE_SQL),
            using="gist",
            name="ex_assignment_no_overlap",
        ),
        # one active assignment per request
        Index(
            "uq_assignment_one_active_per_request",
            "request_id",
            unique=True,
            postgresql_where=text(_ACTIVE_SQL),
        ),
        Index("ix_assignment_tech_start", "technician_id", "start_at"),
        Index("ix_assignment_org_start", "organization_id", "start_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    request_id: Mapped[int] = mapped_column()
    technician_id: Mapped[int] = mapped_column()
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # timezone the visit was planned in, kept with the booking (DATA-03)
    timezone: Mapped[str] = mapped_column(String(64))
    status: Mapped[AssignmentStatus] = mapped_column(
        enum_column(AssignmentStatus, 20), default=AssignmentStatus.SCHEDULED
    )
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
