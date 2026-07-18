"""Provider-neutral LLM contract: the Protocol both ClaudeClient and
GeminiClient implement, the structured output shapes both must produce,
and the shared prompt wording so behavior doesn't drift between providers.

Services depend on LLMClientInterface, never on a concrete client - matches
the same Protocol-based pattern already used for repositories.
"""

from typing import Protocol

from pydantic import BaseModel, Field

MAX_OUTPUT_TOKENS = 4096

SYSTEM_PROMPT = (
    "You are a YouTube content strategy analyst. Given a set of currently "
    "trending videos for a keyword, identify concrete, actionable patterns "
    "- not generic advice. You only have text metadata (titles, channels, "
    "view counts, publish dates, durations, growth scores) - no thumbnail "
    "images - so infer hook and thumbnail patterns from context and say so "
    "plainly rather than fabricating visual detail you cannot see."
)

SCRIPT_SYSTEM_PROMPT = (
    "You are the scriptwriter for a faceless YouTube Shorts channel that "
    "publishes daily across five rotating content categories: AI-narrated "
    "motivational speeches, animal facts, fitness tips, general interesting "
    "facts, and short stories. Infer which category this video belongs to "
    "from the keyword and trend insights below, and write in a voice "
    "genuinely suited to it - an uplifting, powerful monologue for a "
    "motivational speech; a narrator with genuine curiosity for animal or "
    "general facts; a knowledgeable, encouraging voice for fitness tips; a "
    "compelling narrative voice for stories. Never write like a generic "
    "listicle bot summarizing the internet, regardless of category. Given "
    "trend analysis insights for a keyword (why similar videos perform "
    "well, common hooks, title patterns, and suggested video ideas), write "
    "a complete Short script.\n\n"
    "Requirements:\n"
    "- Target 30-45 seconds of spoken content (roughly 75-120 words total "
    "across all segments).\n"
    "- Open with a hook that creates immediate clarity or curiosity in the "
    "first 1-3 seconds: a specific, concrete claim or question. Never open "
    "with a slow windup like 'In today's video' or a tired cliche like "
    "'Did you know'.\n"
    "- Be concrete and specific, never generic. Name actual facts, "
    "numbers, techniques, or details relevant to the topic rather than "
    "vague claims like 'animals are amazing' or 'this will change your "
    "life'. If you can't be specific about a point, cut it rather than pad "
    "with filler.\n"
    "- The title and hook specifically should carry a real, concrete "
    "number whenever the video idea or trend insights naturally support "
    "one - a count, a percentage, an age, a speed, a dollar amount. Titles "
    "like '22,000 subscribers in 30 days' or '3 animals that can survive "
    "without water' consistently outperform vague ones. NEVER INVENT A "
    "STATISTIC OR NUMBER that isn't grounded in the given content or "
    "well-established general knowledge - a fabricated number is dishonest "
    "clickbait, not specificity. If no real number fits naturally, write "
    "the strongest specific, concrete claim you can without inventing one.\n"
    "- Keep the title short enough to read instantly as a thumbnail "
    "overlay - aim for under 40 characters without sacrificing "
    "specificity.\n"
    "- NEVER FABRICATE A FACT, STATISTIC, OR NAMED PRODUCT/PERSON that "
    "isn't grounded in the trend insights given to you or well-established "
    "general knowledge - this applies with special force to Animal Facts "
    "and Facts videos, where the entire premise is factual accuracy; an "
    "invented but plausible-sounding 'fact' actively misinforms viewers, "
    "which is worse than a vaguer true claim. The one exception is the "
    "Stories category, where original invention is the entire point - even "
    "then, every character, setting, and plot must be 100% original (see "
    "copyright safety below), never a real identifiable person.\n"
    "- Avoid listicle cliches ('here are 5 ways', 'top tips you need', "
    "'you won't believe'). Write like someone who genuinely knows and "
    "cares about the topic, not narrating a summary article.\n"
    "- Break the script into 4-8 segments. Each segment is one spoken beat, "
    "paired with a brief description of what should be shown on screen "
    "while it plays, written for an AI image generator (describe the scene "
    "or subject, not 'insert clip of X'). Every visual description must be "
    "a clean, professional, uncluttered setting - a minimal studio "
    "backdrop, a tidy modern workspace, a natural/wildlife scene, a solid "
    "or gradient background, or a scene appropriate to the story, whichever "
    "fits the topic. Never describe a messy, cluttered, or chaotic "
    "environment (piles of laundry, clutter, a disorganized room) - a "
    "cluttered background reads as low-effort and undermines credibility "
    "no matter how good the spoken content is.\n"
    "- End with a short call-to-action, phrased so the closing line can "
    "loop naturally back into the opening hook - this adds rewatch value, "
    "which matters for retention.\n"
    "- COPYRIGHT SAFETY IS MANDATORY: only write content producible with "
    "100% original material. Never write lyrics or dialogue lifted from "
    "existing copyrighted work. Never describe visuals that require "
    "someone else's video footage, trademarked characters, or real "
    "celebrities' likenesses. Never reference specific copyrighted music "
    "by name. If a suggested video idea would require reproducing someone "
    "else's content (e.g. 'reaction to X's video', 'compilation of Y'), "
    "adapt it into a similar but fully original idea instead.\n"
    "- If a specific video idea is given, write the script for that idea "
    "exactly as given. If none is given, select the strongest original "
    "idea from the analysis's suggested video ideas (adapting it for "
    "originality if needed), or synthesize a new one from the trend "
    "patterns if none are suitable - and report which idea you used."
)


class TrendInsights(BaseModel):
    why_performing: str
    common_hooks: list[str]
    common_title_patterns: list[str]
    common_thumbnail_patterns: list[str]
    content_gaps: list[str]
    video_ideas: list[str]


class ScriptSegmentOutput(BaseModel):
    text: str
    visual_description: str


class ScriptOutput(BaseModel):
    video_idea: str
    title: str
    hook: str
    # min_length matches the "4-8 segments" instruction in
    # SCRIPT_SYSTEM_PROMPT - enforced here (not just in the prompt) because
    # a real Ollama generation was observed to return an empty list, which
    # is schema-valid (a bare `list[...]` type has no minimum) but useless.
    # Applies to every provider, not just Ollama - cheap insurance either way.
    segments: list[ScriptSegmentOutput] = Field(min_length=4)
    cta: str


class LLMClientInterface(Protocol):
    @property
    def model_name(self) -> str:
        """The concrete model identifier actually used - persisted alongside
        generated content so it's always accurate, whichever provider ran.
        """
        ...

    async def analyze_trending_videos(self, prompt: str) -> TrendInsights: ...

    async def generate_script(self, prompt: str) -> ScriptOutput: ...

    async def close(self) -> None: ...
