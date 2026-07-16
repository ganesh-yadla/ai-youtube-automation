"""SQLAlchemy implementation of TrendRepositoryInterface."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.models.trend import TrendAnalysis as TrendAnalysisDomain
from app.domain.models.trend import TrendingVideo
from app.domain.models.trend import TrendSearch as TrendSearchDomain
from app.infrastructure.db.models import TrendAnalysis as TrendAnalysisORM
from app.infrastructure.db.models import TrendingVideo as TrendingVideoORM
from app.infrastructure.db.models import TrendSearch as TrendSearchORM


class TrendRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_search(
        self, keyword: str, quota_units_used: int, videos: list[TrendingVideo]
    ) -> TrendSearchDomain:
        search = TrendSearchORM(keyword=keyword, youtube_quota_units_used=quota_units_used)
        search.videos = [
            TrendingVideoORM(**video.model_dump(exclude={"id"})) for video in videos
        ]

        self._session.add(search)
        await self._session.commit()
        await self._session.refresh(search, attribute_names=["videos"])

        return TrendSearchDomain.model_validate(search)

    async def save_analysis(
        self,
        search_id: UUID,
        why_performing: str,
        common_hooks: list[str],
        common_title_patterns: list[str],
        common_thumbnail_patterns: list[str],
        content_gaps: list[str],
        video_ideas: list[str],
        ai_model_used: str,
    ) -> TrendAnalysisDomain:
        analysis = TrendAnalysisORM(
            search_id=search_id,
            why_performing=why_performing,
            common_hooks=common_hooks,
            common_title_patterns=common_title_patterns,
            common_thumbnail_patterns=common_thumbnail_patterns,
            content_gaps=content_gaps,
            video_ideas=video_ideas,
            ai_model_used=ai_model_used,
        )

        self._session.add(analysis)
        await self._session.commit()
        await self._session.refresh(analysis)

        return TrendAnalysisDomain.model_validate(analysis)

    async def get_search(self, search_id: UUID) -> TrendSearchDomain | None:
        stmt = (
            select(TrendSearchORM)
            .where(TrendSearchORM.id == search_id)
            .options(
                selectinload(TrendSearchORM.videos),
                selectinload(TrendSearchORM.analysis),
            )
        )
        result = await self._session.execute(stmt)
        search = result.scalar_one_or_none()

        return TrendSearchDomain.model_validate(search) if search else None
