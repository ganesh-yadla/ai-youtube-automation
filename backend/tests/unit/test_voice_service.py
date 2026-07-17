"""Unit tests for VoiceService, using a fake TTS client and both repositories.

Uses pytest's tmp_path for media_root (explicit constructor dependency, not
global settings) so test runs never write into the real backend/media
directory. The fake TTS client returns real, valid WAV bytes (not opaque
mock bytes) so the actual duration-parsing logic is genuinely exercised.
"""

import io
import wave
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.domain.models.script import Script as ScriptDomain
from app.domain.models.script import ScriptSegment
from app.domain.models.voice import VoiceNarration as VoiceNarrationDomain
from app.exceptions.script_exceptions import ScriptNotFoundError
from app.exceptions.voice_exceptions import NarrationAlreadyExistsError
from app.services.voice_service import VoiceService


def _make_wav_bytes(duration_seconds: float, rate: int = 24000) -> bytes:
    frame_count = int(duration_seconds * rate)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"\x00\x00" * frame_count)
    return buffer.getvalue()


class FakeTTSClient:
    def __init__(self, duration_per_call: float = 2.0) -> None:
        self.duration_per_call = duration_per_call
        self.calls: list[tuple[str, str]] = []

    async def generate_speech(self, text: str, voice_name: str = "Kore") -> bytes:
        self.calls.append((text, voice_name))
        return _make_wav_bytes(self.duration_per_call)


class FakeScriptRepository:
    def __init__(self, script: ScriptDomain | None) -> None:
        self.script = script

    async def get_script(self, script_id):
        return self.script


class FakeVoiceRepository:
    def __init__(self, existing: VoiceNarrationDomain | None = None) -> None:
        self.existing = existing
        self.saved_calls: list[dict] = []
        self.narrations_by_id: dict = {}

    async def create_narration(self, script_id, segments, voice_name) -> VoiceNarrationDomain:
        self.saved_calls.append({"script_id": script_id, "voice_name": voice_name})
        narration = VoiceNarrationDomain(
            id=uuid4(),
            script_id=script_id,
            segments=segments,
            voice_name=voice_name,
            created_at=datetime.now(UTC),
        )
        self.narrations_by_id[narration.id] = narration
        return narration

    async def get_narration(self, narration_id) -> VoiceNarrationDomain | None:
        return self.narrations_by_id.get(narration_id)

    async def get_narration_by_script_id(self, script_id) -> VoiceNarrationDomain | None:
        return self.existing


def _make_script(segment_count: int = 3) -> ScriptDomain:
    return ScriptDomain(
        id=uuid4(),
        search_id=uuid4(),
        video_idea="Top 5 AI tools",
        title="Test Title",
        hook="Test hook",
        segments=[
            ScriptSegment(text=f"Segment {i} text", visual_description=f"Visual {i}")
            for i in range(segment_count)
        ],
        cta="Follow for more",
        ai_model_used="gemini-3.5-flash",
        created_at=datetime.now(UTC),
    )


async def test_generate_creates_one_audio_file_per_segment(tmp_path):
    script = _make_script(segment_count=3)
    tts_client = FakeTTSClient(duration_per_call=1.5)
    service = VoiceService(
        tts_client, FakeScriptRepository(script), FakeVoiceRepository(), media_root=str(tmp_path)
    )

    result = await service.generate(script.id)

    assert len(result.segments) == 3
    assert len(tts_client.calls) == 3
    for index, segment in enumerate(result.segments):
        assert segment.segment_index == index
        assert segment.duration_seconds == 1.5
        assert (tmp_path / segment.audio_file_path).exists()


async def test_generate_calls_tts_with_each_segments_text(tmp_path):
    script = _make_script(segment_count=2)
    tts_client = FakeTTSClient()
    service = VoiceService(
        tts_client, FakeScriptRepository(script), FakeVoiceRepository(), media_root=str(tmp_path)
    )

    await service.generate(script.id, voice_name="Puck")

    called_texts = {text for text, _ in tts_client.calls}
    assert called_texts == {"Segment 0 text", "Segment 1 text"}
    assert all(voice == "Puck" for _, voice in tts_client.calls)


async def test_generate_raises_when_script_not_found(tmp_path):
    tts_client = FakeTTSClient()
    service = VoiceService(
        tts_client, FakeScriptRepository(None), FakeVoiceRepository(), media_root=str(tmp_path)
    )

    with pytest.raises(ScriptNotFoundError):
        await service.generate(uuid4())

    assert tts_client.calls == []


async def test_generate_raises_when_narration_already_exists(tmp_path):
    script = _make_script()
    existing = VoiceNarrationDomain(
        id=uuid4(), script_id=script.id, segments=[], voice_name="Kore", created_at=datetime.now(UTC)
    )
    tts_client = FakeTTSClient()
    service = VoiceService(
        tts_client,
        FakeScriptRepository(script),
        FakeVoiceRepository(existing=existing),
        media_root=str(tmp_path),
    )

    with pytest.raises(NarrationAlreadyExistsError):
        await service.generate(script.id)

    assert tts_client.calls == []


async def test_get_by_id_returns_persisted_narration(tmp_path):
    script = _make_script(segment_count=1)
    tts_client = FakeTTSClient()
    voice_repo = FakeVoiceRepository()
    service = VoiceService(
        tts_client, FakeScriptRepository(script), voice_repo, media_root=str(tmp_path)
    )

    created = await service.generate(script.id)
    fetched = await service.get_by_id(created.id)

    assert fetched is not None
    assert fetched.id == created.id


async def test_get_by_id_returns_none_when_not_found(tmp_path):
    service = VoiceService(
        FakeTTSClient(), FakeScriptRepository(None), FakeVoiceRepository(), media_root=str(tmp_path)
    )

    result = await service.get_by_id(uuid4())

    assert result is None
