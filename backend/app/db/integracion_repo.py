"""Acceso a la base de la API de integración (docs/integracion-marketing.md).

Es un mixin de `SupabaseRepo` (el mismo cliente service_role de `db/repository.py`): vive aparte porque
`repository.py` ya tiene casi 4.000 líneas. Los métodos están declarados también en el Protocol `Repo`
y tienen su doble en `tests/conftest.py` (FakeRepo).

Reglas que se cumplen acá:
  - Nunca `select("*")` sobre `comercios` ni sobre las tablas nuevas: columnas explícitas.
  - Las tablas `integracion_*` no tienen acceso para anon: sólo este cliente (service_role) las toca.
  - Baja lógica (`activo`), nunca DELETE físico (salvo la caché de idempotencia, que vence a los 7 días).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog

logger = structlog.get_logger()

#: Lo que la API de integración puede leer de una publicación. NO incluye `raw`, `wa_message_id`,
#: `contacto_whatsapp`, `moderado_*`, `codigo_recibido`: nada que identifique a una persona.
COLUMNAS_PUBLICACION = (
    "id, comercio_id, tipo, titulo, descripcion, precio, moneda, descuento_pct, vence_el, imagen_url, "
    "estado, activo, origen, identidad_origen, remitente_rol, terminos_ia, ia_veredicto, ia_confianza, "
    "created_at, updated_at, approved_at"
)
COLUMNAS_COMERCIO_INTEGRACION = "id, slug, nombre, ciudad_id, plan, activo"
COLUMNAS_CLIENTE = "id, grupo_id, key_id, nombre, scopes, activo, created_at, last_used_at, rotada_de, revocada_at, creado_por"
COLUMNAS_DIFUSION = ("id, publicacion_id, destino, estado, intentos, motivo, url_publicada, created_at, enviado_at, "
                     "texto_override, imagen_url_override, solicitado_por, external_post_id, ig_container_id, "
                     "permalink, verificado_at")

#: Tiempo después del cual una reclamación de idempotencia "en curso" se considera abandonada.
IDEM_EN_CURSO_SEG = 120
IDEM_TTL_DIAS = 7


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


class IntegracionRepoMixin:
    _db: object

    # ── claves y clientes ────────────────────────────────────────────────────────────────────────────────
    def integracion_cliente_por_key_id(self, key_id: str) -> dict | None:
        """La clave (con su hash) por `key_id`. Es lo único que lee el hash."""
        res = (self._db.table("integracion_clientes")
               .select(COLUMNAS_CLIENTE + ", key_hash").eq("key_id", key_id).limit(1).execute())
        return res.data[0] if res.data else None

    def integracion_get_cliente(self, cliente_id: str) -> dict | None:
        res = self._db.table("integracion_clientes").select(COLUMNAS_CLIENTE).eq("id", cliente_id).limit(1).execute()
        return res.data[0] if res.data else None

    def integracion_listar_clientes(self) -> list[dict]:
        return (self._db.table("integracion_clientes").select(COLUMNAS_CLIENTE)
                .order("created_at").order("id").limit(500).execute().data) or []

    def integracion_crear_cliente(self, row: dict) -> dict:
        res = self._db.table("integracion_clientes").insert(row).execute()
        return res.data[0] if res.data else {}

    def integracion_actualizar_cliente(self, cliente_id: str, patch: dict) -> dict:
        res = self._db.table("integracion_clientes").update(patch).eq("id", cliente_id).execute()
        return res.data[0] if res.data else {}

    def integracion_tocar_cliente(self, cliente_id: str) -> None:
        self._db.table("integracion_clientes").update({"last_used_at": _iso(_ahora())}).eq("id", cliente_id).execute()

    # ── alcance (qué comercios) ──────────────────────────────────────────────────────────────────────────
    def es_comercio_gestionado(self, comercio_id: str) -> bool:
        """¿Está el comercio en el alcance (activo) de un cliente de integración que TODAVÍA tiene una clave activa?

        Un cliente sin ninguna clave activa (todas revocadas) ya no gestiona nada: sus comercios vuelven a su flujo
        de siempre en vez de quedar pendientes para siempre esperando a alguien que ya no puede aprobar."""
        res = (self._db.table("integracion_comercios").select("cliente_id")
               .eq("comercio_id", comercio_id).eq("activo", True).execute())
        grupos = sorted({f["cliente_id"] for f in (res.data or [])})
        if not grupos:
            return False
        claves = (self._db.table("integracion_clientes").select("id")
                  .in_("grupo_id", grupos).eq("activo", True).is_("revocada_at", "null").limit(1).execute())
        return bool(claves.data)

    def integracion_comercios_de(self, grupo_id: str, solo_activos: bool = True) -> list[dict]:
        def filtrar(q):
            q = q.eq("cliente_id", grupo_id)
            return q.eq("activo", True) if solo_activos else q

        return self._traer_todo("integracion_comercios", "cliente_id, comercio_id, desde, activo, agregado_por",
                                "comercio_id", filtrar=filtrar)

    def integracion_set_comercio(self, grupo_id: str, comercio_id: str, activo: bool, por: str | None) -> dict:
        fila = {"cliente_id": grupo_id, "comercio_id": comercio_id, "activo": activo,
                "agregado_por": por, "updated_at": _iso(_ahora())}
        if activo:
            fila["desde"] = _iso(_ahora())
        res = self._db.table("integracion_comercios").upsert(fila, on_conflict="cliente_id,comercio_id").execute()
        return res.data[0] if res.data else {}

    def integracion_comercios_verificados(self) -> list[dict]:
        """Comercios activos y verificados (id, slug, nombre): sólo para armar el alcance desde el admin."""
        return self._traer_todo("comercios", "id, slug, nombre", "id",
                                filtrar=lambda q: q.eq("activo", True).eq("verificado", True))

    def integracion_info_comercios(self, comercio_ids: list[str]) -> list[dict]:
        """Lo que E2 muestra de cada comercio. Columnas explícitas: nada de `codigo` ni `verificado`."""
        if not comercio_ids:
            return []
        filas: list[dict] = []
        for i in range(0, len(comercio_ids), 100):
            lote = comercio_ids[i:i + 100]
            filas.extend((self._db.table("comercios").select(COLUMNAS_COMERCIO_INTEGRACION)
                          .in_("id", lote).execute().data) or [])
        ciudades = {c["id"]: c.get("nombre") for c in
                    ((self._db.table("ciudades").select("id, nombre").execute().data) or [])}
        atados: set[str] = set()
        for i in range(0, len(comercio_ids), 100):
            lote = comercio_ids[i:i + 100]
            for g in (self._db.table("comercio_wa_grupos").select("comercio_id").in_("comercio_id", lote).execute().data) or []:
                atados.add(g["comercio_id"])
        return [{**f, "ciudad": ciudades.get(f.get("ciudad_id")), "grupo_atado": f["id"] in atados} for f in filas]

    def integracion_registrar_evento(self, row: dict) -> None:
        try:
            self._db.table("integracion_eventos").insert(row).execute()
        except Exception:  # noqa: BLE001 - la auditoría no puede tumbar la operación; queda en el log
            logger.error("integracion.evento_no_guardado", tipo=row.get("tipo"), exc_info=True)

    # ── idempotencia ─────────────────────────────────────────────────────────────────────────────────────
    def integracion_idem_reclamar(self, grupo_id: str, key: str, request_hash: str) -> dict:
        """Reclama (cliente, key). Devuelve {"nuevo": True} si es la primera vez, o la fila existente.

        Una fila vencida (7 días) o "en curso" abandonada (> 2 min sin cerrarse: el proceso murió) se
        retoma. El insert contra la clave primaria es lo que resuelve la carrera entre dos pedidos iguales."""
        ahora = _ahora()
        for _ in range(3):
            try:
                self._db.table("integracion_idempotencia").insert({
                    "cliente_id": grupo_id, "key": key, "request_hash": request_hash, "status": 0,
                    "created_at": _iso(ahora)}).execute()
                return {"nuevo": True}
            except Exception as exc:  # noqa: BLE001 - violación de la clave primaria
                if "23505" not in str(exc) and "duplicate" not in str(exc).lower():
                    raise
            res = (self._db.table("integracion_idempotencia").select("request_hash, status, response, created_at")
                   .eq("cliente_id", grupo_id).eq("key", key).limit(1).execute())
            if not res.data:
                continue                       # la liberaron entre el insert y la lectura: se reintenta
            fila = res.data[0]
            creada = datetime.fromisoformat(str(fila["created_at"]).replace("Z", "+00:00"))
            vencida = ahora - creada > timedelta(days=IDEM_TTL_DIAS)
            abandonada = fila["status"] == 0 and (ahora - creada).total_seconds() > IDEM_EN_CURSO_SEG
            if vencida or abandonada:
                self.integracion_idem_liberar(grupo_id, key)
                continue
            return {"nuevo": False, **fila}
        return {"nuevo": False, "request_hash": request_hash, "status": 0, "response": None,
                "created_at": _iso(ahora)}

    def integracion_idem_cerrar(self, grupo_id: str, key: str, status: int, response: dict | None) -> None:
        (self._db.table("integracion_idempotencia").update({"status": status, "response": response})
         .eq("cliente_id", grupo_id).eq("key", key).execute())

    def integracion_idem_liberar(self, grupo_id: str, key: str) -> None:
        (self._db.table("integracion_idempotencia").delete().eq("cliente_id", grupo_id).eq("key", key).execute())

    def integracion_idem_purgar(self) -> int:
        """Borra lo que pasó de 7 días (caché con TTL, no dato de negocio)."""
        corte = _iso(_ahora() - timedelta(days=IDEM_TTL_DIAS))
        res = self._db.table("integracion_idempotencia").delete().lt("created_at", corte).execute()
        return len(res.data or [])

    # ── publicaciones ────────────────────────────────────────────────────────────────────────────────────
    def integracion_listar_publicaciones(self, comercio_ids: list[str], cursor: tuple[str, str] | None,
                                         limite: int, estado: str | None, activo: str = "true") -> list[dict]:
        """Cambios desde el cursor `(updated_at, id)`, sólo de esos comercios, en orden estable.
        `activo`: "true" (por defecto, sólo las vigentes), "false" (sólo las dadas de baja) o "all"."""
        if not comercio_ids:
            return []
        q = (self._db.table("publicaciones").select(COLUMNAS_PUBLICACION).in_("comercio_id", comercio_ids))
        if activo in ("true", "false"):
            q = q.eq("activo", activo == "true")
        if estado:
            q = q.eq("estado", estado)
        if cursor:
            ts, pid = cursor[0].replace("+00:00", "Z"), cursor[1]     # sin '+', que en una URL es un espacio
            q = q.or_(f"updated_at.gt.{ts},and(updated_at.eq.{ts},id.gt.{pid})")
        return (q.order("updated_at").order("id").limit(limite).execute().data) or []

    def integracion_get_publicacion(self, pub_id: str) -> dict | None:
        res = (self._db.table("publicaciones").select(COLUMNAS_PUBLICACION).eq("id", pub_id).limit(1).execute())
        return res.data[0] if res.data else None

    def integracion_actualizar_publicacion_si(self, pub_id: str, patch: dict, condiciones: dict) -> dict | None:
        """UPDATE condicional (control optimista): sólo si TODAS las `condiciones` siguen valiendo
        (p. ej. `estado='pendiente'` y `updated_at` = el que se leyó). None si no aplicó."""
        q = self._db.table("publicaciones").update(patch).eq("id", pub_id)
        for col, val in condiciones.items():
            if isinstance(val, str) and val.endswith("+00:00"):
                val = val[:-6] + "Z"           # un '+' sin escapar en una URL es un espacio
            q = q.eq(col, val)
        res = q.execute()
        return res.data[0] if res.data else None

    def integracion_origen_de_publicacion(self, pub_id: str) -> dict | None:
        """Quién mandó una publicación que entró por WhatsApp: `{remitente_rol, identidad_origen, origen, phone}`.
        `phone` es el número del remitente guardado en la bandeja (`wa_inbox`); None si no hay (panel, importada…).
        Lo usa la ingesta para decidir si dos mensajes son del MISMO remitente (fusión foto + texto)."""
        res = (self._db.table("publicaciones").select("wa_message_id, remitente_rol, identidad_origen, origen")
               .eq("id", pub_id).limit(1).execute())
        if not res.data:
            return None
        fila = res.data[0]
        phone = None
        if fila.get("wa_message_id"):
            ib = (self._db.table("wa_inbox").select("phone").eq("wa_message_id", fila["wa_message_id"])
                  .limit(1).execute())
            phone = (ib.data[0].get("phone") if ib.data else None) or None
        return {"remitente_rol": fila.get("remitente_rol"), "identidad_origen": fila.get("identidad_origen"),
                "origen": fila.get("origen"), "phone": phone}

    # ── media (E6) ───────────────────────────────────────────────────────────────────────────────────────
    def integracion_uso_media(self, grupo_id: str, desde: str) -> tuple[int, int]:
        """(archivos nuevos, bytes) que ese cliente subió por E6 desde `desde` (auditoría `media_subida`)."""
        filas = self._traer_todo(
            "integracion_eventos", "id, detalle", "id",
            filtrar=lambda q: q.eq("tipo", "media_subida").eq("detalle->>grupo_id", grupo_id).gte("created_at", desde))
        return len(filas), sum(int((f.get("detalle") or {}).get("bytes") or 0) for f in filas)

    def difusion_imagenes_en_uso(self) -> set[str]:
        """Las URLs de imagen que alguna fila de `difusion_cola` tiene como `imagen_url_override` (E6)."""
        filas = self._traer_todo("difusion_cola", "id, imagen_url_override", "id",
                                 filtrar=lambda q: q.not_.is_("imagen_url_override", "null"))
        return {f["imagen_url_override"] for f in filas if f.get("imagen_url_override")}

    # ── difusión ─────────────────────────────────────────────────────────────────────────────────────────
    def difusion_de_publicacion(self, publicacion_id: str) -> list[dict]:
        return (self._db.table("difusion_cola").select(COLUMNAS_DIFUSION)
                .eq("publicacion_id", publicacion_id).order("created_at").order("destino").execute().data) or []

    def get_difusion_fila(self, fila_id: str) -> dict | None:
        res = self._db.table("difusion_cola").select(COLUMNAS_DIFUSION).eq("id", fila_id).limit(1).execute()
        return res.data[0] if res.data else None

    def reclamar_difusion(self, fila_id: str, desde: str = "pendiente") -> bool:
        """Pasa la fila de `desde` a `incierto` SI sigue en `desde` (un solo proceso gana). Es la anotación
        previa al envío: si el proceso muere a mitad de la llamada a Meta, la fila queda `incierto`, que es
        lo que de verdad se sabe."""
        res = (self._db.table("difusion_cola").update({"estado": "incierto"})
               .eq("id", fila_id).eq("estado", desde).execute())
        return bool(res.data)

    def actualizar_difusion(self, fila_id: str, patch: dict) -> None:
        self._db.table("difusion_cola").update(patch).eq("id", fila_id).execute()
