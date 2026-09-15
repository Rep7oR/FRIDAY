"""Reminders / scheduled tasks, persisted locally in SQLite.

This intentionally does not integrate with any external calendar/email provider out of the
box (that needs OAuth credentials only the user can supply). It's a self-contained reminders
system; a Google Calendar/Gmail tool can be added later following the same Tool interface,
using the credentials the user sets up themselves.
"""
from __future__ import annotations

import datetime as dt
import threading
import time
from collections.abc import Callable

from jarvis.core.db import get_conn, init_db
from jarvis.core.tools.base import Tool

init_db()


def _parse_due_at(due_at: str | None) -> str | None:
    if not due_at:
        return None
    try:
        # Accept ISO 8601; normalize so it sorts/compares correctly as text.
        return dt.datetime.fromisoformat(due_at).isoformat()
    except ValueError:
        raise ValueError(
            f"'{due_at}' is not a valid ISO 8601 datetime (e.g. 2026-09-16T09:00:00)."
        ) from None


class AddReminderTool(Tool):
    name = "add_reminder"
    description = "Create a reminder/scheduled task, optionally with a due date/time."
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "What to be reminded about."},
            "due_at": {
                "type": "string",
                "description": "ISO 8601 datetime, e.g. 2026-09-16T09:00:00. Omit for no due date.",
            },
        },
        "required": ["text"],
    }

    def run(self, text: str, due_at: str | None = None) -> str:
        try:
            normalized_due = _parse_due_at(due_at)
        except ValueError as exc:
            return f"Error: {exc}"
        with get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO reminders (text, due_at) VALUES (?, ?)",
                (text, normalized_due),
            )
            reminder_id = cur.lastrowid
        due_suffix = f" (due {normalized_due})" if normalized_due else ""
        return f"Reminder #{reminder_id} created: {text}{due_suffix}"


class ListRemindersTool(Tool):
    name = "list_reminders"
    description = "List reminders/scheduled tasks."
    parameters = {
        "type": "object",
        "properties": {
            "include_done": {
                "type": "boolean",
                "description": "Include already-completed reminders (default false).",
            }
        },
        "required": [],
    }

    def run(self, include_done: bool = False) -> str:
        query = "SELECT id, text, due_at, done FROM reminders"
        if not include_done:
            query += " WHERE done = 0"
        query += " ORDER BY (due_at IS NULL), due_at, id"
        with get_conn() as conn:
            rows = conn.execute(query).fetchall()
        if not rows:
            return "No reminders."
        lines = []
        for row in rows:
            status = "done" if row["done"] else "pending"
            due = f" (due {row['due_at']})" if row["due_at"] else ""
            lines.append(f"#{row['id']} [{status}] {row['text']}{due}")
        return "\n".join(lines)


class CompleteReminderTool(Tool):
    name = "complete_reminder"
    description = "Mark a reminder as done, given its id."
    parameters = {
        "type": "object",
        "properties": {"reminder_id": {"type": "integer"}},
        "required": ["reminder_id"],
    }

    def run(self, reminder_id: int) -> str:
        with get_conn() as conn:
            cur = conn.execute(
                "UPDATE reminders SET done = 1 WHERE id = ?", (reminder_id,)
            )
        if cur.rowcount == 0:
            return f"Error: no reminder with id {reminder_id}."
        return f"Reminder #{reminder_id} marked done."


class DeleteReminderTool(Tool):
    name = "delete_reminder"
    description = "Delete a reminder permanently, given its id."
    parameters = {
        "type": "object",
        "properties": {"reminder_id": {"type": "integer"}},
        "required": ["reminder_id"],
    }

    def run(self, reminder_id: int) -> str:
        with get_conn() as conn:
            cur = conn.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
        if cur.rowcount == 0:
            return f"Error: no reminder with id {reminder_id}."
        return f"Reminder #{reminder_id} deleted."


def get_due_reminders(now: dt.datetime | None = None) -> list[dict]:
    """Return pending reminders whose due_at has passed."""
    now = now or dt.datetime.now()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, text, due_at FROM reminders WHERE done = 0 AND due_at IS NOT NULL"
        ).fetchall()
    due = []
    for row in rows:
        try:
            due_at = dt.datetime.fromisoformat(row["due_at"])
        except ValueError:
            continue
        if due_at <= now:
            due.append({"id": row["id"], "text": row["text"], "due_at": row["due_at"]})
    return due


class ReminderChecker:
    """Background poller that calls `on_due(reminder)` for each reminder as it comes due,
    then marks it done so it only fires once. Runs in a daemon thread; used by the voice
    pipeline to speak reminders aloud, or by the CLI to print them."""

    def __init__(self, on_due: Callable[[dict], None], interval_seconds: int = 30) -> None:
        self.on_due = on_due
        self.interval_seconds = interval_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1)

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            for reminder in get_due_reminders():
                CompleteReminderTool().run(reminder_id=reminder["id"])
                self.on_due(reminder)
            time.sleep(self.interval_seconds)
