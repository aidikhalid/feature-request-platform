"""Authentication: identity, and the failure paths that matter."""

from tests.conftest import sign_in


def test_register_signs_the_user_in_and_never_returns_the_password(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "new@example.com", "display_name": "New User", "password": "Password123!"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new@example.com"
    assert "password" not in body and "password_hash" not in body
    # Registration establishes the session, so the client is immediately usable.
    assert client.get("/api/auth/me").status_code == 200


def test_registration_always_creates_a_standard_user(client):
    """Role is server-assigned. A caller cannot promote themselves by sending role=admin."""
    response = client.post(
        "/api/auth/register",
        json={
            "email": "sneaky@example.com",
            "display_name": "Sneaky",
            "password": "Password123!",
            "role": "admin",
        },
    )
    assert response.status_code == 201
    assert response.json()["role"] == "user"


def test_duplicate_email_is_rejected(client, user):
    response = client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "display_name": "Impostor", "password": "Password123!"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_taken"


def test_wrong_password_is_rejected_without_revealing_whether_the_account_exists(client, user):
    known = client.post(
        "/api/auth/login", json={"email": "alice@example.com", "password": "wrong-password"}
    )
    unknown = client.post(
        "/api/auth/login", json={"email": "nobody@example.com", "password": "wrong-password"}
    )
    assert known.status_code == unknown.status_code == 401
    # Identical messages, so login cannot be used to enumerate registered addresses.
    assert known.json()["error"]["message"] == unknown.json()["error"]["message"]


def test_me_requires_a_session(client):
    assert client.get("/api/auth/me").status_code == 401


def test_logout_clears_the_session(client, user):
    sign_in(client, "alice@example.com")
    assert client.get("/api/auth/me").status_code == 200
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401


def test_a_tampered_cookie_is_not_trusted(client, user):
    sign_in(client, "alice@example.com")
    client.cookies.set("frp_session", "not.a.real.token")
    assert client.get("/api/auth/me").status_code == 401
