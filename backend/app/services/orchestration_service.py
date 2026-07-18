"""Chains Script -> Voice -> Visual generation into one call, for the UI's
single "Generate Video" action instead of three separate requests.

A thin wrapper, not new business logic - each step is already a fully
tested, independently-usable service. This exists purely to collapse the
three-request sequence into one for callers (the frontend) that don't
need step-by-step control.
"""

from uuid import UUID

from app.domain.models.script import Script
from app.domain.models.video import AssembledVideo
from app.services.script_service import ScriptService
from app.services.video_service import VideoService
from app.services.voice_service import VoiceService


class OrchestrationService:
    def __init__(
        self,
        script_service: ScriptService,
        voice_service: VoiceService,
        video_service: VideoService,
    ) -> None:
        self._script_service = script_service
        self._voice_service = voice_service
        self._video_service = video_service

    async def generate_video(
        self, search_id: UUID, video_idea: str | None = None
    ) -> tuple[Script, AssembledVideo]:
        script = await self._script_service.generate(search_id, video_idea=video_idea)
        narration = await self._voice_service.generate(script.id)
        video = await self._video_service.generate(narration.id)
        return script, video
