"""Business logic for generating a Short script from a TrendSearch's analysis."""

import logging
from uuid import UUID

from app.domain.models.script import Script as ScriptDomain
from app.domain.models.script import ScriptSegment
from app.domain.models.trend import TrendAnalysis
from app.exceptions.script_exceptions import TrendAnalysisRequiredError
from app.exceptions.trend_exceptions import TrendSearchNotFoundError
from app.infrastructure.external.interfaces.llm_client import LLMClientInterface
from app.repositories.interfaces.script_repository import ScriptRepositoryInterface
from app.repositories.interfaces.trend_repository import TrendRepositoryInterface

logger = logging.getLogger(__name__)

_LANGUAGE_INSTRUCTIONS = {
    "te": (
        "Write the ENTIRE script - title, hook, every segment, and CTA - in Telugu, using "
        "native Telugu script (Unicode), never transliterated Roman letters. Write naturally, "
        "the way a fluent Telugu tech creator actually speaks, not a stiff word-for-word "
        "translation from English. Product/brand names and commonly-used English tech loanwords "
        "(e.g. AI, app names) may stay in English if that's how a Telugu speaker would actually "
        "say them - everything else must be Telugu.\n\n"
    ),
}


class ScriptService:
    """Orchestrates: load a TrendSearch's analysis, generate a script via the LLM, persist it."""

    def __init__(
        self,
        llm_client: LLMClientInterface,
        trend_repository: TrendRepositoryInterface,
        script_repository: ScriptRepositoryInterface,
        content_language: str = "en",
    ) -> None:
        self._llm_client = llm_client
        self._trend_repository = trend_repository
        self._script_repository = script_repository
        self._content_language = content_language

    async def generate(self, search_id: UUID, video_idea: str | None = None) -> ScriptDomain:
        search = await self._trend_repository.get_search(search_id)
        if search is None:
            raise TrendSearchNotFoundError(f"No trend search found with id '{search_id}'")
        if search.analysis is None:
            raise TrendAnalysisRequiredError(
                f"Trend search '{search_id}' has not been analyzed yet - run /insights first"
            )

        logger.info(
            "script_generation_started",
            extra={"search_id": str(search_id), "keyword": search.keyword},
        )

        prompt = self._build_prompt(search.keyword, search.analysis, video_idea, self._content_language)
        output = await self._llm_client.generate_script(prompt)

        segments = [
            ScriptSegment(text=segment.text, visual_description=segment.visual_description)
            for segment in output.segments
        ]

        return await self._script_repository.create_script(
            search_id=search_id,
            video_idea=output.video_idea,
            title=output.title,
            hook=output.hook,
            segments=segments,
            cta=output.cta,
            ai_model_used=self._llm_client.model_name,
        )

    async def get_by_id(self, script_id: UUID) -> ScriptDomain | None:
        return await self._script_repository.get_script(script_id)

    @staticmethod
    def _build_prompt(
        keyword: str, analysis: TrendAnalysis, video_idea: str | None, content_language: str
    ) -> str:
        idea_instruction = (
            f'Write the script for this specific video idea: "{video_idea}"'
            if video_idea
            else "No specific video idea was given - select or adapt the strongest original "
            "idea from the suggested video ideas below."
        )
        language_instruction = _LANGUAGE_INSTRUCTIONS.get(content_language, "")

        return (
            f"{language_instruction}"
            f'Keyword: "{keyword}"\n\n'
            f"Why similar videos perform well: {analysis.why_performing}\n\n"
            f"Common hooks: {', '.join(analysis.common_hooks)}\n"
            f"Common title patterns: {', '.join(analysis.common_title_patterns)}\n"
            f"Content gaps: {', '.join(analysis.content_gaps)}\n"
            f"Suggested video ideas: {', '.join(analysis.video_ideas)}\n\n"
            f"{idea_instruction}"
        )
