"""create trend intelligence tables

Revision ID: 76106014e5ac
Revises:
Create Date: 2026-07-16 14:19:24.911719

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '76106014e5ac'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "trend_searches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("keyword", sa.Text(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("youtube_quota_units_used", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_trend_searches_keyword", "trend_searches", ["keyword"])

    op.create_table(
        "trending_videos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "search_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("trend_searches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("youtube_video_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("channel_name", sa.Text(), nullable=False),
        sa.Column("channel_id", sa.Text(), nullable=False),
        sa.Column("view_count", sa.BigInteger(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("thumbnail_url", sa.Text(), nullable=False),
        sa.Column("video_url", sa.Text(), nullable=False),
        sa.Column("estimated_growth_score", sa.Float(), nullable=False),
        sa.Column("rank_position", sa.Integer(), nullable=False),
    )
    op.create_index("ix_trending_videos_search_id", "trending_videos", ["search_id"])

    op.create_table(
        "trend_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "search_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("trend_searches.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("why_performing", sa.Text(), nullable=False),
        sa.Column("common_hooks", postgresql.JSONB(), nullable=False),
        sa.Column("common_title_patterns", postgresql.JSONB(), nullable=False),
        sa.Column("common_thumbnail_patterns", postgresql.JSONB(), nullable=False),
        sa.Column("content_gaps", postgresql.JSONB(), nullable=False),
        sa.Column("video_ideas", postgresql.JSONB(), nullable=False),
        sa.Column("ai_model_used", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_trend_analyses_search_id", "trend_analyses", ["search_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_trend_analyses_search_id", table_name="trend_analyses")
    op.drop_table("trend_analyses")

    op.drop_index("ix_trending_videos_search_id", table_name="trending_videos")
    op.drop_table("trending_videos")

    op.drop_index("ix_trend_searches_keyword", table_name="trend_searches")
    op.drop_table("trend_searches")
