"""Repository interface (Protocol) for Trend Intelligence persistence.

Services depend on this Protocol, not on the SQLAlchemy implementation,
so the persistence layer can be swapped or mocked without touching
business logic.
"""

from typing import Protocol
from uuid import UUID

from app.domain.models.trend import TrendAnalysis as TrendAnalysisDomain
from app.domain.models.trend import TrendingVideo
from app.domain.models.trend import TrendSearch as TrendSearchDomain


class TrendRepositoryInterface(Protocol):
    async def create_search(
        self, keyword: str, quota_units_used: int, videos: list[TrendingVideo]
    ) -> TrendSearchDomain: ...

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
    ) -> TrendAnalysisDomain: ...

    async def get_search(self, search_id: UUID) -> TrendSearchDomain | None: ...
