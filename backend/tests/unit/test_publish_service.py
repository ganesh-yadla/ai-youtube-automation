"""Unit tests for PublishService, using fake upload client and repositories.

Uses pytest's tmp_path for media_root (explicit constructor dependency, not
global settings) so test runs never touch the real backend/media directory.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.domain.models.publish import YoutubeUpload as YoutubeUploadDomain
from app.domain.models.script import Script as ScriptDomain
from app.domain.models.script import ScriptSegment
from app.domain.models.video import AssembledVideo as AssembledVideoDomain
from app.domain.models.voice import VoiceNarration as VoiceNarrationDomain
from app.domain.models.voice import VoiceSegment
from app.exceptions.publish_exceptions import VideoAlreadyPublishedError
from app.exceptions.script_exceptions import ScriptNotFoundError
from app.exceptions.video_exceptions import VideoNotFoundError
from app.exceptions.voice_exceptions import NarrationNotFoundError
from app.services.publish_service import PublishService


class FakeUploadClient:
    def __init__(self, youtube_video_id: str = "abc123") -> None:
        self.youtube_video_id = youtube_video_id
        self.calls: list[dict] = []

    async def upload_video(
        self, video_path, title, description, tags, category_id, thumbnail_path=None
    ) -> str:
        self.calls.append(
            {
                "video_path": video_path,
                "title": title,
                "description": description,
                "tags": tags,
                "category_id": category_id,
                "thumbnail_path": thumbnail_path,
            }
        )
        return self.youtube_video_id


class FakeVideoRepository:
    def __init__(self, video: AssembledVideoDomain | None) -> None:
        self.video = video

    async def get_video(self, video_id):
        if self.video and self.video.id == video_id:
            return self.video
        return None


class FakeVoiceRepository:
    def __init__(self, narration: VoiceNarrationDomain | None) -> None:
        self.narration = narration

    async def get_narration(self, narration_id):
        if self.narration and self.narration.id == narration_id:
            return self.narration
        return None


class FakeScriptRepository:
    def __init__(self, script: ScriptDomain | None) -> None:
        self.script = script

    async def get_script(self, script_id):
        if self.script and self.script.id == script_id:
            return self.script
        return None


class FakePublishRepository:
    def __init__(self, existing: YoutubeUploadDomain | None = None) -> None:
        self.existing = existing
        self.create_calls: list[dict] = []

    async def create_upload(self, video_id, youtube_video_id, youtube_url) -> YoutubeUploadDomain:
        self.create_calls.append(
            {"video_id": video_id, "youtube_video_id": youtube_video_id, "youtube_url": youtube_url}
        )
        return YoutubeUploadDomain(
            id=uuid4(),
            video_id=video_id,
            youtube_video_id=youtube_video_id,
            youtube_url=youtube_url,
            uploaded_at=datetime.now(UTC),
        )

    async def get_upload_by_video_id(self, video_id):
        return self.existing


def _make_script() -> ScriptDomain:
    return ScriptDomain(
        id=uuid4(),
        search_id=uuid4(),
        video_idea="AI tools for productivity",
        title="This AI Tool Saves Hours",
        hook="Still doing this manually?",
        segments=[ScriptSegment(text="beat", visual_description="visual")],
        cta="Try it today!",
        ai_model_used="llama3.1:8b",
        created_at=datetime.now(UTC),
    )


def _make_narration(script_id) -> VoiceNarrationDomain:
    segments = [VoiceSegment(segment_index=0, audio_file_path="audio/x/segment_0.wav", duration_seconds=2.0)]
    return VoiceNarrationDomain(
        id=uuid4(), script_id=script_id, segments=segments, voice_name="Kore", created_at=datetime.now(UTC)
    )


def _make_video(narration_id) -> AssembledVideoDomain:
    return AssembledVideoDomain(
        id=uuid4(),
        narration_id=narration_id,
        video_file_path="videos/x/final.mp4",
        thumbnail_file_path="videos/x/thumbnail.png",
        duration_seconds=30.0,
        created_at=datetime.now(UTC),
    )


def _make_service(
    tmp_path,
    video: AssembledVideoDomain | None,
    narration: VoiceNarrationDomain | None,
    script: ScriptDomain | None,
    existing_upload: YoutubeUploadDomain | None = None,
):
    upload_client = FakeUploadClient()
    publish_repo = FakePublishRepository(existing=existing_upload)
    service = PublishService(
        upload_client=upload_client,
        video_repository=FakeVideoRepository(video),
        voice_repository=FakeVoiceRepository(narration),
        script_repository=FakeScriptRepository(script),
        publish_repository=publish_repo,
        media_root=str(tmp_path),
        category_id="28",
    )
    return service, upload_client, publish_repo


async def test_publish_uploads_with_metadata_from_script(tmp_path):
    script = _make_script()
    narration = _make_narration(script.id)
    video = _make_video(narration.id)
    service, upload_client, publish_repo = _make_service(tmp_path, video, narration, script)

    result = await service.publish(video.id)

    assert len(upload_client.calls) == 1
    call = upload_client.calls[0]
    assert call["title"] == script.title
    assert script.hook in call["description"]
    assert script.cta in call["description"]
    assert call["category_id"] == "28"
    assert result.youtube_video_id == "abc123"
    assert result.youtube_url == "https://youtu.be/abc123"
    assert publish_repo.create_calls[0]["video_id"] == video.id
    assert "Ganuverse" in call["tags"]
    assert "Saves" in call["tags"] or "saves" in [t.lower() for t in call["tags"]]


def test_build_tags_derives_keywords_from_title_and_idea_not_static_list():
    tags = PublishService._build_tags(
        title="This AI Tool Saves Hours", video_idea="AI tools for productivity"
    )

    assert tags[:3] == ["Shorts", "AI Tools", "Ganuverse"]
    assert "Saves" in tags
    assert "Hours" in tags
    assert "productivity" in tags
    # stop words and short/duplicate tokens shouldn't pollute the tag list
    assert "for" not in tags
    assert tags.count("AI") <= 1


async def test_publish_raises_when_video_not_found(tmp_path):
    service, upload_client, _ = _make_service(tmp_path, video=None, narration=None, script=None)

    with pytest.raises(VideoNotFoundError):
        await service.publish(uuid4())

    assert upload_client.calls == []


async def test_publish_raises_when_already_published(tmp_path):
    script = _make_script()
    narration = _make_narration(script.id)
    video = _make_video(narration.id)
    existing = YoutubeUploadDomain(
        id=uuid4(),
        video_id=video.id,
        youtube_video_id="already-there",
        youtube_url="https://youtu.be/already-there",
        uploaded_at=datetime.now(UTC),
    )
    service, upload_client, _ = _make_service(tmp_path, video, narration, script, existing_upload=existing)

    with pytest.raises(VideoAlreadyPublishedError):
        await service.publish(video.id)

    assert upload_client.calls == []


async def test_publish_raises_when_narration_not_found(tmp_path):
    video = _make_video(uuid4())
    service, upload_client, _ = _make_service(tmp_path, video, narration=None, script=None)

    with pytest.raises(NarrationNotFoundError):
        await service.publish(video.id)

    assert upload_client.calls == []


async def test_publish_raises_when_script_not_found(tmp_path):
    narration = _make_narration(uuid4())
    video = _make_video(narration.id)
    service, upload_client, _ = _make_service(tmp_path, video, narration, script=None)

    with pytest.raises(ScriptNotFoundError):
        await service.publish(video.id)

    assert upload_client.calls == []


async def test_get_by_video_id_returns_existing_upload(tmp_path):
    script = _make_script()
    narration = _make_narration(script.id)
    video = _make_video(narration.id)
    service, _, _ = _make_service(tmp_path, video, narration, script)

    created = await service.publish(video.id)
    fetched_service, _, _ = _make_service(tmp_path, video, narration, script, existing_upload=created)
    fetched = await fetched_service.get_by_video_id(video.id)

    assert fetched is not None
    assert fetched.youtube_video_id == created.youtube_video_id


async def test_get_by_video_id_returns_none_when_not_found(tmp_path):
    service, _, _ = _make_service(tmp_path, video=None, narration=None, script=None)

    result = await service.get_by_video_id(uuid4())

    assert result is None
