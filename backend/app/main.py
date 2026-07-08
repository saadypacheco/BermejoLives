"""Bermejo Live Market · API.

Responsabilidades (ver ADR 2026-06-04-stack-bermejo):
  - Ingesta de WhatsApp (WAHA) -> publicaciones pendientes (idempotente).
  - Moderación (aprobar/rechazar/cambios) con service_role.
El catálogo y el feed los lee el frontend directo de Supabase (anon + RLS).
"""
import time
import traceback
from collections import defaultdict, deque
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from app.api import auth, campo, comercio, health, moderacion, observabilidad, usuario, webhook
from app.core.config import settings
from app.services.observabilidad import registrar_error, registrar_perf

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("api.startup", service="bermejo", environment=settings.environment)
    yield


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
    return JSONResponse({"detail": "Error interno"}, status_code=500)


app.include_router(health.router, tags=["health"])
app.include_router(auth.router, tags=["auth"])
app.include_router(comercio.router, tags=["comercio"])
app.include_router(campo.router, tags=["campo"])
app.include_router(webhook.router, prefix="/ingest", tags=["ingesta"])
app.include_router(moderacion.router, tags=["moderacion"])
app.include_router(usuario.router, tags=["usuario"])
app.include_router(observabilidad.router, tags=["observabilidad"])
