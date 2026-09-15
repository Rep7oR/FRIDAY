"""Standalone single-purpose agents.

Unlike `jarvis.core.agent.Agent` (the one orchestrator behind the CLI/voice/web
entrypoints, which picks from *every* registered tool), each agent in this package
owns one narrow job, its own system prompt, and its own small toolset. They're meant
to be run on their own -- directly, from a script, or on a schedule -- rather than only
when the main assistant decides to reach for a tool.
"""
from jarvis.agents.calendar_agent import CalendarAgent
from jarvis.agents.email_agent import EmailAgent
from jarvis.agents.job_agent import JobAgent

__all__ = ["CalendarAgent", "EmailAgent", "JobAgent"]
