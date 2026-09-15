"""Job posting search via the RemoteOK public API (https://remoteok.com/api) -- free, no key.
Skews remote/tech since that's what RemoteOK lists; swap in a different provider (e.g. Adzuna,
which needs a free API key) here if you want broader/local listings.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from jarvis.core.db import get_conn, init_db
from jarvis.core.tools.base import Tool

init_db()

REMOTEOK_API_URL = "https://remoteok.com/api"
_USER_AGENT = "Jarvis-personal-assistant (+local, non-commercial)"


def fetch_postings() -> list[dict[str, Any]]:
    response = httpx.get(REMOTEOK_API_URL, headers={"User-Agent": _USER_AGENT}, timeout=8)
    response.raise_for_status()
    postings = response.json()
    # RemoteOK's first array element is API metadata, not a job -- drop anything without
    # the fields a real posting always has.
    return [p for p in postings if isinstance(p, dict) and "position" in p and p.get("id")]


def match_postings(query: str, postings: list[dict[str, Any]], max_results: int) -> list[dict[str, Any]]:
    query_lower = query.lower()
    matches = []
    for posting in postings:
        haystack = " ".join(
            str(posting.get(field, "")) for field in ("position", "company", "tags", "description")
        ).lower()
        if query_lower in haystack:
            matches.append(posting)
        if len(matches) >= max_results:
            break
    return matches


def format_postings(query: str, jobs: list[dict[str, Any]], heading: str | None = None) -> str:
    if not jobs:
        return f"No job postings found for '{query}'."

    lines = [heading or f"Job postings for '{query}':"]
    for i, job in enumerate(jobs, start=1):
        title = job.get("position", "Unknown role")
        company = job.get("company", "Unknown company")
        location = job.get("location") or "Remote"
        url = job.get("url", "")
        lines.append(f"{i}. {title} at {company} ({location})\n   {url}")
    return "\n".join(lines)


class NewJobPostingsTool(Tool):
    """Only returns postings this query hasn't seen before --
    remembered in SQLite so re-running the same search later reports only what's new.
    """

    name = "find_new_job_postings"
    description = (
        "Check for NEWLY posted jobs matching a role/keyword since the last time this "
        "query was checked (sourced from RemoteOK). First run for a new query returns "
        "nothing 'new' by design -- it establishes the baseline; run it again later to "
        "see fresh postings."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Job title, keyword, or tag to watch."},
            "max_results": {
                "type": "integer",
                "description": "How many new postings to return (default 5, max 15).",
            },
        },
        "required": ["query"],
    }

    def run(self, query: str, max_results: int = 5) -> str:
        max_results = max(1, min(int(max_results), 15))
        try:
            postings = fetch_postings()
        except Exception as exc:
            return f"Error: job search failed ({type(exc).__name__}: {exc})."

        # Scan a wider pool than max_results so postings already seen don't crowd out
        # genuinely new ones before we've filtered.
        candidates = match_postings(query, postings, max_results=50)

        with get_conn() as conn:
            seen_ids = {
                row["job_id"]
                for row in conn.execute(
                    "SELECT job_id FROM seen_jobs WHERE query = ?", (query.lower(),)
                ).fetchall()
            }

            new_jobs = [j for j in candidates if str(j["id"]) not in seen_ids][:max_results]

            now = datetime.now(timezone.utc).isoformat()
            for job in candidates:
                conn.execute(
                    "INSERT OR IGNORE INTO seen_jobs (query, job_id, seen_at) VALUES (?, ?, ?)",
                    (query.lower(), str(job["id"]), now),
                )

        if not seen_ids:
            return (
                f"First check for '{query}' -- no baseline yet, so nothing to compare "
                f"against. Found {len(candidates)} current postings; run this again later "
                "to see what's new."
            )

        if not new_jobs:
            return (
                f"No new postings for '{query}' since your last check "
                f"({len(candidates)} matching postings currently, none of them new). "
                "This is a normal result, not an error -- nothing has changed since last time."
            )

        return format_postings(query, new_jobs, heading=f"New job postings for '{query}':")
