"""Administrator actions on a request. Authorization is enforced by the route's
`require_admin` dependency; these functions assume an admin caller."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.errors import Conflict
from app.models import FeatureRequest, RequestStatus, User
from app.services.request_service import get_request


def set_status(db: Session, request_id: int, status: RequestStatus) -> FeatureRequest:
    request = get_request(db, request_id)
    if request.is_merged:
        raise Conflict("A merged request's status is owned by the request it was merged into",
                       code="request_merged")
    request.status = status
    db.commit()
    db.refresh(request)
    return request


def set_official_response(db: Session, request_id: int, admin: User, body: str) -> FeatureRequest:
    request = get_request(db, request_id)
    if request.is_merged:
        raise Conflict("Respond on the request this one was merged into", code="request_merged")
    request.official_response = body.strip()
    request.official_response_at = datetime.now(timezone.utc)
    request.official_response_by_id = admin.id
    db.commit()
    db.refresh(request)
    return request
