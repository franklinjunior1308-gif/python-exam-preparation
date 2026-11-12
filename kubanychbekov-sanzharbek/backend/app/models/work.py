from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.enums import NoteVisibility
from app.models.base import enum_column


class WorkNote(Base):
    """Immutable note on a request (COMM-02). Corrections are new notes, never edits."""

    __tablename__ = "work_notes"
    __table_args__ = (
        # the client-chosen command id makes retries (offline queue) safe and survives restarts
        UniqueConstraint("organization_id", "client_command_id"),
        UniqueConstraint("organization_id", "id"),
        ForeignKeyConstraint(
            ["organization_id", "request_id"],
            ["service_requests.organization_id", "service_requests.id"],
        ),
        Index("ix_notes_request", "request_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    request_id: Mapped[int] = mapped_column()
    author_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    visibility: Mapped[NoteVisibility] = mapped_column(
        enum_column(NoteVisibility, 10), default=NoteVisibility.PUBLIC
    )
    kind: Mapped[str] = mapped_column(String(20), default="note")  # "note" | "completion"
    body: Mapped[str] = mapped_column(Text)
    client_command_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvidenceFile(Base):
    """A photo stored on the local volume; served only through authorized endpoints (COMM-06)."""

    __tablename__ = "evidence_files"
    __table_args__ = (
        UniqueConstraint("organization_id", "client_command_id"),
        ForeignKeyConstraint(
            ["organization_id", "request_id"],
            ["service_requests.organization_id", "service_requests.id"],
        ),
        ForeignKeyConstraint(
            ["organization_id", "note_id"], ["work_notes.organization_id", "work_notes.id"]
        ),
        Index("ix_files_request", "request_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    request_id: Mapped[int] = mapped_column()
    note_id: Mapped[int | None] = mapped_column(default=None)
    uploaded_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    purpose: Mapped[str] = mapped_column(String(20), default="evidence")  # before|after|evidence
    content_type: Mapped[str] = mapped_column(String(40))
    size_bytes: Mapped[int] = mapped_column()
    sha256: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(255))  # server-generated, never user input
    width: Mapped[int] = mapped_column()
    height: Mapped[int] = mapped_column()
    client_command_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Notification(Base):
    """Stored notification for one recipient inside one organization (COMM-03/04)."""

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_recipient", "recipient_user_id", "read_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    recipient_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    type: Mapped[str] = mapped_column(String(40))
    request_id: Mapped[int | None] = mapped_column(default=None)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(String(500), default="")
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
