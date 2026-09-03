from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import RequestStatus


class FeatureRequest(Base):
    __tablename__ = "feature_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus, name="request_status", values_callable=lambda e: [m.value for m in e]),
        default=RequestStatus.UNDER_REVIEW,
        nullable=False,
        index=True,
    )
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

    # Official response — written by an admin, shown prominently on the detail page.
    official_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    official_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    official_response_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # When set, this request was merged into another one and is now read-only.
    merged_into_id: Mapped[int | None] = mapped_column(
        ForeignKey("feature_requests.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Denormalised counters. Maintained inside the same transaction as the write that
    # changes them (see services/vote_service.py). Trade-off documented in ARCHITECTURE.md:
    # this keeps the list endpoint to a single query instead of N COUNT subqueries.
    vote_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    comment_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    author = relationship("User", back_populates="requests", foreign_keys=[author_id])
    official_response_by = relationship("User", foreign_keys=[official_response_by_id])
    merged_into = relationship("FeatureRequest", remote_side=[id], backref="merged_duplicates")
    votes = relationship("Vote", back_populates="request", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="request", cascade="all, delete-orphan")

    __table_args__ = (
        # Sorting the browse page by popularity and recency are the two hot paths.
        Index("ix_feature_requests_vote_count", vote_count.desc()),
        Index("ix_feature_requests_created_at", created_at.desc()),
    )

    @property
    def is_merged(self) -> bool:
        return self.merged_into_id is not None
