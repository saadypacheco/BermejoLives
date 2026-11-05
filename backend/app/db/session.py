"""Cliente de la base con service_role (solo backend; bypassa RLS).

Se usa únicamente `.table(...)`, `.from_(...)` y `.rpc(...)`: es PostgREST puro. No hay Auth,
Storage ni Realtime de Supabase (las fotos van al disco del backend), así que alcanza con
`postgrest-py`, que ya viene con supabase-py.

Dos caminos, según la configuración:
- `POSTGREST_INTERNAL_URL` con valor (ej. http://buscadonde-postgrest:3000): cliente directo a
  PostgREST por la red interna del compose, sin `/rest/v1` y sin salir a internet.
- vacío: el comportamiento de siempre, `create_client(SUPABASE_URL, ...)` (que agrega /rest/v1).
"""
from functools import lru_cache

from app.core.config import settings


def crear_cliente_directo(url_interna: str, service_role_key: str):
    """Cliente PostgREST directo a la URL interna (sin `/rest/v1`), con la llave service_role."""
    from postgrest import SyncPostgrestClient

    base = url_interna.strip().rstrip("/")
    return SyncPostgrestClient(
        base,
        headers={
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
        },
        schema="public",
    )


@lru_cache
def get_supabase():
    if not settings.supabase_service_role_key:
        raise RuntimeError("Falta SUPABASE_SERVICE_ROLE_KEY en el entorno del backend")

    if settings.postgrest_internal_url.strip():
        return crear_cliente_directo(
            settings.postgrest_internal_url, settings.supabase_service_role_key
        )

    # Import perezoso: el paquete `supabase` solo se necesita en runtime real,
    # no para importar la app (tests con repo falso no lo requieren).
    from supabase import create_client

    if not settings.supabase_url:
        raise RuntimeError(
            "Faltan SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY en el entorno del backend"
        )
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
