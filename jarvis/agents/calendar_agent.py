"""Standalone agent: calendar events.

Wraps `CalendarEventsTool` (Google Calendar, read-only) so upcoming events can be
asked for directly. Requires a one-time `python -m scripts.google_calendar_auth` run
first -- see README.md.
"""
from __future__ import annotations

from jarvis.agents.base import BaseAgent, agent_system_prompt
from jarvis.core.llm import LLMBackend
from jarvis.core.tools.calendar_events import CalendarEventsTool

SYSTEM_PROMPT = agent_system_prompt(
    "keeping the user oriented on their upcoming Google Calendar events. You are "
    "read-only -- you cannot create, edit, or delete events, and you should never imply "
    "otherwise. Call out anything happening today or tomorrow first, then the rest in "
    "chronological order. Flag back-to-back or overlapping events."
)


class CalendarAgent(BaseAgent):
    name = "CalendarAgent"

    def __init__(self, llm: LLMBackend | None = None) -> None:
        super().__init__(system_prompt=SYSTEM_PROMPT, tools=[CalendarEventsTool()], llm=llm)

    def briefing(self, days_ahead: int = 7) -> str:
        """Convenience entrypoint: summarize what's coming up."""
        return self.run(
            f"What's on my calendar for the next {days_ahead} days? "
            "Flag anything today or tomorrow, and any overlapping events."
        )
