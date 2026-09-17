FROM python:3.11-slim

# hf_transfer gives much faster, resumable downloads of the large GGUF files.
RUN pip install --no-cache-dir "huggingface_hub[hf_transfer]==0.25.2"

ENV HF_HUB_ENABLE_HF_TRANSFER=1

COPY download.py /download.py

ENTRYPOINT ["python", "/download.py"]
