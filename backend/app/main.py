"""Bermejo Live Market · API.

Responsabilidades (ver ADR 2026-06-04-stack-bermejo):
  - Ingesta de WhatsApp (WAHA) -> publicaciones pendientes (idempotente).
  - Moderación (aprobar/rechazar/cambios) con service_role.
El catálogo y el feed los lee el frontend directo de Supabase (anon + RLS).
"""
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from app.api import auth, campo, comercio, health, moderacion, webhook
from app.core.config import settings

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

# Rate limit simple (en memoria) para login/registro: 20 POST/min por IP.
_BUCKETS: dict[str, deque] = defaultdict(deque)
_RL_MAX, _RL_WINDOW = 20, 60
_RL_PREFIXES = ("/auth/",)


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "?"


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    if request.method == "POST" and any(request.url.path.startswith(p) for p in _RL_PREFIXES):
        ip = _client_ip(request)
        now = time.time()
        dq = _BUCKETS[ip]
        while dq and now - dq[0] > _RL_WINDOW:
            dq.popleft()
        if len(dq) >= _RL_MAX:
            return JSONResponse({"detail": "Demasiados intentos, probá en un minuto"}, status_code=429)
        dq.append(now)
    return await call_next(request)

app.include_router(health.router, tags=["health"])
app.include_router(auth.router, tags=["auth"])
app.include_router(comercio.router, tags=["comercio"])
app.include_router(campo.router, tags=["campo"])
app.include_router(webhook.router, prefix="/ingest", tags=["ingesta"])
app.include_router(moderacion.router, tags=["moderacion"])
