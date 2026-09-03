"""Merging duplicate feature requests.

This is the assignment's transaction showcase: several statements must all take effect
together, or none of them. It runs inside the request's single session/transaction and
commits once at the end; any exception rolls the whole thing back and leaves the two
requests exactly as they were.
"""

from datetime import datetime, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.errors import BadRequest, Conflict, NotFound
from app.models import Comment, FeatureRequest, Vote


def merge_requests(db: Session, source_id: int, target_id: int) -> FeatureRequest:
    """Fold `source` into `target`, preserving all of source's votes and comments.

    Steps, all in one transaction:

    1. Lock both rows with SELECT ... FOR UPDATE, **ordered by id**. Deterministic lock
       ordering is what stops two admins merging overlapping pairs (A→B and B→A) from
       deadlocking each other.
    2. Refuse anything that would corrupt the graph: merging into itself, or touching a
       request that is already merged. Refusing a merged *target* is what makes a cycle
       impossible, since every arrow must end at a live request.
    3. Resolve double-voters, then move the remaining votes.
    4. Move the comments.
    5. Re-point anything already merged into the source, so chains stay one hop deep.
    6. Recompute both counters on the target from the underlying rows.
    """
    if source_id == target_id:
        raise BadRequest("A request cannot be merged into itself", code="invalid_merge")

    # Step 1 — lock both rows in a stable order.
    rows = (
        db.execute(
            select(FeatureRequest)
            .where(FeatureRequest.id.in_([source_id, target_id]))
            .order_by(FeatureRequest.id)
            .with_for_update()
        )
        .scalars()
        .all()
    )
    by_id = {r.id: r for r in rows}
    source = by_id.get(source_id)
    target = by_id.get(target_id)

    # Step 2 — validate.
    if source is None:
        raise NotFound(f"Source request {source_id} not found")
    if target is None:
        raise NotFound(f"Target request {target_id} not found")
    if source.is_merged:
        raise Conflict("The source request has already been merged", code="already_merged")
    if target.is_merged:
        raise Conflict(
            "The target request has itself been merged into another request",
            code="already_merged",
        )

    # Step 3 — the interesting case. A user may have voted on *both* requests. Moving
    # their source vote across would violate UNIQUE(user_id, feature_request_id), and
    # simply adding the two counters together would count one person twice. So drop the
    # source-side duplicates first, then move what remains. One human, one vote.
    duplicate_voters = select(Vote.user_id).where(Vote.feature_request_id == target_id)
    db.execute(
        delete(Vote).where(
            Vote.feature_request_id == source_id,
            Vote.user_id.in_(duplicate_voters),
        )
    )
    db.execute(
        update(Vote)
        .where(Vote.feature_request_id == source_id)
        .values(feature_request_id=target_id)
    )

    # Step 4 — comments always move; there is no uniqueness rule to respect.
    db.execute(
        update(Comment)
        .where(Comment.feature_request_id == source_id)
        .values(feature_request_id=target_id)
    )

    # Step 5 — the source may itself be the survivor of an earlier merge. Those earlier
    # duplicates must follow it, or they would point at a request that is now retired and
    # a visitor following the pointer would land on another dead end. Re-pointing them
    # here keeps the invariant that `merged_into_id` always resolves to a live request in
    # exactly one hop. (Their votes and comments already moved to the source when they
    # were merged, and are moving on to the target in steps 3 and 4, so only the pointer
    # is left to update.)
    db.execute(
        update(FeatureRequest)
        .where(FeatureRequest.merged_into_id == source_id)
        .values(merged_into_id=target_id)
    )

    # Step 6 — recompute from the rows themselves. Adding the old counters would be wrong
    # after the de-duplication in step 3.
    target.vote_count = db.execute(
        select(func.count()).select_from(Vote).where(Vote.feature_request_id == target_id)
    ).scalar_one()
    target.comment_count = db.execute(
        select(func.count()).select_from(Comment).where(Comment.feature_request_id == target_id)
    ).scalar_one()

    source.vote_count = 0
    source.comment_count = 0
    source.merged_into_id = target_id
    source.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(target)
    return target
