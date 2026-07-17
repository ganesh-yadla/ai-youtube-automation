"""Repository interface (Protocol) for Voice Generation persistence."""

from typing import Protocol
from uuid import UUID

from app.domain.models.voice import VoiceNarration, VoiceSegment


class VoiceRepositoryInterface(Protocol):
    async def create_narration(
        self,
        script_id: UUID,
        segments: list[VoiceSegment],
        voice_name: str,
    ) -> VoiceNarration: ...

    async def get_narration(self, narration_id: UUID) -> VoiceNarration | None: ...

    async def get_narration_by_script_id(self, script_id: UUID) -> VoiceNarration | None: ...
