from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import UserRole


class RegisterIn(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=2, max_length=80)
    # Length is the one password rule we enforce; complexity rules push users toward
    # predictable substitutions without much real gain.
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    display_name: str
    role: UserRole
    created_at: datetime


class AuthorOut(BaseModel):
    """Deliberately excludes email — author identity is public, contact details are not."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str
