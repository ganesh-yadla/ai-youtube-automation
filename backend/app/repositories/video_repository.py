"""SQLAlchemy implementation of VideoRepositoryInterface."""

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.video import AssembledVideo as AssembledVideoDomain
from app.infrastructure.db.models import AssembledVideo as AssembledVideoORM


class VideoRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_video(
        self,
        narration_id: UUID,
        video_file_path: str,
        thumbnail_file_path: str,
        duration_seconds: float,
    ) -> AssembledVideoDomain:
        video = AssembledVideoORM(
            narration_id=narration_id,
            video_file_path=video_file_path,
            thumbnail_file_path=thumbnail_file_path,
            duration_seconds=duration_seconds,
        )

        self._session.add(video)
        await self._session.commit()
        await self._session.refresh(video)

        return AssembledVideoDomain.model_validate(video)

    async def get_video(self, video_id: UUID) -> AssembledVideoDomain | None:
        stmt = select(AssembledVideoORM).where(AssembledVideoORM.id == video_id)
        result = await self._session.execute(stmt)
        video = result.scalar_one_or_none()

        return AssembledVideoDomain.model_validate(video) if video else None

    async def mark_synthetic_content_disclosed(self, video_id: UUID) -> None:
        stmt = (
            update(AssembledVideoORM)
            .where(AssembledVideoORM.id == video_id)
            .values(synthetic_content_disclosed=True)
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def get_video_by_narration_id(self, narration_id: UUID) -> AssembledVideoDomain | None:
        stmt = select(AssembledVideoORM).where(AssembledVideoORM.narration_id == narration_id)
        result = await self._session.execute(stmt)
        video = result.scalar_one_or_none()

        return AssembledVideoDomain.model_validate(video) if video else None
