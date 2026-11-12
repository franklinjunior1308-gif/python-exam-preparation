from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.enums import Priority, RequestStatus
from app.models.base import TimestampMixin, enum_column


class ServiceRequest(TimestampMixin, Base):
    __tablename__ = "service_requests"
    __table_args__ = (
        # target of composite FKs from assignments
        UniqueConstraint("organization_id", "id", name="uq_service_requests_organization_id_id"),
        # composite FKs make cross-organization links impossible at the database level (DATA-05)
        ForeignKeyConstraint(
            ["organization_id", "category_id"],
            ["service_categories.organization_id", "service_categories.id"],
        ),
        ForeignKeyConstraint(
            ["organization_id", "property_id"],
            ["properties.organization_id", "properties.id"],
        ),
        ForeignKeyConstraint(
            ["organization_id", "asset_id"],
            ["assets.organization_id", "assets.id"],
        ),
        CheckConstraint("char_length(title) BETWEEN 5 AND 120", name="ck_request_title_len"),
        CheckConstraint(
            "char_length(description) BETWEEN 20 AND 3000", name="ck_request_description_len"
        ),
        CheckConstraint(
            "desired_end IS NULL OR desired_start IS NULL OR desired_end > desired_start",
            name="ck_request_window",
        ),
        Index("ix_requests_org_status", "organization_id", "status"),
        Index("ix_requests_org_created", "organization_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    category_id: Mapped[int] = mapped_column()
    property_id: Mapped[int] = mapped_column()
    asset_id: Mapped[int | None] = mapped_column(default=None)
    priority: Mapped[Priority] = mapped_column(enum_column(Priority), default=Priority.NORMAL)
    status: Mapped[RequestStatus] = mapped_column(
        enum_column(RequestStatus), default=RequestStatus.SUBMITTED
    )
    desired_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    desired_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)


class RequestStatusHistory(Base):
    """Every state change of a request (DATA-02: history of states)."""

    __tablename__ = "request_status_history"
    __table_args__ = (Index("ix_history_request", "request_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    request_id: Mapped[int] = mapped_column(ForeignKey("service_requests.id"))
    from_status: Mapped[RequestStatus | None] = mapped_column(
        enum_column(RequestStatus, name="history_from_status"), default=None
    )
    to_status: Mapped[RequestStatus] = mapped_column(
        enum_column(RequestStatus, name="history_to_status")
    )
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str | None] = mapped_column(String(1000), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
