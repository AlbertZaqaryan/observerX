"""One-shot downloader: pulls the model weights and vision projector from
Hugging Face into the shared /models volume. Skips files already present so
`docker compose up` is fast on subsequent runs."""
import os
import sys

from huggingface_hub import hf_hub_download

MODELS_DIR = "/models"
REPO = os.environ.get(
    "MODEL_HF_REPO",
    "0bserverx/Qwen3.8-27B-Heretic-Abliterated-Uncensored-GGUF",
)
MODEL_FILE = os.environ.get("MODEL_HF_FILE", "RVN-Q4_K_M.gguf")
MMPROJ_FILE = os.environ.get("MMPROJ_HF_FILE", "mmproj-Qwen3.8-27B-Q8_0.gguf")
ENABLE_VISION = os.environ.get("ENABLE_VISION", "true").lower() == "true"
HF_TOKEN = os.environ.get("HF_TOKEN") or None


def fetch(filename: str) -> None:
    target = os.path.join(MODELS_DIR, filename)
    if os.path.exists(target) and os.path.getsize(target) > 0:
        print(f"[downloader] already present, skipping: {filename}", flush=True)
        return
    print(f"[downloader] downloading {REPO}/{filename} ...", flush=True)
    hf_hub_download(
        repo_id=REPO,
        filename=filename,
        local_dir=MODELS_DIR,
        token=HF_TOKEN,
    )
    print(f"[downloader] done: {filename}", flush=True)


def main() -> int:
    os.makedirs(MODELS_DIR, exist_ok=True)
    try:
        fetch(MODEL_FILE)
        if ENABLE_VISION:
            fetch(MMPROJ_FILE)
    except Exception as exc:  # noqa: BLE001 - surface a clear error and fail the service
        print(f"[downloader] ERROR: {exc}", file=sys.stderr, flush=True)
        return 1
    print("[downloader] all files ready.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
