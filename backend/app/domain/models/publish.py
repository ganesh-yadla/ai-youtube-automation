"""Domain models for the Publishing Automation feature."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class YoutubeUpload(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    video_id: UUID
    youtube_video_id: str
    youtube_url: str
    uploaded_at: datetime
