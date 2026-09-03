from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Vote(Base):
    __tablename__ = "votes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    feature_request_id: Mapped[int] = mapped_column(
        ForeignKey("feature_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user = relationship("User", back_populates="votes")
    request = relationship("FeatureRequest", back_populates="votes")

    __table_args__ = (
        # THE rule: one vote per user per request, enforced by the database.
        # An application-level "has this user voted?" check cannot be trusted, because two
        # concurrent requests can both read "no" before either of them writes.
        UniqueConstraint("user_id", "feature_request_id", name="uq_votes_user_request"),
    )
