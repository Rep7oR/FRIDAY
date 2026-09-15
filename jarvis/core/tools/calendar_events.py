"""Read-only upcoming-events lookup via the Google Calendar API.

Requires a one-time interactive setup (see scripts/google_calendar_auth.py and the
README) to produce a local token.json -- after that this tool refreshes silently.
Scoped to calendar.readonly: Jarvis can list events but never create, edit, or delete
anything.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jarvis import config
from jarvis.core.tools.base import Tool

NOT_CONFIGURED_MSG = (
    "Error: Google Calendar isn't connected yet. Run `python -m scripts.google_calendar_auth` "
    "after putting your OAuth credentials.json in place -- see README.md for the Google Cloud "
    "Console setup steps."
)


def _load_credentials():
    """Returns valid Credentials, refreshing/saving them if needed, or None if not set up."""
    if not config.GOOGLE_CALENDAR_TOKEN_PATH.exists():
        return None

    # Imported lazily so the rest of Jarvis works without the google-api packages
    # installed if calendar features aren't being used.
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    creds = Credentials.from_authorized_user_file(
        str(config.GOOGLE_CALENDAR_TOKEN_PATH), config.GOOGLE_CALENDAR_SCOPES
    )

    if creds.valid:
        return creds

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError:
            return None
        config.GOOGLE_CALENDAR_TOKEN_PATH.write_text(creds.to_json())
        return creds

    return None


class CalendarEventsTool(Tool):
    name = "check_calendar"
    description = (
        "Look up the user's upcoming Google Calendar events (read-only -- cannot create, "
        "edit, or delete anything). Requires Google Calendar to already be connected."
    )
    parameters = {
        "type": "object",
        "properties": {
            "days_ahead": {
                "type": "integer",
                "description": "How many days ahead to look (default 7, max 30).",
            },
            "max_results": {
                "type": "integer",
                "description": "How many events to list (default 10, max 25).",
            },
        },
        "required": [],
    }

    def run(self, days_ahead: int = 7, max_results: int = 10) -> str:
        try:
            from googleapiclient.discovery import build
            from googleapiclient.errors import HttpError
        except ImportError:
            return (
                "Error: Google Calendar support isn't installed. Run "
                "`pip install -r requirements.txt`."
            )

        creds = _load_credentials()
        if creds is None:
            return NOT_CONFIGURED_MSG

        days_ahead = max(1, min(int(days_ahead), 30))
        max_results = max(1, min(int(max_results), 25))

        now = datetime.now(timezone.utc)
        time_min = now.isoformat().replace("+00:00", "Z")
        time_max = (now + timedelta(days=days_ahead)).isoformat().replace("+00:00", "Z")

        try:
            service = build("calendar", "v3", credentials=creds, cache_discovery=False)
            result = (
                service.events()
                .list(
                    calendarId=config.GOOGLE_CALENDAR_ID,
                    timeMin=time_min,
                    timeMax=time_max,
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
        except HttpError as exc:
            return f"Error: Google Calendar request failed ({exc})."
        except Exception as exc:
            return f"Error: could not reach Google Calendar ({type(exc).__name__}: {exc})."

        events = result.get("items", [])
        if not events:
            return f"No events in the next {days_ahead} day(s)."

        lines = [f"Upcoming events (next {days_ahead} day(s)):"]
        for event in events:
            start = event.get("start", {}).get("dateTime") or event.get("start", {}).get("date", "")
            summary = event.get("summary", "(no title)")
            location = event.get("location")
            line = f"- {start}: {summary}"
            if location:
                line += f" @ {location}"
            lines.append(line)

        return "\n".join(lines)
