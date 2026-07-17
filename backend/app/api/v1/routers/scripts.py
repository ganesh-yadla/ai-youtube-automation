"""Script Agent API routes. Stays thin: parse request, call service, map
result to a response schema. No business logic or DB access here.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.v1.dependencies import get_script_service, get_voice_service
from app.api.v1.schemas.script import ScriptResponse
from app.api.v1.schemas.voice import VoiceGenerationRequest, VoiceNarrationResponse
from app.exceptions.script_exceptions import ScriptNotFoundError
from app.services.script_service import ScriptService
from app.services.voice_service import VoiceService

router = APIRouter(prefix="/scripts", tags=["scripts"])


@router.get("/{script_id}", response_model=ScriptResponse)
async def get_script(
    script_id: UUID,
    service: ScriptService = Depends(get_script_service),
) -> ScriptResponse:
    result = await service.get_by_id(script_id)
    if result is None:
        raise ScriptNotFoundError(f"No script found with id '{script_id}'")
    return ScriptResponse.model_validate(result)


@router.post(
    "/{script_id}/voice",
    response_model=VoiceNarrationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_voice(
    script_id: UUID,
    request: VoiceGenerationRequest,
    service: VoiceService = Depends(get_voice_service),
) -> VoiceNarrationResponse:
    result = await service.generate(script_id, voice_name=request.voice_name)
    return VoiceNarrationResponse.from_domain(result)
