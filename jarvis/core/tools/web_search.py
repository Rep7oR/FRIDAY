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
        DDGS = self._import_ddgs()
        if DDGS is None:
            return (
                "Error: no search backend installed. Run `pip install ddgs` "
                "(the current package name) or `pip install duckduckgo_search`."
            )

        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
        except Exception as exc:
            return (
                f"Error: web search failed ({type(exc).__name__}: {exc}). "
                "This is usually a network/firewall issue or DuckDuckGo rate-limiting -- "
                "try again in a moment, or run `pip install -U ddgs` to get the latest backend."
            )

        if not results:
            return f"No results found for '{query}'."

        lines = [f"Search results for '{query}':"]
        for i, r in enumerate(results, start=1):
            title = r.get("title", "").strip()
            href = r.get("href", "").strip()
            body = r.get("body", "").strip()
            lines.append(f"{i}. {title}\n   {href}\n   {body}")
        return "\n".join(lines)

    @staticmethod
    def _import_ddgs():
        # The package was renamed from `duckduckgo_search` to `ddgs`; support both so this
        # works regardless of which one ended up installed.
        try:
            from ddgs import DDGS

            return DDGS
        except ImportError:
            pass
        try:
            from duckduckgo_search import DDGS

            return DDGS
        except ImportError:
            return None
