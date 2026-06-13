"""Bermejo Live Market · API.

Responsabilidades (ver ADR 2026-06-04-stack-bermejo):
  - Ingesta de WhatsApp (WAHA) -> publicaciones pendientes (idempotente).
  - Moderación (aprobar/rechazar/cambios) con service_role.
El catálogo y el feed los lee el frontend directo de Supabase (anon + RLS).
"""
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
    fe = settings.frontend_url.rstrip("/")
    # permitir apex y www
    alt = fe.replace("https://www.", "https://") if "www." in fe else fe.replace("https://", "https://www.")
    return list({fe, alt})


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(auth.router, tags=["auth"])
app.include_router(comercio.router, tags=["comercio"])
app.include_router(campo.router, tags=["campo"])
app.include_router(webhook.router, prefix="/ingest", tags=["ingesta"])
app.include_router(moderacion.router, tags=["moderacion"])
