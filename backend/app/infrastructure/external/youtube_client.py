"""Thin async wrapper over the YouTube Data API v3 (search + video details).

Deliberately not using google-api-python-client here: it's a synchronous,
heavyweight SDK that doesn't fit an async FastAPI service. Calling the
REST endpoints directly via httpx keeps this consistent with the rest of
our I/O (Redis, Claude) and avoids an extra sync-to-async bridge.
"""

import re
from datetime import datetime

import httpx
from pydantic import BaseModel

from app.core.config import get_settings
from app.exceptions.trend_exceptions import YouTubeAPIError

YOUTUBE_API_BASE_URL = "https://www.googleapis.com/youtube/v3"
SEARCH_QUOTA_COST = 100
VIDEOS_DETAIL_QUOTA_COST = 1

_ISO8601_DURATION_RE = re.compile(
    r"P(?:(?P<days>\d+)D)?T?(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?"
)


def parse_iso8601_duration(duration: str) -> int:
    """Convert a YouTube ISO 8601 duration (e.g. 'PT4M13S') to whole seconds."""
    match = _ISO8601_DURATION_RE.fullmatch(duration)
    if not match:
        return 0
    parts = match.groupdict(default="0")
    days, hours, minutes, seconds = (int(parts[key] or 0) for key in ("days", "hours", "minutes", "seconds"))
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


class YoutubeVideoData(BaseModel):
    """Raw video data as returned by the YouTube API, mechanically parsed."""

    youtube_video_id: str
    title: str
    channel_name: str
    channel_id: str
    view_count: int
    published_at: datetime
    duration_seconds: int
    thumbnail_url: str
    video_url: str


class YoutubeSearchResponse(BaseModel):
    videos: list[YoutubeVideoData]
    quota_units_used: int


class YoutubeClient:
    """Wraps YouTube Data API v3 search.list + videos.list calls."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._settings = get_settings()
        self._http = http_client or httpx.AsyncClient(base_url=YOUTUBE_API_BASE_URL, timeout=10.0)

    async def close(self) -> None:
        await self._http.aclose()

    async def search_trending_videos(self, keyword: str, max_results: int = 10) -> YoutubeSearchResponse:
        """Search YouTube for a keyword and return the top videos by view count."""
        search_items = await self._search(keyword, max_results)
        video_ids = [item["id"]["videoId"] for item in search_items]

        if not video_ids:
            return YoutubeSearchResponse(videos=[], quota_units_used=SEARCH_QUOTA_COST)

        video_items = await self._fetch_video_details(video_ids)
        videos = [self._to_video_data(item) for item in video_items]

        return YoutubeSearchResponse(
            videos=videos,
            quota_units_used=SEARCH_QUOTA_COST + VIDEOS_DETAIL_QUOTA_COST,
        )

    async def _search(self, keyword: str, max_results: int) -> list[dict]:
        response = await self._http.get(
            "/search",
            params={
                "part": "snippet",
                "q": keyword,
                "type": "video",
                "order": "viewCount",
                "maxResults": max_results,
                "key": self._settings.youtube_api_key,
            },
        )
        self._raise_for_error(response)
        return response.json().get("items", [])

    async def _fetch_video_details(self, video_ids: list[str]) -> list[dict]:
        response = await self._http.get(
            "/videos",
            params={
                "part": "snippet,statistics,contentDetails",
                "id": ",".join(video_ids),
                "key": self._settings.youtube_api_key,
            },
        )
        self._raise_for_error(response)
        return response.json().get("items", [])

    @staticmethod
    def _raise_for_error(response: httpx.Response) -> None:
        if response.status_code != 200:
            raise YouTubeAPIError(
                f"YouTube API request failed with status {response.status_code}: {response.text}"
            )

    @staticmethod
    def _to_video_data(item: dict) -> YoutubeVideoData:
        snippet = item["snippet"]
        statistics = item.get("statistics", {})
        content_details = item.get("contentDetails", {})
        video_id = item["id"]
        thumbnails = snippet["thumbnails"]
        thumbnail = thumbnails.get("high") or thumbnails.get("default")

        return YoutubeVideoData(
            youtube_video_id=video_id,
            title=snippet["title"],
            channel_name=snippet["channelTitle"],
            channel_id=snippet["channelId"],
            view_count=int(statistics.get("viewCount", 0)),
            published_at=snippet["publishedAt"],
            duration_seconds=parse_iso8601_duration(content_details.get("duration", "PT0S")),
            thumbnail_url=thumbnail["url"],
            video_url=f"https://www.youtube.com/watch?v={video_id}",
        )
