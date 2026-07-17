"""Repository interface (Protocol) for Script Agent persistence."""

from typing import Protocol
from uuid import UUID

from app.domain.models.script import Script, ScriptSegment


class ScriptRepositoryInterface(Protocol):
    async def create_script(
        self,
        search_id: UUID,
        video_idea: str,
        title: str,
        hook: str,
        segments: list[ScriptSegment],
        cta: str,
        ai_model_used: str,
    ) -> Script: ...

    async def get_script(self, script_id: UUID) -> Script | None: ...
