FROM python:3.12-slim

# ffmpeg para decodificar el audio del navegador (faster-whisper)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
# cache de modelos whisper (se monta como volumen en prod para no re-bajarlo)
ENV HF_HOME=/models PIP_DEFAULT_TIMEOUT=120 UV_HTTP_TIMEOUT=120
COPY pyproject.toml ./
RUN pip install --no-cache-dir --timeout 120 --retries 8 uv \
 && uv pip install --system .

COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
