"""Model -> response-schema mapping.

Kept in one place so `has_voted` is computed the same way everywhere, and so routes stay
thin: they resolve auth, call a service, and hand the result to a presenter.
"""

from sqlalchemy.orm import Session

from app.models import Comment, FeatureRequest, User
from app.schemas import CommentOut, FeatureRequestDetail, FeatureRequestSummary
from app.services.vote_service import voted_request_ids


def request_summary(request: FeatureRequest, has_voted: bool = False) -> FeatureRequestSummary:
    return FeatureRequestSummary.model_validate(request).model_copy(update={"has_voted": has_voted})


def request_summaries(
    db: Session, requests: list[FeatureRequest], user: User | None
) -> list[FeatureRequestSummary]:
    voted = voted_request_ids(db, user.id, [r.id for r in requests]) if user else set()
    return [request_summary(r, r.id in voted) for r in requests]


def request_detail(
    db: Session, request: FeatureRequest, user: User | None
) -> FeatureRequestDetail:
    has_voted = bool(user and voted_request_ids(db, user.id, [request.id]))
    return FeatureRequestDetail.model_validate(request).model_copy(update={"has_voted": has_voted})


def comment_out(comment: Comment) -> CommentOut:
    return CommentOut.model_validate(comment)
