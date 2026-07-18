"""Unit tests for AIAnalysisService, using a fake LLM client and repository."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.domain.models.trend import TrendAnalysis as TrendAnalysisDomain
from app.domain.models.trend import TrendingVideo
from app.domain.models.trend import TrendSearch as TrendSearchDomain
from app.exceptions.trend_exceptions import (
    NoTrendingVideosFoundError,
    TrendAnalysisAlreadyExistsError,
    TrendSearchNotFoundError,
)
from app.infrastructure.external.interfaces.llm_client import TrendInsights
from app.services.ai_analysis_service import AIAnalysisService


class FakeLLMClient:
    def __init__(self, insights: TrendInsights) -> None:
        self.insights = insights
        self.last_prompt: str | None = None
        self.calls = 0

    @property
    def model_name(self) -> str:
        return "fake-llm-model"

    async def analyze_trending_videos(self, prompt: str) -> TrendInsights:
        self.calls += 1
        self.last_prompt = prompt
        return self.insights


class FakeRepository:
    def __init__(self, search: TrendSearchDomain | None) -> None:
        self.search = search
        self.saved_calls: list[dict] = []

    async def get_search(self, search_id):
        return self.search

    async def save_analysis(
        self,
        search_id,
        why_performing,
        common_hooks,
        common_title_patterns,
        common_thumbnail_patterns,
        content_gaps,
        video_ideas,
        ai_model_used,
    ) -> TrendAnalysisDomain:
        self.saved_calls.append(
            {"search_id": search_id, "ai_model_used": ai_model_used, "video_ideas": video_ideas}
        )
        return TrendAnalysisDomain(
            id=uuid4(),
            search_id=search_id,
            why_performing=why_performing,
            common_hooks=common_hooks,
            common_title_patterns=common_title_patterns,
            common_thumbnail_patterns=common_thumbnail_patterns,
            content_gaps=content_gaps,
            video_ideas=video_ideas,
            ai_model_used=ai_model_used,
            created_at=datetime.now(UTC),
        )


class FakeScriptRepository:
    def __init__(self, existing_ideas: list[str] | None = None) -> None:
        self.existing_ideas = existing_ideas or []

    async def get_all_video_ideas(self) -> list[str]:
        return self.existing_ideas


def _make_video(title: str, rank: int) -> TrendingVideo:
    return TrendingVideo(
        id=uuid4(),
        youtube_video_id=f"vid{rank}",
        title=title,
        channel_name="Test Channel",
        channel_id="channel-1",
        view_count=100_000 * rank,
        published_at=datetime.now(UTC),
        duration_seconds=300,
        thumbnail_url="https://example.com/thumb.jpg",
        video_url=f"https://www.youtube.com/watch?v=vid{rank}",
        estimated_growth_score=1000.0,
        rank_position=rank,
    )


def _make_search(
    videos: list[TrendingVideo], analysis: TrendAnalysisDomain | None = None
) -> TrendSearchDomain:
    return TrendSearchDomain(
        id=uuid4(),
        keyword="ai tools",
        requested_at=datetime.now(UTC),
        youtube_quota_units_used=101,
        videos=videos,
        analysis=analysis,
    )


@pytest.fixture
def sample_insights() -> TrendInsights:
    return TrendInsights(
        why_performing="Strong hooks and consistent upload cadence.",
        common_hooks=["Question in first 3 seconds"],
        common_title_patterns=["Numbered list titles"],
        common_thumbnail_patterns=["Inferred: high-contrast text overlay"],
        content_gaps=["Beginner-friendly explainer missing"],
        video_ideas=["Top 5 AI tools for beginners in 2026"],
    )


async def test_analyze_persists_insights_from_claude(sample_insights):
    search = _make_search([_make_video("Top AI Tools", 1), _make_video("AI Tools Review", 2)])
    llm_client = FakeLLMClient(sample_insights)
    repository = FakeRepository(search)
    service = AIAnalysisService(llm_client, repository, FakeScriptRepository())

    result = await service.analyze(search.id)

    assert result.why_performing == sample_insights.why_performing
    assert result.ai_model_used == "fake-llm-model"
    assert len(repository.saved_calls) == 1
    assert repository.saved_calls[0]["search_id"] == search.id


async def test_analyze_builds_prompt_with_video_metadata(sample_insights):
    search = _make_search([_make_video("Top AI Tools", 1)])
    llm_client = FakeLLMClient(sample_insights)
    repository = FakeRepository(search)
    service = AIAnalysisService(llm_client, repository, FakeScriptRepository())

    await service.analyze(search.id)

    assert llm_client.last_prompt is not None
    assert "ai tools" in llm_client.last_prompt
    assert "Top AI Tools" in llm_client.last_prompt
    assert "100,000 views" in llm_client.last_prompt
    assert "growth score 1,000 views/day" in llm_client.last_prompt


async def test_analyze_raises_when_search_not_found(sample_insights):
    llm_client = FakeLLMClient(sample_insights)
    repository = FakeRepository(None)
    service = AIAnalysisService(llm_client, repository, FakeScriptRepository())

    with pytest.raises(TrendSearchNotFoundError):
        await service.analyze(uuid4())

    assert llm_client.calls == 0


async def test_analyze_raises_when_already_analyzed(sample_insights):
    existing_analysis = TrendAnalysisDomain(
        id=uuid4(),
        search_id=uuid4(),
        why_performing="x",
        common_hooks=[],
        common_title_patterns=[],
        common_thumbnail_patterns=[],
        content_gaps=[],
        video_ideas=[],
        ai_model_used="claude-opus-4-8",
        created_at=datetime.now(UTC),
    )
    search = _make_search([_make_video("Top AI Tools", 1)], analysis=existing_analysis)
    llm_client = FakeLLMClient(sample_insights)
    repository = FakeRepository(search)
    service = AIAnalysisService(llm_client, repository, FakeScriptRepository())

    with pytest.raises(TrendAnalysisAlreadyExistsError):
        await service.analyze(search.id)

    assert llm_client.calls == 0


async def test_analyze_filters_out_ideas_too_similar_to_existing_scripts():
    insights = TrendInsights(
        why_performing="x",
        common_hooks=[],
        common_title_patterns=[],
        common_thumbnail_patterns=[],
        content_gaps=[],
        video_ideas=[
            "Top 5 AI Tools for Beginners in 2026",
            "How to Automate Your Inbox with AI",
        ],
    )
    search = _make_search([_make_video("Top AI Tools", 1)])
    llm_client = FakeLLMClient(insights)
    repository = FakeRepository(search)
    # Near-identical (case/wording) to the first idea - should be filtered.
    script_repository = FakeScriptRepository(existing_ideas=["Top 5 AI tools for beginners 2026"])
    service = AIAnalysisService(llm_client, repository, script_repository)

    result = await service.analyze(search.id)

    assert result.video_ideas == ["How to Automate Your Inbox with AI"]


async def test_analyze_persists_full_unfiltered_ideas_even_when_some_are_duplicates():
    insights = TrendInsights(
        why_performing="x",
        common_hooks=[],
        common_title_patterns=[],
        common_thumbnail_patterns=[],
        content_gaps=[],
        video_ideas=["Top 5 AI Tools for Beginners in 2026"],
    )
    search = _make_search([_make_video("Top AI Tools", 1)])
    llm_client = FakeLLMClient(insights)
    repository = FakeRepository(search)
    script_repository = FakeScriptRepository(existing_ideas=["Top 5 AI tools for beginners 2026"])
    service = AIAnalysisService(llm_client, repository, script_repository)

    result = await service.analyze(search.id)

    assert result.video_ideas == []
    assert repository.saved_calls[0]["video_ideas"] == ["Top 5 AI Tools for Beginners in 2026"]


async def test_analyze_raises_when_search_has_no_videos(sample_insights):
    search = _make_search([])
    llm_client = FakeLLMClient(sample_insights)
    repository = FakeRepository(search)
    service = AIAnalysisService(llm_client, repository, FakeScriptRepository())

    with pytest.raises(NoTrendingVideosFoundError):
        await service.analyze(search.id)

    assert llm_client.calls == 0
