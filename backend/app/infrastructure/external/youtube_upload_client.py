"""Thin async wrapper over the YouTube Data API v3's resumable upload
protocol. Uploads a video and (best-effort) sets its custom thumbnail.

Deliberately not using google-api-python-client, matching YoutubeClient's
existing rationale (see youtube_client.py): raw httpx keeps this
consistent with the rest of our async I/O rather than bridging a
synchronous SDK.

OAuth token refresh IS synchronous (google-auth's Credentials.refresh()
has no async variant), so it runs via asyncio.to_thread to avoid blocking
the event loop - same pattern already used for Piper's blocking
synthesis.

Requires backend/token.json, produced by the one-time interactive
scripts/authorize_youtube.py bootstrap - a browser consent flow doesn't
fit an async request cycle, so getting the initial refresh token is a
separate one-time script, not part of this client. Refresh tokens expire
every 7 days while the OAuth consent screen is in Testing mode (the
default for personal/unverified use) - re-run that script when this
client starts raising invalid_grant errors.

Uploads always land as private: any Google Cloud project created after
2020-07-28 has this enforced automatically for videos.insert, regardless
of the requested privacyStatus - see Publishing Automation's plan notes.
This is treated as a feature, not a limitation: it's exactly the human-
review-before-publish gate already decided on, enforced by the platform
instead of custom code.
"""

import json
import logging
from asyncio import to_thread
from pathlib import Path

import httpx
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials

from app.core.config import get_settings
from app.exceptions.publish_exceptions import YoutubeUploadError

UPLOAD_BASE_URL = "https://www.googleapis.com/upload/youtube/v3"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

logger = logging.getLogger(__name__)


class YoutubeUploadClient:
    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        settings = get_settings()
        self._token_path = Path(settings.youtube_token_path)
        self._http = http_client or httpx.AsyncClient(timeout=120.0)

    async def close(self) -> None:
        await self._http.aclose()

    async def upload_video(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: list[str],
        category_id: str,
        thumbnail_path: str | None = None,
    ) -> str:
        if not self._token_path.exists():
            raise YoutubeUploadError(
                f"No OAuth token at {self._token_path}. Run scripts/authorize_youtube.py first."
            )

        access_token = await self._get_access_token()
        video_id = await self._upload_video_file(
            access_token, video_path, title, description, tags, category_id
        )

        if thumbnail_path:
            try:
                await self._set_thumbnail(access_token, video_id, thumbnail_path)
            except httpx.HTTPStatusError as e:
                # Non-fatal: the video itself uploaded successfully, and
                # YouTube auto-generates a fallback thumbnail either way.
                # Custom thumbnails require a phone-verified channel, which
                # may not be true for every account.
                logger.warning("thumbnail_upload_failed", extra={"video_id": video_id, "error": str(e)})

        return video_id

    async def _get_access_token(self) -> str:
        return await to_thread(self._refresh_access_token)

    def _refresh_access_token(self) -> str:
        token_data = json.loads(self._token_path.read_text(encoding="utf-8"))
        credentials = Credentials(
            token=None,
            refresh_token=token_data["refresh_token"],
            client_id=token_data["client_id"],
            client_secret=token_data["client_secret"],
            token_uri=token_data["token_uri"],
            scopes=SCOPES,
        )
        credentials.refresh(GoogleAuthRequest())
        return credentials.token

    async def _upload_video_file(
        self,
        access_token: str,
        video_path: str,
        title: str,
        description: str,
        tags: list[str],
        category_id: str,
    ) -> str:
        video_bytes = Path(video_path).read_bytes()
        metadata = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": category_id,
            },
            "status": {"privacyStatus": "private"},
        }

        init_response = await self._http.post(
            f"{UPLOAD_BASE_URL}/videos",
            params={"uploadType": "resumable", "part": "snippet,status"},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Length": str(len(video_bytes)),
                "X-Upload-Content-Type": "video/mp4",
            },
            json=metadata,
        )
        init_response.raise_for_status()
        session_url = init_response.headers["Location"]

        upload_response = await self._http.put(
            session_url,
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "video/mp4"},
            content=video_bytes,
        )
        upload_response.raise_for_status()
        return upload_response.json()["id"]

    async def _set_thumbnail(self, access_token: str, video_id: str, thumbnail_path: str) -> None:
        thumbnail_bytes = Path(thumbnail_path).read_bytes()
        response = await self._http.post(
            f"{UPLOAD_BASE_URL}/thumbnails/set",
            params={"videoId": video_id},
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "image/png"},
            content=thumbnail_bytes,
        )
        response.raise_for_status()
