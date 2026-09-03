"""A vote or comment landing at the moment a merge commits.

Both writes check "is this request merged?" and then insert. Without a lock held across
that gap, a merge can commit in between and the new row is stranded on a request that is
now retired: invisible on the board, and impossible for the user to withdraw because a
merged request rejects writes.

The fix is that voting and commenting take the same row lock the merge takes, so one of
the two waits for the other.
"""

from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import func, select

from app.db import SessionLocal
from app.errors import AppError
from app.models import Comment, FeatureRequest, Vote
from app.services import merge_service, vote_service
from app.services.request_service import add_comment
from tests.conftest import make_request, make_user

ATTEMPTS = 15


def _in_own_session(work):
    """Run one unit of work in its own session, swallowing the expected 409."""
    session = SessionLocal()
    try:
        work(session)
    except AppError:
        # "This request was merged" is a correct outcome — the write simply lost the race.
        session.rollback()
    finally:
        session.close()


def _orphans(db) -> tuple[int, int]:
    """Votes and comments that point at a request which has been merged away."""
    merged = select(FeatureRequest.id).where(FeatureRequest.merged_into_id.is_not(None))
    votes = db.execute(
        select(func.count()).select_from(Vote).where(Vote.feature_request_id.in_(merged))
    ).scalar_one()
    comments = db.execute(
        select(func.count()).select_from(Comment).where(Comment.feature_request_id.in_(merged))
    ).scalar_one()
    return votes, comments


def test_a_vote_cannot_be_stranded_on_a_request_being_merged(db, user):
    """Either the vote lands on the survivor, or it is refused. Never stranded."""
    for _ in range(ATTEMPTS):
        source = make_request(db, user, title="Duplicate under merge")
        target = make_request(db, user, title="Surviving request")
        voter = make_user(db, f"racer{source.id}@example.com")

        with ThreadPoolExecutor(max_workers=2) as pool:
            pool.submit(_in_own_session, lambda s: vote_service.add_vote(s, voter.id, source.id))
            pool.submit(_in_own_session, lambda s: merge_service.merge_requests(s, source.id, target.id))

        db.expire_all()
        stranded_votes, _ = _orphans(db)
        assert stranded_votes == 0, (
            "a vote is sitting on a merged request: it is hidden from the board and the "
            "user cannot withdraw it"
        )


def test_a_comment_cannot_be_stranded_on_a_request_being_merged(db, user):
    for _ in range(ATTEMPTS):
        source = make_request(db, user, title="Duplicate under merge")
        target = make_request(db, user, title="Surviving request")
        author = make_user(db, f"commenter{source.id}@example.com")

        with ThreadPoolExecutor(max_workers=2) as pool:
            pool.submit(_in_own_session, lambda s: add_comment(s, source.id, author, "Racing comment"))
            pool.submit(_in_own_session, lambda s: merge_service.merge_requests(s, source.id, target.id))

        db.expire_all()
        _, stranded_comments = _orphans(db)
        assert stranded_comments == 0, "a comment is sitting on a merged request"


def test_counters_stay_consistent_with_the_rows_after_a_raced_merge(db, user):
    """Whatever the interleaving, the survivor's counters must match its actual rows."""
    for _ in range(ATTEMPTS):
        source = make_request(db, user, title="Duplicate under merge")
        target = make_request(db, user, title="Surviving request")
        voter = make_user(db, f"counter{source.id}@example.com")

        with ThreadPoolExecutor(max_workers=2) as pool:
            pool.submit(_in_own_session, lambda s: vote_service.add_vote(s, voter.id, source.id))
            pool.submit(_in_own_session, lambda s: merge_service.merge_requests(s, source.id, target.id))

        db.expire_all()
        survivor = db.get(FeatureRequest, target.id)
        actual = db.execute(
            select(func.count()).select_from(Vote).where(Vote.feature_request_id == target.id)
        ).scalar_one()
        assert survivor.vote_count == actual
