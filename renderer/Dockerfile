# Armador de videos 9:16 de URUKU (contenedor `reels`).
# docs/contenido-redes-tecnico.md, 16.4. La imagen trae los navegadores (en /ms-playwright)
# pero NO el paquete de Python: se instala acá, en la MISMA versión que la imagen (1.64.1),
# porque cada versión del paquete busca su propio build de Chromium (chromium-1248).
# Pasó el 3/11: sin esto, /health daba chromium:false («No module named 'playwright'»).
FROM mcr.microsoft.com/playwright/python:v1.64.1-noble

# ffmpeg arma el mp4 a partir de los cuadros que fotografía Chromium.
# --break-system-packages: Ubuntu noble marca el Python del sistema como «administrado»
# (PEP 668); este contenedor no tiene otro uso, así que se instala ahí directo.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg python3-pip \
 && rm -rf /var/lib/apt/lists/* \
 && python3 -m pip install --no-cache-dir --break-system-packages playwright==1.64.1 \
 && python3 -c "import playwright.sync_api"

WORKDIR /app
COPY server.py reel_t1.py render.py ./
# Poppins (+ OFL.txt), logo e íconos del kit. Es lo único de afuera que la página puede leer.
COPY assets ./assets

# Sin cache de bytecode ni salida con buffer; el sistema de archivos va en sólo lectura
# (compose) y todo lo temporal (perfil de Chromium, la página) cae en /tmp, que es tmpfs.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp \
    CONTENT_DIR=/data/content \
    RENDERER_PORT=8090 \
    RENDER_DEADLINE_SEG=280

# Usuario no root (la imagen de Playwright ya trae `pwuser`).
USER pwuser

EXPOSE 8090
CMD ["python3", "server.py"]
