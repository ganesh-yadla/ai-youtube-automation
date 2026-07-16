"""Request/response wire schemas for the /trends API. Kept separate from
domain models so the public API contract can evolve independently of
internal service/repository shapes.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TrendSearchRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=100)
    max_results: int = Field(default=10, ge=1, le=25)


class TrendingVideoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
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


class TrendAnalysisResponse(BaseModel):
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


class TrendSearchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    keyword: str
    requested_at: datetime
    youtube_quota_units_used: int
    videos: list[TrendingVideoResponse]
    analysis: TrendAnalysisResponse | None = None
