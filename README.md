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

## Tests

```bash
pytest
```

Tests cover the tool sandbox (including path-traversal rejection), the reminders CRUD +
due-date logic, and the agent's tool-calling loop (against a scripted fake LLM backend, so no
Ollama server is required to run them).

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
- Scheduling currently only supports local reminders; calendar/email integrations are a
  natural next `Tool` to add once you have credentials for those services.
