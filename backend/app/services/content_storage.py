"""El disco PRIVADO del contenido para redes (docs/contenido-redes-tecnico.md §4).

POR QUÉ NO ES `fotos_dir`
=========================
`/fotos` es público y se cachea un año: lo que está ahí lo ve cualquiera que tenga la
URL. Las fotos del banco son material de trabajo de comercios (a veces con personas) y los
videos armados todavía no los aprobó nadie. Viven en `CONTENT_DIR`, un volumen aparte, y
se ven sólo con una URL FIRMADA que vence a los 15 minutos (el panel) o con el token de
60 días de la página del comerciante (`/public/pieces/{token}`).

En la base van rutas RELATIVAS (como `wa_inbox.media_path`) y toda lectura pasa por
`safe_path`, que exige que la ruta resuelta quede dentro de `CONTENT_DIR`: un valor
adulterado (`../../etc/passwd`) devuelve None.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import structlog

from app.core.config import settings

logger = structlog.get_logger()

#: Foto de trabajo: lado mayor 2048 px, q85. Un cuadro 9:16 mide 1920 de alto y el zoom
#: suma 6 %: con 1600 px la foto vertical se agranda y pierde nitidez (T-12).
FOTO_LADO = 2048
FOTO_CALIDAD = 85
THUMB_LADO = 400
THUMB_CALIDAD = 74
#: Lado menor mínimo para que una foto entre en un video (se guarda igual).
LADO_MENOR_MINIMO = 720

#: La firma son 43 caracteres base64url (SHA-256 sin el relleno).
_RE_FIRMA = re.compile(r"^[A-Za-z0-9_-]{43}$")

SCOPES = {"piece": {"video", "cover"}, "asset": {"file", "thumb"}}

#: El tamaño de la carpeta se mide recorriéndola: se cachea para no hacerlo en cada subida.
_CACHE_PESO_SEG = 600
_peso_cache: dict[str, tuple[float, int]] = {}


# ──────────────────────────────────────────────────────────── rutas

def raiz() -> Path:
    return Path(settings.content_dir)


def dir_seguro() -> bool:
    """`CONTENT_DIR` no puede quedar dentro de `FOTOS_DIR` (ni al revés): lo que está bajo
    `/fotos` se sirve público. Si no es seguro, el banco y el render se apagan."""
    try:
        c = raiz().resolve()
        f = Path(settings.fotos_dir).resolve()
    except OSError:
        return False
    return not (c == f or f in c.parents or c in f.parents)


def safe_path(rel: str | None) -> Path | None:
    """La ruta absoluta de una ruta relativa, sólo si queda DENTRO de `CONTENT_DIR`."""
    if not rel or "\x00" in rel:
        return None
    try:
        base = raiz().resolve()
        destino = (base / rel).resolve()
        if destino == base or base not in destino.parents:
            logger.warning("content.ruta_fuera_del_directorio", ruta=str(rel)[:120])
            return None
        return destino
    except Exception:  # noqa: BLE001
        return None


def _mes(ahora: datetime | None = None) -> str:
    return (ahora or datetime.now(timezone.utc)).strftime("%Y-%m")


def rutas_de_foto(comercio_id: str, asset_id: str, ahora: datetime | None = None) -> tuple[str, str]:
    """(archivo, miniatura), relativas. Llevan el uuid de la fila: sin datos del comercio
    en el nombre del archivo."""
    base = f"assets/{comercio_id}/{_mes(ahora)}/{asset_id}"
    return f"{base}.jpg", f"{base}_t.jpg"


def carpeta_de_render(piece_id: str, ahora: datetime | None = None) -> str:
    return f"renders/{_mes(ahora)}/{piece_id}"


def carpeta_tmp(piece_id: str) -> Path:
    return raiz() / "tmp" / piece_id


def limpiar_tmp() -> int:
    """Borra `tmp/` entero (renders a medias de un arranque anterior). Devuelve cuántas
    carpetas sacó. Nunca lanza."""
    base = raiz() / "tmp"
    n = 0
    try:
        if not base.is_dir():
            return 0
        for hijo in base.iterdir():
            shutil.rmtree(hijo, ignore_errors=True)
            n += 1
    except OSError:
        logger.warning("content.limpiar_tmp_fallo", exc_info=True)
    return n


# ──────────────────────────────────────────────────── foto del banco

def procesar_foto(data: bytes) -> dict:
    """Valida, reorienta y recomprime una foto del banco: 2048 px / q85 y miniatura de
    400 px. Sin EXIF (la regrabación lo descarta). Lanza ValueError si no es una imagen.

    Devuelve `{foto, thumb, width, height, sha256, bytes}`."""
    from io import BytesIO

    from PIL import Image

    from app.services.imagenes import procesar_imagen

    try:
        grande = procesar_imagen(data, FOTO_LADO, FOTO_CALIDAD)
        chica = procesar_imagen(data, THUMB_LADO, THUMB_CALIDAD)
        with Image.open(BytesIO(grande)) as img:
            ancho, alto = img.size
    except Exception as exc:  # noqa: BLE001
        raise ValueError("El archivo no es una imagen válida") from exc
    return {"foto": grande, "thumb": chica, "width": ancho, "height": alto,
            "sha256": hashlib.sha256(grande).hexdigest(), "bytes": len(grande)}


def guardar(rel: str, data: bytes) -> None:
    """Escribe un archivo bajo `CONTENT_DIR` (crea las carpetas). Lanza OSError."""
    destino = safe_path(rel)
    if destino is None:
        raise OSError(f"ruta fuera del directorio: {rel}")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(data)


def guardar_foto(comercio_id: str, asset_id: str, procesada: dict,
                 ahora: datetime | None = None) -> tuple[str, str]:
    """Guarda la foto de trabajo y su miniatura. Devuelve las dos rutas relativas.
    Si la segunda falla borra la primera: no queda un archivo suelto."""
    rel_foto, rel_thumb = rutas_de_foto(comercio_id, asset_id, ahora)
    guardar(rel_foto, procesada["foto"])
    try:
        guardar(rel_thumb, procesada["thumb"])
    except OSError:
        borrar(rel_foto)
        raise
    return rel_foto, rel_thumb


def borrar(rel: str | None) -> bool:
    """Borra el archivo (sólo si está bajo `CONTENT_DIR`). True si lo había."""
    destino = safe_path(rel)
    if destino is None:
        return False
    try:
        if destino.is_file():
            destino.unlink()
            return True
    except OSError:
        logger.warning("content.borrado_fallo", ruta=rel, exc_info=True)
    return False


def borrar_carpeta_si_vacia(rel: str | None) -> None:
    destino = safe_path(rel)
    if destino is None:
        return
    try:
        destino.rmdir()
    except OSError:
        pass


def esta_en_disco(rel: str | None) -> bool:
    destino = safe_path(rel)
    try:
        return bool(destino and destino.is_file())
    except OSError:
        return False


# ───────────────────────────────────────── resolver fotos de otras fuentes

def ruta_local_publica(url: str | None) -> Path | None:
    """La ruta en el disco de una foto pública (`/fotos/...`) para leerla sin salir a
    internet (misma lógica que `vision._leer_local`, sólo lectura). None si la URL no es
    de nuestra base o el archivo no existe."""
    if not url:
        return None
    base = settings.fotos_public_base_url.rstrip("/")
    if not url.startswith(base + "/"):
        return None
    relativo = url[len(base):].lstrip("/").split("?")[0]
    try:
        raiz_fotos = Path(settings.fotos_dir).resolve()
        destino = (raiz_fotos / relativo).resolve()
        if raiz_fotos not in destino.parents or not destino.is_file():
            return None
        return destino
    except Exception:  # noqa: BLE001
        return None


def resolver_fuente(source_type: str, file_ref: str | None) -> Path | None:
    """De una fila de `content_piece_sources` a la ruta local de la foto."""
    if source_type == "asset":
        destino = safe_path(file_ref)
        return destino if destino is not None and destino.is_file() else None
    return ruta_local_publica(file_ref)


def asset_sirve(a: dict) -> bool:
    """Una foto del banco que puede entrar en un video: activa, autorizada para redes, sin personas sin
    consentimiento y con lado menor >= 720 px."""
    return bool(a.get("activo", True) and a.get("usable_for_social")
                and (not a.get("has_people") or a.get("people_ok"))
                and min(int(a.get("width") or 0), int(a.get("height") or 0)) >= LADO_MENOR_MINIMO)


def lado_menor(path: Path) -> int | None:
    """El lado menor de una imagen leyendo sólo el encabezado (sin decodificar)."""
    from PIL import Image

    try:
        with Image.open(path) as img:
            return min(img.size)
    except Exception:  # noqa: BLE001
        return None


# ───────────────────────────────────────────────────── URLs firmadas

def _clave() -> bytes:
    return hashlib.sha256((settings.jwt_secret + ":content-files").encode()).digest()


def firmar(scope: str, id_: str, kind: str, exp: int) -> str:
    """`base64url(HMAC_SHA256(clave, "scope:id:kind:exp"))` (43 caracteres)."""
    mensaje = f"{scope}:{id_}:{kind}:{exp}".encode()
    digest = hmac.new(_clave(), mensaje, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")[:43]


def ruta_firmada(scope: str, id_: str, kind: str, ttl: int | None = None,
                 ahora: float | None = None) -> str:
    """La ruta RELATIVA que el panel pide al backend; el front le antepone la URL de la API."""
    exp = int((ahora if ahora is not None else time.time()) + (ttl or settings.content_signed_url_ttl_seg))
    return f"/content/files/{scope}/{id_}/{kind}?exp={exp}&sig={firmar(scope, id_, kind, exp)}"


def vence_en(ttl: int | None = None, ahora: float | None = None) -> datetime:
    return datetime.fromtimestamp((ahora if ahora is not None else time.time())
                                  + (ttl or settings.content_signed_url_ttl_seg), tz=timezone.utc)


def verificar(scope: str, id_: str, kind: str, exp: int, sig: str,
              ahora: float | None = None) -> str:
    """`"ok"`, `"vencida"` o `"invalida"`. La firma se compara antes que el vencimiento: una
    firma adulterada nunca dice «vencida»."""
    if scope not in SCOPES or kind not in SCOPES[scope]:
        return "invalida"
    # `compare_digest` revienta con caracteres que no son ASCII: una firma mal formada es inválida, nunca un 500.
    if not _RE_FIRMA.match(sig or "") or not hmac.compare_digest(firmar(scope, id_, kind, exp), sig):
        return "invalida"
    if (ahora if ahora is not None else time.time()) > exp:
        return "vencida"
    return "ok"


# ───────────────────────────────────────────────────────────── disco

def peso_bytes(forzar: bool = False) -> int:
    """Cuánto pesa la carpeta del contenido (cacheado 10 min)."""
    from app.services import peso_fotos

    clave = str(raiz())
    hit = _peso_cache.get(clave)
    if hit and not forzar and time.monotonic() - hit[0] < _CACHE_PESO_SEG:
        return hit[1]
    r = peso_fotos.medir(clave, top=0)
    total = 0
    if r.get("existe"):
        total = (r["imagenes"]["bytes"] + r["videos"]["bytes"] + r["otros"]["bytes"])
    _peso_cache[clave] = (time.monotonic(), total)
    return total


def reiniciar_cache_peso() -> None:
    _peso_cache.clear()


def libre_bytes() -> int:
    """Espacio libre del disco donde vive el contenido (mira el primer ancestro que existe)."""
    p = raiz()
    while not p.exists() and p != p.parent:
        p = p.parent
    try:
        return shutil.disk_usage(p).free
    except OSError:
        return 0


def tope_bytes() -> int:
    return int(settings.content_dir_max_gb * 1024 ** 3)


def estado_disco() -> dict:
    return {"content_bytes": peso_bytes(), "free_bytes": libre_bytes(), "max_bytes": tope_bytes()}


def disco_pausado() -> bool:
    """El render se pausa si queda menos de `CONTENT_MIN_FREE_GB` libres."""
    return libre_bytes() < int(settings.content_min_free_gb * 1024 ** 3)


def hay_lugar(extra: int = 0) -> bool:
    """¿Se puede subir algo más? No si la carpeta llegó a su tope ni si el disco está al límite."""
    return (peso_bytes() + extra <= tope_bytes()) and not disco_pausado()


def nuevo_id() -> str:
    return str(uuid.uuid4())


def asegurar_dir() -> bool:
    try:
        raiz().mkdir(parents=True, exist_ok=True)
        return True
    except OSError:
        return False


def nombre_de_descarga(slug: str | None, fecha: str | None, ext: str = "mp4") -> str:
    """`uruku-<slug>-<fecha>.mp4`, sólo con caracteres seguros para una cabecera."""
    s = re.sub(r"[^a-z0-9-]+", "-", (slug or "pieza").lower()).strip("-")[:60] or "pieza"
    f = re.sub(r"[^0-9-]+", "", fecha or "")[:10]
    return f"uruku-{s}{'-' + f if f else ''}.{ext}"
