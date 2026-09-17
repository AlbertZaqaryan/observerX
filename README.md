# observerX_ai

A self-hosted, web-based platform for chatting with the
[**0bserverx/Qwen3.8-27B-Heretic-Abliterated-Uncensored-GGUF**](https://huggingface.co/0bserverx/Qwen3.8-27B-Heretic-Abliterated-Uncensored-GGUF)
model. Users can send **text**, **files**, **audio**, and **images** from a
clean English chat interface. Everything runs locally with **Docker Compose**.

---

## Features

- 💬 **Text chat** — streaming responses, conversation memory, markdown rendering.
- 🖼️ **Images** — passed natively to the model's vision projector for understanding.
- 🎤 **Audio** — transcribed to text with Whisper, then answered by the model.
- 📄 **Documents & code** — PDF, DOCX, TXT, CSV, JSON, and source files are read
  and their contents fed to the model.
- 🐳 **One command** — `docker compose up` builds and starts everything.

## Architecture

```
Browser ──> web (nginx)  ──/api──>  backend (FastAPI)  ──OpenAI API──>  llama (llama.cpp)
                                        │                                     ▲
                                        │ Whisper / PDF / DOCX / image prep   │
                                        └─────────────────────────────────────┘
   downloader (one-shot) ──> pulls the GGUF weights + vision projector into a shared volume
```

| Service      | Role                                                            |
|--------------|-----------------------------------------------------------------|
| `downloader` | Downloads the model weights + vision projector from Hugging Face |
| `llama`      | `llama.cpp` OpenAI-compatible inference server                  |
| `backend`    | FastAPI gateway: audio/document processing + response streaming |
| `web`        | nginx serving the chat UI and proxying the API                  |

## Requirements

- Docker + Docker Compose (v2).
- **Disk:** ~17 GB free for the default `Q4_K_M` weights (plus the ~0.6 GB projector).
- **RAM:** ~16 GB+ recommended to run the default quant on CPU. Pick a smaller
  quant in `.env` if you have less (see `MODEL_HF_FILE`).
- Internet access on first run (to download the model).

## Quick start

```bash
cp .env.example .env      # adjust settings if you like
docker compose up --build
```

The first run downloads ~17 GB, so it takes a while. When it's ready, open:

```
http://localhost:3000
```

The status dot in the header turns **green** once the model has finished loading.

## Configuration

All settings live in `.env` (copied from `.env.example`). Highlights:

| Variable          | Default              | Description                                              |
|-------------------|----------------------|----------------------------------------------------------|
| `MODEL_HF_FILE`   | `RVN-Q4_K_M.gguf`    | Which quantization to download/run (smaller = lighter).  |
| `ENABLE_VISION`   | `true`               | Download the projector and enable image understanding.   |
| `LLAMA_CTX`       | `8192`               | Context window in tokens (model supports up to 262144).  |
| `LLAMA_NGL`       | `0`                  | GPU layers to offload. `0` = CPU only, `99` = full GPU.  |
| `WHISPER_MODEL`   | `base`               | Speech-to-text model size (`tiny`…`large-v3`).           |
| `WHISPER_ENABLED` | `true`               | Toggle audio transcription.                              |
| `MAX_UPLOAD_MB`   | `50`                 | Per-file upload limit.                                   |
| `WEB_PORT`        | `3000`               | Host port for the web UI.                                |

### Using a smaller model

Editing `.env`:

```env
MODEL_HF_FILE=RVN-IQ3_M.gguf   # ~12.6 GB
```

Then `docker compose up` again (only the new file is downloaded).

### Running on a GPU (NVIDIA)

1. Install the NVIDIA Container Toolkit on the host.
2. In `docker-compose.yml`, change the `llama` image to the CUDA build:
   ```yaml
   image: ghcr.io/ggml-org/llama.cpp:server-cuda
   ```
   and add a GPU reservation:
   ```yaml
   deploy:
     resources:
       reservations:
         devices:
           - driver: nvidia
             count: all
             capabilities: [gpu]
   ```
3. Set `LLAMA_NGL=99` in `.env`.

## How each input type is handled

- **Images** are downscaled and sent to the model as image data — understood
  natively via the vision projector (`mmproj-*.gguf`).
- **Audio** is transcribed by Whisper inside the backend; the transcript is
  added to your message before it reaches the model.
- **Documents** (PDF/DOCX) and **text/code files** are parsed to plain text and
  included in your message (long files are truncated to fit the context window).

## Useful commands

```bash
docker compose up --build      # build + start
docker compose logs -f llama   # watch the model server (download/loading)
docker compose logs -f backend # watch the gateway
docker compose down            # stop
docker compose down -v         # stop and delete the downloaded model volume
```

## Troubleshooting

- **Status stays yellow / "model loading" for a long time:** a 27B model on CPU
  is slow to load and to generate. Check `docker compose logs -f llama`.
- **Out of memory:** switch `MODEL_HF_FILE` to a smaller quant and restart.
- **Markdown not rendering:** the UI loads `marked`/`DOMPurify` from a CDN and
  falls back to plain text if you're offline — chat still works.

## Note

This is an **uncensored research model** with reduced safety guardrails. Its
output can be inaccurate, biased, or offensive. Use it responsibly and in
accordance with the model's Apache-2.0 license and applicable law.
