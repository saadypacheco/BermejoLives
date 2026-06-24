"""Fixtures de test: repo en memoria (FakeRepo) + TestClient con override.

No requiere Supabase ni red: toda la lógica de negocio se ejerce contra dicts.
"""
import pytest
from fastapi.testclient import TestClient

from app.core import auth
from app.db.repository import get_repo
from app.main import app


class FakeRepo:
    """Implementación en memoria del Protocol Repo."""

    def __init__(self):
        self.comercios: dict[str, dict] = {}
        self.usuarios: dict[str, dict] = {}          # email -> row
        self.publicaciones: list[dict] = []
        self.wa_inbox: dict[str, dict] = {}          # wa_message_id -> row
        self.leads: list[dict] = []
        self.producto_refs: dict[str, dict] = {}     # id -> row
        self.pagos: dict[str, dict] = {}             # id -> row
        self.mensajes: dict[str, dict] = {}          # id -> row
        self.zonas: dict[str, str] = {"zona-moda": "zona-1"}
        self.rubros: dict[str, str] = {"importadora": "rub-1", "gastronomia": "rub-2", "gomeria": "rub-3", "servicios": "rub-4"}
        self._seq = 0

    def _id(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}-{self._seq}"

    # ---- comercios ----
    def get_comercio_by_jid(self, wa_jid):
        return next((c for c in self.comercios.values() if c.get("wa_jid") == wa_jid), None)

    def upsert_comercio_by_jid(self, wa_jid, phone):
        existing = self.get_comercio_by_jid(wa_jid)
        if existing:
            return existing
        cid = self._id("com")
        row = {
            "id": cid, "slug": f"comercio-{phone[-6:]}", "nombre": f"Comercio {phone[-4:]}",
            "whatsapp": phone, "wa_jid": wa_jid, "confiable": False, "verificado": False, "plan": "gratis",
        }
        self.comercios[cid] = row
        return row

    def get_comercio(self, comercio_id):
        return self.comercios.get(comercio_id)

    def actualizar_ubicacion_comercio(self, comercio_id, lat, lng, direccion=None):
        c = self.comercios.get(comercio_id)
        if c:
            c.update({"lat": lat, "lng": lng})
            if direccion:
                c["direccion"] = direccion

    def seed_comercio(self, **kw):
        cid = kw.get("id") or self._id("com")
        row = {"id": cid, "confiable": False, "verificado": False, "plan": "gratis", **kw}
        self.comercios[cid] = row
        return row

    # ---- ingesta ----
    def insert_wa_inbox(self, row):
        wamid = row["wa_message_id"]
        if wamid in self.wa_inbox:
            return False
        self.wa_inbox[wamid] = row
        return True

    def insert_publicacion(self, row):
        wamid = row.get("wa_message_id")
        if wamid and any(p.get("wa_message_id") == wamid for p in self.publicaciones):
            return False
        self.publicaciones.append({"id": self._id("pub"), "activo": True, **row})
        return True

    def insert_publicacion_directa(self, row):
        pub = {"id": self._id("pub"), "activo": True, **row}
        self.publicaciones.append(pub)
        return pub

    def list_publicaciones(self, estado):
        return [p for p in self.publicaciones if p.get("activo") and (not estado or p.get("estado") == estado)]

    def list_publicaciones_de_comercio(self, comercio_id):
        return [p for p in self.publicaciones if p.get("comercio_id") == comercio_id and p.get("activo")]

    def set_estado_publicacion(self, pub_id, estado, motivo, by):
        for p in self.publicaciones:
            if p["id"] == pub_id:
                p.update({"estado": estado, "motivo_moderacion": motivo, "moderado_por": by})
                return p
        return {}

    def list_comercios_admin(self, verificado):
        out = [c for c in self.comercios.values() if c.get("activo", True)]
        if verificado is not None:
            out = [c for c in out if bool(c.get("verificado")) == verificado]
        return out

    def set_comercio_verificado(self, comercio_id, valor):
        c = self.comercios.get(comercio_id)
        if not c:
            return {}
        c["verificado"] = valor
        return c

    def desactivar_comercio(self, comercio_id):
        c = self.comercios.get(comercio_id)
        if not c:
            return {}
        c["activo"] = False
        return c

    # ---- cuentas ----
    def get_comercio_usuario(self, email):
        u = self.usuarios.get(email)
        return u if (u and u.get("activo", True)) else None

    def crear_comercio(self, row):
        cid = self._id("com")
        full = {"id": cid, **row}
        self.comercios[cid] = full
        return full

    def crear_comercio_usuario(self, row):
        full = {"id": self._id("usr"), "activo": True, **row}
        self.usuarios[row["email"]] = full
        return full

    def set_comercio_rubros(self, comercio_id, rubro_ids):
        self.comercios[comercio_id]["rubros"] = list(rubro_ids)

    # ---- alta self-service ----
    def slug_existe(self, slug):
        return any(c.get("slug") == slug for c in self.comercios.values())

    def get_zona_id(self, slug):
        return self.zonas.get(slug)

    def get_rubro_id(self, slug):
        return self.rubros.get(slug)

    def get_ciudad_id(self, slug):
        return {"bermejo": "ciu-1"}.get(slug)

    def update_comercio(self, comercio_id, patch, rubro_slugs=None):
        c = self.comercios.get(comercio_id)
        if not c:
            return {}
        c.update(patch)
        if rubro_slugs:
            c["rubros"] = list(rubro_slugs)
        return c

    # ---- leads ----
    def insert_lead(self, row):
        self.leads.append({"id": self._id("lead"), **row})

    def list_leads_by_comercio(self, comercio_id, dias=30):
        return [l for l in self.leads if l.get("comercio_id") == comercio_id]

    # ---- producto_ref ----
    def crear_producto_ref(self, row):
        rid = self._id("pref")
        full = {"id": rid, "estado": "publicado", **row}
        self.producto_refs[rid] = full
        return full

    def list_producto_refs(self, comercio_id):
        return [p for p in self.producto_refs.values() if p.get("comercio_id") == comercio_id]

    def get_producto_ref(self, ref_id):
        return self.producto_refs.get(ref_id)

    def update_producto_ref(self, ref_id, patch):
        p = self.producto_refs.get(ref_id)
        if not p:
            return {}
        p.update(patch)
        return p

    def delete_producto_ref(self, ref_id):
        self.producto_refs.pop(ref_id, None)

    # ---- pagos self-service ----
    def crear_pago_pendiente(self, comercio_id, row):
        pid = self._id("pago")
        full = {"id": pid, "comercio_id": comercio_id, "estado": "pendiente", **row}
        self.pagos[pid] = full
        return full

    def list_pagos_pendientes(self):
        return [p for p in self.pagos.values() if p.get("estado") == "pendiente"]

    def confirmar_pago(self, pago_id, meses, by):
        from datetime import date, timedelta
        pago = self.pagos.get(pago_id)
        if not pago:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="pago no encontrado")
        c = self.comercios.get(pago["comercio_id"]) or {}
        nueva = (date.today() + timedelta(days=30 * max(1, int(meses)))).isoformat()
        pago.update({"estado": "confirmado", "registrado_por": by})
        c["paga_hasta"] = nueva
        c["suspendido"] = False
        self.marcar_destacados_cobrados(pago["comercio_id"])
        return {"ok": True, "paga_hasta": nueva, "comercio_id": pago["comercio_id"]}

    def marcar_destacados_cobrados(self, comercio_id):
        for p in self.publicaciones:
            if p.get("comercio_id") == comercio_id and p.get("costo") and not p.get("cobrado"):
                p["cobrado"] = True

    # ---- mensajes ----
    def crear_mensaje(self, row):
        mid = self._id("msg")
        full = {"id": mid, "leido": False, **row}
        self.mensajes[mid] = full
        return full

    def list_mensajes_de_comercio(self, comercio_id):
        return [m for m in self.mensajes.values() if m.get("comercio_id") == comercio_id]

    def marcar_mensaje_leido(self, mensaje_id, comercio_id):
        m = self.mensajes.get(mensaje_id)
        if m and m.get("comercio_id") == comercio_id:
            m["leido"] = True
            return m
        return {}


@pytest.fixture
def repo():
    return FakeRepo()


@pytest.fixture
def client(repo):
    app.dependency_overrides[get_repo] = lambda: repo
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def admin_token():
    return auth.make_token("admin@bermejolive.com", rol="admin")


def comercio_token(comercio_id="com-1", email="x@y.com"):
    return auth.make_comercio_token(comercio_id, email)
