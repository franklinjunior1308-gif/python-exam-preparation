from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.enums import Role


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=200)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


class MembershipOut(BaseModel):
    organization_id: int
    organization_name: str
    timezone: str
    role: Role


class MeOut(BaseModel):
    id: int
    email: str
    full_name: str
    memberships: list[MembershipOut]
