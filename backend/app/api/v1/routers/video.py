"""Visual Generation read API. Stays thin: parse request, call service, map
result to a response schema. No business logic or DB access here.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.v1.dependencies import get_publish_service, get_video_service
from app.api.v1.schemas.publish import YoutubeUploadResponse
from app.api.v1.schemas.video import AssembledVideoResponse
from app.exceptions.video_exceptions import VideoNotFoundError
from app.services.publish_service import PublishService
from app.services.video_service import VideoService

router = APIRouter(prefix="/videos", tags=["video"])


@router.get("/{video_id}", response_model=AssembledVideoResponse)
async def get_video(
    video_id: UUID,
    service: VideoService = Depends(get_video_service),
) -> AssembledVideoResponse:
    result = await service.get_by_id(video_id)
    if result is None:
        raise VideoNotFoundError(f"No assembled video found with id '{video_id}'")
    return AssembledVideoResponse.from_domain(result)


@router.post(
    "/{video_id}/publish",
    response_model=YoutubeUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def publish_video(
    video_id: UUID,
    service: PublishService = Depends(get_publish_service),
) -> YoutubeUploadResponse:
    result = await service.publish(video_id)
    return YoutubeUploadResponse.from_domain(result)
