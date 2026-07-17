"""SQLAlchemy implementation of ScriptRepositoryInterface."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.script import Script as ScriptDomain
from app.domain.models.script import ScriptSegment
from app.infrastructure.db.models import VideoScript as VideoScriptORM


class ScriptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_script(
        self,
        search_id: UUID,
        video_idea: str,
        title: str,
        hook: str,
        segments: list[ScriptSegment],
        cta: str,
        ai_model_used: str,
    ) -> ScriptDomain:
        script = VideoScriptORM(
            search_id=search_id,
            video_idea=video_idea,
            title=title,
            hook=hook,
            segments=[segment.model_dump() for segment in segments],
            cta=cta,
            ai_model_used=ai_model_used,
        )

        self._session.add(script)
        await self._session.commit()
        await self._session.refresh(script)

        return ScriptDomain.model_validate(script)

    async def get_script(self, script_id: UUID) -> ScriptDomain | None:
        stmt = select(VideoScriptORM).where(VideoScriptORM.id == script_id)
        result = await self._session.execute(stmt)
        script = result.scalar_one_or_none()

        return ScriptDomain.model_validate(script) if script else None
