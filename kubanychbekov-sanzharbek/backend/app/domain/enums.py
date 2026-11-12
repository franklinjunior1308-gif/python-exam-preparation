from enum import StrEnum


class Role(StrEnum):
    CUSTOMER = "customer"
    DISPATCHER = "dispatcher"
    ADMIN = "admin"
    TECHNICIAN = "technician"


class Priority(StrEnum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"


class RequestStatus(StrEnum):
    SUBMITTED = "SUBMITTED"
    TRIAGED = "TRIAGED"
    SCHEDULED = "SCHEDULED"
    ACCEPTED = "ACCEPTED"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    CLOSED = "CLOSED"
    CANCELED = "CANCELED"
    REOPENED = "REOPENED"


class NoteVisibility(StrEnum):
    PUBLIC = "public"  # visible to the customer too
    INTERNAL = "internal"  # staff and technicians only


class AssignmentStatus(StrEnum):
    SCHEDULED = "SCHEDULED"
    ACCEPTED = "ACCEPTED"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    CANCELED = "CANCELED"  # removed by a dispatcher before work started
    DECLINED = "DECLINED"  # refused by the technician before work started


# Only these block a technician's time (SCHED-03).
ACTIVE_ASSIGNMENT_STATUSES = (
    AssignmentStatus.SCHEDULED,
    AssignmentStatus.ACCEPTED,
    AssignmentStatus.IN_PROGRESS,
    AssignmentStatus.BLOCKED,
)


class AssetStatus(StrEnum):
    ACTIVE = "ACTIVE"
    OUT_OF_SERVICE = "OUT_OF_SERVICE"
    RETIRED = "RETIRED"
