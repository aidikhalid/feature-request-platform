"""Feature request reads and writes (everything except voting and merging)."""

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session, joinedload

from app.errors import Conflict, Forbidden, NotFound
from app.models import Comment, FeatureRequest, RequestStatus, User
from app.schemas import FeatureRequestCreate, FeatureRequestUpdate

SORT_OPTIONS = ("top", "new", "discussed")


def _base_query():
    # Merged duplicates are hidden from the board: their activity now lives on the
    # surviving request, and showing both would double-count the same idea.
    return select(FeatureRequest).where(FeatureRequest.merged_into_id.is_(None))


def list_requests(
    db: Session,
    *,
    q: str | None = None,
    status: RequestStatus | None = None,
    sort: str = "top",
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[FeatureRequest], int]:
    """Search, filter, sort and paginate. Returns (rows, total_matching)."""
    query = _base_query()

    if q:
        # ILIKE is honest for this dataset size. Postgres full-text search with a GIN
        # index is the documented next step once the board outgrows it.
        #
        # The user's term is escaped first: % and _ are LIKE wildcards, so without this a
        # search for "100%" would also match "1000 concurrent users", "sign_in" would
        # match "signxin", and a lone "%" would return the entire board.
        term = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{term}%"
        query = query.where(
            or_(
                FeatureRequest.title.ilike(pattern, escape="\\"),
                FeatureRequest.description.ilike(pattern, escape="\\"),
            )
        )

    if status is not None:
        query = query.where(FeatureRequest.status == status)

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar_one()

    order = {
        "top": (FeatureRequest.vote_count.desc(), FeatureRequest.created_at.desc()),
        "new": (FeatureRequest.created_at.desc(),),
        "discussed": (FeatureRequest.comment_count.desc(), FeatureRequest.created_at.desc()),
    }[sort if sort in SORT_OPTIONS else "top"]

    rows = (
        db.execute(
            query.options(joinedload(FeatureRequest.author))
            .order_by(*order, FeatureRequest.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return list(rows), total


def get_request_for_update(db: Session, request_id: int) -> FeatureRequest:
    """Load a request and hold a row lock on it for the rest of the transaction.

    Voting and commenting take this lock before they check whether the request has been
    merged. Without it there is a gap between "is this request still open?" and the
    insert, and a merge committing inside that gap strands the new row on a request that
    is now retired — hidden from the board, and impossible for the user to withdraw.

    `merge_service` locks the same rows first, so one of the two operations waits for the
    other rather than interleaving. Only ever one row is locked here, so this cannot
    deadlock against the merge's ordered two-row lock.
    """
    request = db.execute(
        select(FeatureRequest).where(FeatureRequest.id == request_id).with_for_update()
    ).scalar_one_or_none()
    if request is None:
        raise NotFound("Feature request not found")
    return request


def get_request(db: Session, request_id: int) -> FeatureRequest:
    request = db.execute(
        select(FeatureRequest)
        .where(FeatureRequest.id == request_id)
        .options(
            joinedload(FeatureRequest.author),
            joinedload(FeatureRequest.official_response_by),
        )
    ).scalar_one_or_none()
    if request is None:
        raise NotFound("Feature request not found")
    return request


def create_request(db: Session, author: User, payload: FeatureRequestCreate) -> FeatureRequest:
    request = FeatureRequest(
        title=payload.title.strip(),
        description=payload.description.strip(),
        author_id=author.id,
        status=RequestStatus.UNDER_REVIEW,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


def update_request(
    db: Session, request_id: int, user: User, payload: FeatureRequestUpdate
) -> FeatureRequest:
    """Edit a request. A user may only edit their own; admins may edit any.

    Note the ordering: 404 before 403, so this endpoint does not become an oracle that
    tells an attacker which request ids exist.
    """
    request = get_request(db, request_id)

    if request.author_id != user.id and not user.is_admin:
        raise Forbidden("You can only edit your own requests")
    if request.is_merged:
        raise Conflict("This request was merged and can no longer be edited", code="request_merged")

    if payload.title is not None:
        request.title = payload.title.strip()
    if payload.description is not None:
        request.description = payload.description.strip()

    db.commit()
    db.refresh(request)
    return request


def list_comments(db: Session, request_id: int) -> list[Comment]:
    get_request(db, request_id)  # 404 for an unknown request rather than an empty list
    rows = (
        db.execute(
            select(Comment)
            .where(Comment.feature_request_id == request_id)
            .options(joinedload(Comment.author))
            .order_by(Comment.created_at.asc())
        )
        .scalars()
        .all()
    )
    return list(rows)


def add_comment(db: Session, request_id: int, author: User, body: str) -> Comment:
    # Locked before the merged check — see get_request_for_update.
    request = get_request_for_update(db, request_id)
    if request.is_merged:
        raise Conflict("This request was merged; comment on the surviving request instead",
                       code="request_merged")

    comment = Comment(feature_request_id=request_id, author_id=author.id, body=body.strip())
    db.add(comment)
    # Same atomic-increment reasoning as votes: let Postgres do the arithmetic, in the
    # same transaction as the insert.
    db.execute(
        update(FeatureRequest)
        .where(FeatureRequest.id == request_id)
        .values(comment_count=FeatureRequest.comment_count + 1)
    )
    db.commit()
    db.refresh(comment)
    return comment
