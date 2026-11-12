import re
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from app.domain.enums import AssignmentStatus, NoteVisibility, Priority, RequestStatus

_COMMAND_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def _check_command_id(value: str) -> str:
    if not _COMMAND_ID.match(value):
        raise ValueError("client_command_id must be 8-64 characters: letters, digits, '-' or '_'")
    return value


CommandId = Annotated[str, AfterValidator(_check_command_id)]


class NoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
    visibility: NoteVisibility = NoteVisibility.PUBLIC
    client_command_id: CommandId


class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_id: int
    author_user_id: int
    author_name: str = ""
    visibility: NoteVisibility
    kind: str
    body: str
    client_command_id: str
    created_at: datetime


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_id: int
    note_id: int | None
    uploaded_by_user_id: int
    purpose: str
    content_type: str
    size_bytes: int
    width: int
    height: int
    client_command_id: str
    created_at: datetime


class CompleteIn(BaseModel):
    summary: str = Field(min_length=1, max_length=2000)
    client_command_id: CommandId


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    request_id: int | None
    title: str
    body: str
    read_at: datetime | None
    created_at: datetime


class MyTaskOut(BaseModel):
    """A technician's task: only what is needed to do the job (ROLE-03)."""

    assignment_id: int
    assignment_status: AssignmentStatus
    start_at: datetime
    end_at: datetime
    timezone: str
    request_id: int
    title: str
    description: str
    priority: Priority
    request_status: RequestStatus
    allowed_actions: list[RequestStatus]
    category_name: str
    property_name: str
    property_address: str
    contact_instructions: str | None
    asset_label: str | None
    customer_name: str
    updated_at: datetime
