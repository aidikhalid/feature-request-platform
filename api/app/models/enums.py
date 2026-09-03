import enum


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class RequestStatus(str, enum.Enum):
    """The five statuses named in the brief. New requests start at UNDER_REVIEW."""

    UNDER_REVIEW = "under_review"
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    RELEASED = "released"
    DECLINED = "declined"
