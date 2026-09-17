#!/bin/sh
# Entrypoint for the llama.cpp server. Builds the argument list from the
# environment (.env) so vision, GPU offload and context size are configurable.
set -e

# Locate the server binary (path differs slightly between image versions).
BIN="$(command -v llama-server 2>/dev/null || true)"
[ -z "$BIN" ] && [ -x /app/llama-server ] && BIN=/app/llama-server
[ -z "$BIN" ] && [ -x /llama-server ] && BIN=/llama-server
[ -z "$BIN" ] && BIN=llama-server

MODEL_FILE="${MODEL_HF_FILE:-RVN-Q4_K_M.gguf}"
MMPROJ_FILE="${MMPROJ_HF_FILE:-mmproj-Qwen3.8-27B-Q8_0.gguf}"

set -- -m "/models/${MODEL_FILE}" \
    --host 0.0.0.0 --port 8080 \
    -c "${LLAMA_CTX:-8192}" \
    -ngl "${LLAMA_NGL:-0}" \
    --jinja

# Explicit thread count (0 = let llama.cpp auto-detect).
if [ "${LLAMA_THREADS:-0}" -gt 0 ] 2>/dev/null; then
    set -- "$@" -t "${LLAMA_THREADS}"
fi

# Attach the vision projector for image understanding, when enabled and present.
if [ "${ENABLE_VISION:-true}" = "true" ] && [ -f "/models/${MMPROJ_FILE}" ]; then
    set -- "$@" --mmproj "/models/${MMPROJ_FILE}"
    echo "[llama] vision enabled (mmproj: ${MMPROJ_FILE})"
fi

echo "[llama] starting: $BIN $*"
exec "$BIN" "$@"
