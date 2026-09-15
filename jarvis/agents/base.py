"""Shared LLM <-> tool loop for standalone single-purpose agents.

Deliberately mirrors `jarvis.core.agent.Agent`'s loop (LLM turn -> run any requested
tool calls -> feed results back -> repeat) but stays decoupled from it: each subclass
gets its own tiny ToolRegistry and system prompt instead of the main assistant's full
registry, so it only ever does its one job.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from jarvis import config
from jarvis.core.llm import LLMBackend, get_default_backend
from jarvis.core.memory import ConversationMemory
from jarvis.core.tools.base import Tool, ToolRegistry

logger = logging.getLogger(__name__)


class BaseAgent:
    name: str = "Agent"

    def __init__(
        self,
        system_prompt: str,
        tools: list[Tool],
        llm: LLMBackend | None = None,
        max_iterations: int = 4,
        persist_memory: bool = False,
    ) -> None:
        self.llm = llm or get_default_backend()
        self.tools = ToolRegistry()
        for tool in tools:
            self.tools.register(tool)
        self.memory = ConversationMemory(system_prompt, persist=persist_memory)
        self.max_iterations = max_iterations

    def run(self, user_input: str) -> str:
        self.memory.add("user", user_input)

        for _ in range(self.max_iterations):
            response = self.llm.chat(self.memory.as_list(), tools=self.tools.schemas())
            tool_calls = response.get("tool_calls") or []

            if not tool_calls:
                content = response.get("content", "").strip()
                self.memory.add("assistant", content)
                return content

            self.memory.messages.append(
                {"role": "assistant", "content": response.get("content", ""), "tool_calls": tool_calls}
            )
            for call in tool_calls:
                name, arguments, call_id = self._parse_tool_call(call)
                logger.info("%s tool call: %s(%s)", self.name, name, arguments)
                result = self.tools.call(name, arguments)
                self.memory.add_tool_result(call_id, name, result)

        return (
            f"{self.name} couldn't finish that within the allotted tool-call steps. "
            "Try a narrower request."
        )

    @staticmethod
    def _parse_tool_call(call: dict[str, Any]) -> tuple[str, dict[str, Any], str | None]:
        function = call.get("function", {})
        name = function.get("name", "")
        raw_arguments = function.get("arguments", {})
        if isinstance(raw_arguments, str):
            try:
                arguments = json.loads(raw_arguments) if raw_arguments else {}
            except json.JSONDecodeError:
                arguments = {}
        else:
            arguments = raw_arguments or {}
        return name, arguments, call.get("id")


def agent_system_prompt(role_description: str) -> str:
    """Shared preamble so every agent keeps the same voice as the main assistant."""
    return f"""You are {config.AGENT_NAME}, in a focused single-purpose mode: {role_description}
Address the user as "{config.HONORIFIC}" occasionally, not every sentence. Be concise -- a
short summary beats a wall of text. Use your tool when the request needs current data; for
anything else (clarifying questions, small talk about the results), just reply directly.
Every tool here prefixes a real failure with the literal text "Error:" -- only describe a
tool call as failed or erroring when the result actually starts with that. An empty result,
a "nothing new" result, or "no matches found" is a normal, successful outcome, not a
failure -- just report it plainly. Don't invent results; only report what a tool actually
returned.
"""
