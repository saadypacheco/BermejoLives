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
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import structlog

from app.core.config import settings
from app.core.errores_integracion import IntegracionError

logger = structlog.get_logger()

SCOPES = ("publications:read", "publications:write", "media:write", "broadcast:send")
#: Lo que recibe una clave si no se pide otra cosa. `broadcast:send` (mandar a Facebook/Instagram) NO viene por
#: defecto: hay que pedirlo explícitamente al emitir (y además la difusión por la API está apagada por
#: `INTEGRACION_DIFUSION`).
SCOPES_POR_DEFECTO = ("publications:read", "publications:write", "media:write")
SISTEMA = "marketing"
VERSION_API = "uruku-integracion-1"
PREFIJO_CLAVE = "uki_"
LIMITE_PEDIDOS_POR_MIN = 60
MAX_IDEM_KEY = 128
MAX_MEDIA_BYTES = 8 * 1024 * 1024        # el tope de Instagram para una imagen
DESTINOS_INTEGRACION = ("facebook", "instagram")
MONEDAS = ("BOB", "USD", "ARS")
TIPOS = ("oferta", "novedad", "video")

_RE_BEARER = re.compile(r"^Bearer uki_([A-Za-z0-9]{6,32})\.([A-Za-z0-9_\-]{16,128})$")
_RE_MEDIA_ID = re.compile(r"^med_[0-9a-f]{32}$")
_RE_MEDIA_ARCHIVO = re.compile(r"^med_[0-9a-f]{32}\.jpg$")


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
        _fallos_ip.clear()


# ── claves inválidas por IP: frena el adivinar claves (en memoria, una instancia de API) ──────────────────
_fallos_ip: dict[str, deque] = defaultdict(deque)
_MAX_IPS_RECORDADAS = 10_000


def _purgar_fallos(dq: deque, ahora: float) -> None:
    while dq and ahora - dq[0] > 60:
        dq.popleft()


def exigir_ip_sin_exceso_de_fallos(ip: str) -> None:
    """429 si esta IP ya acumuló demasiados 401 en el último minuto (antes de tocar la base)."""
    ahora = time.monotonic()
    with _candado:
        dq = _fallos_ip.get(ip)
        if dq is None:
            return
        _purgar_fallos(dq, ahora)
        if len(dq) >= max(1, settings.integracion_auth_fallos_por_min):
            espera = max(1, int(60 - (ahora - dq[0])) + 1)
            raise IntegracionError(429, "rate_limited", "Demasiados intentos con una clave inválida: esperá un momento.",
                                   headers={"Retry-After": str(espera)})


def registrar_fallo_de_ip(ip: str) -> None:
    ahora = time.monotonic()
    with _candado:
        if ip not in _fallos_ip and len(_fallos_ip) >= _MAX_IPS_RECORDADAS:
            for k in [k for k, dq in _fallos_ip.items() if not dq or ahora - dq[-1] > 60]:
                del _fallos_ip[k]
            if len(_fallos_ip) >= _MAX_IPS_RECORDADAS:
                _fallos_ip.clear()              # bajo ataque masivo: se prefiere olvidar a crecer sin tope
        dq = _fallos_ip[ip]
        _purgar_fallos(dq, ahora)
        dq.append(ahora)


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
    # Quien sólo sabe el código del local (o fue autorizado por el código) NO es el comercio.
    if pub.get("identidad_origen") in ("codigo", "numero_por_codigo"):
        return "third_party"
    if pub.get("identidad_origen") == "numero":
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


# Un teléfono escrito en el texto (el comerciante pone «consultas al 7xxxxxxx»): la API no entrega teléfonos,
# ni siquiera los que vienen adentro de un título o de una descripción. Se tapan grupos de 8 o más dígitos
# (celular boliviano = 8; con 591 = 11), salvo que sigan a una moneda (un precio grande no es un teléfono).
_RE_TELEFONO = re.compile(r"(?<![\w])\+?\d(?:[ .\-()]{0,2}\d){7,}(?![\w])")
_RE_FECHA = re.compile(r"\d{1,4}[-./]\d{1,2}[-./]\d{1,4}")
_RE_MONEDA_ANTES = re.compile(r"(?:bs\.?|bob|\$|us\$|usd|ars|u\$s)\s*$", re.IGNORECASE)


def enmascarar_telefonos(texto: str | None) -> str | None:
    if not texto:
        return texto

    def tapar(m: re.Match) -> str:
        if _RE_FECHA.fullmatch(m.group(0)) or _RE_MONEDA_ANTES.search(texto[max(0, m.start() - 6):m.start()]):
            return m.group(0)
        return "[teléfono]" if sum(c.isdigit() for c in m.group(0)) >= 8 else m.group(0)

    return _RE_TELEFONO.sub(tapar, texto)


def requiere_moderacion_de_uruku(pub: dict) -> bool:
    """¿Esta publicación sólo la puede aprobar el equipo de Uruku desde su panel (nunca la integración)?

    Sí cuando: quien la mandó no es el comercio (`remitente_rol` != merchant: sólo sabía el código, otro
    participante del grupo, el explorador), entró por un camino que Uruku siempre mira a mano
    (`revision_ia._ORIGENES_SIEMPRE_HUMANOS`: explorador, código…) o la revisión automática la marcó para
    rechazar. Lo que no se puede saber (sin `remitente_rol` deducible) se trata como «sí»."""
    from app.services.revision_ia import _ORIGENES_SIEMPRE_HUMANOS

    if remitente_de(pub) != "merchant":
        return True
    if pub.get("origen") in _ORIGENES_SIEMPRE_HUMANOS or pub.get("identidad_origen") in _ORIGENES_SIEMPRE_HUMANOS:
        return True
    return pub.get("ia_veredicto") == "rechazar"


def solicitada_por_integracion(fila: dict) -> bool:
    """¿Esta fila de `difusion_cola` la pidió la integración (E7)? Lo dice `solicitado_por` (`integracion:…`)."""
    return str(fila.get("solicitado_por") or "").startswith("integracion:")


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
        "titulo": enmascarar_telefonos(pub.get("titulo")),
        "descripcion": enmascarar_telefonos(pub.get("descripcion")),
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

def quitar_metadatos_jpeg(contenido: bytes) -> bytes:
    """Saca los segmentos APP1 (EXIF y XMP: GPS, modelo del celular, fecha), APP13 (Photoshop/IPTC) y los
    comentarios (COM) SIN recomprimir: los datos de la imagen (todo desde SOS) pasan byte a byte. Se conserva
    APP0 (JFIF), APP2 (perfil de color) y APP14 (Adobe), que cambian cómo se ve la imagen. Lanza ValueError si
    la estructura no es la de un JPEG."""
    if not contenido.startswith(b"\xff\xd8"):
        raise ValueError("no es JPEG")
    salida = bytearray(b"\xff\xd8")
    i, n = 2, len(contenido)
    while i < n:
        if contenido[i] != 0xFF:
            raise ValueError("marcador esperado")
        while i < n and contenido[i] == 0xFF:        # relleno 0xFF antes del código
            i += 1
        if i >= n:
            raise ValueError("JPEG cortado")
        marca = contenido[i]
        i += 1
        if marca == 0xDA:                             # SOS: de acá hasta el final son datos de la imagen
            # El encabezado de SOS lleva largo propio; todo lo que sigue se copia tal cual.
            salida += b"\xff\xda" + contenido[i:]
            return bytes(salida)
        if marca == 0xD9:                             # EOI antes de SOS: no hay imagen
            raise ValueError("JPEG sin datos")
        if marca == 0x01 or 0xD0 <= marca <= 0xD8 or marca == 0x00:   # sin largo
            salida += bytes([0xFF, marca])
            continue
        if i + 2 > n:
            raise ValueError("JPEG cortado")
        largo = int.from_bytes(contenido[i:i + 2], "big")
        if largo < 2 or i + largo > n:
            raise ValueError("segmento inválido")
        if marca not in (0xE1, 0xED, 0xFE):           # APP1, APP13, COM: se descartan
            salida += bytes([0xFF, marca]) + contenido[i:i + largo]
        i += largo
    raise ValueError("JPEG sin datos")


def _verificar_cuota_media(repo, cliente: Cliente, nuevos_bytes: int) -> None:
    """Cuota diaria (ventana de 24 h) de subidas NUEVAS por cliente: archivos y bytes. Si no se puede medir se
    rechaza (503): sin tope no se escribe al disco."""
    desde = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat().replace("+00:00", "Z")   # sin '+' en la URL
    try:
        archivos, usados = repo.integracion_uso_media(cliente.grupo_id, desde)
    except Exception:  # noqa: BLE001
        logger.error("integracion.cuota_media_no_se_pudo_medir", exc_info=True)
        raise IntegracionError(503, "cuota_no_verificable",
                               "No pudimos comprobar la cuota de imágenes: reintentá en un momento.") from None
    if archivos + 1 > settings.integracion_media_cuota_archivos_dia:
        raise IntegracionError(429, "media_quota_exceeded",
                               "Llegaste al máximo de imágenes nuevas por día.", headers={"Retry-After": "3600"})
    if usados + nuevos_bytes > settings.integracion_media_cuota_bytes_dia:
        raise IntegracionError(429, "media_quota_exceeded",
                               "Llegaste al máximo de megabytes de imágenes por día.", headers={"Retry-After": "3600"})


def guardar_media(contenido: bytes, repo=None, cliente: Cliente | None = None) -> dict:
    """Valida y guarda el JPEG del cuadrado. Idempotente: el mismo contenido da el mismo `media_id`.

    Se guarda SIN recomprimir pero SIN metadatos (EXIF/XMP/IPTC/comentarios: ubicación y datos del equipo del
    que sacó la foto no tienen por qué quedar en un archivo público). El `media_id` y el `sha256` son los del
    archivo ya limpio. Con `repo` y `cliente` se aplica la cuota diaria del cliente (sólo a archivos nuevos)."""
    if not contenido:
        raise IntegracionError(422, "validation", "El archivo está vacío.")
    if len(contenido) > MAX_MEDIA_BYTES:
        raise IntegracionError(413, "media_too_large", "La imagen supera los 8 MB (el máximo de Instagram).")
    if not contenido.startswith(b"\xff\xd8"):
        raise IntegracionError(422, "validation", "Sólo se aceptan imágenes JPEG.")
    from PIL import Image

    from app.services.imagenes import _exigir_tamano_razonable, _preparar_pillow

    try:
        contenido = quitar_metadatos_jpeg(contenido)
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
    if destino.exists():
        try:
            destino.touch()          # lo vuelven a usar: se renueva su plazo antes de la limpieza
        except OSError:
            pass
    else:
        if repo is not None and cliente is not None:
            _verificar_cuota_media(repo, cliente, len(contenido))
        destino.parent.mkdir(parents=True, exist_ok=True)
        tmp = destino.with_suffix(f".tmp{secrets.token_hex(4)}")
        tmp.write_bytes(contenido)
        tmp.replace(destino)
        if repo is not None and cliente is not None:
            repo.integracion_registrar_evento({
                "tipo": "media_subida", "cliente_id": cliente.id, "actor": f"integracion:{cliente.key_id}",
                "detalle": {"grupo_id": cliente.grupo_id, "media_id": media_id, "bytes": len(contenido)}})
    return {"media_id": media_id, "url": settings.public_photo_url(sub), "sha256": sha, "width": ancho, "height": alto}


def limpiar_media_huerfana(repo, dias: int | None = None, ahora: float | None = None) -> int:
    """Borra del disco los `med_*.jpg` subidos por E6 que NINGUNA fila de `difusion_cola` usa y que tienen más de
    `dias` días (por defecto `INTEGRACION_MEDIA_HUERFANA_DIAS`). Devuelve cuántos borró. Si no se puede saber qué
    está en uso no se borra nada."""
    dias = settings.integracion_media_huerfana_dias if dias is None else dias
    carpeta = Path(settings.fotos_dir) / "integracion"
    if not carpeta.is_dir():
        return 0
    corte = (time.time() if ahora is None else ahora) - max(0, dias) * 86400
    viejos = [f for f in carpeta.iterdir() if _RE_MEDIA_ARCHIVO.match(f.name) and f.is_file()
              and f.stat().st_mtime < corte]
    if not viejos:
        return 0
    try:
        en_uso = {u for u in repo.difusion_imagenes_en_uso() if u}
    except Exception:  # noqa: BLE001
        logger.warning("integracion.limpieza_media_no_se_pudo_saber", exc_info=True)
        return 0
    borrados = 0
    for f in viejos:
        if settings.public_photo_url(f"integracion/{f.name}") in en_uso:
            continue
        try:
            f.unlink()
            borrados += 1
        except OSError:
            logger.warning("integracion.media_no_borrada", archivo=f.name, exc_info=True)
    if borrados:
        logger.info("integracion.media_huerfana_borrada", n=borrados, dias=dias)
    return borrados


def mantenimiento_diario(repo) -> dict:
    """Lo que la integración limpia una vez por día: la caché de idempotencia vencida (7 días) y las imágenes
    de E6 sin uso. Nunca lanza (cada paso falla por separado). Lo llama su propio loop diario de
    `main.py` (`_integracion_mantenimiento_loop`)."""
    res = {"idempotencia": 0, "media": 0}
    try:
        res["idempotencia"] = int(repo.integracion_idem_purgar() or 0)
    except Exception:  # noqa: BLE001
        logger.warning("integracion.purga_idempotencia_fallo", exc_info=True)
    try:
        res["media"] = limpiar_media_huerfana(repo)
    except Exception:  # noqa: BLE001
        logger.warning("integracion.limpieza_media_fallo", exc_info=True)
    if res["idempotencia"] or res["media"]:
        logger.info("integracion.mantenimiento", **res)
    return res


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
    elegidos = list(dict.fromkeys(scopes or SCOPES_POR_DEFECTO))
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
