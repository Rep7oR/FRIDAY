#!/usr/bin/env python3
"""One-time interactive setup for the calendar agent's Google Calendar access.

Run this once after downloading your OAuth client credentials from Google Cloud
Console (see README.md for the click-by-click steps) and saving them to the path
JARVIS_GOOGLE_CALENDAR_CREDENTIALS points at (default: data/google_credentials.json).

It opens a browser for you to sign in and grant read-only calendar access, then saves
the resulting token to JARVIS_GOOGLE_CALENDAR_TOKEN (default: data/google_token.json).
After that, CalendarEventsTool/CalendarAgent refresh the token silently -- you should
never need to run this again unless you revoke access.

Run: python -m scripts.google_calendar_auth
"""
from __future__ import annotations

import sys

from jarvis import config


def main() -> None:
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        sys.exit(
            "google-auth-oauthlib isn't installed. Run `pip install -r requirements.txt` first."
        )

    if not config.GOOGLE_CALENDAR_CREDENTIALS_PATH.exists():
        sys.exit(
            f"No credentials file at {config.GOOGLE_CALENDAR_CREDENTIALS_PATH}.\n"
            "Download your OAuth client credentials.json from Google Cloud Console "
            "(APIs & Services -> Credentials -> Create OAuth client ID -> Desktop app) "
            f"and save it to that path, or point JARVIS_GOOGLE_CALENDAR_CREDENTIALS at it."
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        str(config.GOOGLE_CALENDAR_CREDENTIALS_PATH), config.GOOGLE_CALENDAR_SCOPES
    )
    creds = flow.run_local_server(port=0)

    config.GOOGLE_CALENDAR_TOKEN_PATH.write_text(creds.to_json())
    print(f"Saved Google Calendar token to {config.GOOGLE_CALENDAR_TOKEN_PATH}.")
    print("The calendar agent is ready -- try: CalendarAgent().briefing()")


if __name__ == "__main__":
    main()
