"""CLI entrypoint for the standalone agents.

Usage:
    python -m jarvis.agents email [--max-results N] [--all]
    python -m jarvis.agents jobs "python developer" [--max-results N]
    python -m jarvis.agents calendar [--days N]
"""
from __future__ import annotations

import argparse
import sys

from jarvis.agents.calendar_agent import CalendarAgent
from jarvis.agents.email_agent import EmailAgent
from jarvis.agents.job_agent import JobAgent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m jarvis.agents", description=__doc__)
    subparsers = parser.add_subparsers(dest="agent", required=True)

    email_parser = subparsers.add_parser("email", help="Summarize inbox updates.")
    email_parser.add_argument("--max-results", type=int, default=10)
    email_parser.add_argument(
        "--all", action="store_true", help="Include read emails too (default: unread only)."
    )

    jobs_parser = subparsers.add_parser("jobs", help="Check for newly posted jobs matching a query.")
    jobs_parser.add_argument("query", help="Job title/keyword, e.g. 'python developer'.")
    jobs_parser.add_argument("--max-results", type=int, default=5)

    calendar_parser = subparsers.add_parser("calendar", help="Summarize upcoming calendar events.")
    calendar_parser.add_argument("--days", type=int, default=7)

    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)

    if args.agent == "email":
        print(EmailAgent().briefing(max_results=args.max_results, unread_only=not args.all))
    elif args.agent == "jobs":
        print(JobAgent().check(args.query, max_results=args.max_results))
    elif args.agent == "calendar":
        print(CalendarAgent().briefing(days_ahead=args.days))


if __name__ == "__main__":
    try:
        main()
    except ConnectionError as exc:
        sys.exit(str(exc))
    except KeyboardInterrupt:
        sys.exit(1)
