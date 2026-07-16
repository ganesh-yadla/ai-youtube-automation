"""Unit tests for TrendService, using fakes instead of real Postgres/Redis/YouTube."""

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.models.trend import TrendingVideo
from app.domain.models.trend import TrendSearch as TrendSearchDomain
from app.exceptions.trend_exceptions import NoTrendingVideosFoundError, TrendSearchNotFoundError
from app.infrastructure.external.youtube_client import YoutubeSearchResponse, YoutubeVideoData
from app.services.trend_service import TrendService


class FakeYoutubeClient:
    def __init__(self, response: YoutubeSearchResponse) -> None:
        self.response = response
        self.calls = 0

    async def search_trending_videos(self, keyword: str, max_results: int = 10) -> YoutubeSearchResponse:
        self.calls += 1
        return self.response


class FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = value


class FakeRepository:
    def __init__(self, existing_search: TrendSearchDomain | None = None) -> None:
        self.created_searches: list[dict] = []
        self.existing_search = existing_search

    async def create_search(
        self, keyword: str, quota_units_used: int, videos: list[TrendingVideo]
    ) -> TrendSearchDomain:
        self.created_searches.append({"keyword": keyword, "quota_units_used": quota_units_used})
        persisted_videos = [v.model_copy(update={"id": uuid4()}) for v in videos]
        search = TrendSearchDomain(
            id=uuid4(),
            keyword=keyword,
            requested_at=datetime.now(UTC),
            youtube_quota_units_used=quota_units_used,
            videos=persisted_videos,
        )
        self.existing_search = search
        return search

    async def get_search(self, search_id) -> TrendSearchDomain | None:
        if self.existing_search and self.existing_search.id == search_id:
            return self.existing_search
        return None


def _make_youtube_video(video_id: str, views: int, days_old: int) -> YoutubeVideoData:
    return YoutubeVideoData(
        youtube_video_id=video_id,
        title=f"Video {video_id}",
        channel_name="Test Channel",
        channel_id="channel-1",
        view_count=views,
        published_at=datetime.now(UTC) - timedelta(days=days_old),
        duration_seconds=300,
        thumbnail_url="https://example.com/thumb.jpg",
        video_url=f"https://www.youtube.com/watch?v={video_id}",
    )


@pytest.fixture
def youtube_response() -> YoutubeSearchResponse:
    return YoutubeSearchResponse(
        videos=[
            _make_youtube_video("vid1", views=200_000, days_old=2),
            _make_youtube_video("vid2", views=100_000, days_old=1),
        ],
        quota_units_used=101,
    )


async def test_cache_miss_fetches_from_youtube_and_persists(youtube_response):
    youtube_client = FakeYoutubeClient(youtube_response)
    repository = FakeRepository()
    redis = FakeRedis()
    service = TrendService(youtube_client, repository, redis, cache_ttl_seconds=3600)

    result = await service.search("AI Tools", max_results=2)

    assert youtube_client.calls == 1
    assert len(repository.created_searches) == 1
    assert repository.created_searches[0]["quota_units_used"] == 101
    assert len(result.videos) == 2
    assert result.videos[0].rank_position == 1
    assert result.videos[0].estimated_growth_score > 0


async def test_cache_hit_skips_youtube_and_reports_zero_quota(youtube_response):
    youtube_client = FakeYoutubeClient(youtube_response)
    repository = FakeRepository()
    redis = FakeRedis()
    service = TrendService(youtube_client, repository, redis, cache_ttl_seconds=3600)

    await service.search("AI Tools", max_results=2)
    assert youtube_client.calls == 1

    result = await service.search("AI Tools", max_results=2)

    assert youtube_client.calls == 1  # not called again
    assert repository.created_searches[1]["quota_units_used"] == 0
    assert len(result.videos) == 2


async def test_no_videos_found_raises():
    youtube_client = FakeYoutubeClient(YoutubeSearchResponse(videos=[], quota_units_used=100))
    repository = FakeRepository()
    redis = FakeRedis()
    service = TrendService(youtube_client, repository, redis, cache_ttl_seconds=3600)

    with pytest.raises(NoTrendingVideosFoundError):
        await service.search("some obscure nonsense keyword", max_results=2)


async def test_keyword_is_normalized_for_cache_key(youtube_response):
    youtube_client = FakeYoutubeClient(youtube_response)
    repository = FakeRepository()
    redis = FakeRedis()
    service = TrendService(youtube_client, repository, redis, cache_ttl_seconds=3600)

    await service.search("  AI Tools  ", max_results=2)
    await service.search("ai tools", max_results=2)

    assert youtube_client.calls == 1  # second call hit cache despite different casing/whitespace


async def test_cached_videos_round_trip_correctly(youtube_response):
    youtube_client = FakeYoutubeClient(youtube_response)
    repository = FakeRepository()
    redis = FakeRedis()
    service = TrendService(youtube_client, repository, redis, cache_ttl_seconds=3600)

    await service.search("AI Tools", max_results=2)

    cache_key = service._cache_key("ai tools", 2)
    cached_raw = json.loads(await redis.get(cache_key))
    assert len(cached_raw) == 2
    assert cached_raw[0]["youtube_video_id"] == "vid1"


async def test_get_by_id_returns_persisted_search(youtube_response):
    youtube_client = FakeYoutubeClient(youtube_response)
    repository = FakeRepository()
    redis = FakeRedis()
    service = TrendService(youtube_client, repository, redis, cache_ttl_seconds=3600)

    created = await service.search("AI Tools", max_results=2)
    fetched = await service.get_by_id(created.id)

    assert fetched.id == created.id
    assert fetched.keyword == "ai tools"


async def test_get_by_id_raises_when_not_found():
    youtube_client = FakeYoutubeClient(YoutubeSearchResponse(videos=[], quota_units_used=0))
    repository = FakeRepository()
    redis = FakeRedis()
    service = TrendService(youtube_client, repository, redis, cache_ttl_seconds=3600)

    with pytest.raises(TrendSearchNotFoundError):
        await service.get_by_id(uuid4())
