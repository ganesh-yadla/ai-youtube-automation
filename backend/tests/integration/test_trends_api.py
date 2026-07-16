"""Integration tests for the /trends API surface, using a stubbed service
(not a real Postgres/Redis/YouTube) to verify request/response wiring.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.dependencies import get_ai_analysis_service, get_trend_service
from app.domain.models.trend import TrendAnalysis as TrendAnalysisDomain
from app.domain.models.trend import TrendingVideo
from app.domain.models.trend import TrendSearch as TrendSearchDomain
from app.exceptions.trend_exceptions import (
    NoTrendingVideosFoundError,
    TrendAnalysisAlreadyExistsError,
    TrendSearchNotFoundError,
)
from app.main import app


class StubTrendService:
    def __init__(self, result: TrendSearchDomain | None = None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error

    async def search(self, keyword: str, max_results: int = 10) -> TrendSearchDomain:
        if self._error:
            raise self._error
        return self._result

    async def get_by_id(self, search_id) -> TrendSearchDomain:
        if self._error:
            raise self._error
        return self._result


class StubAIAnalysisService:
    def __init__(self, result: TrendAnalysisDomain | None = None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error

    async def analyze(self, search_id) -> TrendAnalysisDomain:
        if self._error:
            raise self._error
        return self._result


def _sample_search_result() -> TrendSearchDomain:
    return TrendSearchDomain(
        id=uuid4(),
        keyword="ai tools",
        requested_at=datetime.now(UTC),
        youtube_quota_units_used=101,
        videos=[
            TrendingVideo(
                id=uuid4(),
                youtube_video_id="vid1",
                title="Top AI Tools 2026",
                channel_name="Tech Channel",
                channel_id="channel-1",
                view_count=500_000,
                published_at=datetime.now(UTC),
                duration_seconds=600,
                thumbnail_url="https://example.com/thumb.jpg",
                video_url="https://www.youtube.com/watch?v=vid1",
                estimated_growth_score=500_000.0,
                rank_position=1,
            )
        ],
    )


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


async def test_search_endpoint_returns_serialized_results():
    app.dependency_overrides[get_trend_service] = lambda: StubTrendService(result=_sample_search_result())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/trends/search", json={"keyword": "AI Tools", "max_results": 5})

    assert response.status_code == 201
    body = response.json()
    assert body["keyword"] == "ai tools"
    assert body["youtube_quota_units_used"] == 101
    assert len(body["videos"]) == 1
    assert body["videos"][0]["youtube_video_id"] == "vid1"


async def test_search_endpoint_returns_404_when_no_videos_found():
    app.dependency_overrides[get_trend_service] = lambda: StubTrendService(
        error=NoTrendingVideosFoundError("No trending videos found for keyword 'zzz'")
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/trends/search", json={"keyword": "zzz"})

    assert response.status_code == 404


async def test_search_endpoint_rejects_empty_keyword():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/trends/search", json={"keyword": ""})

    assert response.status_code == 422


def _sample_analysis_result(search_id) -> TrendAnalysisDomain:
    return TrendAnalysisDomain(
        id=uuid4(),
        search_id=search_id,
        why_performing="Strong hooks and consistent upload cadence.",
        common_hooks=["Question in first 3 seconds"],
        common_title_patterns=["Numbered list titles"],
        common_thumbnail_patterns=["Inferred: high-contrast text overlay"],
        content_gaps=["Beginner-friendly explainer missing"],
        video_ideas=["Top 5 AI tools for beginners in 2026"],
        ai_model_used="claude-opus-4-8",
        created_at=datetime.now(UTC),
    )


async def test_insights_endpoint_returns_serialized_analysis():
    search_id = uuid4()
    app.dependency_overrides[get_ai_analysis_service] = lambda: StubAIAnalysisService(
        result=_sample_analysis_result(search_id)
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/trends/{search_id}/insights")

    assert response.status_code == 201
    body = response.json()
    assert body["search_id"] == str(search_id)
    assert body["ai_model_used"] == "claude-opus-4-8"
    assert body["video_ideas"] == ["Top 5 AI tools for beginners in 2026"]


async def test_insights_endpoint_returns_404_when_search_not_found():
    app.dependency_overrides[get_ai_analysis_service] = lambda: StubAIAnalysisService(
        error=TrendSearchNotFoundError("No trend search found")
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/trends/{uuid4()}/insights")

    assert response.status_code == 404


async def test_insights_endpoint_returns_409_when_already_analyzed():
    app.dependency_overrides[get_ai_analysis_service] = lambda: StubAIAnalysisService(
        error=TrendAnalysisAlreadyExistsError("Already analyzed")
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/trends/{uuid4()}/insights")

    assert response.status_code == 409


async def test_get_search_endpoint_returns_serialized_search():
    result = _sample_search_result()
    app.dependency_overrides[get_trend_service] = lambda: StubTrendService(result=result)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/trends/{result.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(result.id)
    assert body["keyword"] == "ai tools"
    assert len(body["videos"]) == 1


async def test_get_search_endpoint_returns_404_when_not_found():
    app.dependency_overrides[get_trend_service] = lambda: StubTrendService(
        error=TrendSearchNotFoundError("No trend search found")
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/trends/{uuid4()}")

    assert response.status_code == 404
