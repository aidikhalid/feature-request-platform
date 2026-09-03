from pydantic import BaseModel

from app.models.enums import RequestStatus


class TopRequest(BaseModel):
    id: int
    title: str
    vote_count: int


class StatsOut(BaseModel):
    total_requests: int
    total_votes: int
    total_comments: int
    requests_last_7_days: int
    by_status: dict[RequestStatus, int]
    top_requests: list[TopRequest]
