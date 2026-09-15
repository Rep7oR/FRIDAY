"""Standalone agent: inbox updates.

Wraps the existing IMAP-based `CheckEmailTool` (headers only -- sender/subject/date,
never message bodies, no send/delete) in its own agent so it can be asked for a
briefing directly, independent of the main assistant.
"""
from __future__ import annotations

from jarvis.agents.base import BaseAgent, agent_system_prompt
from jarvis.core.llm import LLMBackend
from jarvis.core.tools.email_check import CheckEmailTool

SYSTEM_PROMPT = agent_system_prompt(
    "keeping the user up to date on their email inbox. You only ever see headers "
    "(sender, subject, date), never message bodies, and you cannot send, delete, or "
    "modify anything -- read-only. Group similar senders/subjects together and call out "
    "anything that looks time-sensitive."
)


class EmailAgent(BaseAgent):
    name = "EmailAgent"

    def __init__(self, llm: LLMBackend | None = None) -> None:
        super().__init__(system_prompt=SYSTEM_PROMPT, tools=[CheckEmailTool()], llm=llm)

    def briefing(self, max_results: int = 10, unread_only: bool = True) -> str:
        """Convenience entrypoint: ask for a plain-language summary of the inbox."""
        scope = "unread" if unread_only else "recent"
        return self.run(
            f"Give me a quick briefing on my {scope} emails (up to {max_results}). "
            "Summarize what's new, don't just repeat the raw list."
        )
