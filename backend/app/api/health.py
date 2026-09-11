"""Health-check para debug remoto (lesson KB api-health-endpoint).

La base es Postgres propio con PostgREST adelante, en el VPS. El backend le
habla con la librería `supabase-py` porque PostgREST expone la misma API que
Supabase — la herramienta se llama así, el servidor es nuestro. Por eso la
variable se llama SUPABASE_URL y apunta a db.uruku.bo. Nada va a Supabase
Cloud.
"""
import os

from fastapi import APIRouter

from app.core.config import settings
from app.db.session import get_supabase

router = APIRouter()


@router.get("/health")
def health() -> dict:
    db_ok = False
    detail = "not-checked"
    try:
        get_supabase().table("zonas").select("id").limit(1).execute()
        db_ok = True
        detail = "connected"
    except Exception as exc:  # noqa: BLE001
        detail = str(exc)
    return {
        "status": "ok" if db_ok else "degraded",
        "service": "bermejo-backend",
        "environment": settings.environment,
        # "base", no "supabase": es nuestro Postgres. El nombre viejo confundía
        # justo cuando más importa un health check — el 11/9 hizo pensar que
        # el proyecto dependía de un servicio externo que no usa.
        "base": detail,
        # Qué código corre. El frontend ya lo decía en /version; el backend
        # no, y el 11/9 se reconstruyó sólo el backend y no había forma de
        # confirmar que el nuevo estaba arriba.
        "commit": os.environ.get("GIT_SHA", "dev"),
    }
