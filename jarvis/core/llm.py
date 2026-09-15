"""LLM backend abstraction.

Default implementation talks to a local Ollama server (https://ollama.com), so the whole
assistant can run fully offline. The interface is intentionally narrow so a different backend
(another local runtime, or a hosted API) can be swapped in later without touching the agent.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import httpx

from jarvis import config


class LLMBackend(ABC):
    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Send a chat turn and return a single assistant message dict.

        The returned message follows the OpenAI/Ollama shape:
          {"role": "assistant", "content": "...", "tool_calls": [...] or absent}
        """
        raise NotImplementedError


class OllamaBackend(LLMBackend):
    def __init__(
        self,
        host: str = config.OLLAMA_HOST,
        model: str = config.MODEL_NAME,
        timeout: float = config.LLM_TIMEOUT_SECONDS,
    ) -> None:
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools

        try:
            response = httpx.post(
                f"{self.host}/api/chat", json=payload, timeout=self.timeout
            )
            response.raise_for_status()
        except httpx.ConnectError as exc:
            raise ConnectionError(
                f"Could not reach Ollama at {self.host}. Is `ollama serve` running and is "
                f"the model '{self.model}' pulled (`ollama pull {self.model}`)?"
            ) from exc

        data = response.json()
        message = data.get("message", {})
        return {
            "role": message.get("role", "assistant"),
            "content": message.get("content", ""),
            "tool_calls": message.get("tool_calls", []),
        }


def get_default_backend() -> LLMBackend:
    return OllamaBackend()
