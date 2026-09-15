"""Conversation memory: an in-process message list, optionally persisted to SQLite so
history survives restarts."""
from __future__ import annotations

from typing import Any

from jarvis.core.db import get_conn, init_db

init_db()


class ConversationMemory:
    def __init__(self, system_prompt: str, persist: bool = True) -> None:
        self.system_prompt = system_prompt
        self.persist = persist
        self.messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]

    def add(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})
        if self.persist and role in ("user", "assistant"):
            with get_conn() as conn:
                conn.execute(
                    "INSERT INTO conversation_history (role, content) VALUES (?, ?)",
                    (role, content),
                )

    def add_tool_result(self, tool_call_id: str | None, name: str, content: str) -> None:
        message: dict[str, Any] = {"role": "tool", "name": name, "content": content}
        if tool_call_id:
            message["tool_call_id"] = tool_call_id
        self.messages.append(message)

    def as_list(self) -> list[dict[str, Any]]:
        return list(self.messages)

    def reset(self) -> None:
        self.messages = [{"role": "system", "content": self.system_prompt}]

    @staticmethod
    def load_recent_history(limit: int = 20) -> list[dict[str, str]]:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT role, content FROM conversation_history "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]
