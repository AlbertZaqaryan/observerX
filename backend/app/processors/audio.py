"""Audio -> text via faster-whisper. The Whisper model is loaded lazily on
first use and cached for the process lifetime."""
import os
import tempfile
import threading

from .. import config

_model = None
_lock = threading.Lock()


def _get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from faster_whisper import WhisperModel  # imported lazily

                # int8 keeps CPU memory/latency reasonable.
                _model = WhisperModel(config.WHISPER_MODEL, device="cpu", compute_type="int8")
    return _model


def transcribe(data: bytes, filename: str) -> str:
    """Transcribe audio bytes to text. Returns a human-readable transcript."""
    if not config.WHISPER_ENABLED:
        return "[Audio transcription is disabled on this server.]"

    suffix = os.path.splitext(filename)[1] or ".audio"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    try:
        model = _get_model()
        segments, info = model.transcribe(tmp_path, beam_size=1)
        text = " ".join(seg.text.strip() for seg in segments).strip()
        if not text:
            return "[No speech detected in the audio.]"
        lang = getattr(info, "language", None)
        prefix = f"(detected language: {lang}) " if lang else ""
        return prefix + text
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
