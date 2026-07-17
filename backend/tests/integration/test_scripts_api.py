"""Integration tests for the Script Agent API surface, using a stubbed
service (not real Postgres/Claude) to verify request/response wiring.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.dependencies import get_script_service
from app.domain.models.script import Script as ScriptDomain
from app.domain.models.script import ScriptSegment
from app.exceptions.script_exceptions import TrendAnalysisRequiredError
from app.exceptions.trend_exceptions import TrendSearchNotFoundError
from app.main import app


class StubScriptService:
    def __init__(self, result: ScriptDomain | None = None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error

    async def generate(self, search_id, video_idea: str | None = None) -> ScriptDomain:
        if self._error:
            raise self._error
        return self._result

    async def get_by_id(self, script_id) -> ScriptDomain | None:
        if self._error:
            raise self._error
        return self._result


def _sample_script(search_id=None) -> ScriptDomain:
    return ScriptDomain(
        id=uuid4(),
        search_id=search_id or uuid4(),
        video_idea="Top 5 AI tools for beginners in 2026",
        title="5 AI Tools Beginners NEED in 2026",
        hook="You're wasting hours doing this manually.",
        segments=[
            ScriptSegment(text="Here are 5 AI tools...", visual_description="Text overlay on gradient"),
            ScriptSegment(text="Number one is...", visual_description="Icon of tool 1"),
        ],
        cta="Follow for more AI tool breakdowns.",
        ai_model_used="claude-opus-4-8",
        created_at=datetime.now(UTC),
    )


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


async def test_generate_script_endpoint_returns_serialized_script():
    search_id = uuid4()
    app.dependency_overrides[get_script_service] = lambda: StubScriptService(
        result=_sample_script(search_id)
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/trends/{search_id}/script", json={})

    assert response.status_code == 201
    body = response.json()
    assert body["video_idea"] == "Top 5 AI tools for beginners in 2026"
    assert len(body["segments"]) == 2
    assert body["segments"][0]["text"] == "Here are 5 AI tools..."


async def test_generate_script_endpoint_accepts_explicit_video_idea():
    search_id = uuid4()
    app.dependency_overrides[get_script_service] = lambda: StubScriptService(
        result=_sample_script(search_id)
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/trends/{search_id}/script", json={"video_idea": "My custom idea"}
        )

    assert response.status_code == 201


async def test_generate_script_endpoint_returns_404_when_search_not_found():
    app.dependency_overrides[get_script_service] = lambda: StubScriptService(
        error=TrendSearchNotFoundError("No trend search found")
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/trends/{uuid4()}/script", json={})

    assert response.status_code == 404


async def test_generate_script_endpoint_returns_400_when_analysis_missing():
    app.dependency_overrides[get_script_service] = lambda: StubScriptService(
        error=TrendAnalysisRequiredError("Not analyzed yet")
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/trends/{uuid4()}/script", json={})

    assert response.status_code == 400


async def test_get_script_endpoint_returns_serialized_script():
    script = _sample_script()
    app.dependency_overrides[get_script_service] = lambda: StubScriptService(result=script)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/scripts/{script.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(script.id)
    assert body["title"] == script.title


async def test_get_script_endpoint_returns_404_when_not_found():
    app.dependency_overrides[get_script_service] = lambda: StubScriptService(result=None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/scripts/{uuid4()}")

    assert response.status_code == 404
