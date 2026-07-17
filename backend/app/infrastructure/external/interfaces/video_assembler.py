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
    caption_text: str


class VideoAssemblerInterface(Protocol):
    async def assemble(self, scenes: list[VideoScene], output_path: str) -> None:
        """Renders each scene (image shown for its audio's duration, audio
        playing, caption burned in) and concatenates them, in order, into
        one video file written to output_path.
        """
        ...
