"""Domain exceptions for the Visual Generation feature."""


class VideoGenerationError(Exception):
    """Base exception for all Visual Generation errors."""


class VideoAlreadyExistsError(VideoGenerationError):
    """Raised when re-requesting video assembly for a narration that already has one."""


class VideoNotFoundError(VideoGenerationError):
    """Raised when a requested AssembledVideo id does not exist."""
