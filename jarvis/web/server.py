"""Web UI backend.

A thin FastAPI wrapper around the same `Agent` the CLI uses, plus a static HUD-style
single-page frontend. Voice runs entirely in the browser (Web Speech API for
speech-to-text, `speechSynthesis` for text-to-speech), so this needs no server-side audio
stack -- just a browser tab.

Run with:
    uvicorn jarvis.web.server:app --reload
"""
from __future__ import annotations

from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from jarvis import config
from jarvis.core.agent import Agent
from jarvis.core.tools.scheduler import ListRemindersTool
from jarvis.web import system_stats, weather as weather_module

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title=f"{config.AGENT_NAME} Web")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

_agent: Agent | None = None


def get_agent() -> Agent:
    global _agent
    if _agent is None:
        _agent = Agent()
    return _agent


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    message = request.message.strip()
    if not message:
        return ChatResponse(reply="")
    try:
        reply = get_agent().run(message)
    except ConnectionError as exc:
        reply = str(exc)
    return ChatResponse(reply=reply)


@app.get("/api/reminders")
def reminders() -> dict:
    return {"reminders": ListRemindersTool().run()}


@app.get("/api/status")
def status() -> dict:
    try:
        response = httpx.get(f"{config.OLLAMA_HOST}/api/tags", timeout=2)
        response.raise_for_status()
        models = [m["name"] for m in response.json().get("models", [])]
        online = config.MODEL_NAME in models or any(
            m.startswith(config.MODEL_NAME) for m in models
        )
        return {"ollama_reachable": True, "model_available": online, "model": config.MODEL_NAME}
    except Exception:
        return {"ollama_reachable": False, "model_available": False, "model": config.MODEL_NAME}


@app.get("/api/system")
def system() -> dict:
    return system_stats.get_system_stats()


@app.get("/api/weather")
def weather(lat: float, lon: float) -> dict:
    try:
        return {"ok": True, **weather_module.get_weather(lat, lon)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
