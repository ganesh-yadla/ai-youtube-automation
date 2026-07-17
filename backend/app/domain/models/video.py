"""Domain models for the Visual Generation feature."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AssembledVideo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    narration_id: UUID
    video_file_path: str
    thumbnail_file_path: str
    duration_seconds: float
    created_at: datetime
