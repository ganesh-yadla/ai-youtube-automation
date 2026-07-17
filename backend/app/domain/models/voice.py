"""Domain models for the Voice Generation feature."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class VoiceSegment(BaseModel):
    """Generated audio for one script segment - segment_index ties it back
    to the matching entry in the parent Script's segments list.
    """

    segment_index: int
    audio_file_path: str
    duration_seconds: float


class VoiceNarration(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    script_id: UUID
    segments: list[VoiceSegment]
    voice_name: str
    created_at: datetime
