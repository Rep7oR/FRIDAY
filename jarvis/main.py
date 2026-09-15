"""Voice-mode entrypoint: python -m jarvis.main [--wake-word]

Defaults to push-to-talk (press Enter to speak). Pass --wake-word to use always-listening
wake-word detection instead (requires `pip install openwakeword sounddevice`).

Needs a real microphone and speakers, so this only works on your own machine, not inside a
headless dev container.
"""
from __future__ import annotations

import argparse
import logging
import sys

from jarvis import config
from jarvis.voice.pipeline import VoicePipeline
from jarvis.voice.wake_word import PushToTalkTrigger, WakeWordTrigger


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    parser = argparse.ArgumentParser(description=f"{config.AGENT_NAME} voice assistant")
    parser.add_argument(
        "--wake-word",
        action="store_true",
        help="Use always-listening wake-word detection instead of push-to-talk.",
    )
    args = parser.parse_args()

    trigger = WakeWordTrigger() if args.wake_word else PushToTalkTrigger()
    print(f"{config.AGENT_NAME} voice mode online.")
    VoicePipeline(trigger=trigger).run_forever()


if __name__ == "__main__":
    sys.exit(main())
