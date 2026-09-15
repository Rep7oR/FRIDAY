"""Job posting search via the RemoteOK public API (https://remoteok.com/api) -- free, no key.
Skews remote/tech since that's what RemoteOK lists; swap in a different provider (e.g. Adzuna,
which needs a free API key) here if you want broader/local listings.
"""
from __future__ import annotations

import httpx

from jarvis.core.tools.base import Tool


class JobSearchTool(Tool):
    name = "search_jobs"
    description = (
        "Search current job postings by role/keyword (e.g. 'python developer', 'product "
        "designer', 'data analyst'). Results are sourced from RemoteOK, so they skew "
        "remote/tech roles."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Job title, keyword, or tag to search for."},
            "max_results": {
                "type": "integer",
                "description": "How many postings to return (default 5, max 15).",
            },
        },
        "required": ["query"],
    }

    def run(self, query: str, max_results: int = 5) -> str:
        max_results = max(1, min(int(max_results), 15))
        try:
            response = httpx.get(
                "https://remoteok.com/api",
                headers={"User-Agent": "Jarvis-personal-assistant (+local, non-commercial)"},
                timeout=8,
            )
            response.raise_for_status()
            postings = response.json()
        except Exception as exc:
            return f"Error: job search failed ({type(exc).__name__}: {exc})."

        query_lower = query.lower()
        matches = []
        for posting in postings:
            if not isinstance(posting, dict) or "position" not in posting:
                continue  # RemoteOK's first array element is metadata, not a job
            haystack = " ".join(
                str(posting.get(field, ""))
                for field in ("position", "company", "tags", "description")
            ).lower()
            if query_lower in haystack:
                matches.append(posting)
            if len(matches) >= max_results:
                break

        if not matches:
            return f"No job postings found for '{query}'."

        lines = [f"Job postings for '{query}':"]
        for i, job in enumerate(matches, start=1):
            title = job.get("position", "Unknown role")
            company = job.get("company", "Unknown company")
            location = job.get("location") or "Remote"
            url = job.get("url", "")
            lines.append(f"{i}. {title} at {company} ({location})\n   {url}")
        return "\n".join(lines)
