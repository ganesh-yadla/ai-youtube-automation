"""Domain models for the Trend Intelligence feature.

These are the shapes services and repositories exchange internally.
Kept separate from both the ORM models (infrastructure/db) and the API
request/response schemas (api/v1) so a change to one doesn't ripple into
the others.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TrendingVideo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID | None = None
    youtube_video_id: str
    title: str
    channel_name: str
    channel_id: str
    view_count: int
    published_at: datetime
    duration_seconds: int
    thumbnail_url: str
    video_url: str
    estimated_growth_score: float
    rank_position: int


class TrendAnalysis(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    search_id: UUID
    why_performing: str
    common_hooks: list[str]
    common_title_patterns: list[str]
    common_thumbnail_patterns: list[str]
    content_gaps: list[str]
    video_ideas: list[str]
    ai_model_used: str
    created_at: datetime


class TrendSearch(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    keyword: str
    requested_at: datetime
    youtube_quota_units_used: int
    videos: list[TrendingVideo] = []
    analysis: TrendAnalysis | None = None
