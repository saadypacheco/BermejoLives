"""Fixtures de test: repo en memoria (FakeRepo) + TestClient con override.

No requiere Supabase ni red: toda la lógica de negocio se ejerce contra dicts.
"""
import os
os.environ.setdefault("CLIMA_WORKER", "0")  # el worker de clima no corre en tests (no red)

import pytest
from fastapi.testclient import TestClient

from app.core import auth
from app.db.repository import get_repo
from app.main import _BUCKETS, app


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    """El rate-limit de /auth/* es un dict en memoria a nivel módulo — sin esto,
    los tests de distintos archivos comparten el contador y algunos empiezan a
    devolver 429 según el orden en que corre la suite completa."""
    _BUCKETS.clear()
    yield


@pytest.fixture(autouse=True)
def _tmp_fotos_dir(tmp_path, monkeypatch):
    """Apunta el volumen de fotos a un tmp escribible: así las subidas de
    foto/video no fallan por no poder escribir en /data/fotos."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "fotos_dir", str(tmp_path / "fotos"))
    yield


class FakeRepo:
    """Implementación en memoria del Protocol Repo."""

    def __init__(self):
        self.comercios: dict[str, dict] = {}
        self.usuarios: dict[str, dict] = {}          # email -> row
        self.compradores: dict[str, dict] = {}       # id -> row (usuarios/favoritos: comprador, no comercio)
        self.favoritos: list[dict] = []               # {usuario_id, comercio_id}
        self.publicaciones: list[dict] = []
        self.wa_inbox: dict[str, dict] = {}          # wa_message_id -> row
        self.leads: list[dict] = []
        self.busquedas: list[dict] = []
        self.busqueda_comercios: list[dict] = []
        self.producto_refs: dict[str, dict] = {}     # id -> row
        self.pagos: dict[str, dict] = {}             # id -> row
        self.mensajes: dict[str, dict] = {}          # id -> row
        self.comercio_fotos: list[dict] = []          # galería
        self.comercio_videos: list[dict] = []
        self.cotizaciones: list[dict] = [
            {"clave": "usd_bob", "etiqueta": "Dólar", "detalle": "1 USD", "valor": 0, "unidad": "Bs", "orden": 1},
            {"clave": "ars_bob", "etiqueta": "Peso argentino", "detalle": "100 ARS", "valor": 0, "unidad": "Bs", "orden": 2},
        ]
        self.clima: dict = {"id": 1, "temp_c": None, "descripcion": None, "override_hasta": None}
        self.videos_promo: list[dict] = []
        self.redes: list[dict] = [
            {"clave": "tiktok", "etiqueta": "TikTok", "url": None, "orden": 1},
            {"clave": "instagram", "etiqueta": "Instagram", "url": None, "orden": 2},
        ]
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

    def update_publicacion_de_comercio(self, pub_id, comercio_id, patch):
        for p in self.publicaciones:
            if p["id"] == pub_id and p.get("comercio_id") == comercio_id and p.get("activo"):
                p.update(patch)
                return p
        return None

    def baja_publicacion_de_comercio(self, pub_id, comercio_id):
        for p in self.publicaciones:
            if p["id"] == pub_id and p.get("comercio_id") == comercio_id and p.get("activo"):
                p["activo"] = False
                return True
        return False

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
        for u in self.usuarios.values():
            if u.get("email") == email and u.get("activo", True):
                return u
        return None

    def get_comercio_usuario_por_whatsapp(self, whatsapp):
        digitos = "".join(c for c in whatsapp if c.isdigit())
        for u in self.usuarios.values():
            c = self.comercios.get(u["comercio_id"])
            if c and c.get("whatsapp") == digitos and u.get("activo", True):
                return u
        return None

    def set_reset_code(self, user_id, code, expira):
        for u in self.usuarios.values():
            if u["id"] == user_id:
                u["reset_code"], u["reset_code_expira"] = code, expira
                u["reset_code_confirmado_at"] = None

    def confirmar_reset_code_comercio(self, whatsapp, codigo):
        from datetime import datetime, timezone

        user = self.get_comercio_usuario_por_whatsapp(whatsapp)
        if not user or not user.get("reset_code") or user["reset_code"] != codigo:
            return False
        expira = user.get("reset_code_expira")
        if not expira or datetime.fromisoformat(expira) < datetime.now(timezone.utc):
            return False
        user["reset_code_confirmado_at"] = datetime.now(timezone.utc).isoformat()
        return True

    def set_password(self, user_id, password_hash):
        for u in self.usuarios.values():
            if u["id"] == user_id:
                u["password_hash"] = password_hash
                u["reset_code"] = u["reset_code_expira"] = None

    def crear_comercio(self, row):
        cid = self._id("com")
        full = {"id": cid, **row}
        self.comercios[cid] = full
        return full

    def list_comercios_por_agente(self, email, limit=200):
        items = [
            c for c in self.comercios.values()
            if c.get("cargado_por") == email and c.get("activo", True)
        ]
        return items[:limit]

    # ---- comprador/visitante ----
    def get_usuario_por_whatsapp(self, whatsapp):
        digitos = "".join(c for c in whatsapp if c.isdigit())
        for u in self.compradores.values():
            if u["whatsapp"] == digitos and u.get("activo", True):
                return u
        return None

    def crear_usuario(self, whatsapp):
        digitos = "".join(c for c in whatsapp if c.isdigit())
        full = {"id": self._id("comprador"), "whatsapp": digitos, "activo": True,
                "reset_code": None, "reset_code_expira": None, "consentimiento_ofertas": True}
        self.compradores[full["id"]] = full
        return full

    def set_reset_code_usuario(self, usuario_id, code, expira):
        u = self.compradores.get(usuario_id)
        if u:
            u["reset_code"], u["reset_code_expira"] = code, expira
            u["reset_code_confirmado_at"] = None

    def confirmar_reset_code_usuario(self, whatsapp, codigo):
        from datetime import datetime, timezone

        usuario = self.get_usuario_por_whatsapp(whatsapp)
        if not usuario or not usuario.get("reset_code") or usuario["reset_code"] != codigo:
            return False
        expira = usuario.get("reset_code_expira")
        if not expira or datetime.fromisoformat(expira) < datetime.now(timezone.utc):
            return False
        usuario["reset_code_confirmado_at"] = datetime.now(timezone.utc).isoformat()
        return True

    def get_usuario(self, usuario_id):
        return self.compradores.get(usuario_id)

    def agregar_favorito(self, usuario_id, comercio_id):
        if not any(f["usuario_id"] == usuario_id and f["comercio_id"] == comercio_id for f in self.favoritos):
            self.favoritos.append({"usuario_id": usuario_id, "comercio_id": comercio_id})

    def quitar_favorito(self, usuario_id, comercio_id):
        self.favoritos = [f for f in self.favoritos if not (f["usuario_id"] == usuario_id and f["comercio_id"] == comercio_id)]

    def list_favoritos(self, usuario_id):
        return [
            {"comercio_id": f["comercio_id"], "comercios": self.comercios.get(f["comercio_id"], {})}
            for f in self.favoritos if f["usuario_id"] == usuario_id
        ]

    # galería
    def list_fotos_comercio(self, comercio_id):
        return sorted([f for f in self.comercio_fotos if f["comercio_id"] == comercio_id], key=lambda x: x.get("orden", 0))

    def add_foto_comercio(self, row):
        full = {"id": self._id("foto"), **row}
        self.comercio_fotos.append(full)
        return full

    def delete_foto_comercio(self, foto_id, comercio_id):
        antes = len(self.comercio_fotos)
        self.comercio_fotos = [f for f in self.comercio_fotos if not (f["id"] == foto_id and f["comercio_id"] == comercio_id)]
        return len(self.comercio_fotos) < antes

    def count_fotos_comercio(self, comercio_id):
        return len(self.list_fotos_comercio(comercio_id))

    def list_videos_comercio(self, comercio_id):
        return sorted([v for v in self.comercio_videos if v["comercio_id"] == comercio_id], key=lambda x: x.get("orden", 0))

    def add_video_comercio(self, row):
        full = {"id": self._id("vid"), **row}
        self.comercio_videos.append(full)
        return full

    def delete_video_comercio(self, video_id, comercio_id):
        antes = len(self.comercio_videos)
        self.comercio_videos = [v for v in self.comercio_videos if not (v["id"] == video_id and v["comercio_id"] == comercio_id)]
        return len(self.comercio_videos) < antes

    def count_videos_comercio(self, comercio_id):
        return len(self.list_videos_comercio(comercio_id))

    # contenido de la home
    def list_cotizaciones(self):
        return sorted(self.cotizaciones, key=lambda x: x.get("orden", 0))

    def update_cotizacion(self, clave, valor):
        for c in self.cotizaciones:
            if c["clave"] == clave:
                c["valor"] = valor
                return c
        return None

    def get_clima(self):
        return self.clima

    def update_clima(self, patch):
        self.clima.update(patch)
        return self.clima

    def list_videos_promo(self, solo_activos=False):
        vs = [v for v in self.videos_promo if (not solo_activos or v.get("activo"))]
        return sorted(vs, key=lambda x: x.get("orden", 0))

    def add_video_promo(self, row):
        full = {"id": self._id("vpromo"), "activo": True, **row}
        self.videos_promo.append(full)
        return full

    def delete_video_promo(self, video_id):
        antes = len(self.videos_promo)
        self.videos_promo = [v for v in self.videos_promo if v["id"] != video_id]
        return len(self.videos_promo) < antes

    def list_redes(self):
        return sorted(self.redes, key=lambda x: x.get("orden", 0))

    def update_red(self, clave, url):
        for r in self.redes:
            if r["clave"] == clave:
                r["url"] = url
                return r
        return None

    def crear_comercio_usuario(self, row):
        full = {"id": self._id("usr"), "activo": True, "email": None, "password_hash": None, **row}
        self.usuarios[full["id"]] = full
        return full

    def set_comercio_rubros(self, comercio_id, rubro_ids):
        self.comercios[comercio_id]["rubros"] = list(rubro_ids)

    def get_comercio_rubros(self, comercio_id):
        id_to_slug = {v: k for k, v in self.rubros.items()}
        crudos = self.comercios.get(comercio_id, {}).get("rubros") or []
        return [id_to_slug.get(r, r) for r in crudos]

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

    def insert_busqueda(self, query, resultados, comercios=None):
        bid = self._id("busq")
        self.busquedas.append({"id": bid, "query": query, "resultados": resultados})
        for i, cid in enumerate((comercios or [])[:10]):
            if cid:
                self.busqueda_comercios.append(
                    {"busqueda_id": bid, "comercio_id": cid, "posicion": i, "query": query}
                )

    def terminos_de_comercio(self, comercio_id, dias=30, limit=8):
        from collections import Counter
        cont = Counter(
            (bc["query"] or "").strip().lower()
            for bc in self.busqueda_comercios
            if bc["comercio_id"] == comercio_id and (bc.get("query") or "").strip()
        )
        return [{"query": q, "n": n} for q, n in cont.most_common(limit)]

    def kpis_admin(self):
        from collections import Counter
        from datetime import date
        def norm(q): return (q or "").strip().lower()
        top = Counter(norm(b["query"]) for b in self.busquedas if norm(b.get("query", "")))
        sin = Counter(norm(b["query"]) for b in self.busquedas if norm(b.get("query", "")) and (b.get("resultados") or 0) == 0)
        por_com = Counter(l["comercio_id"] for l in self.leads if l.get("comercio_id"))
        top_comercios = [
            {"comercio_id": cid, "nombre": (self.comercios.get(cid) or {}).get("nombre", "?"), "slug": (self.comercios.get(cid) or {}).get("slug"), "eventos": n}
            for cid, n in por_com.most_common(10)
        ]
        hoy = date.today().isoformat()
        activos = [c for c in self.comercios.values() if c.get("activo", True)]
        pagando = sum(1 for c in activos if not c.get("suspendido") and c.get("paga_hasta") and str(c["paga_hasta"]) >= hoy)
        return {
            "top_busquedas": [{"query": q, "n": n} for q, n in top.most_common(15)],
            "sin_resultado": [{"query": q, "n": n} for q, n in sin.most_common(15)],
            "top_comercios": top_comercios,
            "monetizacion": {"comercios_activos": len(activos), "pagando": pagando, "gratis": max(0, len(activos) - pagando)},
        }

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

    def ocultar_comercios_vencidos(self, dias=40):
        from datetime import date, timedelta
        limite = (date.today() - timedelta(days=dias)).isoformat()
        n = 0
        for c in self.comercios.values():
            ph = c.get("paga_hasta")
            if ph and str(ph) < limite and c.get("activo", True):
                c["activo"] = False
                n += 1
        return n

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
