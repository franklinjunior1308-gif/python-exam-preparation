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


class AssetStatus(StrEnum):
    ACTIVE = "ACTIVE"
    OUT_OF_SERVICE = "OUT_OF_SERVICE"
    RETIRED = "RETIRED"
