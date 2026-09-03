"""Business rule: merging must preserve votes and comments.

The subtle part is a user who voted on *both* requests. Their vote must survive, but it
must count once — the merged request represents one idea, and they are one person.
"""

from sqlalchemy import func, select

from app.models import Comment, FeatureRequest, Vote
from tests.conftest import make_request, make_user, sign_in


def _comment(client, request_id: int, body: str) -> None:
    assert client.post(f"/api/requests/{request_id}/comments", json={"body": body}).status_code == 201


def test_merge_moves_votes_and_comments_to_the_survivor(client, db, admin, user, other_user):
    duplicate = make_request(db, user, title="Add a dark theme please")
    survivor = make_request(db, user, title="Dark mode")

    sign_in(client, "alice@example.com")
    client.post(f"/api/requests/{duplicate.id}/vote")
    _comment(client, duplicate.id, "Yes please, my eyes hurt")
    sign_in(client, "bob@example.com")
    client.post(f"/api/requests/{survivor.id}/vote")
    _comment(client, survivor.id, "Would use this daily")

    sign_in(client, "admin@example.com")
    response = client.post(f"/api/admin/requests/{duplicate.id}/merge", json={"target_id": survivor.id})

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == survivor.id
    assert body["vote_count"] == 2
    assert body["comment_count"] == 2

    # Nothing was deleted — the rows moved.
    assert db.execute(
        select(func.count()).select_from(Vote).where(Vote.feature_request_id == survivor.id)
    ).scalar_one() == 2
    assert db.execute(
        select(func.count()).select_from(Comment).where(Comment.feature_request_id == survivor.id)
    ).scalar_one() == 2
    assert db.execute(
        select(func.count()).select_from(Vote).where(Vote.feature_request_id == duplicate.id)
    ).scalar_one() == 0


def test_a_user_who_voted_on_both_is_counted_once(client, db, admin, user, other_user):
    """Naively adding the two counters would report three votes from two people."""
    duplicate = make_request(db, user, title="Export to CSV")
    survivor = make_request(db, user, title="CSV export")

    sign_in(client, "alice@example.com")
    client.post(f"/api/requests/{duplicate.id}/vote")
    client.post(f"/api/requests/{survivor.id}/vote")  # the overlap
    sign_in(client, "bob@example.com")
    client.post(f"/api/requests/{duplicate.id}/vote")

    sign_in(client, "admin@example.com")
    response = client.post(f"/api/admin/requests/{duplicate.id}/merge", json={"target_id": survivor.id})

    assert response.json()["vote_count"] == 2, "alice must not be counted twice"

    voter_ids = set(
        db.execute(select(Vote.user_id).where(Vote.feature_request_id == survivor.id)).scalars()
    )
    assert voter_ids == {user.id, other_user.id}
    # And the constraint still holds: no user has two votes on the survivor.
    assert db.execute(
        select(func.count()).select_from(Vote).where(Vote.feature_request_id == survivor.id)
    ).scalar_one() == 2


def test_merged_request_becomes_read_only_and_points_at_the_survivor(client, db, admin, user):
    duplicate = make_request(db, user)
    survivor = make_request(db, user, title="The surviving request")

    sign_in(client, "admin@example.com")
    client.post(f"/api/admin/requests/{duplicate.id}/merge", json={"target_id": survivor.id})

    detail = client.get(f"/api/requests/{duplicate.id}").json()
    assert detail["merged_into_id"] == survivor.id

    sign_in(client, "alice@example.com")
    assert client.post(f"/api/requests/{duplicate.id}/vote").status_code == 409
    assert client.post(
        f"/api/requests/{duplicate.id}/comments", json={"body": "still here?"}
    ).status_code == 409
    assert client.patch(f"/api/requests/{duplicate.id}", json={"title": "Edited after merge"}).status_code == 409


def test_merged_request_is_hidden_from_the_board(client, db, admin, user):
    duplicate = make_request(db, user, title="Duplicate idea")
    survivor = make_request(db, user, title="Original idea")

    sign_in(client, "admin@example.com")
    client.post(f"/api/admin/requests/{duplicate.id}/merge", json={"target_id": survivor.id})

    listed = {item["id"] for item in client.get("/api/requests").json()["items"]}
    assert duplicate.id not in listed
    assert survivor.id in listed


def test_a_request_cannot_be_merged_into_itself(client, db, admin, feature_request):
    sign_in(client, "admin@example.com")
    response = client.post(
        f"/api/admin/requests/{feature_request.id}/merge", json={"target_id": feature_request.id}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_merge"


def test_an_already_merged_request_cannot_be_merged_again(client, db, admin, user):
    """Keeps merged_into_id a one-level pointer, so it can never form a cycle or a chain."""
    first = make_request(db, user, title="First idea")
    second = make_request(db, user, title="Second idea")
    third = make_request(db, user, title="Third idea")

    sign_in(client, "admin@example.com")
    client.post(f"/api/admin/requests/{first.id}/merge", json={"target_id": second.id})

    as_source = client.post(f"/api/admin/requests/{first.id}/merge", json={"target_id": third.id})
    as_target = client.post(f"/api/admin/requests/{third.id}/merge", json={"target_id": first.id})

    assert as_source.status_code == 409
    assert as_target.status_code == 409


def test_merging_an_unknown_request_is_404_and_changes_nothing(client, db, admin, feature_request):
    sign_in(client, "admin@example.com")
    response = client.post(
        f"/api/admin/requests/{feature_request.id}/merge", json={"target_id": 999999}
    )
    assert response.status_code == 404
    db.expire_all()
    assert db.get(FeatureRequest, feature_request.id).merged_into_id is None


def test_only_admins_may_merge(client, db, user, other_user):
    duplicate = make_request(db, user)
    survivor = make_request(db, user, title="The survivor")
    sign_in(client, "alice@example.com")
    assert client.post(
        f"/api/admin/requests/{duplicate.id}/merge", json={"target_id": survivor.id}
    ).status_code == 403
