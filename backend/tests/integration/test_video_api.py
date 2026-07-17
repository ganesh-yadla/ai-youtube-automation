"""Integration tests for the Visual Generation API surface, using a stubbed
service (not real Postgres/Gemini/ffmpeg) to verify request/response wiring.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.dependencies import get_video_service
from app.domain.models.video import AssembledVideo as AssembledVideoDomain
from app.exceptions.script_exceptions import ScriptNotFoundError
from app.exceptions.video_exceptions import VideoAlreadyExistsError
from app.exceptions.voice_exceptions import NarrationNotFoundError
from app.main import app


class StubVideoService:
    def __init__(self, result: AssembledVideoDomain | None = None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error

    async def generate(self, narration_id) -> AssembledVideoDomain:
        if self._error:
            raise self._error
        return self._result

    async def get_by_id(self, video_id) -> AssembledVideoDomain | None:
        if self._error:
            raise self._error
        return self._result


def _sample_video(narration_id=None) -> AssembledVideoDomain:
    return AssembledVideoDomain(
        id=uuid4(),
        narration_id=narration_id or uuid4(),
        video_file_path="videos/abc/final.mp4",
        thumbnail_file_path="videos/abc/thumbnail.png",
        duration_seconds=12.5,
        created_at=datetime.now(UTC),
    )


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


async def test_generate_video_endpoint_returns_serialized_video_with_urls():
    narration_id = uuid4()
    app.dependency_overrides[get_video_service] = lambda: StubVideoService(result=_sample_video(narration_id))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/voice-narrations/{narration_id}/video")

    assert response.status_code == 201
    body = response.json()
    assert body["video_url"] == "/media/videos/abc/final.mp4"
    assert body["thumbnail_url"] == "/media/videos/abc/thumbnail.png"
    assert body["duration_seconds"] == 12.5


async def test_generate_video_endpoint_returns_404_when_narration_not_found():
    app.dependency_overrides[get_video_service] = lambda: StubVideoService(
        error=NarrationNotFoundError("No narration found")
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/voice-narrations/{uuid4()}/video")

    assert response.status_code == 404


async def test_generate_video_endpoint_returns_404_when_script_not_found():
    app.dependency_overrides[get_video_service] = lambda: StubVideoService(
        error=ScriptNotFoundError("No script found")
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/voice-narrations/{uuid4()}/video")

    assert response.status_code == 404


async def test_generate_video_endpoint_returns_409_when_already_generated():
    app.dependency_overrides[get_video_service] = lambda: StubVideoService(
        error=VideoAlreadyExistsError("Already has a video")
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/voice-narrations/{uuid4()}/video")

    assert response.status_code == 409


async def test_get_video_endpoint_returns_serialized_video():
    video = _sample_video()
    app.dependency_overrides[get_video_service] = lambda: StubVideoService(result=video)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/videos/{video.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(video.id)


async def test_get_video_endpoint_returns_404_when_not_found():
    app.dependency_overrides[get_video_service] = lambda: StubVideoService(result=None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/videos/{uuid4()}")

    assert response.status_code == 404
