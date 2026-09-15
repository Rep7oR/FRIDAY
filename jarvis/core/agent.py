"""The orchestrator agent: routes each user turn through the LLM, dispatches any tool calls
it asks for, feeds results back, and repeats until it has a final answer.

This is the "multiple tasks allocated to an agent" piece: rather than separate hardcoded
branches per task type, a single LLM decides *which* tool(s) a request needs (web search,
files, code execution, reminders) and calls them, so new capabilities just mean registering
a new Tool.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from jarvis import config
from jarvis.core.llm import LLMBackend, get_default_backend
from jarvis.core.memory import ConversationMemory
from jarvis.core.tools import ToolRegistry, build_default_registry

logger = logging.getLogger(__name__)


class Agent:
    def __init__(
        self,
        llm: LLMBackend | None = None,
        tools: ToolRegistry | None = None,
        system_prompt: str = config.SYSTEM_PROMPT,
        max_iterations: int = config.MAX_TOOL_ITERATIONS,
        persist_memory: bool = True,
    ) -> None:
        self.llm = llm or get_default_backend()
        self.tools = tools or build_default_registry()
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

            # Record the assistant's tool-calling turn, then execute each call and feed
            # the results back so the next LLM call can use them.
            self.memory.messages.append(
                {"role": "assistant", "content": response.get("content", ""), "tool_calls": tool_calls}
            )
            for call in tool_calls:
                name, arguments, call_id = self._parse_tool_call(call)
                logger.info("tool call: %s(%s)", name, arguments)
                result = self.tools.call(name, arguments)
                self.memory.add_tool_result(call_id, name, result)

        return (
            "I couldn't finish that within the allotted tool-call steps. "
            "Try breaking the request into smaller parts."
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
