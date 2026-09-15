"""Sector/topic news via DuckDuckGo's news search -- same backend and zero-config philosophy
as the general web_search tool (no separate API key)."""
from __future__ import annotations

from jarvis.core.tools.base import Tool
from jarvis.core.tools.web_search import WebSearchTool


class NewsTool(Tool):
    name = "get_news"
    description = (
        "Get recent news headlines about a topic or sector (e.g. 'artificial intelligence', "
        "'renewable energy', 'stock market', 'F1'). Returns recent articles with source and date."
    )
    parameters = {
        "type": "object",
        "properties": {
            "topic": {"type": "string", "description": "Topic or sector to get news about."},
            "max_results": {
                "type": "integer",
                "description": "How many articles to return (default 5, max 10).",
            },
        },
        "required": ["topic"],
    }

    def run(self, topic: str, max_results: int = 5) -> str:
        max_results = max(1, min(int(max_results), 10))
        DDGS = WebSearchTool._import_ddgs()
        if DDGS is None:
            return (
                "Error: no search backend installed. Run `pip install ddgs` to enable news search."
            )

        try:
            with DDGS() as ddgs:
                results = list(ddgs.news(topic, max_results=max_results))
        except Exception as exc:
            return (
                f"Error: news search failed ({type(exc).__name__}: {exc}). "
                "Usually a network/rate-limit issue -- try again in a moment."
            )

        if not results:
            return f"No recent news found for '{topic}'."

        lines = [f"Recent news on '{topic}':"]
        for i, r in enumerate(results, start=1):
            title = r.get("title", "").strip()
            source = r.get("source", "").strip()
            date = r.get("date", "").strip()
            url = (r.get("url") or r.get("href") or "").strip()
            body = r.get("body", "").strip()
            lines.append(f"{i}. {title} ({source}, {date})\n   {url}\n   {body}")
        return "\n".join(lines)
