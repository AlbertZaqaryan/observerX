"""Thin async client for the llama.cpp OpenAI-compatible server."""
import json
from typing import AsyncIterator

import httpx

from . import config


async def health() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{config.LLAMA_URL}/health")
            return resp.status_code == 200
    except Exception:
        return False


async def stream_chat(messages: list, temperature: float, max_tokens: int) -> AsyncIterator[str]:
    """Stream assistant text deltas from the model.

    Yields plain text chunks. Raises httpx errors on transport failure.
    """
    payload = {
        "model": config.MODEL_ID,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }

    timeout = httpx.Timeout(connect=15.0, read=None, write=60.0, pool=None)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream(
            "POST",
            f"{config.LLAMA_URL}/v1/chat/completions",
            json=payload,
        ) as resp:
            if resp.status_code != 200:
                body = (await resp.aread()).decode("utf-8", errors="replace")
                raise RuntimeError(f"model server error {resp.status_code}: {body[:500]}")

            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choices = obj.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                piece = delta.get("content")
                if piece:
                    yield piece
