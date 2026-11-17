
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


BASE_DIR = Path(__file__).resolve().parent.parent

# Local defaults; Render paths are configured through environment variables.
CREDENTIALS_FILE = Path(
    os.environ.get(
        "GOOGLE_CREDENTIALS_FILE",
        str(BASE_DIR / "credentials.json")
    )
)

TOKEN_FILE = Path(
    os.environ.get(
        "GOOGLE_TOKEN_FILE",
        str(BASE_DIR / "token.json")
    )
)

# Render Secret Files are read-only, so refreshed tokens go into /tmp.
TOKEN_CACHE_FILE = Path(
    os.environ.get(
        "GOOGLE_TOKEN_CACHE_FILE",
        str(TOKEN_FILE)
    )
)

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def get_gmail_service():
    if not CREDENTIALS_FILE.exists():
        raise FileNotFoundError(
            f"Gmail credentials file not found: {CREDENTIALS_FILE}"
        )

    credentials = None

    # Prefer the writable refreshed-token cache when it exists.
    token_to_load = (
        TOKEN_CACHE_FILE
        if TOKEN_CACHE_FILE.exists()
        else TOKEN_FILE
    )

    if token_to_load.exists():
        credentials = Credentials.from_authorized_user_file(
            str(token_to_load), SCOPES
        )

    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        TOKEN_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_CACHE_FILE.write_text(
            credentials.to_json(),
            encoding="utf-8"
        )

    if not credentials or not credentials.valid:
        # Do not launch an interactive browser login on a hosted server.
        if os.environ.get("GOOGLE_CREDENTIALS_FILE"):
            raise RuntimeError(
                "Gmail OAuth token is missing or invalid. "
                "Generate a valid token locally and upload it to Render."
            )

        flow = InstalledAppFlow.from_client_secrets_file(
            str(CREDENTIALS_FILE), SCOPES
        )

        credentials = flow.run_local_server(port=0)

        TOKEN_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_CACHE_FILE.write_text(
            credentials.to_json(),
            encoding="utf-8"
        )

    return build("gmail", "v1", credentials=credentials)
