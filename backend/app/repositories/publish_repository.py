"""SQLAlchemy implementation of PublishRepositoryInterface."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.publish import YoutubeUpload as YoutubeUploadDomain
from app.infrastructure.db.models import YoutubeUpload as YoutubeUploadORM


class PublishRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_upload(
        self, video_id: UUID, youtube_video_id: str, youtube_url: str
    ) -> YoutubeUploadDomain:
        upload = YoutubeUploadORM(
            video_id=video_id, youtube_video_id=youtube_video_id, youtube_url=youtube_url
        )

        self._session.add(upload)
        await self._session.commit()
        await self._session.refresh(upload)

        return YoutubeUploadDomain.model_validate(upload)

    async def get_upload_by_video_id(self, video_id: UUID) -> YoutubeUploadDomain | None:
        stmt = select(YoutubeUploadORM).where(YoutubeUploadORM.video_id == video_id)
        result = await self._session.execute(stmt)
        upload = result.scalar_one_or_none()

        return YoutubeUploadDomain.model_validate(upload) if upload else None
