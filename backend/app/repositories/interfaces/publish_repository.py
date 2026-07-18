"""Repository interface (Protocol) for Publishing Automation persistence."""

from typing import Protocol
from uuid import UUID

from app.domain.models.publish import YoutubeUpload


class PublishRepositoryInterface(Protocol):
    async def create_upload(
        self, video_id: UUID, youtube_video_id: str, youtube_url: str
    ) -> YoutubeUpload: ...

    async def get_upload_by_video_id(self, video_id: UUID) -> YoutubeUpload | None: ...
