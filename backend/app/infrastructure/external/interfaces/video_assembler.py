"""Provider-neutral video assembly contract.

Not an AI/LLM capability - wraps local video processing (ffmpeg today).
Kept behind an interface anyway so VideoService stays testable with a fake,
without needing the real ffmpeg binary in unit tests.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass
class VideoScene:
    """One segment's worth of material to render into a clip."""

    image_path: str
    audio_path: str


class VideoAssemblerInterface(Protocol):
    async def assemble(self, scenes: list[VideoScene], output_path: str) -> None:
        """Renders each scene (image shown for its audio's duration, audio
        playing) and concatenates them, in order, into one video file
        written to output_path. Captions are not burned in - see
        PublishService for the real YouTube caption track this pipeline
        uploads instead.
        """
        ...

    async def render_thumbnail(self, image_path: str, text: str, output_path: str) -> None:
        """Overlays real, correctly-spelled text onto a background image and
        writes the result to output_path.

        Text is burned in by ffmpeg, not painted by the image model - AI
        image generation renders text as pixel shapes, not real typography,
        which produced real typos in testing (e.g. "isn't" -> "IS'N'T").
        image_path should be a clean background with no text requested in
        its generation prompt.
        """
        ...
