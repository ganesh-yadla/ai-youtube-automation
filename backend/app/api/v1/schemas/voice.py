"""Request/response wire schemas for the Voice Generation API. Kept
separate from domain models so the public API contract can evolve
independently of internal service/repository shapes.

Built explicitly in the router (not via model_validate/from_attributes)
because audio_url is a transform of the domain's audio_file_path - a
relative-path-to-servable-URL mapping, not a plain attribute pass-through.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.models.voice import VoiceNarration
from app.infrastructure.external.interfaces.tts_client import DEFAULT_VOICE_NAME


class VoiceGenerationRequest(BaseModel):
    voice_name: str = Field(default=DEFAULT_VOICE_NAME, max_length=50)


class VoiceSegmentResponse(BaseModel):
    segment_index: int
    audio_url: str
    duration_seconds: float


class VoiceNarrationResponse(BaseModel):
    id: UUID
    script_id: UUID
    segments: list[VoiceSegmentResponse]
    voice_name: str
    created_at: datetime

    @classmethod
    def from_domain(cls, narration: VoiceNarration) -> "VoiceNarrationResponse":
        return cls(
            id=narration.id,
            script_id=narration.script_id,
            segments=[
                VoiceSegmentResponse(
                    segment_index=segment.segment_index,
                    audio_url=f"/media/{segment.audio_file_path}",
                    duration_seconds=segment.duration_seconds,
                )
                for segment in narration.segments
            ],
            voice_name=narration.voice_name,
            created_at=narration.created_at,
        )
