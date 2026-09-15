from jarvis.core.tools.base import Tool, ToolRegistry
from jarvis.core.tools.code_exec import RunPythonTool
from jarvis.core.tools.email_check import CheckEmailTool
from jarvis.core.tools.files import ListFilesTool, ReadFileTool, WriteFileTool
from jarvis.core.tools.job_search import JobSearchTool
from jarvis.core.tools.news import NewsTool
from jarvis.core.tools.scheduler import (
    AddReminderTool,
    CompleteReminderTool,
    DeleteReminderTool,
    ListRemindersTool,
)
from jarvis.core.tools.web_search import WebSearchTool


def build_default_registry() -> ToolRegistry:
    """Assemble the standard set of tools Jarvis ships with."""
    registry = ToolRegistry()
    for tool in (
        WebSearchTool(),
        ReadFileTool(),
        WriteFileTool(),
        ListFilesTool(),
        RunPythonTool(),
        AddReminderTool(),
        ListRemindersTool(),
        CompleteReminderTool(),
        DeleteReminderTool(),
        CheckEmailTool(),
        JobSearchTool(),
        NewsTool(),
    ):
        registry.register(tool)
    return registry


__all__ = ["Tool", "ToolRegistry", "build_default_registry"]
