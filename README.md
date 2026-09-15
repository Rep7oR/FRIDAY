# Jarvis

A personal-assistant agent that runs entirely on your own machine: a local LLM (via
[Ollama](https://ollama.com)) reasons about each request and decides which tool(s) to use —
web search, sandboxed file/code access, or reminders — then replies, optionally by voice.

## Architecture

```
jarvis/
  config.py            Central settings (env-var driven)
  core/
    llm.py              Pluggable LLM backend (Ollama by default)
    agent.py            Orchestrator: LLM <-> tools loop
    memory.py           Conversation history (in-memory + SQLite persistence)
    db.py               Shared SQLite connection/schema
    tools/
      base.py            Tool ABC + ToolRegistry
      web_search.py       DuckDuckGo search (no API key needed)
      files.py            Sandboxed read/write/list under data/workspace/
      code_exec.py        Run short Python snippets in a subprocess
      scheduler.py        Reminders (SQLite) + background due-checker
      email_check.py       Inbox headers via IMAP (needs your credentials, see Setup)
      job_search.py         Job postings via RemoteOK (no API key needed) + new-postings dedupe
      calendar_events.py     Upcoming Google Calendar events, read-only (see Setup)
      news.py                Sector/topic news via DuckDuckGo news search
  agents/                Standalone single-purpose agents (see below)
    base.py               Shared LLM <-> tool loop each one runs on its own
    email_agent.py         EmailAgent — inbox briefings
    job_agent.py            JobAgent — newly posted jobs only
    calendar_agent.py        CalendarAgent — upcoming events
  cli.py                Text-mode entrypoint (no audio hardware needed)
  voice/
    stt.py               Speech-to-text (faster-whisper, local)
    tts.py               Text-to-speech (pyttsx3, local)
    wake_word.py          Push-to-talk or "say the wake word" listening triggers
    pipeline.py          Wires trigger -> record -> STT -> agent -> TTS
  main.py               Voice-mode entrypoint
  web/
    server.py            FastAPI app: /api/chat, /api/reminders, /api/status
    __main__.py          `python -m jarvis.web` entrypoint
    static/               HUD-style single-page frontend (voice via browser Web Speech API)
```

**How "multiple tasks allocated to an agent" works here:** there's one orchestrator
(`core/agent.py`). Every user turn goes to the local LLM along with the JSON schema of every
registered `Tool`. The model itself decides whether the request needs a web search, a file
operation, code execution, a reminder, or just a direct answer, and asks for the matching
tool call(s). Adding a new capability means writing one `Tool` subclass and registering it in
`core/tools/__init__.py` — no routing logic to update.

## Standalone agents

Alongside the one orchestrator above, `jarvis/agents/` has three single-purpose agents —
each with its own system prompt, its own one-tool registry, and its own `run()` loop
(`jarvis/agents/base.py`). Use these when you want to ask one thing directly (or wire them
into your own script/scheduler) instead of going through the main assistant:

```python
from jarvis.agents import EmailAgent, JobAgent, CalendarAgent

print(EmailAgent().briefing())                 # summarize unread inbox
print(JobAgent().check("python developer"))     # only postings new since last check
print(CalendarAgent().briefing(days_ahead=3))   # what's coming up
```

- **EmailAgent** — same read-only IMAP headers as `check_email` (see Setup below for
  credentials), summarized into a briefing instead of a raw list.
- **JobAgent** — searches RemoteOK and remembers what it's already shown you per query
  (in SQLite), so `.check("query")` only ever reports postings that are actually new. The
  first check for a query has no baseline yet and says so rather than implying nothing's open.
- **CalendarAgent** — read-only upcoming Google Calendar events. Needs a one-time OAuth
  setup — see "Enable calendar events" below.

## Setup

1. **Install [Ollama](https://ollama.com)** and pull a tool-calling-capable model:
   ```bash
   ollama pull llama3.1
   ollama serve   # if not already running as a service
   ```
2. **Install Python dependencies:**
   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
   On Linux, voice mode also needs the `espeak` system package for `pyttsx3`
   (`apt install espeak`) and PortAudio for `sounddevice` (`apt install portaudio19-dev`).
3. **(Optional) Enable email checking.** The `check_email` tool needs an app-specific
   password, never your real account password:
   - **Gmail:** turn on 2-Step Verification, then create one at
     [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
   - **Outlook/Microsoft:** create an app password at
     [account.microsoft.com/security](https://account.microsoft.com/security) (needs
     2-factor auth enabled first).
   - Then set:
     ```bash
     export JARVIS_EMAIL_ADDRESS="you@gmail.com"
     export JARVIS_EMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"
     export JARVIS_EMAIL_IMAP_HOST="imap.gmail.com"   # imap-mail.outlook.com for Outlook
     ```
   Without these set, `check_email` just tells you it isn't configured instead of failing
   cryptically. The tool only ever reads headers (sender/subject/date) — never message
   bodies, and there's no send/delete capability.
4. **(Optional) Enable calendar events**, needed for `CalendarAgent`/`check_calendar`:
   - Go to [console.cloud.google.com](https://console.cloud.google.com), create (or pick) a
     project, then **APIs & Services → Library** and enable the **Google Calendar API**.
   - **APIs & Services → Credentials → Create Credentials → OAuth client ID**. If prompted,
     configure the consent screen first (External is fine; add yourself as a test user).
     Application type: **Desktop app**.
   - Download the resulting JSON and save it as `data/google_credentials.json` (or point
     `JARVIS_GOOGLE_CALENDAR_CREDENTIALS` at wherever you put it).
   - Run the one-time interactive auth flow — this opens a browser for you to sign in and
     grant **read-only** calendar access:
     ```bash
     python -m scripts.google_calendar_auth
     ```
     This writes `data/google_token.json`; after that, `CalendarAgent`/`check_calendar`
     refresh the token silently. Without it, they just explain what's missing instead of
     failing cryptically. Google Calendar access here is read-only — Jarvis cannot create,
     edit, or delete events.

## Running it

**Text chat (works anywhere, no mic/speakers needed):**
```bash
python -m jarvis.cli
```

**Voice mode (needs a real microphone/speakers, so run this on your own machine):**
```bash
python -m jarvis.main            # push-to-talk: press Enter, then speak
python -m jarvis.main --wake-word  # always-listening; needs `pip install openwakeword`
                                    # then `python -m openwakeword.download` once
```

Both entrypoints share the same `Agent`, tools, and reminders, so a reminder you set in text
mode will fire (and get spoken) in voice mode too.

**Interactive web UI (HUD-style, with voice, in your browser):**
```bash
python -m jarvis.web
```
Then open **http://127.0.0.1:8000** in Chrome or Edge. The mic button uses the browser's
built-in speech recognition (Web Speech API) to capture voice input, and replies are read
aloud with `speechSynthesis` — no server-side audio libraries needed for this mode, so it
works the same on Windows/macOS/Linux as long as the browser supports it (Firefox and Safari
don't support `SpeechRecognition` yet; typing still works everywhere). The status dot at the
top shows whether it can reach Ollama and whether the configured model is pulled.

## Configuration

All settings are environment variables with local defaults (see `jarvis/config.py`):

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `JARVIS_MODEL` | `llama3.1` | Model to use (needs tool-calling support) |
| `JARVIS_DATA_DIR` | `./data` | Where the SQLite DB and file-tool sandbox live |
| `JARVIS_WAKE_WORD` | `jarvis` | Wake word for `--wake-word` mode |
| `JARVIS_STT_MODEL` | `base.en` | faster-whisper model size |
| `JARVIS_HONORIFIC` | `sir` | How Jarvis addresses you |
| `JARVIS_EMAIL_ADDRESS` | _(unset)_ | Email address for `check_email` |
| `JARVIS_EMAIL_APP_PASSWORD` | _(unset)_ | App-specific password (see Setup) |
| `JARVIS_EMAIL_IMAP_HOST` | `imap.gmail.com` | IMAP server |

## Tests

```bash
pytest
```

Tests cover the tool sandbox (including path-traversal rejection), the reminders CRUD +
due-date logic, the agent's tool-calling loop (against a scripted fake LLM backend, so no
Ollama server is required to run them), and the standalone agents' loop + the job agent's
new-postings dedupe logic (`tests/test_agents.py`).

## Extending it

To add a new capability (e.g. a Google Calendar/Gmail integration, once you have OAuth
credentials set up):
1. Subclass `Tool` in a new file under `jarvis/core/tools/`, defining `name`, `description`,
   a JSON-Schema `parameters`, and a `run(**kwargs) -> str` method.
2. Register an instance of it in `build_default_registry()` in `jarvis/core/tools/__init__.py`.

That's it — the orchestrator will pick it up automatically and the LLM will call it when a
request warrants it.

## Known limitations

- CLI voice mode (`jarvis.main`) requires local audio hardware and hasn't been exercised
  end-to-end in this sandboxed dev environment — verify it on your own machine. The web UI's
  voice input/output runs in the browser instead, so it doesn't have this limitation.
- `run_python` and `web_search` are useful but not hardened against a fully adversarial user;
  don't expose this assistant to untrusted input without adding stricter sandboxing
  (e.g. containerized code execution, output size limits already in place).
- Scheduling currently only supports local reminders.
- `job_search`/`JobAgent` source from RemoteOK's free API, so results skew remote/tech roles.
  Swap in a broader provider (e.g. Adzuna, which needs a free API key) if you want
  local/non-remote listings.
- The Google Calendar setup (`scripts/google_calendar_auth.py`) hasn't been exercised
  end-to-end in this sandboxed dev environment — a broken `cryptography` Rust-binding install
  here made the OAuth flow itself untestable locally, though `CalendarEventsTool`'s
  not-configured/not-installed error paths were verified. Run the setup on your own machine
  and let me know if anything doesn't match.
