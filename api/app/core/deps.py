from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import decode_access_token
from app.db import get_db
from app.errors import Forbidden, Unauthorized
from app.models import User

DbSession = Annotated[Session, Depends(get_db)]


def get_optional_user(request: Request, db: DbSession) -> User | None:
    """Resolve the caller if a valid session cookie is present, otherwise None.

    Used by public read endpoints so they can report `has_voted` for a signed-in
    visitor without forcing authentication on anonymous browsing.
    """
    token = request.cookies.get(settings.cookie_name)
    if not token:
        return None
    user_id = decode_access_token(token)
    if user_id is None:
        return None
    return db.get(User, user_id)


def get_current_user(user: Annotated[User | None, Depends(get_optional_user)]) -> User:
    """Require a signed-in user. 401 means 'we do not know who you are'."""
    if user is None:
        raise Unauthorized()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]


def require_admin(user: CurrentUser) -> User:
    """Require an administrator. 403 means 'we know who you are, and no'.

    Declared once here and attached to admin routes as a dependency, so the rule
    lives in a single place instead of being re-checked in each handler.
    """
    if not user.is_admin:
        raise Forbidden("Administrator role required")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
