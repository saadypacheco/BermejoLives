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
    def set_comercio_rubros(self, comercio_id: str, rubro_ids: list[str]) -> None: ...
    def insert_lead(self, row: dict) -> None: ...
    def list_leads_by_comercio(self, comercio_id: str, dias: int) -> list[dict]: ...
    def stats_admin(self) -> dict: ...
    def list_suscripciones(self) -> list[dict]: ...
    def registrar_pago(self, comercio_id: str, row: dict) -> dict: ...
    def suspender_comercio(self, comercio_id: str) -> None: ...
    def activar_comercio(self, comercio_id: str) -> None: ...
    def list_todos_comercios(self, verificado: bool | None, limit: int) -> list[dict]: ...
    def update_comercio(self, comercio_id: str, patch: dict, rubro_slugs: list[str] | None) -> dict: ...


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

    def set_comercio_rubros(self, comercio_id: str, rubro_ids: list[str]) -> None:
        rows = [{"comercio_id": comercio_id, "rubro_id": rid} for rid in rubro_ids if rid]
        if rows:
            self._db.table("comercio_rubros").upsert(rows).execute()

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

    # ---- leads ----
    def insert_lead(self, row: dict) -> None:
        self._db.table("leads").insert(row).execute()

    def list_leads_by_comercio(self, comercio_id: str, dias: int = 30) -> list[dict]:
        from datetime import datetime, timezone, timedelta
        desde = (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat()
        res = (
            self._db.table("leads")
            .select("tipo, created_at")
            .eq("comercio_id", comercio_id)
            .gte("created_at", desde)
            .order("created_at", desc=True)
            .limit(500)
            .execute()
        )
        return res.data or []

    def stats_admin(self) -> dict:
        """Totales rápidos para el dashboard admin."""
        from datetime import datetime, timezone, timedelta
        hoy = datetime.now(timezone.utc).date().isoformat()
        ayer = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()

        comercios = self._db.table("comercios").select("id", count="exact").eq("activo", True).execute()
        pendientes = self._db.table("comercios").select("id", count="exact").eq("activo", True).eq("verificado", False).execute()
        leads_hoy  = self._db.table("leads").select("id", count="exact").gte("created_at", hoy).execute()
        leads_ayer = self._db.table("leads").select("id", count="exact").gte("created_at", ayer).lt("created_at", hoy).execute()

        return {
            "comercios_total":    comercios.count or 0,
            "comercios_pendientes": pendientes.count or 0,
            "leads_hoy":          leads_hoy.count or 0,
            "leads_ayer":         leads_ayer.count or 0,
        }


    # ── suscripciones ────────────────────────────────────────────────────────

    def list_suscripciones(self) -> list[dict]:
        """Todos los comercios activos con su estado de suscripción."""
        from datetime import date, timedelta
        hoy = date.today().isoformat()
        limite_aviso = (date.today() + timedelta(days=5)).isoformat()

        res = (
            self._db.table("comercios")
            .select("id, slug, nombre, whatsapp, verificado, suspendido, paga_hasta, created_at")
            .eq("activo", True)
            .order("nombre")
            .limit(500)
            .execute()
        )
        items = res.data or []

        for c in items:
            ph = c.get("paga_hasta")
            if c.get("suspendido"):
                c["suscripcion_estado"] = "suspendido"
            elif not ph:
                c["suscripcion_estado"] = "sin_plan"
            elif ph < hoy:
                c["suscripcion_estado"] = "vencido"
            elif ph <= limite_aviso:
                c["suscripcion_estado"] = "por_vencer"
            else:
                c["suscripcion_estado"] = "activo"

        return items

    def registrar_pago(self, comercio_id: str, row: dict) -> dict:
        """Registra el pago, extiende paga_hasta y reactiva si estaba suspendido."""
        from datetime import date
        from calendar import monthrange

        comercio = self.get_comercio(comercio_id)
        if not comercio:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="comercio no encontrado")

        meses = int(row.get("meses", 1))
        hoy = date.today()
        base = max(hoy, date.fromisoformat(comercio["paga_hasta"])) if comercio.get("paga_hasta") else hoy

        # Sumar meses manualmente (sin dateutil)
        m = base.month - 1 + meses
        nueva_fecha = date(base.year + m // 12, m % 12 + 1,
                           min(base.day, monthrange(base.year + m // 12, m % 12 + 1)[1])).isoformat()

        # Insertar registro de pago
        self._db.table("pagos").insert({
            "comercio_id": comercio_id,
            "monto":        row["monto"],
            "moneda":       row.get("moneda", "BOB"),
            "metodo":       row.get("metodo", "qr-bolivia"),
            "referencia":   row.get("referencia"),
            "periodo_desde": hoy.isoformat(),
            "periodo_hasta": nueva_fecha,
            "registrado_por": row["registrado_por"],
            "notas":        row.get("notas"),
        }).execute()

        # Actualizar paga_hasta + desuspender
        self._db.table("comercios").update({
            "paga_hasta": nueva_fecha,
            "suspendido": False,
        }).eq("id", comercio_id).execute()

        return {"paga_hasta": nueva_fecha}

    def suspender_comercio(self, comercio_id: str) -> None:
        self._db.table("comercios").update({"suspendido": True}).eq("id", comercio_id).execute()

    def activar_comercio(self, comercio_id: str) -> None:
        self._db.table("comercios").update({"suspendido": False}).eq("id", comercio_id).execute()

    def list_todos_comercios(self, verificado: bool | None = None, limit: int = 300) -> list[dict]:
        q = (
            self._db.table("comercios")
            .select("id, slug, nombre, whatsapp, modalidad, descripcion, direccion, lat, lng, "
                    "verificado, suspendido, paga_hasta, portada_url, created_at, "
                    "rubros(nombre, slug), ciudades(nombre, slug)")
            .eq("activo", True)
        )
        if verificado is not None:
            q = q.eq("verificado", verificado)
        res = q.order("created_at", desc=True).limit(limit).execute()
        return res.data or []

    def update_comercio(self, comercio_id: str, patch: dict, rubro_slugs: list[str] | None) -> dict:
        if patch:
            self._db.table("comercios").update(patch).eq("id", comercio_id).execute()
        if rubro_slugs is not None:
            rubro_ids = [rid for rid in (self.get_rubro_id(s) for s in rubro_slugs if s) if rid]
            if rubro_ids:
                # Actualiza rubro principal + tabla N:M
                self._db.table("comercios").update({"rubro_id": rubro_ids[0]}).eq("id", comercio_id).execute()
                self._db.table("comercio_rubros").delete().eq("comercio_id", comercio_id).execute()
                self.set_comercio_rubros(comercio_id, rubro_ids)
        return self.get_comercio(comercio_id) or {}


def get_repo() -> Repo:
    return SupabaseRepo()
