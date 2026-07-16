"""FastAPI dependency providers - the composition root for the Trend
Intelligence feature. Routers depend on these, never on concrete
implementations directly.
"""

from functools import lru_cache

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.infrastructure.cache.redis_client import get_redis_client
from app.infrastructure.db.session import get_db
from app.infrastructure.external.claude_client import ClaudeClient
from app.infrastructure.external.youtube_client import YoutubeClient
from app.repositories.trend_repository import TrendRepository
from app.services.ai_analysis_service import AIAnalysisService
from app.services.trend_service import TrendService


@lru_cache
def get_youtube_client() -> YoutubeClient:
    return YoutubeClient()


@lru_cache
def get_claude_client() -> ClaudeClient:
    return ClaudeClient()


def get_trend_repository(session: AsyncSession = Depends(get_db)) -> TrendRepository:
    return TrendRepository(session)


def get_trend_service(
    youtube_client: YoutubeClient = Depends(get_youtube_client),
    repository: TrendRepository = Depends(get_trend_repository),
    redis: Redis = Depends(get_redis_client),
    settings: Settings = Depends(get_settings),
) -> TrendService:
    return TrendService(
        youtube_client=youtube_client,
        repository=repository,
        redis=redis,
        cache_ttl_seconds=settings.trend_cache_ttl_seconds,
    )


def get_ai_analysis_service(
    claude_client: ClaudeClient = Depends(get_claude_client),
    repository: TrendRepository = Depends(get_trend_repository),
) -> AIAnalysisService:
    return AIAnalysisService(claude_client=claude_client, repository=repository)
