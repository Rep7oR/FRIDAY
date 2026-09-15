"""Read-only inbox checking via IMAP (works with Gmail, Outlook, and most providers that
support app-specific passwords). Only fetches headers -- sender, subject, date -- never full
message bodies, and there is no send/delete capability by design.
"""
from __future__ import annotations

import email
import imaplib
from email.header import decode_header

from jarvis import config
from jarvis.core.tools.base import Tool


def _decode_header_value(value: str) -> str:
    parts = decode_header(value)
    decoded = []
    for text, encoding in parts:
        if isinstance(text, bytes):
            decoded.append(text.decode(encoding or "utf-8", errors="replace"))
        else:
            decoded.append(text)
    return "".join(decoded)


class CheckEmailTool(Tool):
    name = "check_email"
    description = (
        "Check the user's email inbox for recent or unread messages (sender, subject, date "
        "only -- not the message body). Requires IMAP credentials to already be configured."
    )
    parameters = {
        "type": "object",
        "properties": {
            "max_results": {
                "type": "integer",
                "description": "How many emails to list (default 5, max 15).",
            },
            "unread_only": {
                "type": "boolean",
                "description": "Only show unread emails (default true).",
            },
        },
        "required": [],
    }

    def run(self, max_results: int = 5, unread_only: bool = True) -> str:
        if not config.EMAIL_ADDRESS or not config.EMAIL_APP_PASSWORD:
            return (
                "Error: email isn't configured. Set the JARVIS_EMAIL_ADDRESS and "
                "JARVIS_EMAIL_APP_PASSWORD environment variables (an app-specific password, "
                "not your normal login password), then restart Jarvis. See README.md for "
                "provider-specific setup steps."
            )

        max_results = max(1, min(int(max_results), 15))
        try:
            conn = imaplib.IMAP4_SSL(config.EMAIL_IMAP_HOST, config.EMAIL_IMAP_PORT)
        except (OSError, imaplib.IMAP4.error) as exc:
            return f"Error: could not connect to {config.EMAIL_IMAP_HOST}:{config.EMAIL_IMAP_PORT} ({exc})."

        try:
            conn.login(config.EMAIL_ADDRESS, config.EMAIL_APP_PASSWORD)
            conn.select("INBOX")
            criterion = "UNSEEN" if unread_only else "ALL"
            status, data = conn.search(None, criterion)
            if status != "OK":
                return "Error: could not search the inbox."

            ids = data[0].split()
            if not ids:
                return "No unread emails." if unread_only else "No emails found."

            ids = list(reversed(ids))[:max_results]  # most recent first
            lines = []
            for msg_id in ids:
                status, msg_data = conn.fetch(msg_id, "(RFC822.HEADER)")
                if status != "OK" or not msg_data or not msg_data[0]:
                    continue
                msg = email.message_from_bytes(msg_data[0][1])
                subject = _decode_header_value(msg.get("Subject", "(no subject)"))
                sender = _decode_header_value(msg.get("From", "(unknown sender)"))
                date = msg.get("Date", "")
                lines.append(f"- From: {sender}\n  Subject: {subject}\n  Date: {date}")

            header = "Unread emails" if unread_only else "Recent emails"
            return f"{header} ({len(lines)}):\n" + "\n".join(lines)
        except imaplib.IMAP4.error as exc:
            return (
                f"Error: IMAP login/search failed ({exc}). Double-check the email address, "
                "app password, and IMAP host."
            )
        except Exception as exc:
            return f"Error: could not check email ({type(exc).__name__}: {exc})."
        finally:
            try:
                conn.logout()
            except Exception:
                pass
