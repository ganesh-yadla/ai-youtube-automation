"""SQLAlchemy 2.0 ORM models for the Trend Intelligence feature."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


class TrendSearch(Base):
    """A single keyword search request and its YouTube quota cost."""

    __tablename__ = "trend_searches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    keyword: Mapped[str] = mapped_column(Text, index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    youtube_quota_units_used: Mapped[int] = mapped_column(default=0)

    videos: Mapped[list["TrendingVideo"]] = relationship(
        back_populates="search", cascade="all, delete-orphan", order_by="TrendingVideo.rank_position"
    )
    analysis: Mapped["TrendAnalysis | None"] = relationship(
        back_populates="search", cascade="all, delete-orphan", uselist=False
    )


class TrendingVideo(Base):
    """A single trending video returned by a TrendSearch."""

    __tablename__ = "trending_videos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    search_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trend_searches.id", ondelete="CASCADE"), index=True
    )

    youtube_video_id: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    channel_name: Mapped[str] = mapped_column(Text)
    channel_id: Mapped[str] = mapped_column(Text)
    view_count: Mapped[int] = mapped_column(BigInteger)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int]
    thumbnail_url: Mapped[str] = mapped_column(Text)
    video_url: Mapped[str] = mapped_column(Text)
    estimated_growth_score: Mapped[float]
    rank_position: Mapped[int]

    search: Mapped["TrendSearch"] = relationship(back_populates="videos")


class TrendAnalysis(Base):
    """AI-generated insights for a TrendSearch (1:1 for this MVP)."""

    __tablename__ = "trend_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    search_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trend_searches.id", ondelete="CASCADE"), unique=True, index=True
    )

    why_performing: Mapped[str] = mapped_column(Text)
    common_hooks: Mapped[list] = mapped_column(JSONB)
    common_title_patterns: Mapped[list] = mapped_column(JSONB)
    common_thumbnail_patterns: Mapped[list] = mapped_column(JSONB)
    content_gaps: Mapped[list] = mapped_column(JSONB)
    video_ideas: Mapped[list] = mapped_column(JSONB)
    ai_model_used: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    search: Mapped["TrendSearch"] = relationship(back_populates="analysis")
