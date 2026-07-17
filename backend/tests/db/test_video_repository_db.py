"""Integration tests for VideoRepository against a REAL Postgres.

Guards the 1:1 uniqueness constraint on assembled_videos.narration_id
(matching the voice_narrations.script_id pattern).

Requires a live, already-migrated Postgres:
    docker compose up -d postgres
    cd backend && alembic upgrade head

Excluded from the default test run (see pyproject.toml `addopts`).
Run explicitly with: pytest -m db
"""

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.script import ScriptSegment
from app.domain.models.voice import VoiceSegment
from app.repositories.script_repository import ScriptRepository
from app.repositories.trend_repository import TrendRepository
from app.repositories.video_repository import VideoRepository
from app.repositories.voice_repository import VoiceRepository

pytestmark = pytest.mark.db


async def _make_narration(db_session: AsyncSession):
    trend_repository = TrendRepository(db_session)
    search = await trend_repository.create_search(keyword="video repo test", quota_units_used=0, videos=[])

    script_repository = ScriptRepository(db_session)
    script = await script_repository.create_script(
        search_id=search.id,
        video_idea="idea",
        title="title",
        hook="hook",
        segments=[ScriptSegment(text="beat", visual_description="visual")],
        cta="cta",
        ai_model_used="gemini-3.5-flash",
    )

    voice_repository = VoiceRepository(db_session)
    segments = [VoiceSegment(segment_index=0, audio_file_path="audio/x/segment_0.wav", duration_seconds=2.0)]
    return await voice_repository.create_narration(script_id=script.id, segments=segments, voice_name="Kore")


async def test_create_video_round_trips_fields(db_session: AsyncSession):
    narration = await _make_narration(db_session)
    repository = VideoRepository(db_session)

    result = await repository.create_video(
        narration_id=narration.id,
        video_file_path="videos/x/final.mp4",
        thumbnail_file_path="videos/x/thumbnail.png",
        duration_seconds=4.5,
    )

    assert result.id is not None
    assert result.narration_id == narration.id
    assert result.video_file_path == "videos/x/final.mp4"
    assert result.duration_seconds == 4.5


async def test_create_video_rejects_second_video_for_same_narration(db_session: AsyncSession):
    """Regression guard: assembled_videos.narration_id is 1:1 (unique index)."""
    narration = await _make_narration(db_session)
    repository = VideoRepository(db_session)

    await repository.create_video(
        narration_id=narration.id,
        video_file_path="videos/x/final.mp4",
        thumbnail_file_path="videos/x/thumbnail.png",
        duration_seconds=4.5,
    )

    with pytest.raises(IntegrityError):
        await repository.create_video(
            narration_id=narration.id,
            video_file_path="videos/x/final2.mp4",
            thumbnail_file_path="videos/x/thumbnail2.png",
            duration_seconds=4.5,
        )


async def test_get_video_by_narration_id_round_trips(db_session: AsyncSession):
    narration = await _make_narration(db_session)
    repository = VideoRepository(db_session)
    created = await repository.create_video(
        narration_id=narration.id,
        video_file_path="videos/x/final.mp4",
        thumbnail_file_path="videos/x/thumbnail.png",
        duration_seconds=4.5,
    )

    fetched = await repository.get_video_by_narration_id(narration.id)

    assert fetched is not None
    assert fetched.id == created.id


async def test_get_video_by_narration_id_returns_none_when_absent(db_session: AsyncSession):
    repository = VideoRepository(db_session)

    result = await repository.get_video_by_narration_id(uuid4())

    assert result is None


async def test_get_video_returns_none_for_unknown_id(db_session: AsyncSession):
    repository = VideoRepository(db_session)

    result = await repository.get_video(uuid4())

    assert result is None
