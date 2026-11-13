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
    is_active: bool


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    property_id: int
    code: str
    name: str
    asset_type: str
    status: AssetStatus
