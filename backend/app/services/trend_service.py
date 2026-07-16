"""Business logic for keyword-based trend search."""

import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from redis.asyncio import Redis

from app.domain.models.trend import TrendingVideo
from app.domain.models.trend import TrendSearch as TrendSearchDomain
from app.exceptions.trend_exceptions import NoTrendingVideosFoundError, TrendSearchNotFoundError
from app.infrastructure.external.youtube_client import YoutubeClient
from app.repositories.interfaces.trend_repository import TrendRepositoryInterface

logger = logging.getLogger(__name__)

_MIN_AGE_DAYS_FOR_GROWTH = 1.0


class TrendService:
    """Orchestrates a keyword search: cache lookup, YouTube fetch, scoring, persistence."""

    def __init__(
        self,
        youtube_client: YoutubeClient,
        repository: TrendRepositoryInterface,
        redis: Redis,
        cache_ttl_seconds: int,
    ) -> None:
        self._youtube_client = youtube_client
        self._repository = repository
        self._redis = redis
        self._cache_ttl_seconds = cache_ttl_seconds

    async def search(self, keyword: str, max_results: int = 10) -> TrendSearchDomain:
        normalized_keyword = keyword.strip().lower()
        cache_key = self._cache_key(normalized_keyword, max_results)

        cached_videos = await self._get_cached_videos(cache_key)
        if cached_videos is not None:
            logger.info("trend_search_cache_hit", extra={"keyword": normalized_keyword})
            return await self._repository.create_search(
                keyword=normalized_keyword, quota_units_used=0, videos=cached_videos
            )

        logger.info("trend_search_cache_miss", extra={"keyword": normalized_keyword})
        youtube_response = await self._youtube_client.search_trending_videos(normalized_keyword, max_results)

        if not youtube_response.videos:
            raise NoTrendingVideosFoundError(f"No trending videos found for keyword '{keyword}'")

        videos = [
            TrendingVideo(
                youtube_video_id=video.youtube_video_id,
                title=video.title,
                channel_name=video.channel_name,
                channel_id=video.channel_id,
                view_count=video.view_count,
                published_at=video.published_at,
                duration_seconds=video.duration_seconds,
                thumbnail_url=video.thumbnail_url,
                video_url=video.video_url,
                estimated_growth_score=self._estimate_growth_score(video.view_count, video.published_at),
                rank_position=rank,
            )
            for rank, video in enumerate(youtube_response.videos, start=1)
        ]

        await self._cache_videos(cache_key, videos)

        return await self._repository.create_search(
            keyword=normalized_keyword,
            quota_units_used=youtube_response.quota_units_used,
            videos=videos,
        )

    async def get_by_id(self, search_id: UUID) -> TrendSearchDomain:
        search = await self._repository.get_search(search_id)
        if search is None:
            raise TrendSearchNotFoundError(f"No trend search found with id '{search_id}'")
        return search

    @staticmethod
    def _estimate_growth_score(view_count: int, published_at: datetime) -> float:
        """Views/day since publish - a proxy for growth, not true velocity.

        True growth requires observing the same video across multiple
        snapshots over time, which this MVP does not do yet.
        """
        age_days = max(
            (datetime.now(UTC) - published_at).total_seconds() / 86400,
            _MIN_AGE_DAYS_FOR_GROWTH,
        )
        return round(view_count / age_days, 2)

    @staticmethod
    def _cache_key(normalized_keyword: str, max_results: int) -> str:
        return f"trend_search:{normalized_keyword}:{max_results}"

    async def _get_cached_videos(self, cache_key: str) -> list[TrendingVideo] | None:
        raw = await self._redis.get(cache_key)
        if raw is None:
            return None
        return [TrendingVideo.model_validate(item) for item in json.loads(raw)]

    async def _cache_videos(self, cache_key: str, videos: list[TrendingVideo]) -> None:
        payload = json.dumps([video.model_dump(mode="json", exclude={"id"}) for video in videos])
        await self._redis.set(cache_key, payload, ex=self._cache_ttl_seconds)
