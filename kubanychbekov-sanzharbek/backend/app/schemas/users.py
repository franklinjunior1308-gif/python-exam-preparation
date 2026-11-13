import re

from pydantic import BaseModel, Field, field_validator

from app.domain.enums import Role

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _check_password(value: str) -> str:
    if len(value) < 10 or not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
        raise ValueError("password needs at least 10 characters with a letter and a digit")
    return value


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: Role
    is_active: bool  # membership in this organization
    technician_id: int | None = None


class UserCreate(BaseModel):
    email: str = Field(max_length=320)
    full_name: str = Field(min_length=2, max_length=200)
    role: Role
    password: str = Field(max_length=200)  # initial password; ignored for an existing account

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        value = value.strip().lower()
        if not _EMAIL.match(value):
            raise ValueError("invalid e-mail address")
        return value

    @field_validator("full_name")
    @classmethod
    def _name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("name is too short")
        return value

    @field_validator("password")
    @classmethod
    def _password(cls, value: str) -> str:
        return _check_password(value)


class UserUpdate(BaseModel):
    role: Role | None = None
    is_active: bool | None = None
