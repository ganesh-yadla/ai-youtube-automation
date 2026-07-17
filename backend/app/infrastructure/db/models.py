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
    scripts: Mapped[list["VideoScript"]] = relationship(
        back_populates="search", cascade="all, delete-orphan"
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


class VideoScript(Base):
    """An AI-generated script for one video idea from a TrendSearch (1:many)."""

    __tablename__ = "video_scripts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    search_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trend_searches.id", ondelete="CASCADE"), index=True
    )

    video_idea: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    hook: Mapped[str] = mapped_column(Text)
    segments: Mapped[list] = mapped_column(JSONB)
    cta: Mapped[str] = mapped_column(Text)
    ai_model_used: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    search: Mapped["TrendSearch"] = relationship(back_populates="scripts")
    narration: Mapped["VoiceNarration | None"] = relationship(
        back_populates="script", cascade="all, delete-orphan", uselist=False
    )


class VoiceNarration(Base):
    """Generated per-segment audio for a VideoScript (1:1 - one narration per script)."""

    __tablename__ = "voice_narrations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    script_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("video_scripts.id", ondelete="CASCADE"), unique=True, index=True
    )

    segments: Mapped[list] = mapped_column(JSONB)
    voice_name: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    script: Mapped["VideoScript"] = relationship(back_populates="narration")
    video: Mapped["AssembledVideo | None"] = relationship(
        back_populates="narration", cascade="all, delete-orphan", uselist=False
    )


class AssembledVideo(Base):
    """The final rendered video for a VoiceNarration (1:1 - one video per narration)."""

    __tablename__ = "assembled_videos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    narration_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("voice_narrations.id", ondelete="CASCADE"), unique=True, index=True
    )

    video_file_path: Mapped[str] = mapped_column(Text)
    thumbnail_file_path: Mapped[str] = mapped_column(Text)
    duration_seconds: Mapped[float]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    narration: Mapped["VoiceNarration"] = relationship(back_populates="video")
