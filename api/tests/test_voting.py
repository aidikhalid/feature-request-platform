"""Business rules: one vote per user, and repeated API calls must not duplicate votes."""

from sqlalchemy import func, select

from app.models import FeatureRequest, Vote
from tests.conftest import sign_in


def _count_votes(db, request_id: int) -> int:
    return db.execute(
        select(func.count()).select_from(Vote).where(Vote.feature_request_id == request_id)
    ).scalar_one()


def test_voting_records_one_vote_and_increments_the_counter(client, db, user, feature_request):
    sign_in(client, "alice@example.com")
    response = client.post(f"/api/requests/{feature_request.id}/vote")

    assert response.status_code == 200
    assert response.json() == {
        "feature_request_id": feature_request.id,
        "vote_count": 1,
        "has_voted": True,
    }
    assert _count_votes(db, feature_request.id) == 1


def test_voting_twice_is_a_no_op(client, db, user, feature_request):
    """A retried request, a double-click, or an impatient user must not add a second vote."""
    sign_in(client, "alice@example.com")

    for _ in range(5):
        response = client.post(f"/api/requests/{feature_request.id}/vote")
        assert response.status_code == 200
        assert response.json()["vote_count"] == 1

    assert _count_votes(db, feature_request.id) == 1


def test_unvoting_removes_the_vote_and_is_also_idempotent(client, db, user, feature_request):
    sign_in(client, "alice@example.com")
    client.post(f"/api/requests/{feature_request.id}/vote")

    first = client.delete(f"/api/requests/{feature_request.id}/vote")
    second = client.delete(f"/api/requests/{feature_request.id}/vote")

    assert first.json()["vote_count"] == 0 and first.json()["has_voted"] is False
    assert second.status_code == 200
    assert second.json()["vote_count"] == 0  # never negative
    assert _count_votes(db, feature_request.id) == 0


def test_vote_then_unvote_leaves_the_counter_consistent_with_the_rows(
    client, db, user, feature_request
):
    sign_in(client, "alice@example.com")
    for _ in range(3):
        client.post(f"/api/requests/{feature_request.id}/vote")
        client.delete(f"/api/requests/{feature_request.id}/vote")
    client.post(f"/api/requests/{feature_request.id}/vote")

    stored = db.execute(
        select(FeatureRequest.vote_count).where(FeatureRequest.id == feature_request.id)
    ).scalar_one()
    assert stored == _count_votes(db, feature_request.id) == 1


def test_different_users_each_get_a_vote(client, db, user, other_user, feature_request):
    sign_in(client, "alice@example.com")
    client.post(f"/api/requests/{feature_request.id}/vote")
    sign_in(client, "bob@example.com")
    response = client.post(f"/api/requests/{feature_request.id}/vote")

    assert response.json()["vote_count"] == 2
    assert _count_votes(db, feature_request.id) == 2


def test_voting_requires_authentication(client, feature_request):
    assert client.post(f"/api/requests/{feature_request.id}/vote").status_code == 401


def test_voting_on_an_unknown_request_is_404(client, user):
    sign_in(client, "alice@example.com")
    assert client.post("/api/requests/999999/vote").status_code == 404


def test_has_voted_is_reported_per_caller(client, db, user, other_user, feature_request):
    sign_in(client, "alice@example.com")
    client.post(f"/api/requests/{feature_request.id}/vote")

    assert client.get(f"/api/requests/{feature_request.id}").json()["has_voted"] is True

    sign_in(client, "bob@example.com")
    assert client.get(f"/api/requests/{feature_request.id}").json()["has_voted"] is False

    client.post("/api/auth/logout")
    assert client.get(f"/api/requests/{feature_request.id}").json()["has_voted"] is False
