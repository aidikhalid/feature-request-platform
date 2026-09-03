"""Business rules: only admins change status; nobody edits someone else's request.

These assert on the API, not on the UI. Hiding a button is presentation; a 403 is
authorization.
"""

from tests.conftest import make_request, sign_in


def test_standard_user_cannot_change_status(client, user, feature_request):
    sign_in(client, "alice@example.com")
    response = client.patch(
        f"/api/admin/requests/{feature_request.id}/status", json={"status": "planned"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_anonymous_visitor_cannot_change_status(client, feature_request):
    response = client.patch(
        f"/api/admin/requests/{feature_request.id}/status", json={"status": "planned"}
    )
    assert response.status_code == 401


def test_admin_can_change_status(client, admin, feature_request):
    sign_in(client, "admin@example.com")
    response = client.patch(
        f"/api/admin/requests/{feature_request.id}/status", json={"status": "in_progress"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"


def test_status_must_be_one_of_the_supported_values(client, admin, feature_request):
    sign_in(client, "admin@example.com")
    response = client.patch(
        f"/api/admin/requests/{feature_request.id}/status", json={"status": "shipped_maybe"}
    )
    assert response.status_code == 422


def test_user_cannot_edit_another_users_request(client, db, user, other_user):
    someone_elses = make_request(db, other_user, title="Bob's own request")
    sign_in(client, "alice@example.com")
    response = client.patch(f"/api/requests/{someone_elses.id}", json={"title": "Hijacked title"})
    assert response.status_code == 403


def test_user_can_edit_their_own_request(client, user, feature_request):
    sign_in(client, "alice@example.com")
    response = client.patch(
        f"/api/requests/{feature_request.id}", json={"title": "A clearer title for my request"}
    )
    assert response.status_code == 200
    assert response.json()["title"] == "A clearer title for my request"


def test_admin_may_edit_any_request(client, db, admin, user, feature_request):
    sign_in(client, "admin@example.com")
    response = client.patch(
        f"/api/requests/{feature_request.id}", json={"title": "Tidied up by a moderator"}
    )
    assert response.status_code == 200


def test_unknown_request_is_404_before_any_permission_check(client, user):
    """404 before 403 — the endpoint must not become an oracle for which ids exist."""
    sign_in(client, "alice@example.com")
    assert client.patch("/api/requests/999999", json={"title": "Does not exist"}).status_code == 404


def test_stats_are_admin_only(client, user):
    sign_in(client, "alice@example.com")
    assert client.get("/api/admin/stats").status_code == 403
