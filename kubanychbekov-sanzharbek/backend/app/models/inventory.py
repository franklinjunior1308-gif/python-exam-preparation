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
from app.models.base import TimestampMixin


class InventoryItem(TimestampMixin, Base):
    __tablename__ = "inventory_items"
    __table_args__ = (
        UniqueConstraint("organization_id", "code"),
        UniqueConstraint("organization_id", "id"),
        # the database itself refuses a negative balance, whatever the application does (INV-02)
        CheckConstraint("stock >= 0", name="ck_inventory_stock_non_negative"),
        CheckConstraint(
            "reorder_threshold >= 0 AND unit_price_cents >= 0", name="ck_inventory_values"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(200))
    unit: Mapped[str] = mapped_column(String(20))
    stock: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal(0))
    reorder_threshold: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal(0))
    unit_price_cents: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(default=True)


class StockReplenishment(Base):
    """Every increase of stock: how much, why, by whom, when (INV-02)."""

    __tablename__ = "stock_replenishments"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_replenishment_positive"),
        ForeignKeyConstraint(
            ["organization_id", "item_id"],
            ["inventory_items.organization_id", "inventory_items.id"],
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    item_id: Mapped[int] = mapped_column()
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    reason: Mapped[str] = mapped_column(String(300))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MaterialUsage(Base):
    """Material written off a request. The price is a snapshot at the moment of use (INV-05)."""

    __tablename__ = "material_usages"
    __table_args__ = (
        UniqueConstraint("organization_id", "client_command_id"),
        CheckConstraint("quantity > 0", name="ck_usage_positive"),
        ForeignKeyConstraint(
            ["organization_id", "item_id"],
            ["inventory_items.organization_id", "inventory_items.id"],
        ),
        ForeignKeyConstraint(
            ["organization_id", "request_id"],
            ["service_requests.organization_id", "service_requests.id"],
        ),
        Index("ix_usage_request", "request_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    request_id: Mapped[int] = mapped_column()
    item_id: Mapped[int] = mapped_column()
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    unit_price_cents: Mapped[int] = mapped_column()
    used_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    client_command_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
