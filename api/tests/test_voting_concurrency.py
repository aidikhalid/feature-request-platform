"""Business rule: concurrent votes must not produce incorrect totals.

These tests use real threads and real separate database connections, because the
protection being tested lives in Postgres — a unique index and row-level locking. Run
against SQLite this test would pass for the wrong reason (SQLite serialises all writers),
which is a large part of why the project uses Postgres everywhere including in tests.
"""

from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import FeatureRequest, Vote
from app.services import vote_service
from tests.conftest import make_user


def _vote_in_its_own_session(user_id: int, request_id: int) -> None:
    """Each thread gets its own session, so these are genuinely concurrent transactions."""
    session = SessionLocal()
    try:
        vote_service.add_vote(session, user_id, request_id)
    finally:
        session.close()


def test_one_user_voting_concurrently_produces_exactly_one_vote(db, user, feature_request):
    """The unique constraint is what makes this safe.

    Twenty transactions all check "has this user voted?" at the same time and all see
    "no". Only the database can break that tie, and ON CONFLICT DO NOTHING lets it.
    """
    with ThreadPoolExecutor(max_workers=20) as pool:
        list(pool.map(lambda _: _vote_in_its_own_session(user.id, feature_request.id), range(20)))

    rows = db.execute(
        select(func.count()).select_from(Vote).where(Vote.feature_request_id == feature_request.id)
    ).scalar_one()
    counter = db.execute(
        select(FeatureRequest.vote_count).where(FeatureRequest.id == feature_request.id)
    ).scalar_one()

    assert rows == 1
    assert counter == 1, "the counter must not drift above the number of vote rows"


def test_many_users_voting_concurrently_produce_an_exact_total(db, user, feature_request):
    """The atomic increment is what makes this safe.

    `vote_count = vote_count + 1` is evaluated by Postgres under a row lock. Had we read
    the value into Python, added one, and written it back, concurrent writers would
    overwrite each other and the total would come out low.
    """
    voters = [make_user(db, f"voter{i}@example.com").id for i in range(25)]

    with ThreadPoolExecutor(max_workers=25) as pool:
        list(pool.map(lambda uid: _vote_in_its_own_session(uid, feature_request.id), voters))

    rows = db.execute(
        select(func.count()).select_from(Vote).where(Vote.feature_request_id == feature_request.id)
    ).scalar_one()
    counter = db.execute(
        select(FeatureRequest.vote_count).where(FeatureRequest.id == feature_request.id)
    ).scalar_one()

    assert rows == 25
    assert counter == 25, "a lost update would show up here as a total below 25"
