"""Integration tests for TrendRepository against a REAL Postgres.

These are the tests that would have caught the two bugs found during live
verification (datetime timezone mismatch, missing relationship load) - the
fake-based unit tests can't exercise real SQLAlchemy type binding or
relationship loading.

Requires a live, already-migrated Postgres:
    docker compose up -d postgres
    cd backend && alembic upgrade head

Excluded from the default test run (see pyproject.toml `addopts`).
Run explicitly with: pytest -m db
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.domain.models.trend import TrendingVideo
from app.repositories.trend_repository import TrendRepository

pytestmark = pytest.mark.db


@pytest.fixture
async def db_session():
    """A dedicated engine per test, bound to that test's event loop.

    Reusing app.infrastructure.db.session's module-level engine singleton
    here would break: pytest-asyncio gives each test function a fresh event
    loop, but a module-level engine's connection pool is bound to whichever
    loop first touched it, so later tests fail with "Event loop is closed".
    """
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        yield session
        await session.execute(text("TRUNCATE trend_searches CASCADE"))
        await session.commit()

    await engine.dispose()


def _make_video(rank: int, view_count: int = 1000) -> TrendingVideo:
    return TrendingVideo(
        youtube_video_id=f"vid{rank}",
        title=f"Video {rank}",
        channel_name="Test Channel",
        channel_id="channel-1",
        view_count=view_count,
        published_at=datetime.now(UTC) - timedelta(days=1),
        duration_seconds=120,
        thumbnail_url="https://example.com/thumb.jpg",
        video_url=f"https://www.youtube.com/watch?v=vid{rank}",
        estimated_growth_score=500.0,
        rank_position=rank,
    )


async def test_create_search_persists_timezone_aware_datetime(db_session: AsyncSession):
    """Regression: published_at is timezone-aware (YouTube's ISO 8601 'Z'
    timestamps). The ORM column was previously declared naive while the
    migration created it as TIMESTAMPTZ, so asyncpg rejected the value.
    """
    repository = TrendRepository(db_session)
    videos = [_make_video(1), _make_video(2)]

    result = await repository.create_search(keyword="regression test", quota_units_used=101, videos=videos)

    assert result.id is not None
    assert len(result.videos) == 2
    assert result.videos[0].published_at.tzinfo is not None


async def test_create_search_returns_search_with_no_analysis(db_session: AsyncSession):
    """Regression: create_search only refreshed the `videos` relationship, not
    `analysis`. Reading the unloaded relationship crashed with MissingGreenlet
    since Pydantic's sync attribute access can't trigger an async lazy load.
    """
    repository = TrendRepository(db_session)

    result = await repository.create_search(
        keyword="regression test 2", quota_units_used=0, videos=[_make_video(1)]
    )

    assert result.analysis is None


async def test_create_search_persists_large_view_counts(db_session: AsyncSession):
    """Regression: view_count needs BigInteger - real viral videos exceed the
    ~2.1 billion ceiling of a 32-bit INTEGER column.
    """
    repository = TrendRepository(db_session)
    video = _make_video(1, view_count=15_000_000_000)  # exceeds int32 range

    result = await repository.create_search(keyword="viral video test", quota_units_used=0, videos=[video])

    assert result.videos[0].view_count == 15_000_000_000


async def test_get_search_round_trips_videos_and_analysis(db_session: AsyncSession):
    repository = TrendRepository(db_session)
    created = await repository.create_search(
        keyword="round trip test", quota_units_used=101, videos=[_make_video(1)]
    )

    await repository.save_analysis(
        search_id=created.id,
        why_performing="Strong hooks",
        common_hooks=["Question hook"],
        common_title_patterns=["Numbered lists"],
        common_thumbnail_patterns=["High contrast"],
        content_gaps=["Beginner content missing"],
        video_ideas=["Top 5 AI tools"],
        ai_model_used="claude-opus-4-8",
    )

    fetched = await repository.get_search(created.id)

    assert fetched is not None
    assert len(fetched.videos) == 1
    assert fetched.analysis is not None
    assert fetched.analysis.why_performing == "Strong hooks"


async def test_get_search_returns_none_for_unknown_id(db_session: AsyncSession):
    repository = TrendRepository(db_session)

    result = await repository.get_search(uuid4())

    assert result is None
