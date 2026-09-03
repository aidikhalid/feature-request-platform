"""The admin statistics endpoint."""

from tests.conftest import make_request, sign_in


def test_stats_summarise_the_board(client, db, admin, user, other_user):
    first = make_request(db, user, title="First idea")
    second = make_request(db, user, title="Second idea")

    sign_in(client, "alice@example.com")
    client.post(f"/api/requests/{first.id}/vote")
    client.post(f"/api/requests/{first.id}/comments", json={"body": "Agreed"})
    sign_in(client, "bob@example.com")
    client.post(f"/api/requests/{first.id}/vote")

    sign_in(client, "admin@example.com")
    client.patch(f"/api/admin/requests/{second.id}/status", json={"status": "released"})

    body = client.get("/api/admin/stats").json()

    assert body["total_requests"] == 2
    assert body["total_votes"] == 2
    assert body["total_comments"] == 1
    assert body["requests_last_7_days"] == 2
    assert body["by_status"]["released"] == 1
    assert body["by_status"]["under_review"] == 1
    # Every status is reported, including the empty ones, so the UI has a stable shape.
    assert set(body["by_status"]) == {
        "under_review", "planned", "in_progress", "released", "declined"
    }
    assert body["top_requests"][0]["id"] == first.id


def test_merged_requests_are_excluded_from_the_totals(client, db, admin, user):
    duplicate = make_request(db, user, title="Duplicate")
    survivor = make_request(db, user, title="Survivor")

    sign_in(client, "admin@example.com")
    assert client.get("/api/admin/stats").json()["total_requests"] == 2

    client.post(f"/api/admin/requests/{duplicate.id}/merge", json={"target_id": survivor.id})
    assert client.get("/api/admin/stats").json()["total_requests"] == 1
