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
    def get_comercio_usuario_por_whatsapp(self, whatsapp: str) -> dict | None: ...
    def set_reset_code(self, user_id: str, code: str | None, expira: str | None) -> None: ...
    def set_password(self, user_id: str, password_hash: str) -> None: ...
    def get_comercio(self, comercio_id: str) -> dict | None: ...
    def list_publicaciones_de_comercio(self, comercio_id: str) -> list[dict]: ...
    def update_publicacion_de_comercio(self, pub_id: str, comercio_id: str, patch: dict) -> dict | None: ...
    def baja_publicacion_de_comercio(self, pub_id: str, comercio_id: str) -> bool: ...
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
    def estadisticas_admin(self) -> dict: ...
    def list_suscripciones(self) -> list[dict]: ...
    def registrar_pago(self, comercio_id: str, row: dict) -> dict: ...
    def suspender_comercio(self, comercio_id: str) -> None: ...
    def activar_comercio(self, comercio_id: str) -> None: ...
    def crear_pago_pendiente(self, comercio_id: str, row: dict) -> dict: ...
    def list_pagos_pendientes(self) -> list[dict]: ...
    def confirmar_pago(self, pago_id: str, meses: int, by: str) -> dict: ...
    def marcar_destacados_cobrados(self, comercio_id: str) -> None: ...
    def crear_mensaje(self, row: dict) -> dict: ...
    def list_mensajes_de_comercio(self, comercio_id: str) -> list[dict]: ...
    def marcar_mensaje_leido(self, mensaje_id: str, comercio_id: str) -> dict: ...
    def list_todos_comercios(self, verificado: bool | None, limit: int) -> list[dict]: ...
    def update_comercio(self, comercio_id: str, patch: dict, rubro_slugs: list[str] | None) -> dict: ...
    def crear_producto_ref(self, row: dict) -> dict: ...
    def list_producto_refs(self, comercio_id: str) -> list[dict]: ...
    def get_producto_ref(self, ref_id: str) -> dict | None: ...
    def update_producto_ref(self, ref_id: str, patch: dict) -> dict: ...
    def delete_producto_ref(self, ref_id: str) -> None: ...
    def crear_reclamo(self, row: dict) -> dict: ...
    def list_reclamos(self, estado: str | None) -> list[dict]: ...
    def responder_reclamo(self, reclamo_id: str, respuesta: str, by: str) -> dict | None: ...
    def buscar_comercios_por_nombre(self, q: str) -> list[dict]: ...
    def crear_solicitud_cambio_numero(self, row: dict) -> dict: ...
    def list_solicitudes_cambio_numero(self, estado: str | None) -> list[dict]: ...
    def aprobar_solicitud_cambio_numero(self, solicitud_id: str, by: str) -> dict | None: ...
    def rechazar_solicitud_cambio_numero(self, solicitud_id: str, by: str) -> dict | None: ...


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

    def get_comercio_usuario_por_whatsapp(self, whatsapp: str) -> dict | None:
        digitos = "".join(c for c in whatsapp if c.isdigit())
        com = (
            self._db.table("comercios").select("id").eq("whatsapp", digitos).eq("activo", True).limit(1).execute()
        )
        if not com.data:
            return None
        res = (
            self._db.table("comercio_usuarios")
            .select("*").eq("comercio_id", com.data[0]["id"]).eq("activo", True).limit(1).execute()
        )
        return res.data[0] if res.data else None

    def set_reset_code(self, user_id: str, code: str | None, expira: str | None) -> None:
        self._db.table("comercio_usuarios").update({"reset_code": code, "reset_code_expira": expira}).eq("id", user_id).execute()

    def set_password(self, user_id: str, password_hash: str) -> None:
        self._db.table("comercio_usuarios").update(
            {"password_hash": password_hash, "reset_code": None, "reset_code_expira": None}
        ).eq("id", user_id).execute()

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

    def update_publicacion_de_comercio(self, pub_id: str, comercio_id: str, patch: dict) -> dict | None:
        """Edita una publicación SOLO si pertenece al comercio (y sigue activa)."""
        res = (
            self._db.table("publicaciones")
            .update(patch)
            .eq("id", pub_id)
            .eq("comercio_id", comercio_id)
            .eq("activo", True)
            .execute()
        )
        return res.data[0] if res.data else None

    def baja_publicacion_de_comercio(self, pub_id: str, comercio_id: str) -> bool:
        """Soft-delete de una publicación propia del comercio."""
        res = (
            self._db.table("publicaciones")
            .update({"activo": False})
            .eq("id", pub_id)
            .eq("comercio_id", comercio_id)
            .eq("activo", True)
            .execute()
        )
        return bool(res.data)

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

    def estadisticas_admin(self) -> dict:
        """Monitoreo: usuarios/comercios nuevos, alertas de baja, ofertas y contactos."""
        from datetime import datetime, timezone, timedelta
        hoy_dt = datetime.now(timezone.utc)
        hace_7d = (hoy_dt - timedelta(days=7)).isoformat()
        hace_30d = (hoy_dt - timedelta(days=30)).isoformat()
        hoy = hoy_dt.date().isoformat()
        limite_aviso = (hoy_dt.date() + timedelta(days=5)).isoformat()

        comercios = (
            self._db.table("comercios")
            .select("id, nombre, created_at, suspendido, paga_hasta")
            .eq("activo", True)
            .limit(2000)
            .execute()
        ).data or []

        nuevos_7d = sum(1 for c in comercios if c["created_at"] >= hace_7d)
        nuevos_30d = sum(1 for c in comercios if c["created_at"] >= hace_30d)

        alertas = {"vencido": 0, "suspendido": 0, "por_vencer": 0}
        for c in comercios:
            ph = c.get("paga_hasta")
            if c.get("suspendido"):
                alertas["suspendido"] += 1
            elif ph and ph < hoy:
                alertas["vencido"] += 1
            elif ph and ph <= limite_aviso:
                alertas["por_vencer"] += 1

        nombre_por_id = {c["id"]: c["nombre"] for c in comercios}

        ofertas = (
            self._db.table("publicaciones")
            .select("comercio_id")
            .not_.is_("descuento_pct", "null")
            .eq("activo", True)
            .limit(5000)
            .execute()
        ).data or []
        conteo_ofertas: dict[str, int] = {}
        for o in ofertas:
            conteo_ofertas[o["comercio_id"]] = conteo_ofertas.get(o["comercio_id"], 0) + 1
        top_ofertas = sorted(
            ({"comercio_id": cid, "nombre": nombre_por_id.get(cid, "?"), "count": n} for cid, n in conteo_ofertas.items()),
            key=lambda x: -x["count"],
        )[:10]

        leads = (
            self._db.table("leads")
            .select("comercio_id, created_at")
            .gte("created_at", hace_30d)
            .limit(5000)
            .execute()
        ).data or []
        conteo_leads: dict[str, int] = {}
        for l in leads:
            conteo_leads[l["comercio_id"]] = conteo_leads.get(l["comercio_id"], 0) + 1
        top_leads = sorted(
            ({"comercio_id": cid, "nombre": nombre_por_id.get(cid, "?"), "count": n} for cid, n in conteo_leads.items()),
            key=lambda x: -x["count"],
        )[:10]

        return {
            "comercios_nuevos_7d": nuevos_7d,
            "comercios_nuevos_30d": nuevos_30d,
            "alertas": alertas,
            "ofertas_total": len(ofertas),
            "ofertas_top_comercios": top_ofertas,
            "contactos_30d": len(leads),
            "contactos_top_comercios": top_leads,
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

    # ---- pago self-service (comercio sube comprobante → admin confirma) ----
    def crear_pago_pendiente(self, comercio_id: str, row: dict) -> dict:
        """El comercio declara un pago con comprobante. Queda 'pendiente' (NO extiende
        paga_hasta hasta que el admin lo confirme)."""
        from datetime import date
        res = self._db.table("pagos").insert({
            "comercio_id":     comercio_id,
            "monto":           row["monto"],
            "moneda":          row.get("moneda", "ARS"),
            "metodo":          row.get("metodo", "qr-bolivia"),
            "referencia":      row.get("referencia"),
            "comprobante_url": row.get("comprobante_url"),
            "estado":          "pendiente",
            "periodo_desde":   date.today().isoformat(),
            "periodo_hasta":   date.today().isoformat(),  # se recalcula al confirmar
            "registrado_por":  "comercio:self-service",
            "notas":           row.get("notas"),
        }).execute()
        return res.data[0]

    def list_pagos_pendientes(self) -> list[dict]:
        res = (
            self._db.table("pagos")
            .select("*, comercios(nombre, slug)")
            .eq("estado", "pendiente")
            .order("created_at", desc=True)
            .limit(200)
            .execute()
        )
        return res.data or []

    def confirmar_pago(self, pago_id: str, meses: int, by: str) -> dict:
        """El admin confirma un pago pendiente: lo marca confirmado y extiende paga_hasta."""
        from datetime import date
        from calendar import monthrange
        from fastapi import HTTPException

        res = self._db.table("pagos").select("*").eq("id", pago_id).limit(1).execute()
        pago = res.data[0] if res.data else None
        if not pago:
            raise HTTPException(status_code=404, detail="pago no encontrado")
        comercio = self.get_comercio(pago["comercio_id"])
        if not comercio:
            raise HTTPException(status_code=404, detail="comercio no encontrado")

        meses = max(1, int(meses))
        hoy = date.today()
        base = max(hoy, date.fromisoformat(comercio["paga_hasta"])) if comercio.get("paga_hasta") else hoy
        m = base.month - 1 + meses
        nueva = date(base.year + m // 12, m % 12 + 1,
                     min(base.day, monthrange(base.year + m // 12, m % 12 + 1)[1])).isoformat()

        self._db.table("pagos").update({
            "estado": "confirmado", "periodo_hasta": nueva, "registrado_por": by,
        }).eq("id", pago_id).execute()
        self._db.table("comercios").update({
            "paga_hasta": nueva, "suspendido": False,
        }).eq("id", pago["comercio_id"]).execute()
        # Los destacados pendientes quedan saldados con este pago.
        self.marcar_destacados_cobrados(pago["comercio_id"])
        return {"ok": True, "paga_hasta": nueva, "comercio_id": pago["comercio_id"]}

    def marcar_destacados_cobrados(self, comercio_id: str) -> None:
        (self._db.table("publicaciones").update({"cobrado": True})
         .eq("comercio_id", comercio_id).eq("cobrado", False)
         .filter("costo", "not.is", "null").execute())

    # ---- mensajes (bandeja del comercio) ----
    def crear_mensaje(self, row: dict) -> dict:
        res = self._db.table("mensajes").insert(row).execute()
        return res.data[0]

    def list_mensajes_de_comercio(self, comercio_id: str) -> list[dict]:
        res = (
            self._db.table("mensajes").select("*")
            .eq("comercio_id", comercio_id).order("created_at", desc=True).limit(200).execute()
        )
        return res.data or []

    def marcar_mensaje_leido(self, mensaje_id: str, comercio_id: str) -> dict:
        (self._db.table("mensajes").update({"leido": True})
         .eq("id", mensaje_id).eq("comercio_id", comercio_id).execute())
        res = self._db.table("mensajes").select("*").eq("id", mensaje_id).limit(1).execute()
        return res.data[0] if res.data else {}

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

    # ---- producto_ref (puente con el ecommerce) ----
    def crear_producto_ref(self, row: dict) -> dict:
        res = self._db.table("producto_ref").insert(row).execute()
        return res.data[0]

    def list_producto_refs(self, comercio_id: str) -> list[dict]:
        res = (
            self._db.table("producto_ref").select("*")
            .eq("comercio_id", comercio_id).order("created_at", desc=True).execute()
        )
        return res.data or []

    def get_producto_ref(self, ref_id: str) -> dict | None:
        res = self._db.table("producto_ref").select("*").eq("id", ref_id).limit(1).execute()
        return res.data[0] if res.data else None

    def update_producto_ref(self, ref_id: str, patch: dict) -> dict:
        self._db.table("producto_ref").update(patch).eq("id", ref_id).execute()
        return self.get_producto_ref(ref_id) or {}

    def delete_producto_ref(self, ref_id: str) -> None:
        self._db.table("producto_ref").delete().eq("id", ref_id).execute()

    # ---- reclamos ----
    def crear_reclamo(self, row: dict) -> dict:
        res = self._db.table("reclamos").insert(row).execute()
        return res.data[0]

    def list_reclamos(self, estado: str | None) -> list[dict]:
        q = (
            self._db.table("reclamos")
            .select("*, comercios(nombre, slug)")
            .order("created_at", desc=True)
            .limit(500)
        )
        if estado:
            q = q.eq("estado", estado)
        return q.execute().data or []

    def responder_reclamo(self, reclamo_id: str, respuesta: str, by: str) -> dict | None:
        from datetime import datetime, timezone
        res = (
            self._db.table("reclamos")
            .update({
                "estado": "respondido",
                "respuesta": respuesta,
                "respondido_por": by,
                "respondido_en": datetime.now(timezone.utc).isoformat(),
            })
            .eq("id", reclamo_id)
            .execute()
        )
        return res.data[0] if res.data else None

    # ---- solicitudes de cambio de número (cuenta sin email/pass, se cambió de celular) ----
    def buscar_comercios_por_nombre(self, q: str) -> list[dict]:
        res = (
            self._db.table("comercios")
            .select("id, slug, nombre, portada_url, direccion")
            .eq("activo", True)
            .ilike("nombre", f"%{q}%")
            .limit(10)
            .execute()
        )
        return res.data or []

    def crear_solicitud_cambio_numero(self, row: dict) -> dict:
        res = self._db.table("solicitudes_cambio_numero").insert(row).execute()
        return res.data[0]

    def list_solicitudes_cambio_numero(self, estado: str | None) -> list[dict]:
        q = (
            self._db.table("solicitudes_cambio_numero")
            .select("*, comercios(nombre, slug, portada_url, whatsapp)")
            .order("created_at", desc=True)
            .limit(200)
        )
        if estado:
            q = q.eq("estado", estado)
        return q.execute().data or []

    def aprobar_solicitud_cambio_numero(self, solicitud_id: str, by: str) -> dict | None:
        from datetime import datetime, timezone
        sol_res = self._db.table("solicitudes_cambio_numero").select("*").eq("id", solicitud_id).limit(1).execute()
        if not sol_res.data:
            return None
        sol = sol_res.data[0]
        self._db.table("comercios").update({"whatsapp": sol["whatsapp_nuevo"]}).eq("id", sol["comercio_id"]).execute()
        res = (
            self._db.table("solicitudes_cambio_numero")
            .update({"estado": "aprobada", "revisada_por": by, "revisada_en": datetime.now(timezone.utc).isoformat()})
            .eq("id", solicitud_id)
            .execute()
        )
        return res.data[0] if res.data else None

    def rechazar_solicitud_cambio_numero(self, solicitud_id: str, by: str) -> dict | None:
        from datetime import datetime, timezone
        res = (
            self._db.table("solicitudes_cambio_numero")
            .update({"estado": "rechazada", "revisada_por": by, "revisada_en": datetime.now(timezone.utc).isoformat()})
            .eq("id", solicitud_id)
            .execute()
        )
        return res.data[0] if res.data else None


def get_repo() -> Repo:
    return SupabaseRepo()
