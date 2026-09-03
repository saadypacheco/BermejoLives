"""Repositorio: encapsula accesos a Supabase (service_role).

Patrón Protocol como en mentorcomercial para poder testear con un fake.
"""
import re
from typing import Protocol

import structlog

from app.core.text import slugify, slug_unico
from app.db.session import get_supabase

logger = structlog.get_logger()

# Slug "genérico" (sin nombre real al dar de alta): comercio, comercio-2, ...
# Mientras el slug sea así, se rearma solo cuando le ponen un nombre de verdad.
_SLUG_GENERICO = re.compile(r"^comercio(-\d+)?$")


def _normalizar_rubro(texto: str) -> str:
    """Agrupa variantes: 'Juguetería', 'jugueterias', '🧸 Juguetería' → 'jugueteria'."""
    import unicodedata

    sin_tildes = "".join(c for c in unicodedata.normalize("NFD", texto or "")
                         if unicodedata.category(c) != "Mn")
    limpio = re.sub(r"[^a-z0-9]+", " ", sin_tildes.lower()).strip()
    # Singular grosero: sin esto "juguetería" y "jugueterías" cuentan como dos
    # necesidades distintas y el ranking de lo que falta queda partido.
    palabras = [p[:-2] if len(p) > 5 and p.endswith("es") else
                p[:-1] if len(p) > 3 and p.endswith("s") else p
                for p in limpio.split()]
    return " ".join(palabras)


class Repo(Protocol):
    def get_comercio_by_jid(self, wa_jid: str) -> dict | None: ...
    def upsert_comercio_by_jid(self, wa_jid: str, phone: str) -> dict: ...
    def actualizar_ubicacion_comercio(self, comercio_id: str, lat: float, lng: float, direccion: str | None) -> None: ...
    def insert_wa_inbox(self, row: dict) -> bool: ...
    def insert_publicacion(self, row: dict) -> bool: ...
    def insert_publicacion_directa(self, row: dict) -> dict: ...
    def list_publicaciones(self, estado: str | None) -> list[dict]: ...
    def get_publicacion(self, pub_id: str) -> dict | None: ...
    def set_estado_publicacion(self, pub_id: str, estado: str, motivo: str | None, by: str) -> dict: ...
    def list_comercios_admin(self, verificado: bool | None) -> list[dict]: ...
    def set_comercio_verificado(self, comercio_id: str, valor: bool) -> dict: ...
    def desactivar_comercio(self, comercio_id: str) -> dict: ...
    def get_comercio_usuario(self, email: str) -> dict | None: ...
    def get_comercio_usuario_por_whatsapp(self, whatsapp: str) -> dict | None: ...
    def set_reset_code(self, user_id: str, code: str | None, expira: str | None) -> None: ...
    def confirmar_reset_code_comercio(self, whatsapp: str, codigo: str) -> bool: ...
    def set_password(self, user_id: str, password_hash: str) -> None: ...
    def get_comercio(self, comercio_id: str) -> dict | None: ...
    def list_publicaciones_de_comercio(self, comercio_id: str) -> list[dict]: ...
    def update_publicacion_de_comercio(self, pub_id: str, comercio_id: str, patch: dict) -> dict | None: ...
    def baja_publicacion_de_comercio(self, pub_id: str, comercio_id: str) -> bool: ...
    def slug_existe(self, slug: str) -> bool: ...
    def get_zona_id(self, slug: str) -> str | None: ...
    def get_rubro_id(self, slug: str) -> str | None: ...
    def get_rubro_nombre(self, slug: str) -> str | None: ...
    def get_ciudad_id(self, slug: str) -> str | None: ...
    def get_ciudad(self, slug: str) -> dict | None: ...
    def crear_comercio(self, row: dict) -> dict: ...
    def get_comercio_por_codigo(self, codigo: str) -> dict | None: ...
    def crear_comercio_usuario(self, row: dict) -> dict: ...
    def set_comercio_rubros(self, comercio_id: str, rubro_ids: list[str]) -> None: ...
    def list_rubros(self) -> list[dict]: ...
    def comercios_sin_analizar(self, limite: int) -> list[dict]: ...
    def contar_sin_analizar(self) -> int: ...
    def registrar_rubros_propuestos(self, textos: list[str], comercio_id: str | None) -> None: ...
    def resumen_rubros_propuestos(self, limite: int = 100) -> list[dict]: ...
    def sugerir_rubros_por_texto(self, texto: str) -> list[str]: ...
    def crear_rubro(self, row: dict) -> dict: ...
    def agregar_palabras_rubro(self, slug: str, patron: str) -> None: ...
    def previsualizar_patron(self, patron: str, rubro: str | None) -> list[dict]: ...
    def publicaciones_sin_analizar(self, limite: int) -> list[dict]: ...
    def update_publicacion(self, pub_id: str, patch: dict) -> dict: ...
    def borrar_propuestas(self, normalizado: str) -> None: ...
    def get_diccionario_sinonimos(self) -> dict[str, str]: ...
    def revisar_sinonimos(self) -> str | None: ...
    def contar(self, tabla: str) -> int: ...
    def list_vencimientos(self) -> list[dict]: ...
    def crear_vencimiento(self, row: dict) -> dict: ...
    def update_vencimiento(self, vid: str, patch: dict) -> dict: ...
    def borrar_vencimiento(self, vid: str) -> None: ...
    def list_comercio_rubros_todos(self) -> list[dict]: ...
    def list_adornos(self, ciudad_id: str | None) -> list[dict]: ...
    def crear_adorno(self, row: dict) -> dict: ...
    def update_adorno(self, adorno_id: str, patch: dict) -> dict: ...
    def guardar_sinonimos(self, entradas: dict[str, str], origen: str = "ia") -> int: ...
    def quitar_rubro_comercio(self, comercio_id: str, rubro_id: str) -> None: ...
    def reemplazar_comercio_rubros(self, comercio_id: str, rubro_ids: list[str]) -> None: ...
    def get_comercio_rubros(self, comercio_id: str) -> list[str]: ...
    def insert_lead(self, row: dict) -> None: ...
    def list_leads_by_comercio(self, comercio_id: str, dias: int) -> list[dict]: ...
    def stats_admin(self) -> dict: ...
    def estadisticas_admin(self) -> dict: ...
    def altas_por_dia(self, dias: int = 60) -> list[dict]: ...
    def insert_busqueda(
        self, query: str, resultados: int, comercios: list[str] | None = None
    ) -> str | None: ...
    def terminos_de_comercio(
        self, comercio_id: str, dias: int = 30, limit: int = 8
    ) -> list[dict]: ...
    def kpis_admin(self) -> dict: ...
    def list_suscripciones(self) -> list[dict]: ...
    def registrar_pago(self, comercio_id: str, row: dict) -> dict: ...
    def suspender_comercio(self, comercio_id: str) -> None: ...
    def activar_comercio(self, comercio_id: str) -> None: ...
    def ocultar_comercios_vencidos(self, dias: int = 40, dias_gracia: int | None = None) -> int: ...
    def get_comercio_por_numero(self, numero: str) -> dict | None: ...
    def vincular_wa_jid(self, comercio_id: str, wa_jid: str) -> None: ...
    def get_comercio_por_grupo(self, grupo_jid: str) -> dict | None: ...
    def vincular_grupo_comercio(self, grupo_jid: str, comercio_id: str,
                                nombre: str | None, origen: str, by: str) -> None: ...
    def list_grupos_comercio(self, comercio_id: str) -> list[dict]: ...
    def desvincular_grupo(self, grupo_jid: str) -> None: ...
    # ---- comercios importados de fuentes externas ----
    def upsert_importado(self, row: dict) -> bool: ...
    def list_importados(self, estado: str | None, ciudad_id: str | None,
                        q: str | None, limite: int) -> list[dict]: ...
    def get_importado(self, importado_id: str) -> dict | None: ...
    def marcar_importado(self, importado_id: str, patch: dict) -> dict | None: ...
    def resumen_importados(self) -> list[dict]: ...
    def comercios_con_coords(self, ciudad_id: str | None) -> list[dict]: ...
    def agregar_numero_comercio(self, comercio_id: str, numero: str, etiqueta: str | None, by: str) -> dict: ...
    def list_numeros_comercio(self, comercio_id: str) -> list[dict]: ...
    def asegurar_comercio_usuario(self, comercio_id: str) -> dict: ...
    def set_comercio_confiable(self, comercio_id: str, valor: bool) -> dict: ...
    def crear_pago_pendiente(self, comercio_id: str, row: dict) -> dict: ...
    def list_pagos_pendientes(self) -> list[dict]: ...
    def confirmar_pago(self, pago_id: str, meses: int, by: str) -> dict: ...
    def marcar_destacados_cobrados(self, comercio_id: str) -> None: ...
    def crear_mensaje(self, row: dict) -> dict: ...
    def list_mensajes_de_comercio(self, comercio_id: str) -> list[dict]: ...
    def marcar_mensaje_leido(self, mensaje_id: str, comercio_id: str) -> dict: ...
    def list_todos_comercios(self, verificado: bool | None, limit: int) -> list[dict]: ...
    def update_comercio(self, comercio_id: str, patch: dict, rubro_slugs: list[str] | None) -> dict: ...
    def crear_lugar(self, row: dict) -> dict: ...
    def list_lugares(self, ciudad_id: str | None) -> list[dict]: ...
    def get_lugar(self, lugar_id: str) -> dict | None: ...
    def update_lugar(self, lugar_id: str, patch: dict) -> dict: ...
    def crear_producto_ref(self, row: dict) -> dict: ...
    def list_producto_refs(self, comercio_id: str) -> list[dict]: ...
    def get_producto_ref(self, ref_id: str) -> dict | None: ...
    def update_producto_ref(self, ref_id: str, patch: dict) -> dict: ...
    def delete_producto_ref(self, ref_id: str) -> None: ...
    def crear_reclamo(self, row: dict) -> dict: ...
    def list_reclamos(self, estado: str | None) -> list[dict]: ...
    def responder_reclamo(self, reclamo_id: str, respuesta: str, by: str) -> dict | None: ...
    def buscar_comercios_por_nombre(self, q: str) -> list[dict]: ...
    def list_comercios_por_agente(self, email: str, limit: int) -> list[dict]: ...
    def crear_solicitud_cambio_numero(self, row: dict) -> dict: ...
    def list_solicitudes_cambio_numero(self, estado: str | None) -> list[dict]: ...
    def aprobar_solicitud_cambio_numero(self, solicitud_id: str, by: str) -> dict | None: ...
    def rechazar_solicitud_cambio_numero(self, solicitud_id: str, by: str) -> dict | None: ...
    def get_usuario_por_whatsapp(self, whatsapp: str) -> dict | None: ...
    def crear_usuario(self, whatsapp: str) -> dict: ...
    def set_reset_code_usuario(self, usuario_id: str, code: str | None, expira: str | None) -> None: ...
    def confirmar_reset_code_usuario(self, whatsapp: str, codigo: str) -> bool: ...
    def get_usuario(self, usuario_id: str) -> dict | None: ...
    def agregar_favorito(self, usuario_id: str, comercio_id: str) -> None: ...
    def quitar_favorito(self, usuario_id: str, comercio_id: str) -> None: ...
    def list_favoritos(self, usuario_id: str) -> list[dict]: ...
    # galería (fotos/videos por comercio)
    def list_fotos_comercio(self, comercio_id: str) -> list[dict]: ...
    def add_foto_comercio(self, row: dict) -> dict: ...
    def delete_foto_comercio(self, foto_id: str, comercio_id: str) -> bool: ...
    def count_fotos_comercio(self, comercio_id: str) -> int: ...
    def list_videos_comercio(self, comercio_id: str) -> list[dict]: ...
    def add_video_comercio(self, row: dict) -> dict: ...
    def delete_video_comercio(self, video_id: str, comercio_id: str) -> bool: ...
    def count_videos_comercio(self, comercio_id: str) -> int: ...
    # contenido de la home (cotizaciones / clima / videos promocionales)
    def list_cotizaciones(self) -> list[dict]: ...
    def update_cotizacion(self, clave: str, valor: float) -> dict | None: ...
    def get_clima(self) -> dict | None: ...
    def update_clima(self, patch: dict) -> dict | None: ...
    def list_videos_promo(self, solo_activos: bool = False) -> list[dict]: ...
    def add_video_promo(self, row: dict) -> dict: ...
    def delete_video_promo(self, video_id: str) -> bool: ...
    def list_redes(self) -> list[dict]: ...
    def update_red(self, clave: str, url: str | None) -> dict | None: ...


# Las columnas del listado del panel. En una constante porque la paginación
# tiene que pedir EXACTAMENTE las mismas: escritas dos veces terminan
# divergiendo, y el síntoma sería que las filas de la página 2 vienen sin algún
# campo y nadie sabe por qué.
_COLS_COMERCIO_ADMIN = (
    "id, slug, nombre, whatsapp, telefono, modalidad, descripcion, prod_obs_human, "
    "prod_det_ia, subcategoria, sinonimos, codigo, direccion, lat, lng, horario, "
    "verificado, suspendido, paga_hasta, portada_url, portada_thumb_url, cargado_por, "
    "created_at, lugar_id, puesto, "
    "rubros!comercios_rubro_id_fkey(nombre, slug), ciudades(nombre, slug), "
    "lugares(nombre, tipo, lat, lng, portada_thumb_url)"
)


class SupabaseRepo:
    """Implementación real sobre Supabase self-hosted/cloud."""

    def __init__(self, client=None):
        self._db = client or get_supabase()

    # ---- comercios ----
    def get_comercio_by_jid(self, wa_jid: str) -> dict | None:
        res = self._db.table("comercios").select("*").eq("wa_jid", wa_jid).limit(1).execute()
        return res.data[0] if res.data else None

    def get_comercio_por_numero(self, numero: str) -> dict | None:
        """Busca el comercio dueño de un número, normalizado a E.164 sin '+'.

        Orden: primero los números autorizados explícitamente (comercio_numeros),
        después el número público del comercio. El segundo paso es el que rescata
        a los comercios cargados por el agente de campo, que tienen `whatsapp`
        tipeado a mano pero todavía no tienen `wa_jid`.
        """
        from app.core.telefono import normalizar_whatsapp

        num = normalizar_whatsapp(numero)
        if not num:
            return None

        aut = (
            self._db.table("comercio_numeros")
            .select("comercio_id").eq("numero", num).eq("activo", True).limit(1).execute()
        )
        if aut.data:
            return self.get_comercio(aut.data[0]["comercio_id"])

        # El número público se guarda con formato libre (nadie lo validaba hasta
        # que el comercio empieza a pagar), así que se comparan los normalizados.
        for candidato in {num, num[3:] if num.startswith("591") else num}:
            res = (
                self._db.table("comercios")
                .select("*").eq("whatsapp", candidato).eq("activo", True).limit(1).execute()
            )
            if res.data:
                return res.data[0]
        return None

    def vincular_wa_jid(self, comercio_id: str, wa_jid: str) -> None:
        self._db.table("comercios").update({"wa_jid": wa_jid}).eq("id", comercio_id).execute()

    # ---- grupos de WhatsApp (uno por comerciante) ----
    def get_comercio_por_grupo(self, grupo_jid: str) -> dict | None:
        res = (
            self._db.table("comercio_wa_grupos")
            .select("comercio_id").eq("grupo_jid", grupo_jid).limit(1).execute()
        )
        return self.get_comercio(res.data[0]["comercio_id"]) if res.data else None

    def vincular_grupo_comercio(self, grupo_jid: str, comercio_id: str,
                                nombre: str | None, origen: str, by: str) -> None:
        """Ata un grupo a un comercio. Idempotente: si el grupo ya estaba atado
        NO se repisa — un mensaje con un código de otro local no puede robarle
        el grupo a nadie."""
        self._db.table("comercio_wa_grupos").upsert({
            "grupo_jid": grupo_jid, "comercio_id": comercio_id,
            "nombre": nombre, "origen": origen, "created_by": by,
        }, on_conflict="grupo_jid", ignore_duplicates=True).execute()

    def list_grupos_comercio(self, comercio_id: str) -> list[dict]:
        res = (
            self._db.table("comercio_wa_grupos")
            .select("*").eq("comercio_id", comercio_id).execute()
        )
        return res.data or []

    def desvincular_grupo(self, grupo_jid: str) -> None:
        """Suelta el grupo. Lo ya publicado NO se toca: son ofertas que
        existieron, y borrarlas por soltar un grupo sería perder historia."""
        self._db.table("comercio_wa_grupos").delete().eq("grupo_jid", grupo_jid).execute()

    # ---- comercios importados ----
    def upsert_importado(self, row: dict) -> bool:
        """Guarda un importado sin pisar la revisión humana.

        Reimportar una ciudad tiene que poder hacerse cuantas veces haga falta:
        si el upsert pisara `estado`, cada corrida resucitaría los descartados y
        el trabajo de revisión se perdería entero.
        """
        clave = {"fuente": row["fuente"], "fuente_id": row["fuente_id"]}
        existe = (
            self._db.table("comercios_importados")
            .select("id").eq("fuente", clave["fuente"]).eq("fuente_id", clave["fuente_id"])
            .limit(1).execute()
        )
        datos = {k: v for k, v in row.items()
                 if k not in ("estado", "comercio_id", "motivo", "revisado_por", "revisado_at")}
        if existe.data:
            self._db.table("comercios_importados").update(datos).eq("id", existe.data[0]["id"]).execute()
            return False
        self._db.table("comercios_importados").insert(row).execute()
        return True

    def list_importados(self, estado: str | None, ciudad_id: str | None,
                        q: str | None, limite: int = 200) -> list[dict]:
        sel = self._db.table("comercios_importados").select("*")
        if estado:
            sel = sel.eq("estado", estado)
        if ciudad_id:
            sel = sel.eq("ciudad_id", ciudad_id)
        if q:
            sel = sel.ilike("nombre", f"%{q}%")
        res = sel.order("nombre").limit(limite).execute()
        return res.data or []

    def get_importado(self, importado_id: str) -> dict | None:
        res = (self._db.table("comercios_importados")
               .select("*").eq("id", importado_id).limit(1).execute())
        return res.data[0] if res.data else None

    def marcar_importado(self, importado_id: str, patch: dict) -> dict | None:
        res = (self._db.table("comercios_importados")
               .update(patch).eq("id", importado_id).execute())
        return res.data[0] if res.data else None

    def resumen_importados(self) -> list[dict]:
        """Cuántos hay por ciudad y estado, para la cabecera del panel."""
        # Con ~19.861 filas de OSM, `.limit(20000)` devolvía 1000 y la cabecera
        # informaba el 5% de lo importado con cara de número exacto.
        filas = self._traer_todo("comercios_importados", "ciudad_id, estado", "id")
        cuenta: dict[tuple, int] = {}
        for r in filas:
            k = (r.get("ciudad_id"), r.get("estado"))
            cuenta[k] = cuenta.get(k, 0) + 1
        return [{"ciudad_id": c, "estado": e, "n": n} for (c, e), n in cuenta.items()]

    def comercios_con_coords(self, ciudad_id: str | None) -> list[dict]:
        """Los que ya están cargados, para detectar duplicados al importar."""
        # Se usa para detectar duplicados al importar: leer de menos no da
        # error, importa el duplicado.
        def filtrar(q):
            q = q.not_.is_("lat", "null")
            return q.eq("ciudad_id", ciudad_id) if ciudad_id else q

        return self._traer_todo("comercios", "id, nombre, lat, lng", "id", filtrar=filtrar)

    def agregar_numero_comercio(self, comercio_id: str, numero: str, etiqueta: str | None, by: str) -> dict:
        from app.core.telefono import normalizar_whatsapp

        num = normalizar_whatsapp(numero)
        if not num:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail=f"Número inválido: {numero}")
        res = self._db.table("comercio_numeros").upsert({
            "comercio_id": comercio_id, "numero": num,
            "etiqueta": etiqueta, "created_by": by, "activo": True,
        }, on_conflict="numero").execute()
        return res.data[0]

    def list_numeros_comercio(self, comercio_id: str) -> list[dict]:
        res = (
            self._db.table("comercio_numeros")
            .select("*").eq("comercio_id", comercio_id).eq("activo", True).execute()
        )
        return res.data or []

    def upsert_comercio_by_jid(self, wa_jid: str, phone: str) -> dict:
        """Devuelve el comercio del remitente, creándolo sólo si es realmente nuevo.

        Antes de crear reconcilia por número: un comercio cargado en la calle por
        el agente tiene `whatsapp` pero no `wa_jid`, así que buscarlo sólo por
        jid no lo encontraba y se creaba un DUPLICADO "Comercio 1989" cada vez
        que el dueño escribía. Si el número ya pertenece a un comercio, se le ata
        el jid a ese y listo.
        """
        existing = self.get_comercio_by_jid(wa_jid)
        if existing:
            return existing

        por_numero = self.get_comercio_por_numero(phone)
        if por_numero:
            self.vincular_wa_jid(por_numero["id"], wa_jid)
            return {**por_numero, "wa_jid": wa_jid}

        slug = f"comercio-{phone[-6:]}"
        row = {
            "slug": slug,
            "nombre": f"Comercio {phone[-4:]}",
            "whatsapp": phone,
            "wa_jid": wa_jid,
            "verificado": False,
            "plan": "gratis",
            "codigo": self._codigo_libre(),
        }
        res = self._db.table("comercios").upsert(row, on_conflict="wa_jid").execute()
        creado = res.data[0]
        # Queda autorizado el número con el que se dio de alta, para que la
        # próxima reconciliación lo encuentre por comercio_numeros.
        try:
            self.agregar_numero_comercio(creado["id"], phone, "alta por WhatsApp", "ingest")
        except Exception:  # noqa: BLE001 — el alta del comercio no depende de esto
            pass
        return creado

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

    # ---- comprador/visitante (celular + código, sin contraseña) ----
    def get_usuario_por_whatsapp(self, whatsapp: str) -> dict | None:
        digitos = "".join(c for c in whatsapp if c.isdigit())
        res = self._db.table("usuarios").select("*").eq("whatsapp", digitos).eq("activo", True).limit(1).execute()
        return res.data[0] if res.data else None

    def crear_usuario(self, whatsapp: str, ref: str | None = None) -> dict:
        digitos = "".join(c for c in whatsapp if c.isdigit())
        row: dict = {"whatsapp": digitos}
        if ref:
            row["ref"] = ref[:64]   # código de origen (referido), acotado
        res = self._db.table("usuarios").insert(row).execute()
        return res.data[0]

    def set_reset_code_usuario(self, usuario_id: str, code: str | None, expira: str | None) -> None:
        self._db.table("usuarios").update(
            {"reset_code": code, "reset_code_expira": expira, "reset_code_confirmado_at": None}
        ).eq("id", usuario_id).execute()

    def confirmar_reset_code_usuario(self, whatsapp: str, codigo: str) -> bool:
        """Llamado desde el webhook: alguien mandó 'CONFIRMAR-XXXXXX' por
        WhatsApp. Confirma solo si el código coincide, no venció, Y el
        remitente es el mismo número que lo pidió (evita que otra persona
        confirme un código ajeno)."""
        from datetime import datetime, timezone

        usuario = self.get_usuario_por_whatsapp(whatsapp)
        if not usuario or not usuario.get("reset_code") or usuario["reset_code"] != codigo:
            return False
        expira = usuario.get("reset_code_expira")
        if not expira or datetime.fromisoformat(expira) < datetime.now(timezone.utc):
            return False
        self._db.table("usuarios").update(
            {"reset_code_confirmado_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", usuario["id"]).execute()
        return True

    def get_usuario(self, usuario_id: str) -> dict | None:
        res = self._db.table("usuarios").select("*").eq("id", usuario_id).limit(1).execute()
        return res.data[0] if res.data else None

    def agregar_favorito(self, usuario_id: str, comercio_id: str) -> None:
        self._db.table("favoritos").upsert(
            {"usuario_id": usuario_id, "comercio_id": comercio_id}, on_conflict="usuario_id,comercio_id"
        ).execute()

    def quitar_favorito(self, usuario_id: str, comercio_id: str) -> None:
        self._db.table("favoritos").delete().eq("usuario_id", usuario_id).eq("comercio_id", comercio_id).execute()

    def list_favoritos(self, usuario_id: str) -> list[dict]:
        res = (
            self._db.table("favoritos")
            .select("comercio_id, created_at, comercios(id, slug, nombre, logo_url, portada_url, direccion, rating, whatsapp, verificado)")
            .eq("usuario_id", usuario_id)
            .order("created_at", desc=True)
            .execute()
        )
        return res.data or []

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
        self._db.table("comercio_usuarios").update(
            {"reset_code": code, "reset_code_expira": expira, "reset_code_confirmado_at": None}
        ).eq("id", user_id).execute()

    def confirmar_reset_code_comercio(self, whatsapp: str, codigo: str) -> bool:
        """Llamado desde el webhook: alguien mandó 'CONFIRMAR-XXXXXX' por
        WhatsApp. Mismo criterio que confirmar_reset_code_usuario."""
        from datetime import datetime, timezone

        user = self.get_comercio_usuario_por_whatsapp(whatsapp)
        if not user or not user.get("reset_code") or user["reset_code"] != codigo:
            return False
        expira = user.get("reset_code_expira")
        if not expira or datetime.fromisoformat(expira) < datetime.now(timezone.utc):
            return False
        self._db.table("comercio_usuarios").update(
            {"reset_code_confirmado_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", user["id"]).execute()
        return True

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

    def get_rubro_nombre(self, slug: str) -> str | None:
        res = self._db.table("rubros").select("nombre").eq("slug", slug).limit(1).execute()
        return res.data[0]["nombre"] if res.data else None

    def get_ciudad_id(self, slug: str) -> str | None:
        res = self._db.table("ciudades").select("id").eq("slug", slug).limit(1).execute()
        return res.data[0]["id"] if res.data else None

    def get_ciudad(self, slug: str) -> dict | None:
        """La fila entera, con lat/lng: el importador necesita el centro de la
        ciudad para saber alrededor de dónde buscar."""
        res = self._db.table("ciudades").select("*").eq("slug", slug).limit(1).execute()
        return res.data[0] if res.data else None

    def crear_comercio(self, row: dict) -> dict:
        """Alta de comercio. Siempre sale con código: es lo que le permite
        publicar por WhatsApp desde cualquier número, sin login ni pago."""
        if not row.get("codigo"):
            row = {**row, "codigo": self._codigo_libre()}
        res = self._db.table("comercios").insert(row).execute()
        return res.data[0]

    def _codigo_libre(self, intentos: int = 12) -> str:
        """Genera un código que no esté tomado. ~923.000 combinaciones, así que
        una colisión es rarísima; igual se reintenta para no fallar un alta."""
        from app.core.codigo import generar_codigo

        for _ in range(intentos):
            candidato = generar_codigo()
            if not self.get_comercio_por_codigo(candidato):
                return candidato
        # Con la tabla llena de códigos esto sería un problema real, pero antes
        # de eso hay que agrandar el largo del código, no seguir reintentando.
        raise RuntimeError("No se pudo generar un código de comercio único")

    def get_comercio_por_codigo(self, codigo: str) -> dict | None:
        from app.core.codigo import normalizar

        norm = normalizar(codigo)
        if not norm:
            return None
        res = (
            self._db.table("comercios")
            .select("*").eq("codigo", norm).eq("activo", True).limit(1).execute()
        )
        return res.data[0] if res.data else None

    def crear_comercio_usuario(self, row: dict) -> dict:
        res = self._db.table("comercio_usuarios").insert(row).execute()
        return res.data[0]

    def asegurar_comercio_usuario(self, comercio_id: str) -> dict:
        """Garantiza que el comercio tenga una cuenta con la que poder entrar.

        El alta por agente de campo crea la fila en `comercios` pero NUNCA creaba
        la de `comercio_usuarios` (el autoregistro sí lo hace). Resultado: un
        comercio cargado en la calle no podía loguearse jamás, ni siquiera con la
        recuperación por WhatsApp, que busca justamente esa fila. Este es el
        puente que faltaba entre el alta mínima y el panel.

        Idempotente: si ya existe, la devuelve sin tocarla.
        """
        existente = (
            self._db.table("comercio_usuarios")
            .select("*").eq("comercio_id", comercio_id).eq("activo", True).limit(1).execute()
        )
        if existente.data:
            return existente.data[0]

        comercio = self.get_comercio(comercio_id)
        if not comercio:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="comercio no encontrado")

        # Sin email ni password: el dueño entra por el OTP de WhatsApp y define
        # su clave ahí (habilitado por 0023_comercio_usuarios_sin_password).
        return self.crear_comercio_usuario({
            "comercio_id": comercio_id,
            "nombre": comercio["nombre"],
        })

    def set_comercio_confiable(self, comercio_id: str, valor: bool) -> dict:
        res = (
            self._db.table("comercios")
            .update({"confiable": valor}).eq("id", comercio_id).execute()
        )
        if not res.data:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="comercio no encontrado")
        return res.data[0]

    def set_comercio_rubros(self, comercio_id: str, rubro_ids: list[str]) -> None:
        """SUMA rubros. No saca los que ya tenía — para eso está
        `reemplazar_comercio_rubros`.

        (El comentario de `completar_rubros.py` decía que esto reemplazaba el
        conjunto entero. No es así: sólo agrega. Ese script manda la unión, así
        que el resultado era el correcto por otro camino, pero la creencia era
        falsa y en algún momento iba a costar caro.)
        """
        rows = [{"comercio_id": comercio_id, "rubro_id": rid} for rid in rubro_ids if rid]
        if rows:
            self._db.table("comercio_rubros").upsert(rows).execute()

    def reemplazar_comercio_rubros(self, comercio_id: str, rubro_ids: list[str]) -> None:
        """Deja EXACTAMENTE estos rubros: borra los que no están y agrega los que faltan.

        Es lo que necesita la edición a mano. Hasta ahora no había forma de
        QUITARLE un rubro mal puesto a un comercio desde el panel — sólo de
        sumarle otro encima, que es justamente lo que ensucia los filtros.

        El primero de la lista queda como principal (`comercios.rubro_id`): es el
        que se muestra en la tarjeta cuando no hay una categoría elegida.
        """
        ids = [r for r in dict.fromkeys(rubro_ids) if r]
        self._db.table("comercio_rubros").delete().eq("comercio_id", comercio_id).execute()
        if ids:
            self._db.table("comercio_rubros").insert(
                [{"comercio_id": comercio_id, "rubro_id": r} for r in ids]).execute()
        self._db.table("comercios").update(
            {"rubro_id": ids[0] if ids else None}).eq("id", comercio_id).execute()

    def list_rubros(self) -> list[dict]:
        # `comercial` viaja con el rubro porque de eso depende cómo se trata cada
        # ficha: un baño público sin WhatsApp está completo, no incompleto.
        res = (self._db.table("rubros").select("slug, nombre, icono, comercial")
               .eq("activo", True).order("orden").execute())
        return res.data or []

    def comercios_sin_analizar(self, limite: int) -> list[dict]:
        """Comercios con foto que todavía no pasaron por el análisis.

        Se ordenan por antigüedad para que el recorrido más viejo —el que lleva
        más tiempo sin clasificar— se procese primero.
        """
        res = (self._db.table("comercios").select("*")
               .eq("activo", True)
               .is_("ia_analizado_at", "null")
               .not_.is_("portada_url", "null")
               .order("created_at")
               .limit(limite).execute())
        return res.data or []

    def contar_sin_analizar(self) -> int:
        res = (self._db.table("comercios").select("id", count="exact")
               .eq("activo", True)
               .is_("ia_analizado_at", "null")
               .not_.is_("portada_url", "null")
               .limit(1).execute())
        return res.count or 0

    def registrar_rubros_propuestos(self, textos: list[str], comercio_id: str | None) -> None:
        """Guarda las categorías que la IA propuso y no existen todavía.

        Es la evidencia para decidir qué rubro o subcategoría crear: sale de
        locales reales, no de una lista pensada de antemano.
        """
        filas = []
        for t in textos:
            limpio = (t or "").strip()
            if limpio:
                filas.append({"texto": limpio, "normalizado": _normalizar_rubro(limpio),
                              "comercio_id": comercio_id})
        if filas:
            self._db.table("rubros_propuestos").insert(filas).execute()

    def resumen_rubros_propuestos(self, limite: int = 100) -> list[dict]:
        """Agrupadas por variante normalizada y ordenadas por frecuencia: las de
        arriba son las que más falta hacen."""
        res = (self._db.table("rubros_propuestos")
               .select("texto, normalizado, comercio_id").limit(5000).execute())
        conteo: dict[str, dict] = {}
        for fila in (res.data or []):
            clave = fila["normalizado"]
            item = conteo.setdefault(clave, {"normalizado": clave, "veces": 0,
                                             "variantes": set(), "comercios": set()})
            item["veces"] += 1
            item["variantes"].add(fila["texto"])
            if fila.get("comercio_id"):
                item["comercios"].add(fila["comercio_id"])
        salida = [{"normalizado": v["normalizado"], "veces": v["veces"],
                   "variantes": sorted(v["variantes"]), "comercios": len(v["comercios"])}
                  for v in conteo.values()]
        return sorted(salida, key=lambda x: -x["veces"])[:limite]

    def crear_rubro(self, row: dict) -> dict:
        """Alta de un rubro. `on conflict` sobre el slug: reactiva en vez de
        fallar, porque el caso común es recrear uno que se había apagado."""
        res = (self._db.table("rubros")
               .upsert({**row, "activo": True}, on_conflict="slug").execute())
        return res.data[0] if res.data else {}

    def agregar_palabras_rubro(self, slug: str, patron: str) -> None:
        """Una fila del diccionario. El patrón se guarda tal cual: es una regex
        de Postgres y normalizarla acá cambiaría lo que significa."""
        self._db.table("rubro_palabras").upsert(
            {"rubro_slug": slug, "patron": patron},
            on_conflict="rubro_slug,patron").execute()

    def publicaciones_sin_analizar(self, limite: int = 10) -> list[dict]:
        """Ofertas con foto que todavía no pasaron por el análisis.

        Sólo las que tienen imagen: una publicación de sólo texto ya es
        buscable por lo que escribió el comerciante, y gastarle una llamada al
        modelo no agrega nada."""
        res = (self._db.table("publicaciones")
               .select("id, comercio_id, titulo, descripcion, imagen_url, precio")
               .is_("ia_analizado_at", "null")
               .not_.is_("imagen_url", "null")
               .eq("activo", True)
               .order("created_at")
               .limit(limite).execute())
        return res.data or []

    def update_publicacion(self, pub_id: str, patch: dict) -> dict:
        res = self._db.table("publicaciones").update(patch).eq("id", pub_id).execute()
        return res.data[0] if res.data else {}

    def previsualizar_patron(self, patron: str, rubro: str | None = None) -> list[dict]:
        """A qué comercios alcanzaría este patrón, antes de guardarlo.

        Se delega a SQL y no se reimplementa acá porque tiene que usar la MISMA
        normalización que `rubros_sugeridos`, que es la que clasifica de verdad.
        Una vista previa que mira otra cosa que el clasificador tranquiliza
        sobre algo que no se probó.
        """
        try:
            res = self._db.rpc("previsualizar_patron",
                               {"p_patron": patron, "p_rubro": rubro}).execute()
            return list(res.data or [])
        except Exception:  # noqa: BLE001
            logger.warning("previsualizar_patron.fallo", patron=patron, exc_info=True)
            return []

    def borrar_propuestas(self, normalizado: str) -> None:
        """Saca de la cola las propuestas ya resueltas.

        Sin esto, una categoría que se creó o se mandó como sinónimo sigue
        apareciendo en la lista para siempre, y una cola que no baja se deja de
        mirar — que es exactamente lo que le pasó a esta tabla hasta hoy."""
        self._db.table("rubros_propuestos").delete().eq("normalizado", normalizado).execute()

    def sugerir_rubros_por_texto(self, texto: str) -> list[str]:
        """Rubros que se deducen de un texto libre, vía el diccionario en la base.

        Se delega a la función SQL rubros_sugeridos() en vez de reimplementar el
        matcheo acá: el vocabulario vive en la tabla rubro_palabras, que se edita
        sin deploy, y así el alta, la reclasificación masiva y el CSV de revisión
        usan exactamente el mismo criterio.
        """
        if not texto or not texto.strip():
            return []
        try:
            res = self._db.rpc("rubros_sugeridos", {"p_texto": texto}).execute()
            return list(res.data or [])
        except Exception:  # noqa: BLE001 — nunca bloquear un alta por esto
            return []

    def get_diccionario_sinonimos(self) -> dict[str, str]:
        """Todo el diccionario de una. Son cientos de filas de texto corto: leerlo
        entero y resolver en memoria es más barato que una consulta por término."""
        try:
            res = self._db.table("producto_sinonimos").select("termino, sinonimos").execute()
            return {r["termino"]: r["sinonimos"] for r in (res.data or []) if r.get("termino")}
        except Exception:  # noqa: BLE001 — el buscador funciona sin sinónimos
            return {}

    def list_adornos(self, ciudad_id: str | None = None) -> list[dict]:
        """Los adornos activos. Nunca falla hacia arriba: si la tabla no está o
        PostgREST tiene el cache viejo, el mapa se dibuja sin decoración. Perder
        un lapacho no puede dejar al comprador sin ver los comercios."""
        try:
            q = self._db.table("mapa_adornos").select("*").eq("activo", True)
            if ciudad_id:
                q = q.eq("ciudad_id", ciudad_id)
            return list((q.execute().data) or [])
        except Exception:  # noqa: BLE001
            return []

    def crear_adorno(self, row: dict) -> dict:
        res = self._db.table("mapa_adornos").insert(row).execute()
        return (res.data or [{}])[0]

    def update_adorno(self, adorno_id: str, patch: dict) -> dict:
        res = (self._db.table("mapa_adornos").update(patch)
               .eq("id", adorno_id).execute())
        return (res.data or [{}])[0]

    def _traer_todo(self, tabla: str, columnas: str, orden: str | list[str],
                    pagina: int = 1000, techo: int = 200_000,
                    filtrar=None) -> list[dict]:
        """Todas las filas, en páginas. NUNCA con `.limit(N)` grande.

        PostgREST corta en `PGRST_DB_MAX_ROWS` (1000 acá) y NO avisa: un
        `.limit(20000)` devuelve mil filas y una respuesta 200. Quien llama no
        tiene forma de distinguir "eso es todo" de "te di lo que entraba", y el
        resultado es un informe que miente con cara de estar completo.

        Es la quinta vez que este mismo tope muerde en el proyecto. El patrón que
        lo evita no es subir el número —eso sólo mueve el día en que vuelve a
        pasar— es pedir de a páginas hasta que una venga incompleta.
        """
        # El orden tiene que ser TOTAL o el paginado se saltea filas: con un
        # orden ambiguo, dos páginas consecutivas pueden traer la misma fila y
        # perder otra, y nadie se entera. Por eso se aceptan varias columnas.
        columnas_orden = [orden] if isinstance(orden, str) else list(orden)
        filas: list[dict] = []
        for inicio in range(0, techo, pagina):
            q = self._db.table(tabla).select(columnas)
            if filtrar:
                q = filtrar(q)
            for col in columnas_orden:
                q = q.order(col)
            lote = (q.range(inicio, inicio + pagina - 1).execute().data) or []
            filas.extend(lote)
            if len(lote) < pagina:
                return filas
        logger.warning("traer_todo.techo_alcanzado", tabla=tabla, techo=techo)
        return filas

    def contar(self, tabla: str) -> int:
        """Cuántas filas hay de verdad, para poder cotejar contra lo leído."""
        res = self._db.table(tabla).select("*", count="exact", head=True).execute()
        return res.count or 0

    # ---- vencimientos ----
    def list_vencimientos(self) -> list[dict]:
        return (self._db.table("vencimientos").select("*")
                .eq("activo", True).order("vence_el").execute().data) or []

    def crear_vencimiento(self, row: dict) -> dict:
        res = self._db.table("vencimientos").insert(row).execute()
        return res.data[0] if res.data else {}

    def update_vencimiento(self, vid: str, patch: dict) -> dict:
        from datetime import datetime, timezone

        patch = {**patch, "updated_at": datetime.now(timezone.utc).isoformat()}
        res = self._db.table("vencimientos").update(patch).eq("id", vid).execute()
        return res.data[0] if res.data else {}

    def borrar_vencimiento(self, vid: str) -> None:
        # Baja lógica: si algo se deja de vigilar conviene saber que ALGUIEN lo
        # decidió, no que la fila desapareció y nadie se acuerda de por qué.
        self._db.table("vencimientos").update({"activo": False}).eq("id", vid).execute()

    def list_comercio_rubros_todos(self) -> list[dict]:
        """Toda la tabla comercio_rubros de una, con el slug ya resuelto.

        Auditar la taxonomía necesita saber qué rubros tiene CADA comercio.
        Pedirlo de a uno son 161 consultas para armar un informe; la relación
        entera son unos cientos de filas de dos columnas.
        """
        # Dos consultas planas en vez de un select embebido, y se cruzan acá.
        #
        # El embed lo resuelve PostgREST leyendo la foreign key de su cache de
        # esquema, que queda viejo cada vez que corre una migración. Cuando falla
        # devolvía [] en silencio, y quien lo llama no puede distinguir "este
        # comercio no tiene rubros" de "no pude leer la tabla". El script de
        # limpieza informó "0 asignaciones sin respaldo" cuando el informe SQL
        # encontraba 37 — un resultado tranquilizador y falso, que es el peor.
        try:
            # `.limit(20000)` devolvía exactamente 1000: el tope de PostgREST.
            # Con 886 comercios el guard del script no lo notaba (1000 > 886) y
            # los comercios que quedaban afuera parecían no tener ningún rubro.
            rels = self._traer_todo("comercio_rubros", "comercio_id, rubro_id",
                                    ["comercio_id", "rubro_id"])
            rubros = (self._db.table("rubros").select("id, slug, nombre")
                      .execute().data) or []
        except Exception:  # noqa: BLE001
            logger.warning("comercio_rubros.lectura_fallo", exc_info=True)
            return []

        por_id = {r["id"]: r for r in rubros}
        salida = []
        for fila in rels:
            rubro = por_id.get(fila.get("rubro_id"))
            if rubro and rubro.get("slug"):
                salida.append({"comercio_id": fila["comercio_id"],
                               "slug": rubro["slug"], "nombre": rubro.get("nombre")})
        return salida

    def revisar_sinonimos(self) -> str | None:
        """None si el diccionario se puede leer; si no, POR QUÉ no.

        get_diccionario_sinonimos() se traga los errores a propósito —el buscador
        tiene que seguir andando sin sinónimos— pero ese mismo silencio hace que
        una tabla inexistente y una tabla vacía se vean iguales: las dos devuelven
        {}. Sin distinguirlas, una migración sin aplicar o un cache de PostgREST
        viejo se leen como "el diccionario está vacío, hay que preguntar todo", y
        se pagan las llamadas a la IA para que la escritura falle al final.

        Devuelve el error y no sólo un booleano porque las causas posibles se
        arreglan de formas distintas —migración, cache, permisos— y un "no pude"
        pelado manda a probar las tres a ciegas. Ya nos costó dos vueltas
        buscando un cache viejo cuando lo que faltaba era un grant.
        """
        try:
            self._db.table("producto_sinonimos").select("termino").limit(1).execute()
            return None
        except Exception as e:  # noqa: BLE001
            return str(e)[:300]

    def guardar_sinonimos(self, entradas: dict[str, str], origen: str = "ia") -> int:
        """Guarda o actualiza términos del diccionario. Devuelve cuántos escribió.

        Lo escrito a mano no se pisa con lo que devuelve la IA: si alguien
        corrigió un sinónimo porque traía resultados equivocados, la próxima
        corrida no puede volver a romperlo.
        """
        from datetime import datetime, timezone

        if not entradas:
            return 0
        protegidos = set()
        if origen != "manual":
            try:
                res = (self._db.table("producto_sinonimos").select("termino")
                       .eq("origen", "manual").execute())
                protegidos = {r["termino"] for r in (res.data or [])}
            except Exception:  # noqa: BLE001
                protegidos = set()

        filas = [{"termino": t, "sinonimos": v, "origen": origen,
                  "actualizado_at": datetime.now(timezone.utc).isoformat()}
                 for t, v in entradas.items() if t and v and t not in protegidos]
        if not filas:
            return 0
        self._db.table("producto_sinonimos").upsert(filas, on_conflict="termino").execute()
        return len(filas)

    def quitar_rubro_comercio(self, comercio_id: str, rubro_id: str) -> None:
        (self._db.table("comercio_rubros").delete()
         .eq("comercio_id", comercio_id).eq("rubro_id", rubro_id).execute())

    def get_comercio_rubros(self, comercio_id: str) -> list[str]:
        res = (
            self._db.table("comercio_rubros")
            .select("rubros(slug)")
            .eq("comercio_id", comercio_id)
            .execute()
        )
        return [row["rubros"]["slug"] for row in (res.data or []) if row.get("rubros")]

    # ---- moderación ----
    def list_publicaciones(self, estado: str | None) -> list[dict]:
        q = self._db.table("publicaciones").select("*, comercios(nombre, slug, logo_url)").eq("activo", True)
        if estado:
            q = q.eq("estado", estado)
        res = q.order("created_at", desc=True).limit(200).execute()
        return res.data or []

    def get_publicacion(self, pub_id: str) -> dict | None:
        res = self._db.table("publicaciones").select("*").eq("id", pub_id).limit(1).execute()
        return res.data[0] if res.data else None

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
        q = self._db.table("comercios").select("*, rubros!comercios_rubro_id_fkey(nombre)").eq("activo", True)
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

    def altas_por_dia(self, dias: int = 60) -> list[dict]:
        """Cuántos comercios se cargaron cada día, y en qué estado quedaron.

        Se pagina en vez de pedir un tope alto: PostgREST corta en 1000 filas
        (PGRST_DB_MAX_ROWS), así que un `.limit(2000)` devuelve mil y el informe
        contaría de menos sin avisar. Con 800 comercios todavía entra; el día que
        pase los mil, un reporte que miente es peor que uno que no está.
        """
        from datetime import datetime, timedelta, timezone

        desde = (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat()
        filas: list[dict] = []
        pagina = 1000
        for inicio in range(0, 50000, pagina):
            lote = (
                self._db.table("comercios")
                .select("created_at, portada_url, whatsapp, ia_analizado_at, nombre, cargado_por")
                .eq("activo", True)
                .gte("created_at", desde)
                .order("created_at")
                .range(inicio, inicio + pagina - 1)
                .execute()
            ).data or []
            filas.extend(lote)
            if len(lote) < pagina:
                break

        por_dia: dict[str, dict] = {}
        for c in filas:
            dia = (c.get("created_at") or "")[:10]
            if not dia:
                continue
            d = por_dia.setdefault(dia, {
                "dia": dia, "altas": 0, "con_foto": 0, "con_whatsapp": 0,
                "analizados": 0, "con_nombre": 0, "agentes": set(),
            })
            d["altas"] += 1
            if c.get("portada_url"):
                d["con_foto"] += 1
            if (c.get("whatsapp") or "").strip():
                d["con_whatsapp"] += 1
            if c.get("ia_analizado_at"):
                d["analizados"] += 1
            # "Comercio 1234" es el nombre que pone el sistema cuando no hay uno
            # real. Contarlo como nombre haría ver completo lo que no lo está.
            if not (c.get("nombre") or "").lower().startswith("comercio"):
                d["con_nombre"] += 1
            if c.get("cargado_por"):
                d["agentes"].add(c["cargado_por"])

        salida = []
        for d in sorted(por_dia.values(), key=lambda x: x["dia"], reverse=True):
            salida.append({**d, "agentes": len(d["agentes"])})
        return salida

    def estadisticas_admin(self) -> dict:
        """Monitoreo: usuarios/comercios nuevos, alertas de baja, ofertas y contactos."""
        from datetime import datetime, timezone, timedelta
        hoy_dt = datetime.now(timezone.utc)
        hace_7d = (hoy_dt - timedelta(days=7)).isoformat()
        hace_30d = (hoy_dt - timedelta(days=30)).isoformat()
        hoy = hoy_dt.date().isoformat()
        limite_aviso = (hoy_dt.date() + timedelta(days=5)).isoformat()

        # Eran 886 activos contra un tope de 1000: faltaban semanas para que
        # este panel empezara a contar de menos sin avisar.
        comercios = self._traer_todo(
            "comercios", "id, nombre, created_at, suspendido, paga_hasta", "id",
            filtrar=lambda q: q.eq("activo", True))

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

        ofertas = self._traer_todo(
            "publicaciones", "comercio_id", "id",
            filtrar=lambda q: q.not_.is_("descuento_pct", "null").eq("activo", True))
        conteo_ofertas: dict[str, int] = {}
        for o in ofertas:
            conteo_ofertas[o["comercio_id"]] = conteo_ofertas.get(o["comercio_id"], 0) + 1
        top_ofertas = sorted(
            ({"comercio_id": cid, "nombre": nombre_por_id.get(cid, "?"), "count": n} for cid, n in conteo_ofertas.items()),
            key=lambda x: -x["count"],
        )[:10]

        # Se pagina en vez de `.limit(5000)`: PostgREST corta en 1000
        # (PGRST_DB_MAX_ROWS), así que el tope alto devolvía mil filas y el
        # panel mostraba un número redondeado hacia abajo sin avisar. Con los
        # leads eso pasa mucho antes que con los comercios: son varios por día.
        leads: list[dict] = []
        for inicio in range(0, 100000, 1000):
            lote = (
                self._db.table("leads")
                .select("comercio_id, tipo, created_at")
                .gte("created_at", hace_30d)
                .order("created_at")
                .range(inicio, inicio + 999)
                .execute()
            ).data or []
            leads.extend(lote)
            if len(lote) < 1000:
                break

        por_tipo: dict[str, int] = {}
        for l in leads:
            t = l.get("tipo") or "otro"
            por_tipo[t] = por_tipo.get(t, 0) + 1

        # `vista` es una ficha abierta, no un contacto. Contarla acá inflaba
        # `contactos_30d` con cada visita a una ficha —que dispara VistaLogger
        # sola— y dejaba el número más importante del panel diciendo cualquier
        # cosa. El top por comercio arrastraba el mismo error.
        contactos = [l for l in leads if (l.get("tipo") or "") != "vista"]
        conteo_leads: dict[str, int] = {}
        for l in contactos:
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
            "contactos_30d": len(contactos),
            "contactos_top_comercios": top_leads,
            # Desglose: cuántos abrieron el WhatsApp del comercio, cuántos
            # pidieron cómo llegar, cuántos sólo miraron la ficha.
            "contactos_por_tipo": por_tipo,
            "vistas_30d": por_tipo.get("vista", 0),
        }


    # ── suscripciones ────────────────────────────────────────────────────────

    def list_suscripciones(self) -> list[dict]:
        """Todos los comercios activos con su estado de suscripción."""
        from datetime import date, timedelta
        hoy = date.today().isoformat()
        limite_aviso = (date.today() + timedelta(days=5)).isoformat()

        res = (
            self._db.table("comercios")
            .select("id, slug, nombre, whatsapp, verificado, confiable, plan, codigo, suspendido, paga_hasta, created_at")
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

        # Actualizar paga_hasta + desuspender + reactivar (si el job lo había ocultado)
        self._db.table("comercios").update({
            "paga_hasta": nueva_fecha,
            "suspendido": False,
            "activo": True,
        }).eq("id", comercio_id).execute()

        return {"paga_hasta": nueva_fecha}

    def suspender_comercio(self, comercio_id: str) -> None:
        self._db.table("comercios").update({"suspendido": True}).eq("id", comercio_id).execute()

    def activar_comercio(self, comercio_id: str) -> None:
        self._db.table("comercios").update({"suspendido": False, "activo": True}).eq("id", comercio_id).execute()

    def ocultar_comercios_vencidos(self, dias: int = 40, dias_gracia: int | None = None) -> int:
        """Baja automática del mapa. Devuelve cuántos ocultó.

        Dos poblaciones distintas, con relojes distintos:

        1. El que PAGÓ alguna vez y se venció: `paga_hasta` + `dias`.
        2. El que NUNCA pagó (`paga_hasta` NULL, típico del alta de campo):
           `created_at` + `dias_gracia`. Este caso antes no se contemplaba —
           `.lt("paga_hasta", ...)` excluye los NULL en PostgREST — así que el
           comercio cargado en la calle se quedaba en el mapa para siempre y la
           segunda pasada no tenía ninguna consecuencia si no pagaba.

        `dias_gracia=None` desactiva la baja de los que nunca pagaron, que es el
        comportamiento viejo (útil durante la captación inicial).
        """
        from datetime import date, datetime, timedelta, timezone

        hoy = date.today()
        vencidos = (
            self._db.table("comercios")
            .update({"activo": False})
            .lt("paga_hasta", (hoy - timedelta(days=dias)).isoformat())
            .eq("activo", True)
            .execute()
        )
        total = len(vencidos.data or [])

        if dias_gracia is not None:
            corte = datetime.now(timezone.utc) - timedelta(days=dias_gracia)
            nunca_pagaron = (
                self._db.table("comercios")
                .update({"activo": False})
                .is_("paga_hasta", "null")
                .lt("created_at", corte.isoformat())
                .eq("activo", True)
                .execute()
            )
            total += len(nunca_pagaron.data or [])

        return total

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
            .select(_COLS_COMERCIO_ADMIN)
            .eq("activo", True)
        )
        if verificado is not None:
            q = q.eq("verificado", verificado)
        res = q.order("created_at", desc=True).limit(limit).execute()
        filas = res.data or []
        # PostgREST corta en 1000 (PGRST_DB_MAX_ROWS) sin avisar: un `limit(5000)`
        # devuelve mil filas y un 200. Con 888 comercios todavía entra, pero
        # faltan semanas — y el día que pase, el panel mostraría 1000 de 1100 y
        # el catálogo contaría de menos, los dos con cara de estar completos.
        if len(filas) >= 1000 and limit > 1000:
            for inicio in range(1000, min(limit, 100_000), 1000):
                q2 = (self._db.table("comercios").select(_COLS_COMERCIO_ADMIN)
                      .eq("activo", True))
                if verificado is not None:
                    q2 = q2.eq("verificado", verificado)
                lote = (q2.order("created_at", desc=True)
                        .range(inicio, inicio + 999).execute().data) or []
                filas.extend(lote)
                if len(lote) < 1000:
                    break
        return filas

    def list_comercios_por_agente(self, email: str, limit: int = 200) -> list[dict]:
        """Comercios que este agente de campo dio de alta (para que vea su propio recorrido)."""
        res = (
            self._db.table("comercios")
            .select("id, slug, nombre, whatsapp, telefono, modalidad, direccion, lat, lng, "
                    "portada_url, portada_thumb_url, verificado, created_at, lugar_id, puesto, "
                    "rubros!comercios_rubro_id_fkey(nombre, slug), lugares(nombre, tipo, lat, lng, portada_thumb_url)")
            .eq("cargado_por", email)
            .eq("activo", True)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []

    def update_comercio(self, comercio_id: str, patch: dict, rubro_slugs: list[str] | None) -> dict:
        patch = dict(patch)  # copia: no mutamos el dict del caller
        # Si le ponen un NOMBRE real y el slug actual todavía es genérico
        # (comercio / comercio-N), rearmamos el slug desde ese nombre. Los slugs
        # ya "buenos" no se tocan, así no se rompen los links ya compartidos.
        nombre_nuevo = patch.get("nombre")
        if nombre_nuevo and nombre_nuevo.strip() and "slug" not in patch:
            actual = self.get_comercio(comercio_id)
            if actual and _SLUG_GENERICO.match(actual.get("slug") or ""):
                base = slugify(nombre_nuevo)
                if base and base != "comercio":
                    patch["slug"] = slug_unico(self, base)
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

    # ---- lugares (mercados / galerías / paseos: contenedores de puestos) ----
    def crear_lugar(self, row: dict) -> dict:
        res = self._db.table("lugares").insert(row).execute()
        return res.data[0]

    def list_lugares(self, ciudad_id: str | None = None) -> list[dict]:
        # comercios(count): cuántos puestos ya tiene cada lugar (para mostrar el
        # progreso en el selector del alta → "Mercado Central (6)" y poder resumir).
        q = self._db.table("lugares").select("id, nombre, tipo, lat, lng, ciudad_id, portada_url, portada_thumb_url, video_url, poligono, comercios(count)").eq("activo", True)
        if ciudad_id:
            q = q.eq("ciudad_id", ciudad_id)
        return q.order("nombre").execute().data or []

    def get_lugar(self, lugar_id: str) -> dict | None:
        res = self._db.table("lugares").select("*").eq("id", lugar_id).limit(1).execute()
        return res.data[0] if res.data else None

    def update_lugar(self, lugar_id: str, patch: dict) -> dict:
        if patch:
            self._db.table("lugares").update(patch).eq("id", lugar_id).execute()
        return self.get_lugar(lugar_id) or {}

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
        """Los reclamos, con el nombre del comercio cuando hay uno.

        El nombre viene de un select embebido, y eso lo resuelve PostgREST
        leyendo la foreign key de su cache de esquema. Si el cache está viejo
        —lo que pasa cada vez que corre una migración y nadie lo reinicia—, el
        embed falla y se lleva puesto todo el listado.

        Reintenta sin el embed: es preferible mostrar los reclamos sin el nombre
        del comercio a no mostrar ninguno. Un reclamo sin responder es una
        persona esperando.
        """
        def _consulta(select: str):
            q = (self._db.table("reclamos").select(select)
                 .order("created_at", desc=True).limit(500))
            return (q.eq("estado", estado) if estado else q).execute().data or []

        try:
            return _consulta("*, comercios(nombre, slug)")
        except Exception:  # noqa: BLE001
            logger.warning("reclamos.embed_fallo", exc_info=True)
            return _consulta("*")

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
        """Igual que list_reclamos: el embed puede caerse con el cache viejo de
        PostgREST, y una solicitud de cambio de número sin atender deja a un
        comercio sin poder recibir reservas."""
        def _consulta(select: str):
            q = (self._db.table("solicitudes_cambio_numero").select(select)
                 .order("created_at", desc=True).limit(200))
            return (q.eq("estado", estado) if estado else q).execute().data or []

        try:
            return _consulta("*, comercios(nombre, slug, portada_url, whatsapp)")
        except Exception:  # noqa: BLE001
            logger.warning("solicitudes.embed_fallo", exc_info=True)
            return _consulta("*")

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

    # ---- galería (fotos/videos por comercio) ----
    def list_fotos_comercio(self, comercio_id: str) -> list[dict]:
        res = self._db.table("comercio_fotos").select("*").eq("comercio_id", comercio_id).order("orden").execute()
        return res.data or []

    def add_foto_comercio(self, row: dict) -> dict:
        res = self._db.table("comercio_fotos").insert(row).execute()
        return res.data[0] if res.data else {}

    def delete_foto_comercio(self, foto_id: str, comercio_id: str) -> bool:
        res = self._db.table("comercio_fotos").delete().eq("id", foto_id).eq("comercio_id", comercio_id).execute()
        return bool(res.data)

    def count_fotos_comercio(self, comercio_id: str) -> int:
        return len(self.list_fotos_comercio(comercio_id))

    def list_videos_comercio(self, comercio_id: str) -> list[dict]:
        res = self._db.table("comercio_videos").select("*").eq("comercio_id", comercio_id).order("orden").execute()
        return res.data or []

    def add_video_comercio(self, row: dict) -> dict:
        res = self._db.table("comercio_videos").insert(row).execute()
        return res.data[0] if res.data else {}

    def delete_video_comercio(self, video_id: str, comercio_id: str) -> bool:
        res = self._db.table("comercio_videos").delete().eq("id", video_id).eq("comercio_id", comercio_id).execute()
        return bool(res.data)

    def count_videos_comercio(self, comercio_id: str) -> int:
        return len(self.list_videos_comercio(comercio_id))

    # ---- contenido de la home (cotizaciones / clima / videos promocionales) ----
    def list_cotizaciones(self) -> list[dict]:
        res = self._db.table("cotizaciones").select("*").order("orden").execute()
        return res.data or []

    def update_cotizacion(self, clave: str, valor: float) -> dict | None:
        from datetime import datetime, timezone
        res = (
            self._db.table("cotizaciones")
            .update({"valor": valor, "actualizado_en": datetime.now(timezone.utc).isoformat()})
            .eq("clave", clave).execute()
        )
        return res.data[0] if res.data else None

    def get_clima(self) -> dict | None:
        res = self._db.table("clima").select("*").eq("id", 1).limit(1).execute()
        return res.data[0] if res.data else None

    def update_clima(self, patch: dict) -> dict | None:
        from datetime import datetime, timezone
        res = (
            self._db.table("clima")
            .update({**patch, "actualizado_en": datetime.now(timezone.utc).isoformat()})
            .eq("id", 1).execute()
        )
        return res.data[0] if res.data else None

    def list_videos_promo(self, solo_activos: bool = False) -> list[dict]:
        q = self._db.table("videos_promocionales").select("*")
        if solo_activos:
            q = q.eq("activo", True)
        res = q.order("orden").execute()
        return res.data or []

    def add_video_promo(self, row: dict) -> dict:
        res = self._db.table("videos_promocionales").insert(row).execute()
        return res.data[0] if res.data else {}

    def delete_video_promo(self, video_id: str) -> bool:
        res = self._db.table("videos_promocionales").delete().eq("id", video_id).execute()
        return bool(res.data)

    def insert_busqueda(
        self, query: str, resultados: int, comercios: list[str] | None = None
    ) -> str | None:
        """Guarda la búsqueda y devuelve su id, para poder atarle el click que
        venga después. Sin ese puente se sabe qué se mostró y qué se contactó,
        pero no si una cosa llevó a la otra."""
        res = (
            self._db.table("busquedas")
            .insert({"query": query, "resultados": resultados})
            .execute()
        )
        bid = res.data[0]["id"] if res.data else None
        if bid and comercios:
            rows = [
                {"busqueda_id": bid, "comercio_id": cid, "posicion": i}
                for i, cid in enumerate(comercios[:10])
                if cid
            ]
            if rows:
                self._db.table("busqueda_comercios").insert(rows).execute()
        return bid

    def terminos_de_comercio(
        self, comercio_id: str, dias: int = 30, limit: int = 8
    ) -> list[dict]:
        """Términos con los que la gente encontró a este comercio (para 'Mi negocio')."""
        from datetime import datetime, timezone, timedelta
        from collections import Counter

        desde = (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat()
        res = (
            self._db.table("busqueda_comercios")
            .select("busquedas(query, created_at)")
            .eq("comercio_id", comercio_id)
            .limit(2000)
            .execute()
        )
        cont: Counter = Counter()
        for row in res.data or []:
            b = row.get("busquedas") or {}
            if (b.get("created_at") or "") >= desde:
                q = (b.get("query") or "").strip().lower()
                if q:
                    cont[q] += 1
        return [{"query": q, "n": n} for q, n in cont.most_common(limit)]

    def kpis_admin(self) -> dict:
        from collections import Counter
        from datetime import date

        def norm(q: str) -> str:
            return (q or "").strip().lower()

        bus = (self._db.table("busquedas").select("query, resultados").order("created_at", desc=True).limit(1000).execute().data) or []
        top = Counter(norm(b["query"]) for b in bus if norm(b.get("query", "")))
        sin = Counter(norm(b["query"]) for b in bus if norm(b.get("query", "")) and (b.get("resultados") or 0) == 0)

        leads = (self._db.table("leads").select("comercio_id, tipo").order("created_at", desc=True).limit(3000).execute().data) or []
        por_com = Counter(l["comercio_id"] for l in leads if l.get("comercio_id"))
        top_ids = [cid for cid, _ in por_com.most_common(10)]
        coms: dict = {}
        if top_ids:
            cd = (self._db.table("comercios").select("id, nombre, slug").in_("id", top_ids).execute().data) or []
            coms = {c["id"]: c for c in cd}
        top_comercios = [
            {"comercio_id": cid, "nombre": coms.get(cid, {}).get("nombre", "?"), "slug": coms.get(cid, {}).get("slug"), "eventos": n}
            for cid, n in por_com.most_common(10)
        ]

        hoy = date.today().isoformat()
        total = (self._db.table("comercios").select("id", count="exact").eq("activo", True).limit(1).execute().count) or 0
        pagando = (self._db.table("comercios").select("id", count="exact").eq("activo", True).eq("suspendido", False).gte("paga_hasta", hoy).limit(1).execute().count) or 0

        return {
            "top_busquedas": [{"query": q, "n": n} for q, n in top.most_common(15)],
            "sin_resultado": [{"query": q, "n": n} for q, n in sin.most_common(15)],
            "top_comercios": top_comercios,
            "monetizacion": {"comercios_activos": total, "pagando": pagando, "gratis": max(0, total - pagando)},
        }

    def list_redes(self) -> list[dict]:
        res = self._db.table("redes_sociales").select("*").order("orden").execute()
        return res.data or []

    def update_red(self, clave: str, url: str | None) -> dict | None:
        res = self._db.table("redes_sociales").update({"url": url}).eq("clave", clave).execute()
        return res.data[0] if res.data else None


def get_repo() -> Repo:
    return SupabaseRepo()
