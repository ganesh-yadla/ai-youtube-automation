"""Business logic for generating AI insights over a TrendSearch's videos."""

import logging
from uuid import UUID

from app.domain.models.trend import TrendAnalysis as TrendAnalysisDomain
from app.domain.models.trend import TrendingVideo
from app.exceptions.trend_exceptions import (
    NoTrendingVideosFoundError,
    TrendAnalysisAlreadyExistsError,
    TrendSearchNotFoundError,
)
from app.infrastructure.external.interfaces.llm_client import LLMClientInterface
from app.repositories.interfaces.trend_repository import TrendRepositoryInterface

logger = logging.getLogger(__name__)


class AIAnalysisService:
    """Orchestrates: load a TrendSearch, build a prompt, call the LLM, persist insights."""

    def __init__(self, llm_client: LLMClientInterface, repository: TrendRepositoryInterface) -> None:
        self._llm_client = llm_client
        self._repository = repository

    async def analyze(self, search_id: UUID) -> TrendAnalysisDomain:
        search = await self._repository.get_search(search_id)
        if search is None:
            raise TrendSearchNotFoundError(f"No trend search found with id '{search_id}'")
        if search.analysis is not None:
            raise TrendAnalysisAlreadyExistsError(
                f"Trend search '{search_id}' has already been analyzed"
            )
        if not search.videos:
            raise NoTrendingVideosFoundError(f"Trend search '{search_id}' has no videos to analyze")

        logger.info(
            "trend_analysis_started", extra={"search_id": str(search_id), "keyword": search.keyword}
        )

        prompt = self._build_prompt(search.keyword, search.videos)
        insights = await self._llm_client.analyze_trending_videos(prompt)

        return await self._repository.save_analysis(
            search_id=search_id,
            why_performing=insights.why_performing,
            common_hooks=insights.common_hooks,
            common_title_patterns=insights.common_title_patterns,
            common_thumbnail_patterns=insights.common_thumbnail_patterns,
            content_gaps=insights.content_gaps,
            video_ideas=insights.video_ideas,
            ai_model_used=self._llm_client.model_name,
        )

    @staticmethod
    def _build_prompt(keyword: str, videos: list[TrendingVideo]) -> str:
        video_lines = "\n".join(
            f'{rank}. "{video.title}" - {video.channel_name} | '
            f"{video.view_count:,} views | published {video.published_at.date()} | "
            f"{video.duration_seconds}s | growth score {video.estimated_growth_score:,.0f} views/day"
            for rank, video in enumerate(videos, start=1)
        )

        return (
            f'Keyword: "{keyword}"\n\n'
            f"Trending videos:\n{video_lines}\n\n"
            "Based on the titles, channels, view counts, publish dates, durations, "
            "and growth scores above, analyze why these videos are performing well. "
            "Growth score is an estimate (views divided by days since publish), not "
            "verified velocity. Infer likely hooks and thumbnail patterns from the "
            "titles and context - you do not have the actual thumbnail images. Then "
            "suggest content gaps and concrete new video ideas for this keyword."
        )
