"""Domain exceptions for the Publishing Automation feature."""


class PublishError(Exception):
    """Base exception for all Publishing Automation errors."""


class YoutubeUploadError(PublishError):
    """Raised when the YouTube upload itself fails (auth, network, API error)."""


class VideoAlreadyPublishedError(PublishError):
    """Raised when re-requesting publish for a video that's already uploaded."""
