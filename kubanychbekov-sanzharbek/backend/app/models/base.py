from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """created/updated stored as timezone-aware UTC (DATA-02, DATA-03)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


def enum_column(enum_cls: type[StrEnum], length: int = 20) -> Enum:
    """Enum stored as VARCHAR with a CHECK constraint (easy to migrate, enforced by the DB)."""
    return Enum(
        enum_cls,
        native_enum=False,
        length=length,
        create_constraint=True,
        values_callable=lambda e: [m.value for m in e],
    )
