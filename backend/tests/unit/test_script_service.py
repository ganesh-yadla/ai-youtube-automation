"""Unit tests for ScriptService, using a fake LLM client and both repositories."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.domain.models.script import Script as ScriptDomain
from app.domain.models.trend import TrendAnalysis as TrendAnalysisDomain
from app.domain.models.trend import TrendSearch as TrendSearchDomain
from app.exceptions.script_exceptions import TrendAnalysisRequiredError
from app.exceptions.trend_exceptions import TrendSearchNotFoundError
from app.infrastructure.external.interfaces.llm_client import ScriptOutput, ScriptSegmentOutput
from app.services.script_service import ScriptService


class FakeLLMClient:
    def __init__(self, output: ScriptOutput) -> None:
        self.output = output
        self.last_prompt: str | None = None
        self.calls = 0

    @property
    def model_name(self) -> str:
        return "fake-llm-model"

    async def generate_script(self, prompt: str) -> ScriptOutput:
        self.calls += 1
        self.last_prompt = prompt
        return self.output


class FakeTrendRepository:
    def __init__(self, search: TrendSearchDomain | None) -> None:
        self.search = search

    async def get_search(self, search_id):
        return self.search


class FakeScriptRepository:
    def __init__(self) -> None:
        self.saved_calls: list[dict] = []
        self.scripts_by_id: dict = {}

    async def create_script(
        self, search_id, video_idea, title, hook, segments, cta, ai_model_used
    ) -> ScriptDomain:
        self.saved_calls.append({"search_id": search_id, "video_idea": video_idea})
        script = ScriptDomain(
            id=uuid4(),
            search_id=search_id,
            video_idea=video_idea,
            title=title,
            hook=hook,
            segments=segments,
            cta=cta,
            ai_model_used=ai_model_used,
            created_at=datetime.now(UTC),
        )
        self.scripts_by_id[script.id] = script
        return script

    async def get_script(self, script_id) -> ScriptDomain | None:
        return self.scripts_by_id.get(script_id)


def _make_analysis() -> TrendAnalysisDomain:
    return TrendAnalysisDomain(
        id=uuid4(),
        search_id=uuid4(),
        why_performing="Strong hooks and consistent upload cadence.",
        common_hooks=["Question in first 3 seconds"],
        common_title_patterns=["Numbered list titles"],
        common_thumbnail_patterns=["High contrast text overlay"],
        content_gaps=["Beginner-friendly explainer missing"],
        video_ideas=["Top 5 AI tools for beginners in 2026", "AI tools comparison"],
        ai_model_used="claude-opus-4-8",
        created_at=datetime.now(UTC),
    )


def _make_search(analysis: TrendAnalysisDomain | None) -> TrendSearchDomain:
    return TrendSearchDomain(
        id=uuid4(),
        keyword="ai tools",
        requested_at=datetime.now(UTC),
        youtube_quota_units_used=101,
        videos=[],
        analysis=analysis,
    )


@pytest.fixture
def sample_output() -> ScriptOutput:
    return ScriptOutput(
        video_idea="Top 5 AI tools for beginners in 2026",
        title="5 AI Tools Beginners NEED in 2026",
        hook="You're wasting hours doing this manually.",
        segments=[
            ScriptSegmentOutput(text="Here are 5 AI tools...", visual_description="Text overlay on gradient"),
            ScriptSegmentOutput(text="Number one is...", visual_description="Icon of tool 1"),
            ScriptSegmentOutput(text="Number two is...", visual_description="Icon of tool 2"),
            ScriptSegmentOutput(text="Number three is...", visual_description="Icon of tool 3"),
        ],
        cta="Follow for more AI tool breakdowns.",
    )


async def test_generate_persists_script_with_explicit_video_idea(sample_output):
    analysis = _make_analysis()
    search = _make_search(analysis)
    llm_client = FakeLLMClient(sample_output)
    trend_repo = FakeTrendRepository(search)
    script_repo = FakeScriptRepository()
    service = ScriptService(llm_client, trend_repo, script_repo)

    result = await service.generate(search.id, video_idea="Top 5 AI tools for beginners in 2026")

    assert result.title == sample_output.title
    assert result.ai_model_used == "fake-llm-model"
    assert len(result.segments) == 4
    assert script_repo.saved_calls[0]["search_id"] == search.id


async def test_generate_prompt_includes_explicit_idea_instruction(sample_output):
    analysis = _make_analysis()
    search = _make_search(analysis)
    llm_client = FakeLLMClient(sample_output)
    service = ScriptService(llm_client, FakeTrendRepository(search), FakeScriptRepository())

    await service.generate(search.id, video_idea="My custom idea")

    assert llm_client.last_prompt is not None
    assert 'Write the script for this specific video idea: "My custom idea"' in llm_client.last_prompt


async def test_generate_prompt_omits_idea_instruction_when_not_given(sample_output):
    analysis = _make_analysis()
    search = _make_search(analysis)
    llm_client = FakeLLMClient(sample_output)
    service = ScriptService(llm_client, FakeTrendRepository(search), FakeScriptRepository())

    await service.generate(search.id)

    assert llm_client.last_prompt is not None
    assert "No specific video idea was given" in llm_client.last_prompt
    assert "Top 5 AI tools for beginners in 2026" in llm_client.last_prompt  # from analysis.video_ideas


async def test_generate_uses_claude_resolved_idea_when_none_given(sample_output):
    analysis = _make_analysis()
    search = _make_search(analysis)
    llm_client = FakeLLMClient(sample_output)
    script_repo = FakeScriptRepository()
    service = ScriptService(llm_client, FakeTrendRepository(search), script_repo)

    result = await service.generate(search.id)

    assert result.video_idea == sample_output.video_idea


async def test_generate_raises_when_search_not_found(sample_output):
    llm_client = FakeLLMClient(sample_output)
    service = ScriptService(llm_client, FakeTrendRepository(None), FakeScriptRepository())

    with pytest.raises(TrendSearchNotFoundError):
        await service.generate(uuid4())

    assert llm_client.calls == 0


async def test_generate_raises_when_analysis_missing(sample_output):
    search = _make_search(analysis=None)
    llm_client = FakeLLMClient(sample_output)
    service = ScriptService(llm_client, FakeTrendRepository(search), FakeScriptRepository())

    with pytest.raises(TrendAnalysisRequiredError):
        await service.generate(search.id)

    assert llm_client.calls == 0


async def test_get_by_id_returns_persisted_script(sample_output):
    analysis = _make_analysis()
    search = _make_search(analysis)
    llm_client = FakeLLMClient(sample_output)
    script_repo = FakeScriptRepository()
    service = ScriptService(llm_client, FakeTrendRepository(search), script_repo)

    created = await service.generate(search.id, video_idea="Top 5 AI tools for beginners in 2026")
    fetched = await service.get_by_id(created.id)

    assert fetched is not None
    assert fetched.id == created.id


async def test_get_by_id_returns_none_when_not_found(sample_output):
    llm_client = FakeLLMClient(sample_output)
    service = ScriptService(llm_client, FakeTrendRepository(None), FakeScriptRepository())

    result = await service.get_by_id(uuid4())

    assert result is None
