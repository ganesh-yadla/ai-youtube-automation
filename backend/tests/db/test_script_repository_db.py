"""Integration tests for ScriptRepository against a REAL Postgres.

Primarily guards the JSONB round-trip of `segments` (a list of nested
objects, not flat strings like TrendAnalysis's JSONB columns) and the
1:many relationship to trend_searches (unlike trend_analyses, which is 1:1).

Requires a live, already-migrated Postgres:
    docker compose up -d postgres
    cd backend && alembic upgrade head

Excluded from the default test run (see pyproject.toml `addopts`).
Run explicitly with: pytest -m db
"""

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.script import ScriptSegment
from app.repositories.script_repository import ScriptRepository
from app.repositories.trend_repository import TrendRepository

pytestmark = pytest.mark.db


async def _make_search(db_session: AsyncSession):
    trend_repository = TrendRepository(db_session)
    return await trend_repository.create_search(keyword="script repo test", quota_units_used=0, videos=[])


async def test_create_script_round_trips_segments(db_session: AsyncSession):
    """Regression guard: segments is a JSONB list of nested {text,
    visual_description} objects, not flat strings like TrendAnalysis's JSONB
    columns - confirms Pydantic correctly reconstructs the nested objects
    from what Postgres actually stored, not just what Python passed in.
    """
    search = await _make_search(db_session)
    repository = ScriptRepository(db_session)
    segments = [
        ScriptSegment(text="Here are 5 AI tools...", visual_description="Text overlay on gradient"),
        ScriptSegment(text="Number one is...", visual_description="Icon of tool 1"),
    ]

    result = await repository.create_script(
        search_id=search.id,
        video_idea="Top 5 AI tools for beginners",
        title="5 AI Tools Beginners NEED",
        hook="You're wasting hours doing this manually.",
        segments=segments,
        cta="Follow for more.",
        ai_model_used="claude-opus-4-8",
    )

    assert result.id is not None
    assert len(result.segments) == 2
    assert result.segments[0].text == "Here are 5 AI tools..."
    assert result.segments[0].visual_description == "Text overlay on gradient"
    assert result.segments[1].text == "Number one is..."


async def test_create_script_allows_multiple_scripts_per_search(db_session: AsyncSession):
    """Regression guard: video_scripts.search_id is 1:many (unlike
    trend_analyses' 1:1) - two scripts for the same search must both persist,
    not collide on a uniqueness constraint.
    """
    search = await _make_search(db_session)
    repository = ScriptRepository(db_session)
    segment = [ScriptSegment(text="beat", visual_description="visual")]

    first = await repository.create_script(
        search_id=search.id,
        video_idea="idea one",
        title="title one",
        hook="hook one",
        segments=segment,
        cta="cta",
        ai_model_used="claude-opus-4-8",
    )
    second = await repository.create_script(
        search_id=search.id,
        video_idea="idea two",
        title="title two",
        hook="hook two",
        segments=segment,
        cta="cta",
        ai_model_used="claude-opus-4-8",
    )

    assert first.id != second.id
    assert first.search_id == second.search_id == search.id


async def test_get_script_round_trips_by_id(db_session: AsyncSession):
    search = await _make_search(db_session)
    repository = ScriptRepository(db_session)
    created = await repository.create_script(
        search_id=search.id,
        video_idea="idea",
        title="title",
        hook="hook",
        segments=[ScriptSegment(text="beat", visual_description="visual")],
        cta="cta",
        ai_model_used="claude-opus-4-8",
    )

    fetched = await repository.get_script(created.id)

    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.title == "title"


async def test_get_script_returns_none_for_unknown_id(db_session: AsyncSession):
    repository = ScriptRepository(db_session)

    result = await repository.get_script(uuid4())

    assert result is None
