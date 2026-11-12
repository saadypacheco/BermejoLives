FROM python:3.12-slim

# ffmpeg para decodificar el audio del navegador (faster-whisper) y tesseract-ocr para leer los teléfonos de las
# portadas (OCR local gratis, docs/telefonos-en-fotos.md; con los datos del inglés alcanza: sólo se leen dígitos).
# tesseract-ocr-spa (~2 MB): las tarjetas de presentación (docs/carga-tarjetas.md) se leen con spa+eng; sin él
# se lee con eng solo (services/tarjetas.py cae solo), con peores acentos.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg tesseract-ocr tesseract-ocr-spa \
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

# Usuario no root. uid/gid 1001 A PROPÓSITO: es el mismo del contenedor `reels` (`pwuser`),
# y el backend le entrega a ese uid la carpeta `out/` de cada job de video con
# os.chown(out, 1001, -1) (content_render.py). Chownear al propio uid no pide
# privilegios, así que anda sin CAP_CHOWN y con `cap_drop: [ALL]` (un uid distinto
# sí lo pediría, y Docker no le da capacidades a un proceso no root).
# Lo único que el backend escribe: /data/fotos, /data/content, /data/wa_received y
# /models (cache de whisper). Las carpetas se crean acá con dueño 1001 para que un
# volumen NUEVO herede el dueño; los volúmenes que ya existen en el VPS (creados
# cuando corría como root) se arreglan una vez con `chown -R 1001:1001`
# (ver docker-compose.prod.yml).
RUN groupadd --gid 1001 app \
 && useradd --uid 1001 --gid 1001 --no-create-home --shell /usr/sbin/nologin app \
 && mkdir -p /models /data/fotos /data/content /data/wa_received \
 && chown -R 1001:1001 /models /data
USER 1001:1001

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
