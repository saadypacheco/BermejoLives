"""Repositorio de los teléfonos leídos en las fotos (migración 0184, docs/telefonos-en-fotos.md).

Aparte de `repository.py` (4.000 líneas) a propósito, como `content_repository.py`: menos choques de merge y
el módulo se prueba solo con su propio fake (`tests/telefonos_fakes.py`).

Las dos tablas son SÓLO de `service_role`: el front nunca las lee por PostgREST. `comercios` se lee SIEMPRE
por columnas (regla 11 de AGENTS.md): nunca `select("*")`, y nunca la columna del código del comercio.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

import structlog

from app.db.session import get_supabase

logger = structlog.get_logger()

#: Lo que el panel y la aplicación necesitan de un comercio. Nada más (regla 11).
COLS_COMERCIO = "id, slug, nombre, whatsapp, telefono, activo, ciudad_id"
COLS_DETECTADO = "id, comercio_id, numero, tipo, texto_leido, foto_url, motor, estado, compartido, created_at"


class TelefonosRepo(Protocol):
    def list_ciudades(self) -> list[dict]: ...
    def get_comercio_min(self, comercio_id: str) -> dict | None: ...
    # ── el worker ──
    def portadas_sin_escanear(self, motor: str, limit: int = 20, ciudad_id: str | None = None) -> list[dict]: ...
    def registrar_escaneada(self, foto_url: str, motor: str, comercio_id: str, numeros: int,
                            error: str | None = None) -> None: ...
    def insert_detectados(self, rows: list[dict]) -> list[dict]: ...
    def list_por_numero(self, numero: str) -> list[dict]: ...
    def marcar_compartido(self, numero: str) -> None: ...
    # ── el panel ──
    def resumen(self, motor: str, ciudad_id: str | None = None) -> dict: ...
    def list_detectados(self, estado: str | None, ciudad_id: str | None, sin_whatsapp: bool,
                        limit: int, offset: int) -> tuple[list[dict], int]: ...
    def contar_comercios_por_numero(self, numeros: list[str]) -> dict[str, int]: ...
    def get_detectado(self, detectado_id: str) -> dict | None: ...
    def update_detectado(self, detectado_id: str, patch: dict) -> dict | None: ...


class SupabaseTelefonosRepo:
    """Implementación real sobre Supabase self-hosted (PostgREST)."""

    def __init__(self, client=None):
        self._client = client

    @property
    def _db(self):
        """El cliente, recién cuando se necesita (un endpoint que recibe este repo por inyección no toca la
        base hasta que lo usa)."""
        if self._client is None:
            self._client = get_supabase()
        return self._client

    # ── lecturas de tablas viejas ────────────────────────────────────────────
    def list_ciudades(self) -> list[dict]:
        res = self._db.table("ciudades").select("id, slug, nombre, departamento").order("orden").limit(200).execute()
        return res.data or []

    def get_comercio_min(self, comercio_id: str) -> dict | None:
        res = self._db.table("comercios").select(COLS_COMERCIO).eq("id", comercio_id).limit(1).execute()
        return res.data[0] if res.data else None

    # ── el worker ────────────────────────────────────────────────────────────
    def portadas_sin_escanear(self, motor: str, limit: int = 20, ciudad_id: str | None = None) -> list[dict]:
        """`[{comercio_id, portada_url, whatsapp, telefono, ciudad_id}]` de las portadas que faltan leer
        con ese motor, primero las de comercios sin WhatsApp (función SQL de la 0184)."""
        res = self._db.rpc("portadas_sin_escanear",
                           {"p_motor": motor, "p_limit": limit, "p_ciudad_id": ciudad_id}).execute()
        return res.data or []

    def registrar_escaneada(self, foto_url: str, motor: str, comercio_id: str, numeros: int,
                            error: str | None = None) -> None:
        self._db.table("fotos_escaneadas").upsert(
            {"foto_url": foto_url, "motor": motor, "comercio_id": comercio_id, "numeros": numeros,
             "error": error[:300] if error else None, "escaneada_at": datetime.now(timezone.utc).isoformat()},
            on_conflict="foto_url,motor").execute()

    def insert_detectados(self, rows: list[dict]) -> list[dict]:
        """Inserta las propuestas nuevas. Una que ya existe (mismo comercio y número) se IGNORA: no se pisa lo
        que una persona ya aplicó o descartó. Devuelve sólo las filas que se crearon."""
        if not rows:
            return []
        res = (self._db.table("telefonos_detectados")
               .upsert(rows, on_conflict="comercio_id,numero", ignore_duplicates=True).execute())
        return res.data or []

    def list_por_numero(self, numero: str) -> list[dict]:
        res = (self._db.table("telefonos_detectados").select("id, comercio_id")
               .eq("numero", numero).eq("activo", True).limit(1000).execute())
        return res.data or []

    def marcar_compartido(self, numero: str) -> None:
        (self._db.table("telefonos_detectados").update({"compartido": True})
         .eq("numero", numero).eq("activo", True).execute())

    # ── el panel ─────────────────────────────────────────────────────────────
    def resumen(self, motor: str, ciudad_id: str | None = None) -> dict:
        res = self._db.rpc("telefonos_resumen", {"p_motor": motor, "p_ciudad_id": ciudad_id}).execute()
        return res.data or {}

    def list_detectados(self, estado: str | None, ciudad_id: str | None, sin_whatsapp: bool,
                        limit: int, offset: int) -> tuple[list[dict], int]:
        """Las propuestas con su comercio embebido (clave `comercios`, un dict), las más nuevas primero. Sólo de comercios
        activos. `sin_whatsapp` = el comercio tiene el WhatsApp en null (uno vacío cuenta como cargado)."""
        sel = (f"{COLS_DETECTADO}, comercios!inner(id, slug, nombre, whatsapp, telefono, ciudad_id, "
               "portada_url, portada_thumb_url, ciudades(nombre, slug))")
        q = (self._db.table("telefonos_detectados").select(sel, count="exact")
             .eq("activo", True).eq("comercios.activo", True))
        if estado:
            q = q.eq("estado", estado)
        if ciudad_id:
            q = q.eq("comercios.ciudad_id", ciudad_id)
        if sin_whatsapp:
            q = q.is_("comercios.whatsapp", "null")
        res = q.order("created_at", desc=True).order("id").range(offset, offset + limit - 1).execute()
        return res.data or [], int(res.count or 0)

    def contar_comercios_por_numero(self, numeros: list[str]) -> dict[str, int]:
        """Cuántos comercios distintos tienen cada número (para «Compartido con N comercios»)."""
        out: dict[str, set[str]] = {}
        for i in range(0, len(numeros), 50):
            res = (self._db.table("telefonos_detectados").select("numero, comercio_id")
                   .in_("numero", numeros[i:i + 50]).eq("activo", True).limit(5000).execute())
            for f in res.data or []:
                out.setdefault(f["numero"], set()).add(f["comercio_id"])
        return {n: len(c) for n, c in out.items()}

    def get_detectado(self, detectado_id: str) -> dict | None:
        res = (self._db.table("telefonos_detectados").select(COLS_DETECTADO + ", activo")
               .eq("id", detectado_id).limit(1).execute())
        return res.data[0] if res.data else None

    def update_detectado(self, detectado_id: str, patch: dict) -> dict | None:
        res = self._db.table("telefonos_detectados").update(patch).eq("id", detectado_id).execute()
        return res.data[0] if res.data else None


def get_telefonos_repo() -> TelefonosRepo:
    return SupabaseTelefonosRepo()
