"""Central configuration for Jarvis, driven by environment variables with sane local defaults."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("JARVIS_DATA_DIR", BASE_DIR / "data"))
WORKSPACE_DIR = Path(os.environ.get("JARVIS_WORKSPACE_DIR", DATA_DIR / "workspace"))
DB_PATH = Path(os.environ.get("JARVIS_DB_PATH", DATA_DIR / "jarvis.db"))

DATA_DIR.mkdir(parents=True, exist_ok=True)
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

# LLM backend (local Ollama server by default; kept pluggable via core/llm.py)
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
MODEL_NAME = os.environ.get("JARVIS_MODEL", "llama3.1")

AGENT_NAME = os.environ.get("JARVIS_NAME", "Jarvis")
HONORIFIC = os.environ.get("JARVIS_HONORIFIC", "sir")
MAX_TOOL_ITERATIONS = int(os.environ.get("JARVIS_MAX_TOOL_ITERATIONS", "6"))
LLM_TIMEOUT_SECONDS = float(os.environ.get("JARVIS_LLM_TIMEOUT", "120"))

# Voice
WAKE_WORD = os.environ.get("JARVIS_WAKE_WORD", "jarvis")
TTS_RATE = int(os.environ.get("JARVIS_TTS_RATE", "185"))
STT_MODEL_SIZE = os.environ.get("JARVIS_STT_MODEL", "base.en")

# Email (optional -- the check_email tool explains what's missing if these aren't set).
# Use an app-specific password, never your real account password. See README for
# provider-specific setup (Gmail/Outlook/etc).
EMAIL_ADDRESS = os.environ.get("JARVIS_EMAIL_ADDRESS", "")
EMAIL_APP_PASSWORD = os.environ.get("JARVIS_EMAIL_APP_PASSWORD", "")
EMAIL_IMAP_HOST = os.environ.get("JARVIS_EMAIL_IMAP_HOST", "imap.gmail.com")
EMAIL_IMAP_PORT = int(os.environ.get("JARVIS_EMAIL_IMAP_PORT", "993"))

# Google Calendar (optional -- CalendarEventsTool explains what's missing if unset).
# credentials.json is the OAuth client secret you download from Google Cloud Console;
# token.json is generated locally by scripts/google_calendar_auth.py after a one-time
# interactive consent flow and holds no secret beyond your own refresh token. Both are
# read-only scoped -- Jarvis cannot create, edit, or delete events.
GOOGLE_CALENDAR_CREDENTIALS_PATH = Path(
    os.environ.get("JARVIS_GOOGLE_CALENDAR_CREDENTIALS", DATA_DIR / "google_credentials.json")
)
GOOGLE_CALENDAR_TOKEN_PATH = Path(
    os.environ.get("JARVIS_GOOGLE_CALENDAR_TOKEN", DATA_DIR / "google_token.json")
)
GOOGLE_CALENDAR_ID = os.environ.get("JARVIS_GOOGLE_CALENDAR_ID", "primary")
GOOGLE_CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

SYSTEM_PROMPT = f"""You are {AGENT_NAME}, a personal AI assistant running locally on the user's own
machine, in the style of a calm, unflappable butler-AI: formal but warm, dryly witty, never
obsequious or overly chipper. Address the user as "{HONORIFIC}" occasionally and naturally
(e.g. to open a reply, or when confirming something important) -- not in every single sentence,
that gets tiresome fast. Be concise and efficient: no filler, no "As an AI..." disclaimers, get
to the point, then offer a next step if one is useful. A touch of dry humor is welcome when it fits,
but never at the expense of clarity.

You can converse directly, and you have tools for web search, reading/writing files in a sandboxed
workspace, running short Python snippets, managing reminders/scheduled tasks, checking the user's
email inbox, searching current job postings, and getting recent news for a topic/sector.

Rules:
- For greetings and small talk (e.g. "hi", "how are you"), just reply directly -- do not call a tool.
- Use a tool only when the request actually needs current information, file/code work, or reminders.
- If a tool call fails or returns an error, say plainly what went wrong (e.g. "web search failed:
  <reason>") instead of guessing or repeatedly retrying the same call.
- Don't invent tool results; only report what a tool actually returned.
- Keep spoken/short replies concise, since responses may be read aloud.
- If a request is ambiguous or destructive (deleting files, running risky code), ask for confirmation first.
"""
