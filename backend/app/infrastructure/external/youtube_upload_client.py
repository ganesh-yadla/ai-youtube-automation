"""Thin async wrapper over the YouTube Data API v3's resumable upload
protocol. Uploads a video and (best-effort) sets its custom thumbnail and
caption track.

Caption upload (captions.insert) is why SCOPES uses youtube.force-ssl
instead of the narrower youtube.upload used previously - force-ssl also
covers videos.insert, so one scope replaces two rather than needing both.
Existing tokens obtained under the old scope do not have caption-upload
permission; scripts/authorize_youtube.py must be re-run once to pick up
the wider scope.

The resumable-upload protocol (init with X-Upload-Content-* headers, then
PUT the raw bytes to the returned session URL) is used for captions the
same way it's used for videos - the Data API reference docs for
captions.insert don't explicitly document which upload types it supports,
but the generic Google API media-upload protocol is consistent across
insert-with-media endpoints, and this mirrors the already-proven
videos.insert implementation rather than introducing a different
multipart/related body format untested anywhere else in this codebase.

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
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

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
        contains_synthetic_media: bool,
        thumbnail_path: str | None = None,
        default_language: str | None = None,
        caption_content: str | None = None,
        caption_language: str | None = None,
    ) -> str:
        if not self._token_path.exists():
            raise YoutubeUploadError(
                f"No OAuth token at {self._token_path}. Run scripts/authorize_youtube.py first."
            )

        access_token = await self._get_access_token()
        video_id = await self._upload_video_file(
            access_token,
            video_path,
            title,
            description,
            tags,
            category_id,
            contains_synthetic_media,
            default_language,
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

        if caption_content:
            try:
                await self._upload_caption(
                    access_token, video_id, caption_content, caption_language or "en"
                )
            except httpx.HTTPStatusError as e:
                # Non-fatal for the same reason as thumbnail: the video
                # itself is already published successfully. A missing
                # caption track is a quality gap, not a failed publish.
                logger.warning("caption_upload_failed", extra={"video_id": video_id, "error": str(e)})

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
        contains_synthetic_media: bool,
        default_language: str | None,
    ) -> str:
        video_bytes = Path(video_path).read_bytes()
        snippet = {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id,
        }
        if default_language:
            # Matters for reaching a non-English audience through YouTube's
            # own language-based search/recommendation - a video with
            # Telugu audio but no language metadata is easy for YouTube to
            # miscategorize as English content.
            snippet["defaultLanguage"] = default_language
            snippet["defaultAudioLanguage"] = default_language
        metadata = {
            "snippet": snippet,
            "status": {
                "privacyStatus": "private",
                # YouTube's 2026 synthetic-media disclosure requirement:
                # every video this pipeline produces has AI-generated
                # narration and AI-generated visuals, so this is always
                # true rather than a per-video decision.
                "containsSyntheticMedia": contains_synthetic_media,
            },
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

    async def _upload_caption(
        self, access_token: str, video_id: str, caption_content: str, language: str
    ) -> None:
        caption_bytes = caption_content.encode("utf-8")
        metadata = {
            "snippet": {
                "videoId": video_id,
                "language": language,
                "name": "",  # empty name = track has no extra label, just the language
            }
        }

        init_response = await self._http.post(
            f"{UPLOAD_BASE_URL}/captions",
            params={"uploadType": "resumable", "part": "snippet"},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Length": str(len(caption_bytes)),
                "X-Upload-Content-Type": "application/octet-stream",
            },
            json=metadata,
        )
        init_response.raise_for_status()
        session_url = init_response.headers["Location"]

        upload_response = await self._http.put(
            session_url,
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/octet-stream"},
            content=caption_bytes,
        )
        upload_response.raise_for_status()

    async def _set_thumbnail(self, access_token: str, video_id: str, thumbnail_path: str) -> None:
        thumbnail_bytes = Path(thumbnail_path).read_bytes()
        response = await self._http.post(
            f"{UPLOAD_BASE_URL}/thumbnails/set",
            params={"videoId": video_id},
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "image/png"},
            content=thumbnail_bytes,
        )
        response.raise_for_status()
