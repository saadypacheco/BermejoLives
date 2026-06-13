"""Health-check para debug remoto (lesson KB api-health-endpoint)."""
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
        "supabase": detail,
    }
