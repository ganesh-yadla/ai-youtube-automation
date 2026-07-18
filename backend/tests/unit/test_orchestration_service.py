"""Unit tests for OrchestrationService, verifying it chains the three
underlying services with the right arguments and returns their combined
result - it has no logic of its own to test beyond that wiring.
"""

from datetime import UTC, datetime
from uuid import uuid4

from app.domain.models.script import Script as ScriptDomain
from app.domain.models.script import ScriptSegment
from app.domain.models.video import AssembledVideo as AssembledVideoDomain
from app.domain.models.voice import VoiceNarration as VoiceNarrationDomain
from app.domain.models.voice import VoiceSegment
from app.services.orchestration_service import OrchestrationService


class FakeScriptService:
    def __init__(self, script: ScriptDomain) -> None:
        self.script = script
        self.calls: list[dict] = []

    async def generate(self, search_id, video_idea=None) -> ScriptDomain:
        self.calls.append({"search_id": search_id, "video_idea": video_idea})
        return self.script


class FakeVoiceService:
    def __init__(self, narration: VoiceNarrationDomain) -> None:
        self.narration = narration
        self.calls: list[dict] = []

    async def generate(self, script_id, voice_name="Kore") -> VoiceNarrationDomain:
        self.calls.append({"script_id": script_id, "voice_name": voice_name})
        return self.narration


class FakeVideoService:
    def __init__(self, video: AssembledVideoDomain) -> None:
        self.video = video
        self.calls: list[dict] = []

    async def generate(self, narration_id) -> AssembledVideoDomain:
        self.calls.append({"narration_id": narration_id})
        return self.video


def _make_script() -> ScriptDomain:
    return ScriptDomain(
        id=uuid4(),
        search_id=uuid4(),
        video_idea="idea",
        title="title",
        hook="hook",
        segments=[ScriptSegment(text=f"beat {i}", visual_description=f"visual {i}") for i in range(4)],
        cta="cta",
        ai_model_used="llama3.1:8b",
        created_at=datetime.now(UTC),
    )


def _make_narration(script_id) -> VoiceNarrationDomain:
    return VoiceNarrationDomain(
        id=uuid4(),
        script_id=script_id,
        segments=[
            VoiceSegment(segment_index=0, audio_file_path="audio/x/segment_0.wav", duration_seconds=2.0)
        ],
        voice_name="Kore",
        created_at=datetime.now(UTC),
    )


def _make_video(narration_id) -> AssembledVideoDomain:
    return AssembledVideoDomain(
        id=uuid4(),
        narration_id=narration_id,
        video_file_path="videos/x/final.mp4",
        thumbnail_file_path="videos/x/thumbnail.png",
        duration_seconds=20.0,
        created_at=datetime.now(UTC),
    )


async def test_generate_video_chains_script_voice_and_video_services():
    script = _make_script()
    narration = _make_narration(script.id)
    video = _make_video(narration.id)

    script_service = FakeScriptService(script)
    voice_service = FakeVoiceService(narration)
    video_service = FakeVideoService(video)
    service = OrchestrationService(script_service, voice_service, video_service)

    search_id = uuid4()
    result_script, result_video = await service.generate_video(search_id, video_idea="my idea")

    assert result_script == script
    assert result_video == video
    assert script_service.calls == [{"search_id": search_id, "video_idea": "my idea"}]
    assert voice_service.calls == [{"script_id": script.id, "voice_name": "Kore"}]
    assert video_service.calls == [{"narration_id": narration.id}]


async def test_generate_video_passes_none_video_idea_through():
    script = _make_script()
    narration = _make_narration(script.id)
    video = _make_video(narration.id)

    script_service = FakeScriptService(script)
    service = OrchestrationService(script_service, FakeVoiceService(narration), FakeVideoService(video))

    await service.generate_video(uuid4())

    assert script_service.calls[0]["video_idea"] is None
