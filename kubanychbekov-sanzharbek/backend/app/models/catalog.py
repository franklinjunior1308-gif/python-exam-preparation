from datetime import date

from sqlalchemy import ForeignKey, ForeignKeyConstraint, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.enums import AssetStatus
from app.models.base import TimestampMixin, enum_column


class ServiceCategory(TimestampMixin, Base):
    __tablename__ = "service_categories"
    __table_args__ = (
        UniqueConstraint("organization_id", "name"),
        # target of composite FKs: guarantees a row can only be referenced inside its organization
        UniqueConstraint("organization_id", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    default_duration_min: Mapped[int] = mapped_column(default=60)
    # a technician needs ALL of these skills to be assigned (SCHED-01)
    required_skills: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    is_active: Mapped[bool] = mapped_column(default=True)


class Property(TimestampMixin, Base):
    """A serviced site (building, office, ...)."""

    __tablename__ = "properties"
    __table_args__ = (UniqueConstraint("organization_id", "id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str] = mapped_column(String(500))
    contact_instructions: Mapped[str | None] = mapped_column(Text, default=None)
    is_active: Mapped[bool] = mapped_column(default=True)


class Asset(TimestampMixin, Base):
    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint("organization_id", "code"),
        UniqueConstraint("organization_id", "id"),
        ForeignKeyConstraint(
            ["organization_id", "property_id"],
            ["properties.organization_id", "properties.id"],
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    property_id: Mapped[int] = mapped_column()
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(200))
    asset_type: Mapped[str] = mapped_column(String(100))
    serial_number: Mapped[str | None] = mapped_column(String(100), default=None)
    installed_on: Mapped[date | None] = mapped_column(default=None)
    status: Mapped[AssetStatus] = mapped_column(
        enum_column(AssetStatus, 20), default=AssetStatus.ACTIVE
    )
    notes: Mapped[str | None] = mapped_column(Text, default=None)
