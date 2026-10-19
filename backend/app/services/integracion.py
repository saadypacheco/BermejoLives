"""API de integración (sistema de marketing): claves, alcance, idempotencia, ETag y vistas.

Decisión y contrato: docs/integracion-marketing.md. La idea en una línea: un sistema externo puede LEER las
publicaciones de los comercios que el admin de Uruku le asignó y APROBAR/RECHAZAR lo pendiente de esos
comercios; nada más. Un comercio en ese alcance es "gestionado": sus publicaciones nunca se aprueban solas.

Lo que NO sale por esta API, a propósito: teléfonos, `wa_jid`, el crudo de WAHA, el código URUKU-XXXX del
comercio, `verificado`, ni conteos de comercios fuera del alcance.
"""
from __future__ import annotations

import hashlib
import hmac
import io
import json
import re
import secrets
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

import structlog

from app.core.config import settings
from app.core.errores_integracion import IntegracionError

logger = structlog.get_logger()

SCOPES = ("publications:read", "publications:write", "media:write", "broadcast:send")
SISTEMA = "marketing"
VERSION_API = "uruku-integracion-1"
PREFIJO_CLAVE = "uki_"
LIMITE_PEDIDOS_POR_MIN = 60
MAX_IDEM_KEY = 128
MAX_MEDIA_BYTES = 12 * 1024 * 1024
DESTINOS_INTEGRACION = ("facebook", "instagram")
MONEDAS = ("BOB", "USD", "ARS")
TIPOS = ("oferta", "novedad", "video")

_RE_BEARER = re.compile(r"^Bearer uki_([A-Za-z0-9]{6,32})\.([A-Za-z0-9_\-]{16,128})$")
_RE_MEDIA_ID = re.compile(r"^med_[0-9a-f]{32}$")


# ══════════════════════════════════════════════════════════════════════ comercio gestionado

def es_gestionado(repo, comercio_id: str | None) -> bool:
    """¿El comercio está en el alcance de algún cliente de integración?

    FALLA CERRADO: si no se puede saber (la base no contesta, la tabla no existe) se responde True. Para
    quien llama eso significa "tratalo como gestionado" = la publicación queda PENDIENTE para una persona,
    que es siempre el estado seguro (nunca aprobar algo que alguien tenía que mirar)."""
    if not comercio_id:
        return False
    try:
        return bool(repo.es_comercio_gestionado(comercio_id))
    except Exception:  # noqa: BLE001
        logger.error("integracion.gestionado_no_se_pudo_saber", comercio=comercio_id, exc_info=True)
        return True


def es_confiable(repo, comercio: dict | None) -> bool:
    """`confiable` de verdad: un comercio gestionado NUNCA publica directo, aunque tenga la marca."""
    if not comercio or not comercio.get("confiable"):
        return False
    return not es_gestionado(repo, comercio.get("id"))


# ══════════════════════════════════════════════════════════════════════ claves

def hash_secreto(secreto: str) -> str:
    return hashlib.sha256(secreto.encode("utf-8")).hexdigest()


def generar_clave() -> tuple[str, str, str]:
    """(key_id, secreto, clave completa `uki_<key_id>.<secreto>`). El secreto sólo existe acá y en la
    respuesta que se le muestra a quien la emite: en la base queda sha256(secreto)."""
    key_id = secrets.token_hex(6)
    secreto = secrets.token_urlsafe(32)
    return key_id, secreto, f"{PREFIJO_CLAVE}{key_id}.{secreto}"


@dataclass(frozen=True)
class Cliente:
    id: str                 # la clave con la que se autenticó
    grupo_id: str           # el cliente (la rotación deja varias claves en el mismo grupo)
    key_id: str
    nombre: str
    scopes: frozenset[str]


def autenticar(repo, authorization: str | None) -> Cliente:
    """401 `unauthorized` ante cualquier problema con la clave (misma respuesta para clave inexistente,
    secreto equivocado, revocada o inactiva: no se filtra cuál fue)."""
    no_autorizado = IntegracionError(401, "unauthorized", "Clave de integración inválida.")
    m = _RE_BEARER.match((authorization or "").strip())
    if not m:
        raise no_autorizado
    key_id, secreto = m.group(1), m.group(2)
    fila = repo.integracion_cliente_por_key_id(key_id)
    esperado = (fila or {}).get("key_hash") or "0" * 64
    coincide = hmac.compare_digest(hash_secreto(secreto), esperado)     # siempre se compara (tiempo parejo)
    if not fila or not coincide or not fila.get("activo") or fila.get("revocada_at"):
        raise no_autorizado
    _tocar(repo, fila)
    return Cliente(id=fila["id"], grupo_id=fila.get("grupo_id") or fila["id"], key_id=key_id,
                   nombre=fila.get("nombre") or "", scopes=frozenset(fila.get("scopes") or ()))


def _tocar(repo, fila: dict) -> None:
    """`last_used_at`, como mucho una vez por minuto (no una escritura por pedido)."""
    ultimo = fila.get("last_used_at")
    if ultimo:
        try:
            edad = (datetime.now(timezone.utc) - datetime.fromisoformat(str(ultimo).replace("Z", "+00:00"))).total_seconds()
            if edad < 60:
                return
        except ValueError:
            pass
    try:
        repo.integracion_tocar_cliente(fila["id"])
    except Exception:  # noqa: BLE001 - un dato informativo no puede tumbar el pedido
        logger.warning("integracion.last_used_no_guardado", exc_info=True)


# ── rate limit: 60 pedidos por minuto por clave (en memoria: una instancia de API) ─────────────────────
_ventanas: dict[str, deque] = defaultdict(deque)
_candado = threading.Lock()


def limitar(cliente: Cliente, limite: int | None = None) -> None:
    tope = limite or LIMITE_PEDIDOS_POR_MIN
    ahora = time.monotonic()
    with _candado:
        dq = _ventanas[cliente.id]
        while dq and ahora - dq[0] > 60:
            dq.popleft()
        if len(dq) >= tope:
            espera = max(1, int(60 - (ahora - dq[0])) + 1)
            raise IntegracionError(429, "rate_limited", "Demasiados pedidos: esperá un momento.",
                                   headers={"Retry-After": str(espera)})
        dq.append(ahora)


def reiniciar_limites() -> None:
    with _candado:
        _ventanas.clear()


def exigir_scope(cliente: Cliente, scope: str | None) -> None:
    if scope and scope not in cliente.scopes:
        raise IntegracionError(403, "scope_insuficiente", f"Esta clave no tiene el permiso «{scope}».")


# ══════════════════════════════════════════════════════════════════════ idempotencia

def exigir_idempotency_key(valor: str | None) -> str:
    if not valor or len(valor) > MAX_IDEM_KEY or not valor.strip():
        raise IntegracionError(422, "idempotency_key_required", "Falta Idempotency-Key (hasta 128 caracteres).")
    return valor


def hash_de_pedido(metodo: str, ruta: str, cuerpo: bytes) -> str:
    return hashlib.sha256(metodo.encode() + b"\0" + ruta.encode() + b"\0" + cuerpo).hexdigest()


def con_idempotencia(repo, cliente: Cliente, key: str, request_hash: str,
                     ejecutar: Callable[[], tuple[int, dict]]) -> tuple[int, dict]:
    """Misma clave + mismo cuerpo ⇒ la MISMA respuesta (sin volver a aplicar). Misma clave + otro cuerpo ⇒ 422.

    La búsqueda va ANTES de cualquier otra validación del pedido (If-Match, estado, existencia): un reintento
    tras un timeout tiene que recibir la respuesta original, no un 412 porque su propio efecto ya cambió el
    ETag. Sólo se guardan las respuestas exitosas; un error libera la clave para que el reintento ejecute."""
    reclamo = repo.integracion_idem_reclamar(cliente.grupo_id, key, request_hash)
    if not reclamo.get("nuevo"):
        if reclamo.get("request_hash") != request_hash:
            raise IntegracionError(422, "idempotency_key_reused", "Esa Idempotency-Key ya se usó con otro cuerpo.")
        if not reclamo.get("status"):
            raise IntegracionError(409, "idempotency_in_progress",
                                   "Ese pedido todavía se está procesando: reintentá en unos segundos.",
                                   headers={"Retry-After": "2"})
        return int(reclamo["status"]), reclamo.get("response") or {}
    try:
        status, cuerpo = ejecutar()
    except BaseException:
        try:
            repo.integracion_idem_liberar(cliente.grupo_id, key)
        except Exception:  # noqa: BLE001
            logger.warning("integracion.idem_no_liberada", exc_info=True)
        raise
    try:
        repo.integracion_idem_cerrar(cliente.grupo_id, key, status, cuerpo)
    except Exception:  # noqa: BLE001 - se aplicó pero no quedó guardada: el reintento verá el ETag nuevo
        logger.error("integracion.idem_no_guardada", exc_info=True)
    return status, cuerpo


# ══════════════════════════════════════════════════════════════════════ ETag y vistas

def _num(valor: Any) -> str | None:
    if valor is None or valor == "":
        return None
    try:
        return f"{float(valor):.2f}"
    except (TypeError, ValueError):
        return str(valor)


def etag_de(pub: dict) -> str:
    """sha256 de los campos de contenido + estado + activo (entrecomillado, como pide HTTP)."""
    base = json.dumps([
        pub.get("titulo"), pub.get("descripcion"), _num(pub.get("precio")), pub.get("moneda"),
        pub.get("descuento_pct"), str(pub.get("vence_el")) if pub.get("vence_el") else None,
        pub.get("tipo"), pub.get("imagen_url"), pub.get("estado"), bool(pub.get("activo", True)),
    ], ensure_ascii=False, sort_keys=True)
    return '"' + hashlib.sha256(base.encode("utf-8")).hexdigest()[:32] + '"'


def etag_coincide(enviado: str | None, pub: dict) -> bool:
    if not enviado:
        return False
    return enviado.strip().removeprefix("W/") == etag_de(pub)


def exigir_if_match(enviado: str | None, pub: dict) -> None:
    if not enviado:
        raise IntegracionError(428, "if_match_required", "Falta If-Match con el ETag que leíste.")
    if not etag_coincide(enviado, pub):
        raise IntegracionError(412, "etag_mismatch", "La publicación cambió desde que la leíste (la editó el comercio o alguien la moderó).")


def url_publica(slug: str | None) -> str | None:
    if not slug:
        return None
    return f"{settings.sitio_url.rstrip('/')}/comercios/{slug}"


def remitente_de(pub: dict) -> str | None:
    """merchant | third_party | uruku_explorer. Lo guardado por la ingesta manda; para publicaciones viejas
    se deduce de lo que sí se sabe, y si no alcanza queda None (el cliente lo ignora, que es lo seguro)."""
    guardado = pub.get("remitente_rol")
    if guardado:
        return guardado
    if pub.get("origen") == "explorador" or pub.get("identidad_origen") == "explorador":
        return "uruku_explorer"
    if pub.get("origen") == "panel":
        return "merchant"
    if pub.get("identidad_origen") in ("numero", "numero_por_codigo"):
        return "merchant"
    return None


_cache_media: dict[str, tuple[float, dict]] = {}


def _ruta_local(url: str) -> Path | None:
    base = settings.fotos_public_base_url.rstrip("/") + "/"
    if not url.startswith(base):
        return None
    raiz = Path(settings.fotos_dir).resolve()
    candidata = (raiz / url[len(base):]).resolve()
    if raiz not in candidata.parents:        # nada de `..` para salirse del volumen de fotos
        return None
    return candidata if candidata.is_file() else None


def media_de(imagen_url: str | None) -> list[dict]:
    """La foto de la publicación: url, sha256, mime, ancho y alto (de nuestro propio volumen de fotos)."""
    if not imagen_url:
        return []
    mime = "image/png" if imagen_url.lower().endswith(".png") else "image/webp" if imagen_url.lower().endswith(".webp") else "image/jpeg"
    ruta = _ruta_local(imagen_url)
    if ruta is None:
        return [{"url": imagen_url, "sha256": None, "mime": mime, "width": None, "height": None}]
    mtime = ruta.stat().st_mtime
    previo = _cache_media.get(imagen_url)
    if previo and previo[0] == mtime:
        return [previo[1]]
    data = ruta.read_bytes()
    ancho = alto = None
    try:
        from PIL import Image

        with Image.open(io.BytesIO(data)) as img:
            ancho, alto = img.size
    except Exception:  # noqa: BLE001
        pass
    item = {"url": imagen_url, "sha256": hashlib.sha256(data).hexdigest(), "mime": mime, "width": ancho, "height": alto}
    if len(_cache_media) > 2000:
        _cache_media.clear()
    _cache_media[imagen_url] = (mtime, item)
    return [item]


def vista_publicacion(pub: dict, comercio: dict | None) -> dict:
    """Una publicación como la ve la integración. Lista blanca de campos: lo que no está acá no sale."""
    slug = (comercio or {}).get("slug")
    ia = None
    if pub.get("ia_veredicto") or pub.get("terminos_ia"):
        ia = {"veredicto": pub.get("ia_veredicto"),
              "confianza": float(pub["ia_confianza"]) if pub.get("ia_confianza") is not None else None,
              "terminos": pub.get("terminos_ia") or ""}
    return {
        "id": pub["id"],
        "comercio_id": pub.get("comercio_id"),
        "comercio_slug": slug,
        "tipo": pub.get("tipo"),
        "estado": pub.get("estado"),
        "activo": bool(pub.get("activo", True)),
        "titulo": pub.get("titulo"),
        "descripcion": pub.get("descripcion"),
        "precio": float(pub["precio"]) if pub.get("precio") is not None else None,
        "moneda": pub.get("moneda"),
        "descuento_pct": pub.get("descuento_pct"),
        "vence_el": str(pub["vence_el"]) if pub.get("vence_el") else None,
        "media": media_de(pub.get("imagen_url")),
        "origen": pub.get("origen"),
        "identidad_origen": pub.get("identidad_origen"),
        "sender_role": remitente_de(pub),
        "ia": ia,
        "created_at": pub.get("created_at"),
        "updated_at": pub.get("updated_at") or pub.get("created_at"),
        "public_url": url_publica(slug),
        "etag": etag_de(pub),
    }


# ── cursor opaco (updated_at, id) ──────────────────────────────────────────────────────────────────────

def codificar_cursor(pub: dict) -> str:
    import base64

    crudo = json.dumps([str(pub.get("updated_at") or pub.get("created_at") or ""), str(pub["id"])])
    return base64.urlsafe_b64encode(crudo.encode()).decode().rstrip("=")


def decodificar_cursor(cursor: str | None) -> tuple[str, str] | None:
    import base64

    if not cursor:
        return None
    try:
        crudo = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        ts, pid = json.loads(crudo)
        if not isinstance(ts, str) or not isinstance(pid, str) or not ts or not pid:
            raise ValueError
        # sólo caracteres de una fecha ISO y de un uuid: va dentro de un filtro de PostgREST
        if not re.fullmatch(r"[0-9T:.+\-Z ]{10,40}", ts) or not re.fullmatch(r"[0-9a-fA-F\-]{8,40}", pid):
            raise ValueError
        return ts.replace(" ", "T"), pid
    except Exception:  # noqa: BLE001
        raise IntegracionError(422, "validation", "El cursor no es válido.") from None


# ══════════════════════════════════════════════════════════════════════ validación de E5

def validar_enriquecimiento(cuerpo: dict) -> dict:
    """Valida y limpia el PATCH de E5. Devuelve sólo los campos a escribir. Lanza 422 `validation`."""
    if not isinstance(cuerpo, dict) or not cuerpo:
        raise IntegracionError(422, "validation", "El cuerpo tiene que traer al menos un campo.")
    permitidos = {"titulo", "descripcion", "precio", "moneda", "descuento_pct", "vence_el", "tipo"}
    extra = sorted(set(cuerpo) - permitidos)
    if extra:
        raise IntegracionError(422, "validation", f"Campos no permitidos: {', '.join(extra)}.")
    salida: dict[str, Any] = {}
    if "titulo" in cuerpo:
        t = cuerpo["titulo"]
        if t is not None and (not isinstance(t, str) or len(t.strip()) > 120):
            raise IntegracionError(422, "validation", "El título tiene que ser texto de hasta 120 caracteres.")
        salida["titulo"] = t.strip() or None if isinstance(t, str) else None
    if "descripcion" in cuerpo:
        d = cuerpo["descripcion"]
        if d is not None and (not isinstance(d, str) or len(d) > 2000):
            raise IntegracionError(422, "validation", "La descripción tiene que ser texto de hasta 2000 caracteres.")
        salida["descripcion"] = d.strip() or None if isinstance(d, str) else None
    if "precio" in cuerpo:
        p = cuerpo["precio"]
        if p is not None:
            if isinstance(p, bool) or not isinstance(p, (int, float)) or not (0 < p < 10**9):
                raise IntegracionError(422, "validation", "El precio tiene que ser un número mayor a cero.")
            if round(float(p), 2) != float(p):
                raise IntegracionError(422, "validation", "El precio admite hasta 2 decimales.")
        salida["precio"] = p
    if "moneda" in cuerpo:
        if cuerpo["moneda"] not in (*MONEDAS, None):
            raise IntegracionError(422, "validation", f"Moneda inválida (BOB, USD o ARS).")
        salida["moneda"] = cuerpo["moneda"]
    if "descuento_pct" in cuerpo:
        d = cuerpo["descuento_pct"]
        if d is not None and (isinstance(d, bool) or not isinstance(d, int) or not 1 <= d <= 99):
            raise IntegracionError(422, "validation", "El descuento tiene que ser un entero entre 1 y 99.")
        salida["descuento_pct"] = d
    if "vence_el" in cuerpo:
        v = cuerpo["vence_el"]
        if v is not None:
            try:
                date.fromisoformat(v)
            except (TypeError, ValueError):
                raise IntegracionError(422, "validation", "vence_el tiene que ser una fecha AAAA-MM-DD.") from None
        salida["vence_el"] = v
    if "tipo" in cuerpo:
        if cuerpo["tipo"] not in TIPOS:
            raise IntegracionError(422, "validation", "tipo tiene que ser oferta, novedad o video.")
        salida["tipo"] = cuerpo["tipo"]
    return salida


def actor_de(actor: dict | None) -> str:
    """`integracion:<sistema>:<usuario>` para `moderado_por` / `solicitado_por`, saneado."""
    actor = actor if isinstance(actor, dict) else {}
    limpio = lambda x, d: re.sub(r"[^\w@.\-+ ]", "", str(x or d))[:80].strip() or d  # noqa: E731
    return f"integracion:{limpio(actor.get('sistema'), SISTEMA)}:{limpio(actor.get('usuario'), '?')}"


# ══════════════════════════════════════════════════════════════════════ media (E6)

def guardar_media(contenido: bytes) -> dict:
    """Valida y guarda el JPEG del cuadrado. Idempotente por sha256: el mismo archivo da el mismo `media_id`.
    El archivo se guarda TAL CUAL (sin recomprimir): la integración sube la imagen ya lista para Instagram."""
    if not contenido:
        raise IntegracionError(422, "validation", "El archivo está vacío.")
    if len(contenido) > MAX_MEDIA_BYTES:
        raise IntegracionError(413, "media_too_large", "La imagen supera los 12 MB.")
    if not contenido.startswith(b"\xff\xd8"):
        raise IntegracionError(422, "validation", "Sólo se aceptan imágenes JPEG.")
    from PIL import Image

    from app.services.imagenes import _exigir_tamano_razonable, _preparar_pillow

    try:
        _preparar_pillow()
        with Image.open(io.BytesIO(contenido)) as img:
            _exigir_tamano_razonable(img)
            if img.format != "JPEG":
                raise ValueError("no es JPEG")
            ancho, alto = img.size
            img.verify()
    except Exception:  # noqa: BLE001
        raise IntegracionError(422, "validation", "El archivo no es una imagen JPEG válida.") from None
    sha = hashlib.sha256(contenido).hexdigest()
    media_id = f"med_{sha[:32]}"
    sub = f"integracion/{media_id}.jpg"
    destino = Path(settings.fotos_dir) / sub
    if not destino.exists():
        destino.parent.mkdir(parents=True, exist_ok=True)
        tmp = destino.with_suffix(f".tmp{secrets.token_hex(4)}")
        tmp.write_bytes(contenido)
        tmp.replace(destino)
    return {"media_id": media_id, "url": settings.public_photo_url(sub), "sha256": sha, "width": ancho, "height": alto}


def resolver_media(media_id: str | None) -> str | None:
    """La URL pública de un media subido por E6, o None si no existe (o el id no tiene forma de id)."""
    if not media_id or not _RE_MEDIA_ID.match(media_id):
        return None
    sub = f"integracion/{media_id}.jpg"
    if not (Path(settings.fotos_dir) / sub).is_file():
        return None
    return settings.public_photo_url(sub)


# ══════════════════════════════════════════════════════════════════════ ciclo de vida de una clave
# (lo usa `scripts/integracion_clave.py`; el secreto NO pasa por la API HTTP)

def _scopes_validos(scopes: list[str] | None) -> list[str]:
    elegidos = list(dict.fromkeys(scopes or SCOPES))
    malos = [s for s in elegidos if s not in SCOPES]
    if malos:
        raise ValueError(f"scopes inválidos: {', '.join(malos)} (válidos: {', '.join(SCOPES)})")
    return elegidos


def emitir_clave(repo, nombre: str, scopes: list[str] | None = None, por: str = "script") -> dict:
    """Crea un cliente nuevo con su primera clave. Devuelve `{"clave": "uki_…", ...}`: ESA es la única vez que
    existe el secreto (en la base queda sha256)."""
    nombre = (nombre or "").strip()
    if not 1 <= len(nombre) <= 80:
        raise ValueError("el nombre tiene que tener entre 1 y 80 caracteres")
    key_id, secreto, clave = generar_clave()
    cid = str(uuid.uuid4())
    fila = repo.integracion_crear_cliente({
        "id": cid, "grupo_id": cid, "key_id": key_id, "nombre": nombre, "key_hash": hash_secreto(secreto),
        "scopes": _scopes_validos(scopes), "creado_por": por})
    repo.integracion_registrar_evento({"tipo": "clave_emitida", "cliente_id": fila["id"], "actor": por,
                                       "detalle": {"key_id": key_id, "scopes": fila["scopes"]}})
    return {"clave": clave, "key_id": key_id, "cliente_id": fila["id"], "grupo_id": fila["grupo_id"], "scopes": fila["scopes"]}


def _clave_por_key_id(repo, key_id: str) -> dict:
    fila = repo.integracion_cliente_por_key_id(key_id)
    if not fila:
        raise ValueError(f"no existe la clave {key_id!r}")
    return fila


def rotar_clave(repo, key_id: str, por: str = "script") -> dict:
    """Emite una clave NUEVA para el mismo cliente (mismo alcance, mismos scopes). La vieja sigue activa hasta que
    se la revoque con `revocar_clave`: así hay dos válidas durante el cambio y no se corta la integración."""
    vieja = _clave_por_key_id(repo, key_id)
    if not vieja.get("activo") or vieja.get("revocada_at"):
        raise ValueError("esa clave ya está revocada")
    nuevo_key_id, secreto, clave = generar_clave()
    fila = repo.integracion_crear_cliente({
        "id": str(uuid.uuid4()), "grupo_id": vieja.get("grupo_id") or vieja["id"], "key_id": nuevo_key_id,
        "nombre": vieja["nombre"], "key_hash": hash_secreto(secreto), "scopes": vieja["scopes"],
        "rotada_de": vieja["id"], "creado_por": por})
    repo.integracion_registrar_evento({"tipo": "clave_rotada", "cliente_id": fila["id"], "actor": por,
                                       "detalle": {"key_id": nuevo_key_id, "reemplaza": key_id}})
    return {"clave": clave, "key_id": nuevo_key_id, "cliente_id": fila["id"], "grupo_id": fila["grupo_id"],
            "scopes": fila["scopes"], "reemplaza": key_id}


def revocar_clave(repo, key_id: str, por: str = "script") -> dict:
    """Desactiva una clave (baja lógica: queda la fila y `revocada_at`). Los pedidos con ella dan 401 desde ya."""
    fila = _clave_por_key_id(repo, key_id)
    if fila.get("revocada_at"):
        return {"key_id": key_id, "ya_revocada": True}
    repo.integracion_actualizar_cliente(fila["id"], {"activo": False, "revocada_at": datetime.now(timezone.utc).isoformat()})
    repo.integracion_registrar_evento({"tipo": "clave_revocada", "cliente_id": fila["id"], "actor": por,
                                       "detalle": {"key_id": key_id}})
    return {"key_id": key_id, "ya_revocada": False}
