"""Unit tests for VideoService, using fake image/assembler clients and both
repositories.

Uses pytest's tmp_path for media_root (explicit constructor dependency, not
global settings) so test runs never write into the real backend/media
directory. The fake image client returns real bytes and the fake assembler
records what it was asked to render, without needing the real ffmpeg binary.
"""

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from app.domain.models.script import Script as ScriptDomain
from app.domain.models.script import ScriptSegment
from app.domain.models.video import AssembledVideo as AssembledVideoDomain
from app.domain.models.voice import VoiceNarration as VoiceNarrationDomain
from app.domain.models.voice import VoiceSegment
from app.exceptions.script_exceptions import ScriptNotFoundError
from app.exceptions.video_exceptions import VideoAlreadyExistsError
from app.exceptions.voice_exceptions import NarrationNotFoundError
from app.infrastructure.external.interfaces.video_assembler import VideoScene
from app.services.video_service import VideoService


class FakeImageClient:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate_image(self, prompt: str, aspect_ratio: str = "9:16") -> bytes:
        self.prompts.append(prompt)
        return b"fake-png-bytes"


class FakeVideoAssembler:
    def __init__(self) -> None:
        self.calls: list[tuple[list[VideoScene], str]] = []

    async def assemble(self, scenes: list[VideoScene], output_path: str) -> None:
        self.calls.append((scenes, output_path))


class FakeScriptRepository:
    def __init__(self, script: ScriptDomain | None) -> None:
        self.script = script

    async def get_script(self, script_id):
        return self.script


class FakeVoiceRepository:
    def __init__(self, narration: VoiceNarrationDomain | None) -> None:
        self.narration = narration

    async def get_narration(self, narration_id):
        if self.narration and self.narration.id == narration_id:
            return self.narration
        return None


class FakeVideoRepository:
    def __init__(self, existing: AssembledVideoDomain | None = None) -> None:
        self.existing = existing
        self.create_calls: list[dict] = []
        self.videos_by_id: dict = {}

    async def create_video(
        self, narration_id, video_file_path, thumbnail_file_path, duration_seconds
    ) -> AssembledVideoDomain:
        self.create_calls.append(
            {
                "narration_id": narration_id,
                "video_file_path": video_file_path,
                "thumbnail_file_path": thumbnail_file_path,
                "duration_seconds": duration_seconds,
            }
        )
        video = AssembledVideoDomain(
            id=uuid4(),
            narration_id=narration_id,
            video_file_path=video_file_path,
            thumbnail_file_path=thumbnail_file_path,
            duration_seconds=duration_seconds,
            created_at=datetime.now(UTC),
        )
        self.videos_by_id[video.id] = video
        return video

    async def get_video(self, video_id):
        return self.videos_by_id.get(video_id)

    async def get_video_by_narration_id(self, narration_id):
        return self.existing


def _make_script(segment_count: int = 2) -> ScriptDomain:
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


def _make_narration(script_id, segment_count: int = 2) -> VoiceNarrationDomain:
    return VoiceNarrationDomain(
        id=uuid4(),
        script_id=script_id,
        segments=[
            VoiceSegment(
                segment_index=i,
                audio_file_path=f"audio/{script_id}/segment_{i}.wav",
                duration_seconds=2.0,
            )
            for i in range(segment_count)
        ],
        voice_name="Kore",
        created_at=datetime.now(UTC),
    )


def _make_service(
    tmp_path, script: ScriptDomain | None, narration: VoiceNarrationDomain | None, video_repo=None
) -> tuple[VideoService, FakeImageClient, FakeVideoAssembler, FakeVideoRepository]:
    image_client = FakeImageClient()
    assembler = FakeVideoAssembler()
    video_repo = video_repo or FakeVideoRepository()
    service = VideoService(
        image_client=image_client,
        video_assembler=assembler,
        script_repository=FakeScriptRepository(script),
        voice_repository=FakeVoiceRepository(narration),
        video_repository=video_repo,
        media_root=str(tmp_path),
    )
    return service, image_client, assembler, video_repo


async def test_generate_creates_one_image_per_segment_plus_thumbnail(tmp_path):
    script = _make_script(segment_count=3)
    narration = _make_narration(script.id, segment_count=3)
    service, image_client, _, _ = _make_service(tmp_path, script, narration)

    await service.generate(narration.id)

    assert len(image_client.prompts) == 4  # 3 segments + 1 thumbnail
    assert image_client.prompts[:3] == ["Visual 0", "Visual 1", "Visual 2"]


async def test_generate_assembles_scenes_with_matching_audio_and_captions(tmp_path):
    script = _make_script(segment_count=2)
    narration = _make_narration(script.id, segment_count=2)
    service, _, assembler, _ = _make_service(tmp_path, script, narration)

    await service.generate(narration.id)

    assert len(assembler.calls) == 1
    scenes, _output_path = assembler.calls[0]
    assert len(scenes) == 2
    assert scenes[0].caption_text == "Segment 0 text"
    expected_audio_path = tmp_path / narration.segments[0].audio_file_path
    assert Path(scenes[0].audio_path) == expected_audio_path


async def test_generate_persists_video_with_summed_duration(tmp_path):
    script = _make_script(segment_count=2)
    narration = _make_narration(script.id, segment_count=2)
    service, _, _, video_repo = _make_service(tmp_path, script, narration)

    result = await service.generate(narration.id)

    assert result.duration_seconds == 4.0
    assert video_repo.create_calls[0]["narration_id"] == narration.id


async def test_generate_raises_when_narration_not_found(tmp_path):
    service, image_client, assembler, _ = _make_service(tmp_path, script=None, narration=None)

    with pytest.raises(NarrationNotFoundError):
        await service.generate(uuid4())

    assert image_client.prompts == []
    assert assembler.calls == []


async def test_generate_raises_when_video_already_exists(tmp_path):
    script = _make_script()
    narration = _make_narration(script.id)
    existing = AssembledVideoDomain(
        id=uuid4(),
        narration_id=narration.id,
        video_file_path="videos/x/final.mp4",
        thumbnail_file_path="videos/x/thumbnail.png",
        duration_seconds=4.0,
        created_at=datetime.now(UTC),
    )
    service, image_client, assembler, _ = _make_service(
        tmp_path, script, narration, video_repo=FakeVideoRepository(existing=existing)
    )

    with pytest.raises(VideoAlreadyExistsError):
        await service.generate(narration.id)

    assert image_client.prompts == []
    assert assembler.calls == []


async def test_generate_raises_when_script_not_found(tmp_path):
    narration = _make_narration(uuid4())
    service, image_client, assembler, _ = _make_service(tmp_path, script=None, narration=narration)

    with pytest.raises(ScriptNotFoundError):
        await service.generate(narration.id)

    assert image_client.prompts == []
    assert assembler.calls == []


async def test_get_by_id_returns_persisted_video(tmp_path):
    script = _make_script(segment_count=1)
    narration = _make_narration(script.id, segment_count=1)
    service, _, _, _ = _make_service(tmp_path, script, narration)

    created = await service.generate(narration.id)
    fetched = await service.get_by_id(created.id)

    assert fetched is not None


async def test_get_by_id_returns_none_when_not_found(tmp_path):
    service, _, _, _ = _make_service(tmp_path, script=None, narration=None)

    result = await service.get_by_id(uuid4())

    assert result is None
