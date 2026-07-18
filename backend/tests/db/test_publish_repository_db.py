"""Integration tests for PublishRepository against a REAL Postgres.

Guards the 1:1 uniqueness constraint on youtube_uploads.video_id.

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
from app.repositories.publish_repository import PublishRepository
from app.repositories.script_repository import ScriptRepository
from app.repositories.trend_repository import TrendRepository
from app.repositories.video_repository import VideoRepository
from app.repositories.voice_repository import VoiceRepository

pytestmark = pytest.mark.db


async def _make_video(db_session: AsyncSession):
    trend_repository = TrendRepository(db_session)
    search = await trend_repository.create_search(keyword="publish repo test", quota_units_used=0, videos=[])

    script_repository = ScriptRepository(db_session)
    script = await script_repository.create_script(
        search_id=search.id,
        video_idea="idea",
        title="title",
        hook="hook",
        segments=[ScriptSegment(text="beat", visual_description="visual")],
        cta="cta",
        ai_model_used="llama3.1:8b",
    )

    voice_repository = VoiceRepository(db_session)
    segments = [VoiceSegment(segment_index=0, audio_file_path="audio/x/segment_0.wav", duration_seconds=2.0)]
    narration = await voice_repository.create_narration(
        script_id=script.id, segments=segments, voice_name="Kore"
    )

    video_repository = VideoRepository(db_session)
    return await video_repository.create_video(
        narration_id=narration.id,
        video_file_path="videos/x/final.mp4",
        thumbnail_file_path="videos/x/thumbnail.png",
        duration_seconds=30.0,
    )


async def test_create_upload_round_trips_fields(db_session: AsyncSession):
    video = await _make_video(db_session)
    repository = PublishRepository(db_session)

    result = await repository.create_upload(
        video_id=video.id, youtube_video_id="dQw4w9WgXcQ", youtube_url="https://youtu.be/dQw4w9WgXcQ"
    )

    assert result.id is not None
    assert result.video_id == video.id
    assert result.youtube_video_id == "dQw4w9WgXcQ"


async def test_create_upload_rejects_second_upload_for_same_video(db_session: AsyncSession):
    """Regression guard: youtube_uploads.video_id is 1:1 (unique index)."""
    video = await _make_video(db_session)
    repository = PublishRepository(db_session)

    await repository.create_upload(
        video_id=video.id, youtube_video_id="dQw4w9WgXcQ", youtube_url="https://youtu.be/dQw4w9WgXcQ"
    )

    with pytest.raises(IntegrityError):
        await repository.create_upload(
            video_id=video.id, youtube_video_id="other-id", youtube_url="https://youtu.be/other-id"
        )


async def test_get_upload_by_video_id_round_trips(db_session: AsyncSession):
    video = await _make_video(db_session)
    repository = PublishRepository(db_session)
    created = await repository.create_upload(
        video_id=video.id, youtube_video_id="dQw4w9WgXcQ", youtube_url="https://youtu.be/dQw4w9WgXcQ"
    )

    fetched = await repository.get_upload_by_video_id(video.id)

    assert fetched is not None
    assert fetched.id == created.id


async def test_get_upload_by_video_id_returns_none_when_absent(db_session: AsyncSession):
    repository = PublishRepository(db_session)

    result = await repository.get_upload_by_video_id(uuid4())

    assert result is None
