from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import AuthorOut


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    body: str
    created_at: datetime
    author: AuthorOut
