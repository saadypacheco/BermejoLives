"""Bermejo Live Market · API.

Responsabilidades (ver ADR 2026-06-04-stack-bermejo):
  - Ingesta de WhatsApp (WAHA) -> publicaciones pendientes (idempotente).
  - Moderación (aprobar/rechazar/cambios) con service_role.
El catálogo y el feed los lee el frontend directo de Supabase (anon + RLS).
"""
import asyncio
import time
import traceback
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from app.api import auth, campo, comercio, contenido, health, moderacion, observabilidad, usuario, webhook
from app.core.config import settings
from app.services.clima import fetch_clima_bermejo
from app.services.observabilidad import registrar_error, registrar_perf
from app.db.repository import get_repo

logger = structlog.get_logger()


async def _clima_loop():
    """Refresca el clima de Bermejo desde open-meteo cada 30 min, salvo que
    haya un override manual del publicador vigente."""
    while True:
        try:
            repo = get_repo()
            actual = await run_in_threadpool(repo.get_clima) or {}
            oh = actual.get("override_hasta")
            vigente = False
            if oh:
                try:
                    vigente = datetime.fromisoformat(str(oh).replace("Z", "+00:00")) > datetime.now(timezone.utc)
                except Exception:  # noqa: BLE001
                    vigente = False
            if not vigente:
                data = await fetch_clima_bermejo()
                if data:
                    data["override_hasta"] = None
                    await run_in_threadpool(repo.update_clima, data)
        except Exception as exc:  # noqa: BLE001
            logger.warning("clima_loop.error", error=str(exc))
        await asyncio.sleep(1800)  # 30 min


async def _baja_loop():
    """Baja automática diaria del mapa. Dos relojes:

    - el que pagó y venció: `dias_vencido_baja` (40 = 10 de gracia + 1 mes en
      'solo mapa');
    - el que nunca pagó: `dias_gracia_sin_pago` desde el alta (la segunda pasada).

    Corre dentro del proceso, así que se reinicia en cada deploy; para dispararlo
    a mano está POST /admin/bajas/ejecutar.
    """
    while True:
        try:
            repo = get_repo()
            n = await run_in_threadpool(
                repo.ocultar_comercios_vencidos,
                settings.dias_vencido_baja,
                settings.dias_gracia_sin_pago,
            )
            if n:
                logger.info("baja_automatica", ocultados=n)
        except Exception as exc:  # noqa: BLE001
            logger.warning("baja_loop.error", error=str(exc))
        await asyncio.sleep(86400)  # 1 día


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("api.startup", service="bermejo", environment=settings.environment)
    tareas = []
    if settings.clima_worker:
        tareas.append(asyncio.create_task(_clima_loop()))
        tareas.append(asyncio.create_task(_baja_loop()))
    yield
    for t in tareas:
        t.cancel()


app = FastAPI(title="Bermejo Live Market API", version="0.1.0", lifespan=lifespan)


def _cors_origins() -> list[str]:
    if settings.environment == "development":
        return ["*"]
    # FRONTEND_URL puede listar varios dominios separados por coma (ej. durante la
    # migración: "https://encontralo.store,https://buscadonde.com"). Por cada uno se
    # permite apex y www.
    out: set[str] = set()
    for fe in settings.frontend_url.split(","):
        fe = fe.strip().rstrip("/")
        if not fe:
            continue
        out.add(fe)
        out.add(fe.replace("https://www.", "https://") if "www." in fe else fe.replace("https://", "https://www."))
    return list(out)


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limit simple (en memoria) por prefijo de ruta + IP.
_BUCKETS: dict[str, deque] = defaultdict(deque)
_RL_WINDOW = 60
_RL_RULES: dict[str, int] = {
    "/auth/": 20,
    "/errores": 60,
    "/metricas": 120,
}


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "?"


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    if request.method == "POST":
        for prefix, limite in _RL_RULES.items():
            if not request.url.path.startswith(prefix):
                continue
            ip = _client_ip(request)
            now = time.time()
            dq = _BUCKETS[f"{prefix}:{ip}"]
            while dq and now - dq[0] > _RL_WINDOW:
                dq.popleft()
            if len(dq) >= limite:
                return JSONResponse({"detail": "Demasiados intentos, probá en un minuto"}, status_code=429)
            dq.append(now)
            break
    return await call_next(request)


_UMBRAL_LENTO_BACKEND_MS = 1000


@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    inicio = time.perf_counter()
    response = await call_next(request)
    duracion_ms = (time.perf_counter() - inicio) * 1000
    if duracion_ms > _UMBRAL_LENTO_BACKEND_MS:
        await run_in_threadpool(registrar_perf, "backend", request.url.path, "duracion", duracion_ms)
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("api.unhandled_exception", path=request.url.path, error=str(exc))
    await run_in_threadpool(
        registrar_error,
        "backend",
        str(exc) or exc.__class__.__name__,
        "".join(traceback.format_exception(exc)),
        request.url.path,
        500,
    )
    # Las cabeceras CORS se agregan A MANO acá porque este handler corre POR FUERA
    # del CORSMiddleware: sin esto, TODO error 500 le llega al navegador como
    # "blocked by CORS policy" y el error real queda invisible. Cuesta horas de
    # diagnóstico buscando un problema de CORS que no existe.
    headers = {}
    origen = request.headers.get("origin")
    permitidos = _cors_origins()
    if origen and (permitidos == ["*"] or origen in permitidos):
        headers["Access-Control-Allow-Origin"] = origen
        headers["Access-Control-Allow-Credentials"] = "true"
        headers["Vary"] = "Origin"
    return JSONResponse({"detail": "Error interno"}, status_code=500, headers=headers)


app.include_router(health.router, tags=["health"])
app.include_router(auth.router, tags=["auth"])
app.include_router(comercio.router, tags=["comercio"])
app.include_router(campo.router, tags=["campo"])
app.include_router(webhook.router, prefix="/ingest", tags=["ingesta"])
app.include_router(moderacion.router, tags=["moderacion"])
app.include_router(usuario.router, tags=["usuario"])
app.include_router(observabilidad.router, tags=["observabilidad"])
app.include_router(contenido.router, tags=["contenido"])

# Fotos de comercio: servidas por el propio backend (reemplaza a Supabase
# Storage en el self-host — ver services/imagenes.py).
import pathlib  # noqa: E402

pathlib.Path(settings.fotos_dir).mkdir(parents=True, exist_ok=True)
app.mount("/fotos", StaticFiles(directory=settings.fotos_dir), name="fotos")
