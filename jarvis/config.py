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
MAX_TOOL_ITERATIONS = int(os.environ.get("JARVIS_MAX_TOOL_ITERATIONS", "6"))
LLM_TIMEOUT_SECONDS = float(os.environ.get("JARVIS_LLM_TIMEOUT", "120"))

# Voice
WAKE_WORD = os.environ.get("JARVIS_WAKE_WORD", "jarvis")
TTS_RATE = int(os.environ.get("JARVIS_TTS_RATE", "185"))
STT_MODEL_SIZE = os.environ.get("JARVIS_STT_MODEL", "base.en")

SYSTEM_PROMPT = f"""You are {AGENT_NAME}, a personal assistant agent running locally on the user's machine.
You can converse directly, and you have tools for web search, reading/writing files in a sandboxed
workspace, running short Python snippets, and managing reminders/scheduled tasks.

Rules:
- Use a tool whenever the request needs current information, file/code work, or reminders.
- Don't invent tool results; only report what a tool actually returned.
- Keep spoken/short replies concise, since responses may be read aloud.
- If a request is ambiguous or destructive (deleting files, running risky code), ask for confirmation first.
"""
