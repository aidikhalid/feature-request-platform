from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RequestStatus
from app.schemas.user import AuthorOut

T = TypeVar("T")


class FeatureRequestCreate(BaseModel):
    title: str = Field(min_length=5, max_length=200)
    description: str = Field(min_length=10, max_length=5000)


class FeatureRequestUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=5, max_length=200)
    description: str | None = Field(default=None, min_length=10, max_length=5000)


class StatusUpdateIn(BaseModel):
    status: RequestStatus


class OfficialResponseIn(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class MergeIn(BaseModel):
    target_id: int


class FeatureRequestSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    status: RequestStatus
    vote_count: int
    comment_count: int
    created_at: datetime
    author: AuthorOut
    merged_into_id: int | None = None
    # Whether the *calling* user has voted. Computed per request so the browse page can
    # render the correct button state without a second round trip.
    has_voted: bool = False


class FeatureRequestDetail(FeatureRequestSummary):
    description: str
    official_response: str | None = None
    official_response_at: datetime | None = None
    official_response_by: AuthorOut | None = None
    updated_at: datetime


class VoteState(BaseModel):
    """Returned by both vote and unvote so the client always gets the settled truth."""

    feature_request_id: int
    vote_count: int
    has_voted: bool


class Page(BaseModel, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total: int
    total_pages: int
