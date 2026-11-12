from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.work import CommandId

Quantity = Field(gt=0, max_digits=12, decimal_places=3)


class ItemIn(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    unit: str = Field(min_length=1, max_length=20)
    stock: Decimal = Field(default=Decimal(0), ge=0, max_digits=12, decimal_places=3)
    reorder_threshold: Decimal = Field(default=Decimal(0), ge=0, max_digits=12, decimal_places=3)
    unit_price_cents: int = Field(default=0, ge=0, le=10**10)


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    unit: str
    stock: Decimal
    reorder_threshold: Decimal
    unit_price_cents: int
    is_active: bool
    low_stock: bool = False


class ReplenishIn(BaseModel):
    quantity: Decimal = Quantity
    reason: str = Field(min_length=1, max_length=300)


class UsageIn(BaseModel):
    item_id: int
    quantity: Decimal = Quantity
    client_command_id: CommandId


class UsageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_id: int
    item_id: int
    item_name: str = ""
    quantity: Decimal
    unit_price_cents: int
    total_cents: int = 0
    used_by_user_id: int
    client_command_id: str
    created_at: datetime
