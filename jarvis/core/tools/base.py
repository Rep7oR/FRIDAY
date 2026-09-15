"""Tool abstraction shared by every capability Jarvis can invoke."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Tool(ABC):
    name: str
    description: str
    # JSON Schema for the tool's parameters (the "properties"/"required" object),
    # following the same convention OpenAI/Ollama function-calling expects.
    parameters: dict[str, Any] = {"type": "object", "properties": {}, "required": []}

    @abstractmethod
    def run(self, **kwargs: Any) -> str:
        """Execute the tool and return a plain-text result to feed back to the LLM."""
        raise NotImplementedError

    def to_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def schemas(self) -> list[dict[str, Any]]:
        return [tool.to_schema() for tool in self._tools.values()]

    def call(self, name: str, arguments: dict[str, Any]) -> str:
        tool = self.get(name)
        if tool is None:
            return f"Error: no such tool '{name}'."
        try:
            return tool.run(**arguments)
        except TypeError as exc:
            return f"Error: bad arguments for tool '{name}': {exc}"
        except Exception as exc:  # tool failures shouldn't crash the agent loop
            return f"Error: tool '{name}' failed: {exc}"
