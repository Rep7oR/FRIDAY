from jarvis.core.tools.base import Tool, ToolRegistry
from jarvis.core.tools.calendar_events import CalendarEventsTool
from jarvis.core.tools.email_check import CheckEmailTool
from jarvis.core.tools.job_search import NewJobPostingsTool


def build_default_registry() -> ToolRegistry:
    """Assemble the tools Jarvis ships with: email, new job postings, calendar."""
    registry = ToolRegistry()
    for tool in (
        CheckEmailTool(),
        NewJobPostingsTool(),
        CalendarEventsTool(),
    ):
        registry.register(tool)
    return registry


__all__ = ["Tool", "ToolRegistry", "build_default_registry"]
