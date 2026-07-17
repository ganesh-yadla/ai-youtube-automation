"""Provider-neutral image generation contract.

Kept as a separate interface from LLMClientInterface and TTSClientInterface -
image generation is a distinct capability from text and speech.
"""

from typing import Protocol


class ImageClientInterface(Protocol):
    async def generate_image(self, prompt: str, aspect_ratio: str = "9:16") -> bytes:
        """Returns image bytes (PNG) for the given prompt."""
        ...
