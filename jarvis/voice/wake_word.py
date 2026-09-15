"""Listening triggers: something that decides *when* to start recording a command.

Two implementations:
  - PushToTalkTrigger: press Enter in the terminal. Zero extra dependencies, always works,
    and is the default -- useful for testing/headless setups or anyone who doesn't want an
    always-on mic listener.
  - WakeWordTrigger: open-source wake-word detection via `openwakeword`, so you can just say
    "jarvis" (or another configured word) instead of pressing a key. Optional dependency.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from jarvis import config


class ListenTrigger(ABC):
    @abstractmethod
    def wait_for_trigger(self) -> None:
        """Block until the user signals they want to speak a command."""
        raise NotImplementedError


class PushToTalkTrigger(ListenTrigger):
    def wait_for_trigger(self) -> None:
        input("Press Enter, then speak your command... ")


class WakeWordTrigger(ListenTrigger):
    """Streams microphone audio and blocks until the configured wake word is detected."""

    def __init__(self, wake_word: str = config.WAKE_WORD, sample_rate: int = 16000) -> None:
        try:
            import openwakeword
            from openwakeword.model import Model
        except ImportError as exc:
            raise ImportError(
                "openwakeword is not installed. Run `pip install openwakeword` and "
                "`python -m openwakeword.download` to enable wake-word listening, or use "
                "PushToTalkTrigger instead."
            ) from exc
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise ImportError(
                "sounddevice is not installed. Run `pip install sounddevice` (and ensure "
                "PortAudio is available on your system) to enable microphone capture."
            ) from exc

        self._sd = sd
        self._wake_word = wake_word.lower()
        self._sample_rate = sample_rate
        self._model = Model(wakeword_models=openwakeword.get_pretrained_model_paths())

    def wait_for_trigger(self) -> None:
        import numpy as np

        chunk_size = 1280  # openwakeword expects 80ms chunks at 16kHz
        with self._sd.InputStream(
            samplerate=self._sample_rate, channels=1, dtype="int16"
        ) as stream:
            while True:
                audio_chunk, _ = stream.read(chunk_size)
                audio = np.squeeze(audio_chunk)
                predictions = self._model.predict(audio)
                for model_name, score in predictions.items():
                    if self._wake_word in model_name.lower() and score > 0.5:
                        return
