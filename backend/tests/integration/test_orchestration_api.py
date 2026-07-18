"""Integration tests for the combined generate-video API surface, using a
stubbed service (not real script/voice/visual generation) to verify
request/response wiring.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.dependencies import get_orchestration_service
from app.domain.models.script import Script as ScriptDomain
from app.domain.models.script import ScriptSegment
from app.domain.models.video import AssembledVideo as AssembledVideoDomain
from app.exceptions.script_exceptions import TrendAnalysisRequiredError
from app.exceptions.trend_exceptions import TrendSearchNotFoundError
from app.main import app


class StubOrchestrationService:
    def __init__(
        self,
        script: ScriptDomain | None = None,
        video: AssembledVideoDomain | None = None,
        error: Exception | None = None,
    ) -> None:
        self._script = script
        self._video = video
        self._error = error

    async def generate_video(self, search_id, video_idea=None):
        if self._error:
            raise self._error
        return self._script, self._video


def _sample_script(search_id) -> ScriptDomain:
    return ScriptDomain(
        id=uuid4(),
        search_id=search_id,
        video_idea="idea",
        title="A Great Title",
        hook="hook",
        segments=[ScriptSegment(text="beat", visual_description="visual")],
        cta="cta",
        ai_model_used="llama3.1:8b",
        created_at=datetime.now(UTC),
    )


def _sample_video() -> AssembledVideoDomain:
    return AssembledVideoDomain(
        id=uuid4(),
        narration_id=uuid4(),
        video_file_path="videos/x/final.mp4",
        thumbnail_file_path="videos/x/thumbnail.png",
        duration_seconds=20.0,
        created_at=datetime.now(UTC),
    )


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


async def test_generate_video_endpoint_returns_script_and_video():
    search_id = uuid4()
    script = _sample_script(search_id)
    video = _sample_video()
    app.dependency_overrides[get_orchestration_service] = lambda: StubOrchestrationService(
        script=script, video=video
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/trends/{search_id}/generate-video", json={})

    assert response.status_code == 201
    body = response.json()
    assert body["script"]["title"] == "A Great Title"
    assert body["video"]["video_url"] == "/media/videos/x/final.mp4"
    assert body["video"]["thumbnail_url"] == "/media/videos/x/thumbnail.png"


async def test_generate_video_endpoint_returns_404_when_search_not_found():
    app.dependency_overrides[get_orchestration_service] = lambda: StubOrchestrationService(
        error=TrendSearchNotFoundError("No trend search found")
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/trends/{uuid4()}/generate-video", json={})

    assert response.status_code == 404


async def test_generate_video_endpoint_returns_400_when_analysis_missing():
    app.dependency_overrides[get_orchestration_service] = lambda: StubOrchestrationService(
        error=TrendAnalysisRequiredError("Not analyzed yet")
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/trends/{uuid4()}/generate-video", json={})

    assert response.status_code == 400
