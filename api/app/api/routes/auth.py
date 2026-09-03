from fastapi import APIRouter, Response, status
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.core.deps import CurrentUser, DbSession
from app.core.security import create_access_token, hash_password, verify_password
from app.errors import Conflict, Unauthorized
from app.models import User, UserRole
from app.schemas import LoginIn, RegisterIn, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_session_cookie(response: Response, user_id: int) -> None:
    """Session travels in an httpOnly cookie.

    httponly    -> JavaScript cannot read it, so an XSS bug cannot exfiltrate the session.
    samesite    -> 'lax' stops other sites from driving state-changing requests as the user.
    secure      -> on over HTTPS; off locally so plain-http development still works.
    """
    response.set_cookie(
        key=settings.cookie_name,
        value=create_access_token(user_id),
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.jwt_expire_minutes * 60,
        path="/",
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterIn, response: Response, db: DbSession) -> User:
    user = User(
        email=payload.email.lower(),
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
        role=UserRole.USER,  # Never client-supplied: the API decides who is an admin.
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # The unique index on users.email is the authority, not a prior SELECT — two
        # simultaneous registrations for the same address cannot both succeed.
        db.rollback()
        raise Conflict("An account with that email already exists", code="email_taken")

    db.refresh(user)
    _set_session_cookie(response, user.id)
    return user


@router.post("/login", response_model=UserOut)
def login(payload: LoginIn, response: Response, db: DbSession) -> User:
    user = db.query(User).filter(User.email == payload.email.lower()).one_or_none()
    # One generic message for both "no such account" and "wrong password", so the endpoint
    # cannot be used to enumerate which email addresses are registered.
    if user is None or not verify_password(payload.password, user.password_hash):
        raise Unauthorized("Incorrect email or password")

    _set_session_cookie(response, user.id)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    response.delete_cookie(settings.cookie_name, path="/")


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user
