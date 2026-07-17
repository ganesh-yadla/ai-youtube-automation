"""Integration tests for VoiceRepository against a REAL Postgres.

Guards the JSONB round-trip of `segments` and the 1:1 uniqueness
constraint on voice_narrations.script_id (unlike video_scripts, which is
1:many with its parent).

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
from app.repositories.voice_repository import VoiceRepository

pytestmark = pytest.mark.db


async def _make_script(db_session: AsyncSession):
    trend_repository = TrendRepository(db_session)
    search = await trend_repository.create_search(keyword="voice repo test", quota_units_used=0, videos=[])

    script_repository = ScriptRepository(db_session)
    return await script_repository.create_script(
        search_id=search.id,
        video_idea="idea",
        title="title",
        hook="hook",
        segments=[ScriptSegment(text="beat", visual_description="visual")],
        cta="cta",
        ai_model_used="gemini-3.5-flash",
    )


async def test_create_narration_round_trips_segments(db_session: AsyncSession):
    script = await _make_script(db_session)
    repository = VoiceRepository(db_session)
    segments = [
        VoiceSegment(segment_index=0, audio_file_path="audio/x/segment_0.wav", duration_seconds=2.1),
        VoiceSegment(segment_index=1, audio_file_path="audio/x/segment_1.wav", duration_seconds=3.4),
    ]

    result = await repository.create_narration(script_id=script.id, segments=segments, voice_name="Kore")

    assert result.id is not None
    assert len(result.segments) == 2
    assert result.segments[0].audio_file_path == "audio/x/segment_0.wav"
    assert result.segments[1].duration_seconds == 3.4


async def test_create_narration_rejects_second_narration_for_same_script(db_session: AsyncSession):
    """Regression guard: voice_narrations.script_id is 1:1 (unique index) -
    unlike video_scripts' 1:many with trend_searches.
    """
    script = await _make_script(db_session)
    repository = VoiceRepository(db_session)
    segment = [VoiceSegment(segment_index=0, audio_file_path="audio/x/segment_0.wav", duration_seconds=1.0)]

    await repository.create_narration(script_id=script.id, segments=segment, voice_name="Kore")

    with pytest.raises(IntegrityError):
        await repository.create_narration(script_id=script.id, segments=segment, voice_name="Kore")


async def test_get_narration_by_script_id_round_trips(db_session: AsyncSession):
    script = await _make_script(db_session)
    repository = VoiceRepository(db_session)
    segment = [VoiceSegment(segment_index=0, audio_file_path="audio/x/segment_0.wav", duration_seconds=1.0)]
    created = await repository.create_narration(script_id=script.id, segments=segment, voice_name="Kore")

    fetched = await repository.get_narration_by_script_id(script.id)

    assert fetched is not None
    assert fetched.id == created.id


async def test_get_narration_by_script_id_returns_none_when_absent(db_session: AsyncSession):
    repository = VoiceRepository(db_session)

    result = await repository.get_narration_by_script_id(uuid4())

    assert result is None


async def test_get_narration_returns_none_for_unknown_id(db_session: AsyncSession):
    repository = VoiceRepository(db_session)

    result = await repository.get_narration(uuid4())

    assert result is None
