"""Standalone agent: newly posted jobs.

Wraps `NewJobPostingsTool` (RemoteOK-sourced, dedupes against previously seen postings
per query via SQLite) so it can be asked directly: "anything new for X?" The first check
for a given query establishes a baseline -- there's nothing "new" to compare against yet
-- and every check after that only surfaces postings that weren't there before.
"""
from __future__ import annotations

from jarvis.agents.base import BaseAgent, agent_system_prompt
from jarvis.core.llm import LLMBackend
from jarvis.core.tools.job_search import NewJobPostingsTool

SYSTEM_PROMPT = agent_system_prompt(
    "watching the job market for newly posted roles (sourced from RemoteOK, so results "
    "skew remote/tech). Only report postings the tool flags as new -- never claim "
    "something is new if the tool didn't say so. On a query's first-ever check there's no "
    "baseline yet, so say that plainly rather than implying nothing's out there."
)


class JobAgent(BaseAgent):
    name = "JobAgent"

    def __init__(self, llm: LLMBackend | None = None) -> None:
        super().__init__(system_prompt=SYSTEM_PROMPT, tools=[NewJobPostingsTool()], llm=llm)

    def check(self, query: str, max_results: int = 5) -> str:
        """Convenience entrypoint: check one query for new postings."""
        return self.run(f"Check for new job postings matching '{query}' (up to {max_results}).")
