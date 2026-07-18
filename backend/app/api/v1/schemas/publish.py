"""Request/response wire schemas for the Publishing Automation API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.domain.models.publish import YoutubeUpload


class YoutubeUploadResponse(BaseModel):
    id: UUID
    video_id: UUID
    youtube_video_id: str
    youtube_url: str
    uploaded_at: datetime

    @classmethod
    def from_domain(cls, upload: YoutubeUpload) -> "YoutubeUploadResponse":
        return cls(
            id=upload.id,
            video_id=upload.video_id,
            youtube_video_id=upload.youtube_video_id,
            youtube_url=upload.youtube_url,
            uploaded_at=upload.uploaded_at,
        )
