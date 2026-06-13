"""Repositorio: encapsula accesos a Supabase (service_role).

Patrón Protocol como en mentorcomercial para poder testear con un fake.
"""
from typing import Protocol

from app.db.session import get_supabase


class Repo(Protocol):
    def get_comercio_by_jid(self, wa_jid: str) -> dict | None: ...
    def upsert_comercio_by_jid(self, wa_jid: str, phone: str) -> dict: ...
    def actualizar_ubicacion_comercio(self, comercio_id: str, lat: float, lng: float, direccion: str | None) -> None: ...
    def insert_wa_inbox(self, row: dict) -> bool: ...
    def insert_publicacion(self, row: dict) -> bool: ...
    def insert_publicacion_directa(self, row: dict) -> dict: ...
    def list_publicaciones(self, estado: str | None) -> list[dict]: ...
    def set_estado_publicacion(self, pub_id: str, estado: str, motivo: str | None, by: str) -> dict: ...
    def list_comercios_admin(self, verificado: bool | None) -> list[dict]: ...
    def set_comercio_verificado(self, comercio_id: str, valor: bool) -> dict: ...
    def desactivar_comercio(self, comercio_id: str) -> dict: ...
    def get_comercio_usuario(self, email: str) -> dict | None: ...
    def get_comercio(self, comercio_id: str) -> dict | None: ...
    def list_publicaciones_de_comercio(self, comercio_id: str) -> list[dict]: ...
    def slug_existe(self, slug: str) -> bool: ...
    def get_zona_id(self, slug: str) -> str | None: ...
    def get_rubro_id(self, slug: str) -> str | None: ...
    def get_ciudad_id(self, slug: str) -> str | None: ...
    def crear_comercio(self, row: dict) -> dict: ...
    def crear_comercio_usuario(self, row: dict) -> dict: ...


class SupabaseRepo:
    """Implementación real sobre Supabase self-hosted/cloud."""

    def __init__(self, client=None):
        self._db = client or get_supabase()

    # ---- comercios ----
    def get_comercio_by_jid(self, wa_jid: str) -> dict | None:
        res = self._db.table("comercios").select("*").eq("wa_jid", wa_jid).limit(1).execute()
        return res.data[0] if res.data else None

    def upsert_comercio_by_jid(self, wa_jid: str, phone: str) -> dict:
        """Crea un comercio 'borrador' si el remitente es nuevo (alta progresiva)."""
        existing = self.get_comercio_by_jid(wa_jid)
        if existing:
            return existing
        slug = f"comercio-{phone[-6:]}"
        row = {
            "slug": slug,
            "nombre": f"Comercio {phone[-4:]}",
            "whatsapp": phone,
            "wa_jid": wa_jid,
            "verificado": False,
            "plan": "gratis",
        }
        res = self._db.table("comercios").upsert(row, on_conflict="wa_jid").execute()
        return res.data[0]

    def actualizar_ubicacion_comercio(self, comercio_id, lat, lng, direccion=None):
        patch: dict = {"lat": lat, "lng": lng}
        if direccion:
            patch["direccion"] = direccion
        self._db.table("comercios").update(patch).eq("id", comercio_id).execute()

    # ---- ingesta ----
    def insert_wa_inbox(self, row: dict) -> bool:
        res = (
            self._db.table("wa_inbox")
            .upsert(row, on_conflict="wa_message_id", ignore_duplicates=True)
            .execute()
        )
        return bool(res.data)  # vacío => duplicado

    def insert_publicacion(self, row: dict) -> bool:
        res = (
            self._db.table("publicaciones")
            .upsert(row, on_conflict="wa_message_id", ignore_duplicates=True)
            .execute()
        )
        return bool(res.data)

    def insert_publicacion_directa(self, row: dict) -> dict:
        """Inserta una publicación del chatbot/panel (sin wa_message_id)."""
        res = self._db.table("publicaciones").insert(row).execute()
        return res.data[0] if res.data else {}

    # ---- cuentas de comercio ----
    def get_comercio_usuario(self, email: str) -> dict | None:
        res = (
            self._db.table("comercio_usuarios")
            .select("*")
            .eq("email", email)
            .eq("activo", True)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    def get_comercio(self, comercio_id: str) -> dict | None:
        res = self._db.table("comercios").select("*").eq("id", comercio_id).limit(1).execute()
        return res.data[0] if res.data else None

    def list_publicaciones_de_comercio(self, comercio_id: str) -> list[dict]:
        res = (
            self._db.table("publicaciones")
            .select("*")
            .eq("comercio_id", comercio_id)
            .eq("activo", True)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        return res.data or []

    # ---- alta self-service ----
    def slug_existe(self, slug: str) -> bool:
        res = self._db.table("comercios").select("id").eq("slug", slug).limit(1).execute()
        return bool(res.data)

    def get_zona_id(self, slug: str) -> str | None:
        res = self._db.table("zonas").select("id").eq("slug", slug).limit(1).execute()
        return res.data[0]["id"] if res.data else None

    def get_rubro_id(self, slug: str) -> str | None:
        res = self._db.table("rubros").select("id").eq("slug", slug).limit(1).execute()
        return res.data[0]["id"] if res.data else None

    def get_ciudad_id(self, slug: str) -> str | None:
        res = self._db.table("ciudades").select("id").eq("slug", slug).limit(1).execute()
        return res.data[0]["id"] if res.data else None

    def crear_comercio(self, row: dict) -> dict:
        res = self._db.table("comercios").insert(row).execute()
        return res.data[0]

    def crear_comercio_usuario(self, row: dict) -> dict:
        res = self._db.table("comercio_usuarios").insert(row).execute()
        return res.data[0]

    # ---- moderación ----
    def list_publicaciones(self, estado: str | None) -> list[dict]:
        q = self._db.table("publicaciones").select("*, comercios(nombre, slug, logo_url)").eq("activo", True)
        if estado:
            q = q.eq("estado", estado)
        res = q.order("created_at", desc=True).limit(200).execute()
        return res.data or []

    def set_estado_publicacion(self, pub_id: str, estado: str, motivo: str | None, by: str) -> dict:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        patch = {
            "estado": estado,
            "motivo_moderacion": motivo,
            "moderado_por": by,
            "moderado_at": now,
        }
        if estado == "aprobado":
            patch["approved_at"] = now
        res = self._db.table("publicaciones").update(patch).eq("id", pub_id).execute()
        return res.data[0] if res.data else {}

    # ---- moderación de comercios (alta de campo) ----
    def list_comercios_admin(self, verificado: bool | None) -> list[dict]:
        q = self._db.table("comercios").select("*, rubros(nombre)").eq("activo", True)
        if verificado is not None:
            q = q.eq("verificado", verificado)
        res = q.order("created_at", desc=True).limit(200).execute()
        return res.data or []

    def set_comercio_verificado(self, comercio_id: str, valor: bool) -> dict:
        res = self._db.table("comercios").update({"verificado": valor}).eq("id", comercio_id).execute()
        return res.data[0] if res.data else {}

    def desactivar_comercio(self, comercio_id: str) -> dict:
        res = self._db.table("comercios").update({"activo": False}).eq("id", comercio_id).execute()
        return res.data[0] if res.data else {}


def get_repo() -> Repo:
    return SupabaseRepo()
