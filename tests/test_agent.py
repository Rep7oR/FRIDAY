import json

from jarvis.core.agent import Agent
from jarvis.core.llm import LLMBackend
from jarvis.core.tools.base import Tool, ToolRegistry


class EchoTool(Tool):
    name = "echo"
    description = "Echoes back its input, uppercased."
    parameters = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }

    def run(self, text: str) -> str:
        return text.upper()


class ScriptedBackend(LLMBackend):
    """Replays a fixed sequence of responses, one per `chat()` call, so tests don't need a
    real Ollama server."""

    def __init__(self, responses: list[dict]) -> None:
        self.responses = responses
        self.calls: list[list[dict]] = []

    def chat(self, messages, tools=None):
        self.calls.append(messages)
        return self.responses.pop(0)


def make_agent(responses: list[dict]) -> Agent:
    registry = ToolRegistry()
    registry.register(EchoTool())
    backend = ScriptedBackend(responses)
    return Agent(llm=backend, tools=registry, persist_memory=False)


def test_direct_reply_without_tool_use():
    agent = make_agent([{"role": "assistant", "content": "Hello there.", "tool_calls": []}])
    reply = agent.run("hi")
    assert reply == "Hello there."


def test_tool_call_then_final_answer():
    tool_call = {
        "id": "call_1",
        "function": {"name": "echo", "arguments": json.dumps({"text": "hi"})},
    }
    responses = [
        {"role": "assistant", "content": "", "tool_calls": [tool_call]},
        {"role": "assistant", "content": "Done: HI", "tool_calls": []},
    ]
    agent = make_agent(responses)
    reply = agent.run("please echo hi")
    assert reply == "Done: HI"

    # The tool result should have been fed back into the next LLM call.
    second_call_messages = agent.llm.calls[1]
    tool_messages = [m for m in second_call_messages if m.get("role") == "tool"]
    assert any(m["content"] == "HI" for m in tool_messages)


def test_gives_up_after_max_iterations():
    tool_call = {
        "id": "call_1",
        "function": {"name": "echo", "arguments": {"text": "loop"}},
    }
    # Every response keeps asking for another tool call, so the agent should hit the cap.
    responses = [
        {"role": "assistant", "content": "", "tool_calls": [tool_call]} for _ in range(10)
    ]
    agent = make_agent(responses)
    agent.max_iterations = 3
    reply = agent.run("loop forever")
    assert "couldn't finish" in reply
