"""Runtime configuration, read from environment variables."""
import os


def _bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


LLAMA_URL = os.environ.get("LLAMA_URL", "http://llama:8080").rstrip("/")
# llama.cpp ignores the model name but the OpenAI schema requires the field.
MODEL_ID = os.environ.get("MODEL_ID", "local-model")

MODEL_DISPLAY_NAME = os.environ.get(
    "MODEL_DISPLAY_NAME", "Qwen3.8-27B Heretic (Abliterated, Uncensored)"
)
SYSTEM_PROMPT = os.environ.get(
    "SYSTEM_PROMPT",
    "You are a helpful, knowledgeable assistant. Answer clearly and concisely in English.",
).strip()

ENABLE_VISION = _bool("ENABLE_VISION", True)
WHISPER_ENABLED = _bool("WHISPER_ENABLED", True)
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "base")

MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "50"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

# Generation defaults.
DEFAULT_TEMPERATURE = float(os.environ.get("DEFAULT_TEMPERATURE", "0.7"))
DEFAULT_MAX_TOKENS = int(os.environ.get("DEFAULT_MAX_TOKENS", "1024"))

# Largest edge (px) an image is downscaled to before being sent to the model.
IMAGE_MAX_EDGE = int(os.environ.get("IMAGE_MAX_EDGE", "1536"))
