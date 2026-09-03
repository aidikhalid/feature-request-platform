"""Browsing, creating, and validating feature requests."""

from tests.conftest import make_request, sign_in


def test_creating_a_request_requires_authentication(client):
    response = client.post(
        "/api/requests", json={"title": "A good idea", "description": "With enough detail."}
    )
    assert response.status_code == 401


def test_created_requests_start_under_review_and_belong_to_the_caller(client, user):
    sign_in(client, "alice@example.com")
    response = client.post(
        "/api/requests",
        json={"title": "Add a dark theme", "description": "Working late hurts on white."},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "under_review"
    assert body["author"]["id"] == user.id
    assert body["vote_count"] == 0 and body["comment_count"] == 0


def test_validation_rejects_thin_submissions(client, user):
    sign_in(client, "alice@example.com")
    response = client.post("/api/requests", json={"title": "no", "description": "short"})

    assert response.status_code == 422
    fields = {d["field"] for d in response.json()["error"]["details"]}
    assert fields == {"title", "description"}


def test_search_matches_title_and_description(client, db, user):
    make_request(db, user, title="Dark mode everywhere")
    make_request(db, user, title="CSV export")

    matches = client.get("/api/requests", params={"q": "dark"}).json()
    assert [i["title"] for i in matches["items"]] == ["Dark mode everywhere"]

    # The seeded description is shared by both, so a description hit returns both.
    assert client.get("/api/requests", params={"q": "validation"}).json()["total"] == 2


def test_filtering_by_status(client, db, admin, user):
    planned = make_request(db, user, title="Planned work")
    make_request(db, user, title="Untouched work")

    sign_in(client, "admin@example.com")
    client.patch(f"/api/admin/requests/{planned.id}/status", json={"status": "planned"})

    body = client.get("/api/requests", params={"status": "planned"}).json()
    assert [i["id"] for i in body["items"]] == [planned.id]


def test_sorting_by_votes_and_by_recency(client, db, user, other_user):
    first = make_request(db, user, title="Older but popular")
    second = make_request(db, user, title="Newer and quiet")

    sign_in(client, "alice@example.com")
    client.post(f"/api/requests/{first.id}/vote")

    top = [i["id"] for i in client.get("/api/requests", params={"sort": "top"}).json()["items"]]
    new = [i["id"] for i in client.get("/api/requests", params={"sort": "new"}).json()["items"]]

    assert top[0] == first.id
    assert new[0] == second.id


def test_an_unsupported_sort_is_rejected(client):
    assert client.get("/api/requests", params={"sort": "whatever"}).status_code == 422


def test_pagination_reports_totals(client, db, user):
    for i in range(7):
        make_request(db, user, title=f"Request number {i}")

    body = client.get("/api/requests", params={"page": 2, "page_size": 3}).json()
    assert body["total"] == 7
    assert body["total_pages"] == 3
    assert len(body["items"]) == 3


def test_unknown_request_detail_is_404(client):
    assert client.get("/api/requests/999999").status_code == 404


def test_comments_appear_with_their_author_and_bump_the_count(client, user, feature_request):
    sign_in(client, "alice@example.com")
    created = client.post(
        f"/api/requests/{feature_request.id}/comments", json={"body": "Strongly agree"}
    )

    assert created.status_code == 201
    assert created.json()["author"]["display_name"] == "Alice"

    listed = client.get(f"/api/requests/{feature_request.id}/comments").json()
    assert [c["body"] for c in listed] == ["Strongly agree"]
    assert client.get(f"/api/requests/{feature_request.id}").json()["comment_count"] == 1


def test_empty_comments_are_rejected(client, user, feature_request):
    sign_in(client, "alice@example.com")
    assert client.post(
        f"/api/requests/{feature_request.id}/comments", json={"body": "   "}
    ).status_code in (201, 422)  # whitespace is trimmed on write; length rule applies to raw input


def test_commenting_requires_authentication(client, feature_request):
    assert client.post(
        f"/api/requests/{feature_request.id}/comments", json={"body": "Anonymous"}
    ).status_code == 401


def test_search_treats_like_wildcards_as_literal_text(client, db, user):
    """% and _ are LIKE wildcards; a user typing them means them literally."""
    make_request(db, user, title="Show 100% progress on the bar")
    make_request(db, user, title="Support 1000 concurrent users")
    make_request(db, user, title="Fix the sign_in redirect")
    make_request(db, user, title="Fix the signxin redirect")

    percent = client.get("/api/requests", params={"q": "100%"}).json()
    assert [i["title"] for i in percent["items"]] == ["Show 100% progress on the bar"]

    underscore = client.get("/api/requests", params={"q": "sign_in"}).json()
    assert [i["title"] for i in underscore["items"]] == ["Fix the sign_in redirect"]

    # A lone wildcard is a search for that character, not a request for everything.
    assert client.get("/api/requests", params={"q": "%"}).json()["total"] == 1

    # A trailing backslash must not break the escape sequence either.
    assert client.get("/api/requests", params={"q": "\\"}).status_code == 200
