# Armador de videos 9:16 de URUKU (contenedor `reels`).
# docs/contenido-redes-tecnico.md, 16.4. Versión de la imagen fija: tiene que coincidir con
# la del paquete `playwright` que ya trae (v1.64.1), por eso no se instala nada por pip.
FROM mcr.microsoft.com/playwright/python:v1.64.1-noble

# ffmpeg arma el mp4 a partir de los cuadros que fotografía Chromium.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

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
