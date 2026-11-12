from pydantic import BaseModel, ConfigDict

from app.domain.enums import AssetStatus


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    default_duration_min: int
    is_active: bool


class PropertyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    address: str
    is_active: bool


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    property_id: int
    code: str
    name: str
    asset_type: str
    status: AssetStatus
