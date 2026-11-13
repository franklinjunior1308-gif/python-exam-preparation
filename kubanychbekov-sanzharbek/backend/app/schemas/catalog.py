from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.enums import AssetStatus


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    default_duration_min: int
    required_skills: list[str] = []
    is_active: bool


class CategoryIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=2000)
    default_duration_min: int = Field(ge=5, le=480)
    required_skills: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("name is too short")
        return value

    @field_validator("required_skills")
    @classmethod
    def _skills(cls, value: list[str]) -> list[str]:
        cleaned = sorted({s.strip().lower() for s in value if s.strip()})
        if any(len(s) > 60 for s in cleaned):
            raise ValueError("a skill is at most 60 characters")
        return cleaned


class CategoryUpdate(CategoryIn):
    is_active: bool | None = None


class PropertyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    address: str
    contact_instructions: str | None = None
    is_active: bool


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    property_id: int
    code: str
    name: str
    asset_type: str
    status: AssetStatus
    serial_number: str | None = None
    installed_on: date | None = None
    notes: str | None = None


def _clean(value: str, label: str, minimum: int = 2) -> str:
    value = value.strip()
    if len(value) < minimum:
        raise ValueError(f"{label} is too short")
    return value


class PropertyIn(BaseModel):
    name: str = Field(max_length=200)
    address: str = Field(max_length=500)
    contact_instructions: str | None = Field(default=None, max_length=2000)
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        return _clean(value, "name")

    @field_validator("address")
    @classmethod
    def _address(cls, value: str) -> str:
        return _clean(value, "address", 3)


class AssetUpdate(BaseModel):
    """Everything about a piece of equipment except its code, which other records refer to."""

    property_id: int
    name: str = Field(max_length=200)
    asset_type: str = Field(max_length=100)
    serial_number: str | None = Field(default=None, max_length=100)
    installed_on: date | None = None
    status: AssetStatus = AssetStatus.ACTIVE
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("name", "asset_type")
    @classmethod
    def _text(cls, value: str) -> str:
        return _clean(value, "text")


class AssetIn(AssetUpdate):
    code: str = Field(min_length=1, max_length=64)

    @field_validator("code")
    @classmethod
    def _code(cls, value: str) -> str:
        return _clean(value, "code", 1)


class HistoryMaterial(BaseModel):
    item_name: str
    quantity: Decimal
    total_cents: int


class HistoryFile(BaseModel):
    id: int
    purpose: str


class HistoryEntry(BaseModel):
    """One request on this equipment: who did it, when, with what result (ASSET-04)."""

    request_id: int
    title: str
    status: str
    priority: str
    created_at: datetime
    completed_at: datetime | None
    technicians: list[str]
    result: str | None  # the technician's closing note
    materials: list[HistoryMaterial]
    attachments: list[HistoryFile]
