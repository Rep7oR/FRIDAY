"""Web search tool, backed by DuckDuckGo (no API key required)."""
from __future__ import annotations

from jarvis.core.tools.base import Tool


class WebSearchTool(Tool):
    name = "web_search"
    description = (
        "Search the public web for current information (news, facts, docs). "
        "Returns a short list of titles, URLs, and snippets."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query."},
            "max_results": {
                "type": "integer",
                "description": "How many results to return (default 5, max 10).",
            },
        },
        "required": ["query"],
    }

    def run(self, query: str, max_results: int = 5) -> str:
        max_results = max(1, min(int(max_results), 10))
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            return (
                "Error: the 'duckduckgo_search' package is not installed. "
                "Run `pip install duckduckgo_search` to enable web search."
            )

        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
        except Exception as exc:
            return f"Error: web search failed ({exc}). Check network connectivity."

        if not results:
            return f"No results found for '{query}'."

        lines = [f"Search results for '{query}':"]
        for i, r in enumerate(results, start=1):
            title = r.get("title", "").strip()
            href = r.get("href", "").strip()
            body = r.get("body", "").strip()
            lines.append(f"{i}. {title}\n   {href}\n   {body}")
        return "\n".join(lines)
