"""Initial schema: users, feature_requests, votes, comments.

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# create_type=False keeps the type creation explicit and in one place below; without it
# SQLAlchemy would also emit CREATE TYPE from the first create_table that references it,
# and the second CREATE would fail.
user_role = postgresql.ENUM("user", "admin", name="user_role", create_type=False)
request_status = postgresql.ENUM(
    "under_review", "planned", "in_progress", "released", "declined",
    name="request_status", create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    user_role.create(bind, checkfirst=True)
    request_status.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(80), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False, server_default="user"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "feature_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", request_status, nullable=False, server_default="under_review"),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("official_response", sa.Text(), nullable=True),
        sa.Column("official_response_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "official_response_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "merged_into_id", sa.Integer(), sa.ForeignKey("feature_requests.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("vote_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("comment_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_feature_requests_status", "feature_requests", ["status"])
    op.create_index("ix_feature_requests_merged_into_id", "feature_requests", ["merged_into_id"])
    op.create_index("ix_feature_requests_vote_count", "feature_requests", [sa.text("vote_count DESC")])
    op.create_index("ix_feature_requests_created_at", "feature_requests", [sa.text("created_at DESC")])

    op.create_table(
        "votes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "feature_request_id",
            sa.Integer(),
            sa.ForeignKey("feature_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # One vote per user per request, enforced by the database rather than by
        # application logic, so concurrent requests cannot both slip through.
        sa.UniqueConstraint("user_id", "feature_request_id", name="uq_votes_user_request"),
    )
    op.create_index("ix_votes_feature_request_id", "votes", ["feature_request_id"])

    op.create_table(
        "comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "feature_request_id",
            sa.Integer(),
            sa.ForeignKey("feature_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_comments_feature_request_id", "comments", ["feature_request_id"])


def downgrade() -> None:
    op.drop_table("comments")
    op.drop_table("votes")
    op.drop_table("feature_requests")
    op.drop_table("users")
    bind = op.get_bind()
    request_status.drop(bind, checkfirst=True)
    user_role.drop(bind, checkfirst=True)
