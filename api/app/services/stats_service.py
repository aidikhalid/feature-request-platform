"""A small, useful set of usage statistics — five aggregate queries, no dashboard."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Comment, FeatureRequest, RequestStatus, Vote
from app.schemas import StatsOut, TopRequest


def get_stats(db: Session) -> StatsOut:
    active = FeatureRequest.merged_into_id.is_(None)
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)

    total_requests = db.execute(
        select(func.count()).select_from(FeatureRequest).where(active)
    ).scalar_one()
    total_votes = db.execute(select(func.count()).select_from(Vote)).scalar_one()
    total_comments = db.execute(select(func.count()).select_from(Comment)).scalar_one()
    recent = db.execute(
        select(func.count())
        .select_from(FeatureRequest)
        .where(active, FeatureRequest.created_at >= week_ago)
    ).scalar_one()

    grouped = db.execute(
        select(FeatureRequest.status, func.count())
        .where(active)
        .group_by(FeatureRequest.status)
    ).all()
    # Report every status, including the ones with no requests, so the UI has a stable shape.
    by_status = {status: 0 for status in RequestStatus}
    by_status.update({status: count for status, count in grouped})

    top = db.execute(
        select(FeatureRequest.id, FeatureRequest.title, FeatureRequest.vote_count)
        .where(active)
        .order_by(FeatureRequest.vote_count.desc(), FeatureRequest.id.desc())
        .limit(5)
    ).all()

    return StatsOut(
        total_requests=total_requests,
        total_votes=total_votes,
        total_comments=total_comments,
        requests_last_7_days=recent,
        by_status=by_status,
        top_requests=[TopRequest(id=r.id, title=r.title, vote_count=r.vote_count) for r in top],
    )
