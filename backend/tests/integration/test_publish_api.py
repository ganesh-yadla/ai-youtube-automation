"""Integration tests for the Publishing Automation API surface, using a
stubbed service (not real YouTube OAuth/upload) to verify request/response
wiring.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.dependencies import get_publish_service
from app.domain.models.publish import YoutubeUpload as YoutubeUploadDomain
from app.exceptions.publish_exceptions import VideoAlreadyPublishedError
from app.exceptions.video_exceptions import VideoNotFoundError
from app.main import app


class StubPublishService:
    def __init__(self, result: YoutubeUploadDomain | None = None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error

    async def publish(self, video_id) -> YoutubeUploadDomain:
        if self._error:
            raise self._error
        return self._result

    async def get_by_video_id(self, video_id) -> YoutubeUploadDomain | None:
        if self._error:
            raise self._error
        return self._result


def _sample_upload(video_id=None) -> YoutubeUploadDomain:
    return YoutubeUploadDomain(
        id=uuid4(),
        video_id=video_id or uuid4(),
        youtube_video_id="dQw4w9WgXcQ",
        youtube_url="https://youtu.be/dQw4w9WgXcQ",
        uploaded_at=datetime.now(UTC),
    )


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


async def test_publish_video_endpoint_returns_serialized_upload():
    video_id = uuid4()
    app.dependency_overrides[get_publish_service] = lambda: StubPublishService(
        result=_sample_upload(video_id)
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/videos/{video_id}/publish")

    assert response.status_code == 201
    body = response.json()
    assert body["youtube_video_id"] == "dQw4w9WgXcQ"
    assert body["youtube_url"] == "https://youtu.be/dQw4w9WgXcQ"


async def test_publish_video_endpoint_returns_404_when_video_not_found():
    app.dependency_overrides[get_publish_service] = lambda: StubPublishService(
        error=VideoNotFoundError("No video found")
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/videos/{uuid4()}/publish")

    assert response.status_code == 404


async def test_publish_video_endpoint_returns_409_when_already_published():
    app.dependency_overrides[get_publish_service] = lambda: StubPublishService(
        error=VideoAlreadyPublishedError("Already published")
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/videos/{uuid4()}/publish")

    assert response.status_code == 409
