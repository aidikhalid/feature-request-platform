from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from app.config import settings

# pool_pre_ping avoids handing out connections the database has already dropped
# (common after a container restart in local development).
engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """Request-scoped session.

    One HTTP request maps to one session and therefore one transaction boundary:
    handlers commit explicitly on success, and anything unhandled rolls the whole
    request back rather than leaving a half-applied write.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
