"""Domain models for the Script Agent feature.

Kept as a separate module from trend.py even though a Script is FK'd to a
TrendSearch — scripting is a distinct bounded concept (and the next feature
in the pipeline, Voice Generation, will depend on this shape specifically).
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ScriptSegment(BaseModel):
    """One spoken beat of the script, paired with what should be shown on
    screen while it plays - text feeds Voice Generation, visual_description
    feeds Visual Generation, both downstream phases.
    """

    text: str
    visual_description: str


class Script(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    search_id: UUID
    video_idea: str
    title: str
    hook: str
    segments: list[ScriptSegment]
    cta: str
    ai_model_used: str
    created_at: datetime
