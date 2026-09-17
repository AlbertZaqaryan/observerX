"""observerX_ai backend gateway.

Accepts multimodal chat requests (text + files + audio + images), preprocesses
each attachment into something the model can consume, then streams the model's
reply back to the browser via Server-Sent Events.
"""
import asyncio
import json
from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from . import config, llm
from .processors import audio as audio_proc
from .processors import document as doc_proc
from .processors import image as image_proc

app = FastAPI(title="observerX_ai", version="1.0.0")

IMAGE_MIME_PREFIX = "image/"
AUDIO_MIME_PREFIX = "audio/"
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")
AUDIO_EXTS = (".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac", ".webm", ".opus")


def _kind(filename: str, content_type: Optional[str]) -> str:
    ct = (content_type or "").lower()
    name = (filename or "").lower()
    if ct.startswith(IMAGE_MIME_PREFIX) or name.endswith(IMAGE_EXTS):
        return "image"
    if ct.startswith(AUDIO_MIME_PREFIX) or name.endswith(AUDIO_EXTS):
        return "audio"
    return "document"


@app.get("/api/config")
async def get_config():
    return {
        "model_name": config.MODEL_DISPLAY_NAME,
        "vision_enabled": config.ENABLE_VISION,
        "audio_enabled": config.WHISPER_ENABLED,
        "max_upload_mb": config.MAX_UPLOAD_MB,
    }


@app.get("/api/health")
async def get_health():
    ok = await llm.health()
    return JSONResponse(
        {"status": "ok" if ok else "starting", "model_ready": ok},
        status_code=200 if ok else 503,
    )


async def _build_user_content(message: str, files: List[UploadFile]) -> list:
    """Assemble OpenAI-style content parts from the message and attachments."""
    text_segments: List[str] = []
    image_parts: List[dict] = []

    if message and message.strip():
        text_segments.append(message.strip())

    for f in files:
        data = await f.read()
        if len(data) > config.MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File '{f.filename}' exceeds the {config.MAX_UPLOAD_MB} MB limit.",
            )
        if not data:
            continue

        kind = _kind(f.filename, f.content_type)

        if kind == "image" and config.ENABLE_VISION:
            uri = await asyncio.to_thread(image_proc.to_data_uri, data)
            image_parts.append({"type": "image_url", "image_url": {"url": uri}})
        elif kind == "image":
            text_segments.append(
                f"[An image '{f.filename}' was attached, but image understanding "
                f"is disabled on this server.]"
            )
        elif kind == "audio":
            transcript = await asyncio.to_thread(audio_proc.transcribe, data, f.filename)
            text_segments.append(f"[Transcript of audio '{f.filename}']:\n{transcript}")
        else:  # document
            text = await asyncio.to_thread(doc_proc.extract_text, data, f.filename)
            text_segments.append(f"[Contents of file '{f.filename}']:\n{text}")

    content: list = []
    combined = "\n\n".join(text_segments).strip()
    if combined:
        content.append({"type": "text", "text": combined})
    content.extend(image_parts)

    if not content:
        content.append({"type": "text", "text": ""})
    return content


def _parse_history(raw: Optional[str]) -> list:
    """History is a JSON array of {role, content} objects (text only)."""
    if not raw:
        return []
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        return []
    messages = []
    for it in items:
        role = it.get("role")
        text = it.get("content")
        if role in ("user", "assistant") and isinstance(text, str) and text:
            messages.append({"role": role, "content": text})
    return messages


@app.post("/api/chat")
async def chat(
    message: str = Form(""),
    history: str = Form(""),
    temperature: float = Form(config.DEFAULT_TEMPERATURE),
    max_tokens: int = Form(config.DEFAULT_MAX_TOKENS),
    files: List[UploadFile] = File(default=[]),
):
    files = files or []

    user_content = await _build_user_content(message, files)

    messages: list = []
    if config.SYSTEM_PROMPT:
        messages.append({"role": "system", "content": config.SYSTEM_PROMPT})
    messages.extend(_parse_history(history))
    messages.append({"role": "user", "content": user_content})

    async def event_stream():
        try:
            async for piece in llm.stream_chat(messages, temperature, max_tokens):
                yield f"data: {json.dumps({'delta': piece})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as exc:  # noqa: BLE001
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
