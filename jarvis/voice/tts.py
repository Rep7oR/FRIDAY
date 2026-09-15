"""Text-to-speech via pyttsx3 (offline, uses the OS speech engine / espeak on Linux).

pyttsx3 is the default because it needs no model download and works out of the box on
Linux/macOS/Windows. For higher-quality voices, swap this out for Piper TTS later --
it implements the same two-method interface so callers don't need to change.
"""
from __future__ import annotations

from jarvis import config


class TextToSpeech:
    def __init__(self, rate: int = config.TTS_RATE) -> None:
        try:
            import pyttsx3
        except ImportError as exc:
            raise ImportError(
                "pyttsx3 is not installed. Run `pip install pyttsx3` to enable speech "
                "output (on Linux you'll also need the `espeak` system package)."
            ) from exc
        self._engine = pyttsx3.init()
        self._engine.setProperty("rate", rate)

    def say(self, text: str) -> None:
        if not text:
            return
        self._engine.say(text)
        self._engine.runAndWait()

    def save_to_file(self, text: str, path: str) -> None:
        self._engine.save_to_file(text, path)
        self._engine.runAndWait()
