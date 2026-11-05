FROM python:3.12-slim

# ffmpeg para decodificar el audio del navegador (faster-whisper) y tesseract-ocr para leer los teléfonos de las
# portadas (OCR local gratis, docs/telefonos-en-fotos.md; con los datos del inglés alcanza: sólo se leen dígitos)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg tesseract-ocr \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
# cache de modelos whisper (se monta como volumen en prod para no re-bajarlo)
ENV HF_HOME=/models PIP_DEFAULT_TIMEOUT=120 UV_HTTP_TIMEOUT=120
ARG GIT_SHA=dev
ENV GIT_SHA=$GIT_SHA
COPY pyproject.toml ./
RUN pip install --no-cache-dir --timeout 120 --retries 8 uv \
 && uv pip install --system .

COPY app ./app
# Scripts de mantenimiento que se corren con `docker compose exec`
# (regenerar miniaturas, etc.). Sin esto no existen dentro del contenedor.
COPY scripts ./scripts
# Datos que se importan con un comando (rol de turnos de las farmacias, etc.).
COPY data ./data

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
