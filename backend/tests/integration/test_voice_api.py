"""Integration tests for the Voice Generation API surface, using a stubbed
service (not real Postgres/Gemini) to verify request/response wiring.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.dependencies import get_voice_service
from app.domain.models.voice import VoiceNarration as VoiceNarrationDomain
from app.domain.models.voice import VoiceSegment
from app.exceptions.script_exceptions import ScriptNotFoundError
from app.exceptions.voice_exceptions import NarrationAlreadyExistsError
from app.main import app


class StubVoiceService:
    def __init__(
        self, result: VoiceNarrationDomain | None = None, error: Exception | None = None
    ) -> None:
        self._result = result
        self._error = error

    async def generate(self, script_id, voice_name: str = "Kore") -> VoiceNarrationDomain:
        if self._error:
            raise self._error
        return self._result

    async def get_by_id(self, narration_id) -> VoiceNarrationDomain | None:
        if self._error:
            raise self._error
        return self._result


def _sample_narration(script_id=None) -> VoiceNarrationDomain:
    return VoiceNarrationDomain(
        id=uuid4(),
        script_id=script_id or uuid4(),
        segments=[
            VoiceSegment(segment_index=0, audio_file_path="audio/abc/segment_0.wav", duration_seconds=2.1),
            VoiceSegment(segment_index=1, audio_file_path="audio/abc/segment_1.wav", duration_seconds=3.4),
        ],
        voice_name="Kore",
        created_at=datetime.now(UTC),
    )


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


async def test_generate_voice_endpoint_returns_serialized_narration_with_urls():
    script_id = uuid4()
    app.dependency_overrides[get_voice_service] = lambda: StubVoiceService(
        result=_sample_narration(script_id)
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/scripts/{script_id}/voice", json={})

    assert response.status_code == 201
    body = response.json()
    assert len(body["segments"]) == 2
    assert body["segments"][0]["audio_url"] == "/media/audio/abc/segment_0.wav"
    assert body["segments"][0]["duration_seconds"] == 2.1
    assert body["voice_name"] == "Kore"


async def test_generate_voice_endpoint_accepts_custom_voice_name():
    app.dependency_overrides[get_voice_service] = lambda: StubVoiceService(
        result=_sample_narration()
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/scripts/{uuid4()}/voice", json={"voice_name": "Puck"}
        )

    assert response.status_code == 201


async def test_generate_voice_endpoint_returns_404_when_script_not_found():
    app.dependency_overrides[get_voice_service] = lambda: StubVoiceService(
        error=ScriptNotFoundError("No script found")
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/scripts/{uuid4()}/voice", json={})

    assert response.status_code == 404


async def test_generate_voice_endpoint_returns_409_when_already_generated():
    app.dependency_overrides[get_voice_service] = lambda: StubVoiceService(
        error=NarrationAlreadyExistsError("Already has a narration")
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/scripts/{uuid4()}/voice", json={})

    assert response.status_code == 409


async def test_get_voice_narration_endpoint_returns_serialized_narration():
    narration = _sample_narration()
    app.dependency_overrides[get_voice_service] = lambda: StubVoiceService(result=narration)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/voice-narrations/{narration.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(narration.id)


async def test_get_voice_narration_endpoint_returns_404_when_not_found():
    app.dependency_overrides[get_voice_service] = lambda: StubVoiceService(result=None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/voice-narrations/{uuid4()}")

    assert response.status_code == 404
