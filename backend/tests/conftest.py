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
        self.adornos: dict[str, dict] = {}
        self.sinonimos: dict[str, str] = {}
        self.sinonimos_manuales: set[str] = set()
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
        self.comercio_numeros: list[dict] = []        # números autorizados a publicar
        self.reclamos: dict[str, dict] = {}           # id -> row
        self.solicitudes_numero: dict[str, dict] = {} # id -> row
        self.rubros_propuestos: list[dict] = []       # categorías que la IA propuso y no existen
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
        self.rubros: dict[str, str] = {
            "importadora": "rub-1", "gastronomia": "rub-2", "gomeria": "rub-3", "servicios": "rub-4",
            # Los que usa la deducción por texto (espejo de rubro_palabras).
            "otros": "rub-otros", "calzado": "rub-cal", "ropa": "rub-ropa",
            "neumaticos": "rub-neu", "electronica": "rub-ele", "ferreteria": "rub-fer",
        }
        self.lugares: dict[str, dict] = {}
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
        por_numero = self.get_comercio_por_numero(phone)
        if por_numero:
            self.vincular_wa_jid(por_numero["id"], wa_jid)
            return por_numero
        cid = self._id("com")
        row = {
            "id": cid, "slug": f"comercio-{phone[-6:]}", "nombre": f"Comercio {phone[-4:]}",
            "whatsapp": phone, "wa_jid": wa_jid, "confiable": False, "verificado": False, "plan": "gratis",
            "codigo": self._codigo_libre(),
        }
        self.comercios[cid] = row
        self.agregar_numero_comercio(cid, phone, "alta por WhatsApp", "ingest")
        return row

    # ---- números autorizados ----
    def get_comercio_por_numero(self, numero):
        from app.core.telefono import normalizar_whatsapp
        num = normalizar_whatsapp(numero)
        if not num:
            return None
        for n in self.comercio_numeros:
            if n["numero"] == num and n.get("activo", True):
                return self.comercios.get(n["comercio_id"])
        candidatos = {num, num[3:] if num.startswith("591") else num}
        for c in self.comercios.values():
            if c.get("whatsapp") in candidatos and c.get("activo", True):
                return c
        return None

    def vincular_wa_jid(self, comercio_id, wa_jid):
        if comercio_id in self.comercios:
            self.comercios[comercio_id]["wa_jid"] = wa_jid

    def agregar_numero_comercio(self, comercio_id, numero, etiqueta, by):
        from app.core.telefono import normalizar_whatsapp
        num = normalizar_whatsapp(numero)
        if not num:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail=f"Número inválido: {numero}")
        for n in self.comercio_numeros:
            if n["numero"] == num:
                n.update({"comercio_id": comercio_id, "etiqueta": etiqueta, "activo": True})
                return n
        fila = {"id": self._id("num"), "comercio_id": comercio_id, "numero": num,
                "etiqueta": etiqueta, "created_by": by, "activo": True}
        self.comercio_numeros.append(fila)
        return fila

    def list_numeros_comercio(self, comercio_id):
        return [n for n in self.comercio_numeros
                if n["comercio_id"] == comercio_id and n.get("activo", True)]

    def asegurar_comercio_usuario(self, comercio_id):
        for u in self.usuarios.values():
            if u.get("comercio_id") == comercio_id and u.get("activo", True):
                return u
        comercio = self.comercios.get(comercio_id)
        if not comercio:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="comercio no encontrado")
        return self.crear_comercio_usuario({"comercio_id": comercio_id, "nombre": comercio.get("nombre")})

    def set_comercio_confiable(self, comercio_id, valor):
        c = self.comercios.get(comercio_id)
        if not c:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="comercio no encontrado")
        c["confiable"] = valor
        return c

    def _ahora(self):
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    def get_comercio(self, comercio_id):
        return self.comercios.get(comercio_id)

    def get_comercio_por_codigo(self, codigo):
        from app.core.codigo import normalizar
        norm = normalizar(codigo)
        if not norm:
            return None
        for c in self.comercios.values():
            if c.get("codigo") == norm and c.get("activo", True):
                return c
        return None

    def _codigo_libre(self):
        from app.core.codigo import generar_codigo
        for _ in range(20):
            c = generar_codigo()
            if not self.get_comercio_por_codigo(c):
                return c
        raise RuntimeError("sin códigos libres")

    def get_publicacion(self, pub_id):
        for p in self.publicaciones:
            if p.get("id") == pub_id:
                return p
        return None

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
        if not row.get("codigo"):
            row["codigo"] = self._codigo_libre()
        return row

    # ---- lugares (mercados / galerías) ----
    def crear_lugar(self, row):
        lid = row.get("id") or self._id("lug")
        r = {"id": lid, "activo": True, **row}
        self.lugares[lid] = r
        return r

    def list_lugares(self, ciudad_id=None):
        return [l for l in self.lugares.values() if l.get("activo", True)]

    def get_lugar(self, lugar_id):
        return self.lugares.get(lugar_id)

    def update_lugar(self, lugar_id, patch):
        l = self.lugares.get(lugar_id)
        if l:
            l.update(patch)
        return l or {}

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
        if not full.get("codigo"):
            full["codigo"] = self._codigo_libre()
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

    def crear_usuario(self, whatsapp, ref=None):
        digitos = "".join(c for c in whatsapp if c.isdigit())
        full = {"id": self._id("comprador"), "whatsapp": digitos, "activo": True,
                "reset_code": None, "reset_code_expira": None, "consentimiento_ofertas": True,
                "ref": ref}
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

    # Espejo mínimo del diccionario real (tabla rubro_palabras). No busca ser
    # completo: alcanza para ejercer la lógica de "sumar sin pisar" y el descarte
    # de "otros". El vocabulario de verdad vive en la base.
    _PALABRAS_FAKE = {
        "calzado":    ("zapatilla", "championes", "chinela", "sandalia"),
        "ropa":       ("ropa", "remera", "pantalon", "vestido", "medias"),
        "neumaticos": ("neumatico", "cubierta", "llanta", "goma"),
        "electronica": ("televisor", "parlante", "audio"),
        "ferreteria": ("tornillo", "pintura", "foco", "herramienta"),
    }

    # Columnas que el repo real pide en el select. PostgREST las devuelve TODAS,
    # con null si están vacías; el fake tiene que hacer lo mismo o los tests no
    # detectan que falte una en el select de producción (pasó con `codigo`).
    _COLS_LISTADO_ADMIN = (
        "id", "slug", "nombre", "whatsapp", "telefono", "modalidad", "descripcion",
        "prod_obs_human", "prod_det_ia", "subcategoria", "codigo", "direccion", "lat", "lng", "verificado", "suspendido",
        "paga_hasta", "portada_url", "portada_thumb_url", "cargado_por", "created_at",
        "lugar_id", "puesto",
    )

    # ---- reclamos ----
    def crear_reclamo(self, row):
        rid = self._id("rec")
        full = {"id": rid, "estado": "pendiente", "created_at": self._ahora(), **row}
        self.reclamos[rid] = full
        return full

    def list_reclamos(self, estado=None):
        items = list(self.reclamos.values())
        if estado:
            items = [r for r in items if r.get("estado") == estado]
        return sorted(items, key=lambda r: r.get("created_at", ""), reverse=True)

    def responder_reclamo(self, reclamo_id, respuesta, by):
        r = self.reclamos.get(reclamo_id)
        if not r:
            return None
        r.update({"respuesta": respuesta, "estado": "respondido",
                  "respondido_por": by, "respondido_en": self._ahora()})
        return r

    # ---- solicitudes de cambio de número ----
    def crear_solicitud_cambio_numero(self, row):
        sid = self._id("sol")
        full = {"id": sid, "estado": "pendiente", "created_at": self._ahora(), **row}
        self.solicitudes_numero[sid] = full
        return full

    def list_solicitudes_cambio_numero(self, estado=None):
        items = list(self.solicitudes_numero.values())
        if estado:
            items = [x for x in items if x.get("estado") == estado]
        return sorted(items, key=lambda x: x.get("created_at", ""), reverse=True)

    def aprobar_solicitud_cambio_numero(self, solicitud_id, by):
        sol = self.solicitudes_numero.get(solicitud_id)
        if not sol:
            return None
        # Igual que el repo real: aprobar CAMBIA el whatsapp del comercio.
        c = self.comercios.get(sol["comercio_id"])
        if c:
            c["whatsapp"] = sol["whatsapp_nuevo"]
        sol.update({"estado": "aprobada", "revisada_por": by, "revisada_en": self._ahora()})
        return sol

    def rechazar_solicitud_cambio_numero(self, solicitud_id, by):
        sol = self.solicitudes_numero.get(solicitud_id)
        if not sol:
            return None
        sol.update({"estado": "rechazada", "revisada_por": by, "revisada_en": self._ahora()})
        return sol

    # ---- suscripciones y estado de plataforma ----
    def list_suscripciones(self):
        from datetime import date, timedelta
        hoy, aviso = date.today().isoformat(), (date.today() + timedelta(days=5)).isoformat()
        out = []
        for c in self.comercios.values():
            if not c.get("activo", True):
                continue
            ph = c.get("paga_hasta")
            if c.get("suspendido"):
                estado = "suspendido"
            elif not ph:
                estado = "sin_plan"
            elif str(ph) < hoy:
                estado = "vencido"
            elif str(ph) <= aviso:
                estado = "por_vencer"
            else:
                estado = "activo"
            out.append({**c, "suscripcion_estado": estado})
        return out

    def suspender_comercio(self, comercio_id):
        if comercio_id in self.comercios:
            self.comercios[comercio_id]["suspendido"] = True

    def activar_comercio(self, comercio_id):
        if comercio_id in self.comercios:
            self.comercios[comercio_id].update({"suspendido": False, "activo": True})

    def buscar_comercios_por_nombre(self, q):
        nq = (q or "").lower()
        return [c for c in self.comercios.values()
                if c.get("activo", True) and nq in (c.get("nombre") or "").lower()]

    def stats_admin(self):
        return {
            "comercios": len([c for c in self.comercios.values() if c.get("activo", True)]),
            "publicaciones": len(self.publicaciones),
            "pendientes": len([p for p in self.publicaciones if p.get("estado") == "pendiente"]),
        }

    def estadisticas_admin(self):
        activos = [c for c in self.comercios.values() if c.get("activo", True)]
        return {
            "comercios_nuevos_7d": len(activos),
            "comercios_nuevos_30d": len(activos),
            "alertas": {
                "vencido": len([c for c in activos if c.get("paga_hasta") and not c.get("suspendido")]),
                "suspendido": len([c for c in activos if c.get("suspendido")]),
                "por_vencer": 0,
            },
            "ofertas_total": len(self.publicaciones),
            "ofertas_top_comercios": [],
            "contactos_30d": len(self.leads),
            "contactos_top_comercios": [],
        }

    def list_todos_comercios(self, verificado=None, limit=200):
        items = [c for c in self.comercios.values() if c.get("activo", True)]
        if verificado is not None:
            items = [c for c in items if c.get("verificado") == verificado]
        return [
            {**{k: c.get(k) for k in self._COLS_LISTADO_ADMIN},
             "rubros": c.get("rubros_join"), "ciudades": c.get("ciudades_join"),
             "lugares": c.get("lugares_join")}
            for c in items[:limit]
        ]

    def comercios_sin_analizar(self, limite):
        pend = [c for c in self.comercios.values()
                if c.get("activo", True) and not c.get("ia_analizado_at") and c.get("portada_url")]
        return sorted(pend, key=lambda c: c.get("created_at") or "")[:limite]

    def contar_sin_analizar(self):
        return len([c for c in self.comercios.values()
                    if c.get("activo", True) and not c.get("ia_analizado_at") and c.get("portada_url")])

    def registrar_rubros_propuestos(self, textos, comercio_id):
        from app.db.repository import _normalizar_rubro
        for t in textos:
            limpio = (t or "").strip()
            if limpio:
                self.rubros_propuestos.append(
                    {"texto": limpio, "normalizado": _normalizar_rubro(limpio),
                     "comercio_id": comercio_id})

    def resumen_rubros_propuestos(self, limite=100):
        conteo = {}
        for fila in self.rubros_propuestos:
            item = conteo.setdefault(fila["normalizado"],
                                     {"normalizado": fila["normalizado"], "veces": 0,
                                      "variantes": set(), "comercios": set()})
            item["veces"] += 1
            item["variantes"].add(fila["texto"])
            if fila.get("comercio_id"):
                item["comercios"].add(fila["comercio_id"])
        salida = [{"normalizado": v["normalizado"], "veces": v["veces"],
                   "variantes": sorted(v["variantes"]), "comercios": len(v["comercios"])}
                  for v in conteo.values()]
        return sorted(salida, key=lambda x: -x["veces"])[:limite]

    def list_rubros(self):
        return [{"slug": s, "nombre": s.title()} for s in self.rubros]

    def sugerir_rubros_por_texto(self, texto):
        if not texto or not texto.strip():
            return []
        t = texto.lower()
        return sorted({slug for slug, palabras in self._PALABRAS_FAKE.items()
                       if any(p in t for p in palabras)})

    def get_diccionario_sinonimos(self):
        return dict(self.sinonimos)

    def list_adornos(self, ciudad_id=None):
        return [a for a in self.adornos.values() if a.get("activo", True)
                and (not ciudad_id or a.get("ciudad_id") == ciudad_id)]

    def crear_adorno(self, row):
        aid = row.get("id") or f"adorno-{len(self.adornos) + 1}"
        self.adornos[aid] = {**row, "id": aid, "activo": True}
        return self.adornos[aid]

    def update_adorno(self, adorno_id, patch):
        self.adornos.setdefault(adorno_id, {"id": adorno_id}).update(patch)
        return self.adornos[adorno_id]

    def list_comercio_rubros_todos(self):
        salida = []
        for cid, c in self.comercios.items():
            for slug in (c.get("rubros") or []):
                salida.append({"comercio_id": cid, "slug": slug, "nombre": slug})
        return salida

    def revisar_sinonimos(self):
        return None

    def guardar_sinonimos(self, entradas, origen="ia"):
        escritos = 0
        for t, v in (entradas or {}).items():
            if not t or not v:
                continue
            # Lo cargado a mano no se pisa desde la IA: es la regla que protege
            # las correcciones de quien revisa.
            if origen != "manual" and t in self.sinonimos_manuales:
                continue
            self.sinonimos[t] = v
            if origen == "manual":
                self.sinonimos_manuales.add(t)
            escritos += 1
        return escritos

    def quitar_rubro_comercio(self, comercio_id, rubro_id):
        c = self.comercios.get(comercio_id)
        if c and c.get("rubros"):
            c["rubros"] = [r for r in c["rubros"] if r != rubro_id]

    def set_comercio_rubros(self, comercio_id, rubro_ids):
        # El repo real hace upsert: SUMA, no reemplaza. El fake tiene que hacer lo
        # mismo o los tests validarían un comportamiento que no existe.
        actuales = self.comercios[comercio_id].get("rubros") or []
        self.comercios[comercio_id]["rubros"] = list(dict.fromkeys([*actuales, *rubro_ids]))

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

    def get_rubro_nombre(self, slug):
        return slug.title() if self.rubros.get(slug) else None

    def get_ciudad_id(self, slug):
        return {"bermejo": "ciu-1"}.get(slug)

    def update_comercio(self, comercio_id, patch, rubro_slugs=None):
        c = self.comercios.get(comercio_id)
        if not c:
            return {}
        patch = dict(patch)
        # Espeja al repo real: rearma el slug si es genérico y le ponen nombre real.
        import re as _re
        from app.core.text import slugify as _slugify, slug_unico as _slug_unico
        nombre_nuevo = patch.get("nombre")
        if nombre_nuevo and nombre_nuevo.strip() and "slug" not in patch:
            if _re.match(r"^comercio(-\d+)?$", c.get("slug") or ""):
                base = _slugify(nombre_nuevo)
                if base and base != "comercio":
                    patch["slug"] = _slug_unico(self, base)
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

    def registrar_pago(self, comercio_id, row):
        from datetime import date, timedelta
        c = self.comercios.get(comercio_id)
        if not c:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="comercio no encontrado")
        nueva = (date.today() + timedelta(days=30 * max(1, int(row.get("meses", 1))))).isoformat()
        pid = self._id("pag")
        self.pagos[pid] = {"id": pid, "comercio_id": comercio_id, "estado": "confirmado", **row}
        c["paga_hasta"] = nueva
        c["suspendido"] = False
        self.marcar_destacados_cobrados(comercio_id)
        return {"paga_hasta": nueva, "comercio_id": comercio_id}

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

    def ocultar_comercios_vencidos(self, dias=40, dias_gracia=None):
        from datetime import date, datetime, timedelta, timezone
        limite = (date.today() - timedelta(days=dias)).isoformat()
        corte = (datetime.now(timezone.utc) - timedelta(days=dias_gracia)).isoformat() if dias_gracia is not None else None
        n = 0
        for c in self.comercios.values():
            if not c.get("activo", True):
                continue
            ph = c.get("paga_hasta")
            if ph and str(ph) < limite:
                c["activo"] = False
                n += 1
            elif not ph and corte and str(c.get("created_at") or "") < corte:
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
def agente_token():
    return auth.make_agente_token("agente@bermejolive.com")


@pytest.fixture
def admin_token():
    return auth.make_token("admin@bermejolive.com", rol="admin")


def comercio_token(comercio_id="com-1", email="x@y.com"):
    return auth.make_comercio_token(comercio_id, email)
