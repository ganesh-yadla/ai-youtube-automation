"""Response schema for the combined Script -> Voice -> Visual generation
endpoint. Bundles both so the frontend gets everything it needs to render
a result screen (script text + playable video) in one round trip.
"""

from pydantic import BaseModel

from app.api.v1.schemas.script import ScriptResponse
from app.api.v1.schemas.video import AssembledVideoResponse


class GenerateVideoResponse(BaseModel):
    script: ScriptResponse
    video: AssembledVideoResponse
