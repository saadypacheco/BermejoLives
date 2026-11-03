# renderer — contenedor `reels`

Arma el video 9:16 de las piezas de contenido para redes con la plantilla T1 del kit
(carrusel de 4 a 6 fotos). Cada video es una página HTML con animaciones CSS: Chromium
(Playwright) fotografía cada cuadro y ffmpeg arma el mp4. Spec: `docs/contenido-redes-tecnico.md`
§16.3 y §16.4.

| Archivo | Qué hace |
|---|---|
| `server.py` | HTTP (stdlib): `POST /render`, `GET /health`. Uno a la vez, plazo `RENDER_DEADLINE_SEG` (280) |
| `render.py` | Cuadros con Chromium → ffmpeg, portada en t = 2,6 s, verificación con ffprobe |
| `reel_t1.py` | Valida `job.json` y arma el HTML (todo texto escapado, CSP, sin `<script>`) |
| `assets/` | Poppins (+ `OFL.txt`), `logo.png`, `iconos/ic_*.png` |

## Contrato

```
POST /render   Authorization: Bearer <RENDERER_TOKEN>   {"piece_id": "<uuid>"}
  200 {"ok": true, "duration_s", "video_bytes", "render_ms", "frames"}
  200 {"ok": false, "error": "...", "retryable": true|false}
  400 job o piece_id inválido (retryable: false)   401 token   409 ocupado
GET  /health → {"ok", "chromium", "ffmpeg", "busy"}   (sin token)
```

Lee `CONTENT_DIR/tmp/<piece_id>/job.json` + `sN.jpg` y sólo escribe `video.mp4` y `cover.jpg` ahí.

## Correr con Docker (compose del repo)

```bash
cp renderer/.env.example renderer/.env      # RENDERER_TOKEN igual al de backend/.env
docker compose -f docker-compose.prod.yml up -d --build reels
docker compose -f docker-compose.prod.yml exec backend python -c \
  "import httpx; print(httpx.get('http://buscadonde-reels:8090/health').json())"
```

## Correr y probar sin Docker

Hace falta Python 3.12, `playwright` (+ `playwright install chromium`), `ffmpeg` en el PATH y `pytest`.
Si el Chromium de Playwright no está, `CHROME_EXE` apunta a otro ejecutable.

```bash
cd renderer
pip install playwright pytest
export CHROME_EXE=/ruta/a/chrome   # opcional
python -m pytest -q                # ~100 s: incluye un render real de 14 s de video
python -m pytest -q -m "not e2e"   # sin el render completo (~20 s)

# un job a mano
RENDERER_TOKEN=prueba CONTENT_DIR=/ruta/content python server.py
python render.py /ruta/content/tmp/<uuid>      # imprime el resultado en JSON
```

Los tests que necesitan navegador o ffmpeg se saltean solos si no están.
