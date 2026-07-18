"""One-time interactive OAuth bootstrap for YouTube uploads.

Run this once (and again whenever token.json's refresh token expires -
every 7 days on an OAuth consent screen left in Testing mode, which is
the default for personal/unverified use). Opens a browser for you to sign
in and grant the youtube.upload scope, then saves the resulting
credentials (including the refresh token) to backend/token.json.

The actual backend service (YoutubeUploadClient) only ever reads
token.json and refreshes the access token as needed - it never runs this
interactive flow itself, since a browser-based consent screen doesn't fit
an async request/response cycle.

Usage: python scripts/authorize_youtube.py
Requires backend/client_secrets.json (OAuth 2.0 Desktop app client,
downloaded from Google Cloud Console - see Publishing Automation setup).
"""

import json
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRETS_PATH = Path(__file__).resolve().parent.parent / "client_secrets.json"
TOKEN_PATH = Path(__file__).resolve().parent.parent / "token.json"


def main() -> None:
    if not CLIENT_SECRETS_PATH.exists():
        raise SystemExit(
            f"Missing {CLIENT_SECRETS_PATH}. Download it from Google Cloud Console "
            "(APIs & Services -> Credentials -> your Desktop app OAuth client)."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRETS_PATH), SCOPES)
    credentials = flow.run_local_server(port=0)

    TOKEN_PATH.write_text(
        json.dumps(
            {
                "refresh_token": credentials.refresh_token,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "token_uri": credentials.token_uri,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Saved credentials to {TOKEN_PATH}")


if __name__ == "__main__":
    main()
