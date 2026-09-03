"""Test harness.

Tests run against a real PostgreSQL database, not SQLite. That is deliberate: the rules
under test are enforced by Postgres itself (a unique index, row-level locks, atomic
UPDATE arithmetic), so testing on a different engine would prove nothing about the
behaviour that actually ships.

The test database is created alongside the development one and migrated with Alembic —
the same migrations a deployment runs, so the schema under test is the real schema.
"""

import os

# Point the application at a dedicated test database BEFORE importing anything that
# reads configuration or builds the engine.
_DEV_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg2://frp:frp_local_password@localhost:5432/frp"
)
_TEST_URL = f"{_DEV_URL}_test"
os.environ["DATABASE_URL"] = _TEST_URL

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import FeatureRequest, User, UserRole  # noqa: E402

API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TABLES = ("votes", "comments", "feature_requests", "users")


@pytest.fixture(scope="session", autouse=True)
def _database():
    """Create the test database once, then migrate it with Alembic."""
    admin_engine = create_engine(_DEV_URL, isolation_level="AUTOCOMMIT")
    db_name = _TEST_URL.rsplit("/", 1)[1]
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": db_name}
        ).first()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    admin_engine.dispose()

    cfg = Config(os.path.join(API_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(API_DIR, "alembic"))
    command.upgrade(cfg, "head")
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def _clean_tables():
    """Truncate between tests.

    Services commit their own transactions (that is the point — we are testing real
    transaction boundaries), so the usual "wrap each test in a rollback" trick would not
    isolate them. Truncating is slower but honest.
    """
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    return TestClient(app)


def make_user(db, email: str, *, admin: bool = False, password: str = "Password123!") -> User:
    user = User(
        email=email,
        display_name=email.split("@")[0].title(),
        password_hash=hash_password(password),
        role=UserRole.ADMIN if admin else UserRole.USER,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_request(db, author: User, title: str = "A perfectly reasonable request") -> FeatureRequest:
    request = FeatureRequest(
        title=title, description="Description long enough to pass validation.", author_id=author.id
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


def sign_in(client: TestClient, email: str, password: str = "Password123!") -> TestClient:
    """Log in, leaving the session cookie on the client's cookie jar."""
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return client


@pytest.fixture
def user(db) -> User:
    return make_user(db, "alice@example.com")


@pytest.fixture
def other_user(db) -> User:
    return make_user(db, "bob@example.com")


@pytest.fixture
def admin(db) -> User:
    return make_user(db, "admin@example.com", admin=True)


@pytest.fixture
def feature_request(db, user) -> FeatureRequest:
    return make_request(db, user)
