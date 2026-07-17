"""Request/response wire schemas for the Visual Generation API. Kept
separate from domain models so the public API contract can evolve
independently of internal service/repository shapes.

Built explicitly in the router (not via model_validate/from_attributes)
because video_url/thumbnail_url are transforms of the domain's stored
relative file paths, not plain attribute pass-throughs.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.domain.models.video import AssembledVideo


class AssembledVideoResponse(BaseModel):
    id: UUID
    narration_id: UUID
    video_url: str
    thumbnail_url: str
    duration_seconds: float
    created_at: datetime

    @classmethod
    def from_domain(cls, video: AssembledVideo) -> "AssembledVideoResponse":
        return cls(
            id=video.id,
            narration_id=video.narration_id,
            video_url=f"/media/{video.video_file_path}",
            thumbnail_url=f"/media/{video.thumbnail_file_path}",
            duration_seconds=video.duration_seconds,
            created_at=video.created_at,
        )
