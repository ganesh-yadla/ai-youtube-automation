"""Request/response wire schemas for the Script Agent API. Kept separate
from domain models so the public API contract can evolve independently of
internal service/repository shapes.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ScriptGenerationRequest(BaseModel):
    video_idea: str | None = Field(default=None, max_length=300)


class ScriptSegmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    text: str
    visual_description: str


class ScriptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    search_id: UUID
    video_idea: str
    title: str
    hook: str
    segments: list[ScriptSegmentResponse]
    cta: str
    ai_model_used: str
    created_at: datetime
