"""SQLAlchemy implementation of VoiceRepositoryInterface."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.voice import VoiceNarration as VoiceNarrationDomain
from app.domain.models.voice import VoiceSegment
from app.infrastructure.db.models import VoiceNarration as VoiceNarrationORM


class VoiceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_narration(
        self,
        script_id: UUID,
        segments: list[VoiceSegment],
        voice_name: str,
    ) -> VoiceNarrationDomain:
        narration = VoiceNarrationORM(
            script_id=script_id,
            segments=[segment.model_dump() for segment in segments],
            voice_name=voice_name,
        )

        self._session.add(narration)
        await self._session.commit()
        await self._session.refresh(narration)

        return VoiceNarrationDomain.model_validate(narration)

    async def get_narration(self, narration_id: UUID) -> VoiceNarrationDomain | None:
        stmt = select(VoiceNarrationORM).where(VoiceNarrationORM.id == narration_id)
        result = await self._session.execute(stmt)
        narration = result.scalar_one_or_none()

        return VoiceNarrationDomain.model_validate(narration) if narration else None

    async def get_narration_by_script_id(self, script_id: UUID) -> VoiceNarrationDomain | None:
        stmt = select(VoiceNarrationORM).where(VoiceNarrationORM.script_id == script_id)
        result = await self._session.execute(stmt)
        narration = result.scalar_one_or_none()

        return VoiceNarrationDomain.model_validate(narration) if narration else None
