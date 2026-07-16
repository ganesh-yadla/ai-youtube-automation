"""Domain exceptions for the Trend Intelligence feature."""


class TrendIntelligenceError(Exception):
    """Base exception for all Trend Intelligence errors."""


class YouTubeAPIError(TrendIntelligenceError):
    """Raised when the YouTube Data API returns an error or unexpected response."""


class NoTrendingVideosFoundError(TrendIntelligenceError):
    """Raised when a keyword search returns no videos."""


class TrendSearchNotFoundError(TrendIntelligenceError):
    """Raised when a requested TrendSearch id does not exist."""


class TrendAnalysisAlreadyExistsError(TrendIntelligenceError):
    """Raised when re-requesting AI insights for a search that already has them."""
