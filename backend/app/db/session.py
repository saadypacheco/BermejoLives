"""Cliente Supabase con service_role (solo backend; bypassa RLS)."""
from functools import lru_cache

from app.core.config import settings


@lru_cache
def get_supabase():
    # Import perezoso: el paquete `supabase` solo se necesita en runtime real,
    # no para importar la app (tests con repo falso no lo requieren).
    from supabase import Client, create_client  # noqa: F401

    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError(
            "Faltan SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY en el entorno del backend"
        )
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
