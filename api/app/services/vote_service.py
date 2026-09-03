"""Voting.

Four of the assignment's six business rules concern voting, so this module is where
most of the integrity work lives. The design in one sentence: the database decides
uniqueness, the endpoints are idempotent, and the counter is moved with an atomic SQL
increment inside the same transaction as the vote row itself.
"""

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.errors import Conflict
from app.models import FeatureRequest, Vote
from app.schemas import VoteState
from app.services.request_service import get_request_for_update


def _load_votable_request(db: Session, request_id: int) -> FeatureRequest:
    # The row lock is taken before the merged check, so a merge cannot commit between the
    # two and strand this vote on a retired request. See request_service.get_request_for_update.
    request = get_request_for_update(db, request_id)
    if request.is_merged:
        # A merged request is an archive pointer; votes belong on the surviving request.
        raise Conflict(
            "This request was merged into another one and can no longer be voted on",
            code="request_merged",
        )
    return request


def _current_state(db: Session, request_id: int, user_id: int) -> VoteState:
    """Read the settled truth back out of the database rather than guessing in Python."""
    vote_count = db.execute(
        select(FeatureRequest.vote_count).where(FeatureRequest.id == request_id)
    ).scalar_one()
    has_voted = db.execute(
        select(Vote.id).where(Vote.feature_request_id == request_id, Vote.user_id == user_id)
    ).first() is not None
    return VoteState(feature_request_id=request_id, vote_count=vote_count, has_voted=has_voted)


def add_vote(db: Session, user_id: int, request_id: int) -> VoteState:
    """Cast a vote. Safe to call any number of times — the second call is a no-op.

    Why this is correct under concurrency:

    1. `ON CONFLICT DO NOTHING` leans on the UNIQUE(user_id, feature_request_id) index.
       If two requests race, the database serialises them on that index and exactly one
       insert wins. An `if already_voted:` check in Python could not do this — both
       requests can read "not voted" before either writes.
    2. We only touch the counter when we actually inserted a row (`rowcount == 1`), so a
       retried or double-clicked request cannot inflate the total.
    3. The counter moves with `vote_count = vote_count + 1` evaluated *by Postgres*, not
       by reading the value into Python and writing it back. Two concurrent increments on
       different requests therefore cannot lose an update.
    4. Insert and increment share one transaction: either both land, or neither does.
    """
    _load_votable_request(db, request_id)

    result = db.execute(
        pg_insert(Vote)
        .values(user_id=user_id, feature_request_id=request_id)
        .on_conflict_do_nothing(constraint="uq_votes_user_request")
    )

    if result.rowcount == 1:
        db.execute(
            update(FeatureRequest)
            .where(FeatureRequest.id == request_id)
            .values(vote_count=FeatureRequest.vote_count + 1)
        )

    db.commit()
    return _current_state(db, request_id, user_id)


def remove_vote(db: Session, user_id: int, request_id: int) -> VoteState:
    """Withdraw a vote. Also idempotent: removing a vote that is not there is a no-op."""
    _load_votable_request(db, request_id)

    result = db.execute(
        delete(Vote).where(Vote.user_id == user_id, Vote.feature_request_id == request_id)
    )

    if result.rowcount == 1:
        db.execute(
            update(FeatureRequest)
            .where(FeatureRequest.id == request_id, FeatureRequest.vote_count > 0)
            .values(vote_count=FeatureRequest.vote_count - 1)
        )

    db.commit()
    return _current_state(db, request_id, user_id)


def voted_request_ids(db: Session, user_id: int, request_ids: list[int]) -> set[int]:
    """Which of these requests has the user voted on?

    One query for a whole page of results, so the browse list can render button state
    without an N+1 query per card.
    """
    if not request_ids:
        return set()
    rows = db.execute(
        select(Vote.feature_request_id).where(
            Vote.user_id == user_id, Vote.feature_request_id.in_(request_ids)
        )
    ).scalars()
    return set(rows)
