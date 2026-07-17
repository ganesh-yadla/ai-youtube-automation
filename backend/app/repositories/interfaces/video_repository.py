"""Repository interface (Protocol) for Visual Generation persistence."""

from typing import Protocol
from uuid import UUID

from app.domain.models.video import AssembledVideo


class VideoRepositoryInterface(Protocol):
    async def create_video(
        self,
        narration_id: UUID,
        video_file_path: str,
        thumbnail_file_path: str,
        duration_seconds: float,
    ) -> AssembledVideo: ...

    async def get_video(self, video_id: UUID) -> AssembledVideo | None: ...

    async def get_video_by_narration_id(self, narration_id: UUID) -> AssembledVideo | None: ...
