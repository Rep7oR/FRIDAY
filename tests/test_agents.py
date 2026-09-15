import json

import jarvis.core.tools.job_search as job_search
from jarvis.agents.base import BaseAgent
from jarvis.core.llm import LLMBackend
from jarvis.core.tools.base import Tool
from jarvis.core.tools.job_search import NewJobPostingsTool


class ScriptedBackend(LLMBackend):
    """Replays a fixed sequence of responses, one per `chat()` call."""

    def __init__(self, responses: list[dict]) -> None:
        self.responses = responses
        self.calls: list[list[dict]] = []

    def chat(self, messages, tools=None):
        self.calls.append(messages)
        return self.responses.pop(0)


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


def test_base_agent_direct_reply_without_tool_use():
    backend = ScriptedBackend([{"role": "assistant", "content": "Hi there.", "tool_calls": []}])
    agent = BaseAgent(system_prompt="test agent", tools=[EchoTool()], llm=backend)
    assert agent.run("hello") == "Hi there."


def test_base_agent_tool_call_then_final_answer():
    tool_call = {
        "id": "call_1",
        "function": {"name": "echo", "arguments": json.dumps({"text": "hi"})},
    }
    responses = [
        {"role": "assistant", "content": "", "tool_calls": [tool_call]},
        {"role": "assistant", "content": "Done: HI", "tool_calls": []},
    ]
    backend = ScriptedBackend(responses)
    agent = BaseAgent(system_prompt="test agent", tools=[EchoTool()], llm=backend)
    assert agent.run("please echo hi") == "Done: HI"

    tool_messages = [m for m in backend.calls[1] if m.get("role") == "tool"]
    assert any(m["content"] == "HI" for m in tool_messages)


def _posting(job_id: str, position: str) -> dict:
    return {
        "id": job_id,
        "position": position,
        "company": "Acme",
        "tags": [],
        "description": "",
        "url": f"http://example.test/{job_id}",
    }


def test_new_job_postings_first_check_has_no_baseline(monkeypatch):
    postings = [_posting("1", "Python Developer"), _posting("2", "Data Analyst")]
    monkeypatch.setattr(job_search, "fetch_postings", lambda: postings)

    tool = NewJobPostingsTool()
    result = tool.run(query="python", max_results=5)

    assert "no baseline" in result.lower()


def test_new_job_postings_only_reports_new_on_later_checks(monkeypatch):
    first_batch = [_posting("1", "Python Developer")]
    monkeypatch.setattr(job_search, "fetch_postings", lambda: first_batch)
    tool = NewJobPostingsTool()
    tool.run(query="python", max_results=5)  # establishes the baseline

    second_batch = first_batch + [_posting("2", "Python Backend Engineer")]
    monkeypatch.setattr(job_search, "fetch_postings", lambda: second_batch)
    result = tool.run(query="python", max_results=5)

    assert "Python Backend Engineer" in result
    assert "Python Developer" not in result  # already seen -- shouldn't repeat

    # A third check with nothing new should report no new postings at all.
    result_again = tool.run(query="python", max_results=5)
    assert "Python Backend Engineer" not in result_again
