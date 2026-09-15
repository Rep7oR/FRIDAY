"""Speech-to-text via faster-whisper, running fully locally (no cloud calls)."""
from __future__ import annotations

from jarvis import config


class SpeechToText:
    def __init__(self, model_size: str = config.STT_MODEL_SIZE) -> None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise ImportError(
                "faster-whisper is not installed. Run `pip install faster-whisper` "
                "to enable speech-to-text."
            ) from exc
        self._model = WhisperModel(model_size, device="cpu", compute_type="int8")

    def transcribe_file(self, wav_path: str) -> str:
        segments, _info = self._model.transcribe(wav_path)
        return " ".join(segment.text.strip() for segment in segments).strip()

    def transcribe_array(self, audio, sample_rate: int = 16000) -> str:
        """Transcribe an in-memory float32 mono audio array (e.g. captured from a mic)."""
        segments, _info = self._model.transcribe(audio, language=None)
        return " ".join(segment.text.strip() for segment in segments).strip()
