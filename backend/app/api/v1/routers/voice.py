"""Voice Generation API routes. Stays thin: parse request, call service,
map result to a response schema. No business logic or DB access here.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.v1.dependencies import get_video_service, get_voice_service
from app.api.v1.schemas.video import AssembledVideoResponse
from app.api.v1.schemas.voice import VoiceNarrationResponse
from app.exceptions.voice_exceptions import NarrationNotFoundError
from app.services.video_service import VideoService
from app.services.voice_service import VoiceService

router = APIRouter(prefix="/voice-narrations", tags=["voice"])


@router.get("/{narration_id}", response_model=VoiceNarrationResponse)
async def get_voice_narration(
    narration_id: UUID,
    service: VoiceService = Depends(get_voice_service),
) -> VoiceNarrationResponse:
    result = await service.get_by_id(narration_id)
    if result is None:
        raise NarrationNotFoundError(f"No voice narration found with id '{narration_id}'")
    return VoiceNarrationResponse.from_domain(result)


@router.post(
    "/{narration_id}/video",
    response_model=AssembledVideoResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_video(
    narration_id: UUID,
    service: VideoService = Depends(get_video_service),
) -> AssembledVideoResponse:
    result = await service.generate(narration_id)
    return AssembledVideoResponse.from_domain(result)
