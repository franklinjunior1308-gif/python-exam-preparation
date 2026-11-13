from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator


class OrganizationOut(BaseModel):
    id: int
    name: str
    timezone: str


class OrganizationUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    timezone: str = Field(min_length=1, max_length=64)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("name is too short")
        return value

    @field_validator("timezone")
    @classmethod
    def _timezone(cls, value: str) -> str:
        value = value.strip()
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError, OSError) as err:
            raise ValueError("unknown IANA time zone, for example Asia/Bishkek") from err
        return value
