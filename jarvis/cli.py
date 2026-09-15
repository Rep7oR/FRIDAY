"""Text-mode entrypoint: a REPL chat with Jarvis. Works anywhere Python + Ollama run, no
audio hardware required. Run with: python -m jarvis.cli
"""
from __future__ import annotations

import logging
import sys

from jarvis import config
from jarvis.core.agent import Agent
from jarvis.core.tools.scheduler import ReminderChecker


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    agent = Agent()

    def announce_due_reminder(reminder: dict) -> None:
        print(f"\n[reminder] {reminder['text']}\n> ", end="", flush=True)

    checker = ReminderChecker(on_due=announce_due_reminder)
    checker.start()

    print(f"{config.AGENT_NAME} is online. Type 'exit' or Ctrl-D to quit.")
    try:
        while True:
            try:
                user_input = input("> ").strip()
            except EOFError:
                print()
                break
            if not user_input:
                continue
            if user_input.lower() in {"exit", "quit"}:
                break
            try:
                reply = agent.run(user_input)
            except ConnectionError as exc:
                print(f"[error] {exc}")
                continue
            print(reply)
    finally:
        checker.stop()


if __name__ == "__main__":
    sys.exit(main())
