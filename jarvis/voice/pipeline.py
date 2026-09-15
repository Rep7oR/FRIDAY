"""Wires together: trigger -> record -> transcribe -> agent -> speak.

Requires a working microphone and speakers, so it can't be exercised in a headless
container -- run it on your own machine. See README.md for setup.
"""
from __future__ import annotations

import logging

from jarvis.core.agent import Agent
from jarvis.core.tools.scheduler import ReminderChecker
from jarvis.voice.stt import SpeechToText
from jarvis.voice.tts import TextToSpeech
from jarvis.voice.wake_word import ListenTrigger, PushToTalkTrigger

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
MAX_RECORD_SECONDS = 12
SILENCE_HOLD_SECONDS = 1.2
SILENCE_RMS_THRESHOLD = 300  # int16 RMS; tune for your mic/room noise floor


def record_command(sample_rate: int = SAMPLE_RATE) -> "object":
    """Record audio from the default mic until the user pauses, and return a numpy array
    of float32 samples suitable for faster-whisper."""
    import numpy as np
    import sounddevice as sd

    chunk_ms = 100
    chunk_samples = int(sample_rate * chunk_ms / 1000)
    silence_chunks_needed = int(SILENCE_HOLD_SECONDS * 1000 / chunk_ms)
    max_chunks = int(MAX_RECORD_SECONDS * 1000 / chunk_ms)

    frames: list = []
    silent_run = 0
    heard_speech = False

    with sd.InputStream(samplerate=sample_rate, channels=1, dtype="int16") as stream:
        for _ in range(max_chunks):
            chunk, _ = stream.read(chunk_samples)
            frames.append(chunk.copy())
            rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
            if rms > SILENCE_RMS_THRESHOLD:
                heard_speech = True
                silent_run = 0
            elif heard_speech:
                silent_run += 1
                if silent_run >= silence_chunks_needed:
                    break

    audio = np.concatenate(frames).flatten().astype(np.float32) / 32768.0
    return audio


class VoicePipeline:
    def __init__(self, trigger: ListenTrigger | None = None) -> None:
        self.trigger = trigger or PushToTalkTrigger()
        self.agent = Agent()
        self.stt = SpeechToText()
        self.tts = TextToSpeech()

    def _speak_reminder(self, reminder: dict) -> None:
        self.tts.say(f"Reminder: {reminder['text']}")

    def run_forever(self) -> None:
        checker = ReminderChecker(on_due=self._speak_reminder)
        checker.start()
        try:
            while True:
                self.trigger.wait_for_trigger()
                audio = record_command()
                text = self.stt.transcribe_array(audio)
                if not text:
                    print("(didn't catch that)")
                    continue
                print(f"you: {text}")
                if text.strip().lower() in {"exit", "quit", "stop listening"}:
                    self.tts.say("Goodbye.")
                    break
                try:
                    reply = self.agent.run(text)
                except ConnectionError as exc:
                    reply = str(exc)
                print(f"jarvis: {reply}")
                self.tts.say(reply)
        finally:
            checker.stop()
