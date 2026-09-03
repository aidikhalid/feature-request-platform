from fastapi import APIRouter, Query, status

from app.api.presenters import comment_out, request_detail, request_summaries, request_summary
from app.core.deps import CurrentUser, DbSession, OptionalUser
from app.models import RequestStatus
from app.schemas import (
    CommentCreate,
    CommentOut,
    FeatureRequestCreate,
    FeatureRequestDetail,
    FeatureRequestSummary,
    FeatureRequestUpdate,
    Page,
    VoteState,
)
from app.services import request_service, vote_service

router = APIRouter(prefix="/api/requests", tags=["requests"])


@router.get("", response_model=Page[FeatureRequestSummary])
def list_requests(
    db: DbSession,
    user: OptionalUser,
    q: str | None = Query(default=None, max_length=200, description="Free-text search"),
    status_filter: RequestStatus | None = Query(default=None, alias="status"),
    sort: str = Query(default="top", pattern="^(top|new|discussed)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
) -> Page[FeatureRequestSummary]:
    """Browsing is public; `has_voted` is filled in only when the caller is signed in."""
    rows, total = request_service.list_requests(
        db, q=q, status=status_filter, sort=sort, page=page, page_size=page_size
    )
    return Page[FeatureRequestSummary](
        items=request_summaries(db, rows, user),
        page=page,
        page_size=page_size,
        total=total,
        total_pages=max(1, -(-total // page_size)),
    )


@router.post("", response_model=FeatureRequestDetail, status_code=status.HTTP_201_CREATED)
def create_request(payload: FeatureRequestCreate, db: DbSession, user: CurrentUser):
    request = request_service.create_request(db, user, payload)
    return request_detail(db, request, user)


@router.get("/{request_id}", response_model=FeatureRequestDetail)
def get_request(request_id: int, db: DbSession, user: OptionalUser):
    return request_detail(db, request_service.get_request(db, request_id), user)


@router.patch("/{request_id}", response_model=FeatureRequestDetail)
def update_request(
    request_id: int, payload: FeatureRequestUpdate, db: DbSession, user: CurrentUser
):
    """Ownership is checked server-side in the service — hiding the edit button in the UI
    is presentation, not authorization."""
    request = request_service.update_request(db, request_id, user, payload)
    return request_detail(db, request, user)


@router.post("/{request_id}/vote", response_model=VoteState)
def vote(request_id: int, db: DbSession, user: CurrentUser) -> VoteState:
    """Idempotent: calling this twice leaves exactly one vote and one increment."""
    return vote_service.add_vote(db, user.id, request_id)


@router.delete("/{request_id}/vote", response_model=VoteState)
def unvote(request_id: int, db: DbSession, user: CurrentUser) -> VoteState:
    """Idempotent: removing a vote that isn't there is a no-op, not an error."""
    return vote_service.remove_vote(db, user.id, request_id)


@router.get("/{request_id}/comments", response_model=list[CommentOut])
def list_comments(request_id: int, db: DbSession):
    return [comment_out(c) for c in request_service.list_comments(db, request_id)]


@router.post(
    "/{request_id}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED
)
def add_comment(request_id: int, payload: CommentCreate, db: DbSession, user: CurrentUser):
    return comment_out(request_service.add_comment(db, request_id, user, payload.body))
