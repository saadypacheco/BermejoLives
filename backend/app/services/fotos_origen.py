"""Leer la foto de origen de un comercio (docs/fotos-estilo-uruku.md §8.1).

Es el ÚNICO lugar que lee la foto de la que parte la portada de diseño o el diseño de una foto de galería. Dos
fuentes, en este orden:

1. **El disco local** (`FOTOS_DIR`), con la validación estricta de rutas de siempre. Es lo que pasa en producción.
2. **Sólo si no está en el disco y `FOTOS_LECTURA_REMOTA_BASES` tiene algo**: se descarga por HTTPS. Es el caso de QA,
   que tiene la base de producción (las URLs apuntan a `https://api.uruku.bo/fotos/...`) pero no sus archivos.

LO REMOTO SÓLO LEE
==================
- La URL tiene que empezar EXACTAMENTE con una de las bases del setting (todas `https://`) y pasar la misma
  validación que una ruta local (`ruta_relativa_canonica`): `<carpeta>/<archivo>.jpg`, sin `?`, `#`, `%`, `\\`, NUL,
  `.` ni `..`. La función es pura y la comparten `fotos_galeria._ruta_en_disco` y este módulo, para que las dos
  validaciones no se separen nunca.
- Sin seguir redirecciones (un 3xx da None), timeout corto (3 s de conexión, 10 s en total), sólo se acepta 200, y se
  corta al pasar `MAX_BYTES_FOTO`. El resultado son `bytes`: Pillow los valida después igual que una foto local.
- Nunca se escribe ni se borra nada remoto. Lo que se arma se guarda en el disco local.
- Con el setting vacío (producción) jamás hay red.
"""
from __future__ import annotations

import time
from urllib.parse import urlsplit

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger()

#: Lo máximo que se lee de una foto de origen (disco o red). Igual que el tope de siempre de la portada de diseño.
MAX_BYTES_FOTO = 8 * 1024 * 1024
#: Tiempos de la descarga remota: conexión y total.
TIMEOUT_CONEXION_SEG = 3.0
TIMEOUT_TOTAL_SEG = 10.0

#: Sólo para pruebas: un `httpx.BaseTransport` (p. ej. `httpx.MockTransport`) que reemplaza a la red.
_TRANSPORTE: httpx.BaseTransport | None = None


def ruta_relativa_canonica(url: str | None, base: str, slug: str | None = None) -> str | None:
    """`<carpeta>/<archivo>.jpg` si `url` es una foto en forma canónica bajo `base`; None si no hay que tocarla.

    Pura: no mira el disco ni la red. `base` se normaliza con `/` al final y `url` tiene que empezar exactamente con
    ella (ni `base-evil/...` ni otro host). Se rechaza lo que traiga `?`, `#`, `%`, `\\` o NUL, lo que no sean dos
    tramos, un tramo vacío, `.` o `..`, y lo que no termine en `.jpg`. Con `slug`, además la carpeta tiene que SER
    ese slug (las fotos de un comercio viven en la carpeta de su slug; un comercio renombrado deja las viejas en el
    slug anterior: esas no se tocan)."""
    if not url or not base:
        return None
    base = base.rstrip("/") + "/"
    if not url.startswith(base):
        return None
    relativa = url[len(base):]
    if any(c in relativa for c in "?#%\\\x00"):
        return None
    partes = relativa.split("/")
    if len(partes) != 2 or any(p in ("", ".", "..") for p in partes):
        return None
    if slug is not None and partes[0] != slug:
        return None
    if not partes[1].endswith(".jpg"):
        return None
    return relativa


def bases_remotas() -> list[str]:
    """Las bases `https://` de `FOTOS_LECTURA_REMOTA_BASES` (vacía en producción)."""
    return settings.fotos_lectura_remota_bases_list()


def registrar_arranque() -> None:
    """Al arrancar: avisa en el log qué bases del setting se ignoran (no son `https://` o vienen mal armadas) y cuáles rigen."""
    crudas = [b.strip() for b in (settings.fotos_lectura_remota_bases or "").split(",") if b.strip()]
    validas = {b.rstrip("/") + "/" for b in bases_remotas()}
    for cruda in crudas:
        if cruda.rstrip("/") + "/" not in validas:
            logger.warning("fotos.lectura_remota_base_ignorada",
                           detalle="FOTOS_LECTURA_REMOTA_BASES: sólo se aceptan bases https:// sin parámetros",
                           host=urlsplit(cruda).hostname)
    if validas:
        logger.info("fotos.lectura_remota_activa", hosts=sorted({urlsplit(b).hostname or "" for b in validas}))


def _cliente() -> httpx.Client:
    return httpx.Client(
        timeout=httpx.Timeout(TIMEOUT_TOTAL_SEG, connect=TIMEOUT_CONEXION_SEG),
        follow_redirects=False,
        transport=_TRANSPORTE,
    )


def _log(url: str, resultado: str, nbytes: int = 0) -> None:
    # Sin la URL completa: sólo el host, el resultado y el tamaño.
    logger.info("fotos.lectura_remota", host=urlsplit(url).hostname, resultado=resultado, bytes=nbytes)


def _descargar(url: str) -> bytes | None:
    """Baja `url` (ya validada) con los límites de arriba. None ante cualquier cosa que no sea un 200 chico."""
    inicio = time.monotonic()
    try:
        with _cliente() as cliente, cliente.stream("GET", url) as r:
            if r.status_code != 200:
                _log(url, f"http_{r.status_code}")
                return None
            largo = r.headers.get("content-length")
            if largo and largo.isdigit() and int(largo) > MAX_BYTES_FOTO:
                _log(url, "muy_grande")
                return None
            trozos: list[bytes] = []
            total = 0
            for trozo in r.iter_bytes():
                total += len(trozo)
                if total > MAX_BYTES_FOTO:
                    _log(url, "muy_grande", total)
                    return None
                if time.monotonic() - inicio > TIMEOUT_TOTAL_SEG:
                    _log(url, "timeout", total)
                    return None
                trozos.append(trozo)
        datos = b"".join(trozos)
        _log(url, "ok" if datos else "vacia", len(datos))
        return datos or None
    except httpx.HTTPError as exc:
        _log(url, f"error_{type(exc).__name__}")
        return None
    except Exception as exc:  # noqa: BLE001 - leer la foto nunca puede tumbar el pedido
        _log(url, f"error_{type(exc).__name__}")
        return None


def _leer_local(url: str, slug: str | None) -> bytes | None:
    from app.services import fotos_galeria     # import tardío: fotos_galeria importa este módulo
    ruta = fotos_galeria._ruta_en_disco(url, slug)
    if ruta is None or not ruta.is_file() or ruta.stat().st_size > MAX_BYTES_FOTO:
        return None
    return ruta.read_bytes()


def leer_foto_origen(url: str | None, slug: str | None = None) -> bytes | None:
    """Los bytes de la foto de origen, o None si no hay URL, no es una foto nuestra, no se puede leer o pesa de más.

    Disco local primero (con `slug`, la carpeta tiene que ser ese slug; `leer_portada` llama sin él, porque un comercio
    renombrado deja sus fotos en la carpeta del slug viejo). Si no está, y sólo si hay bases remotas listadas, se
    descarga por HTTPS. Sincrónica (bloquea): quien la llama desde un endpoint async la corre en el threadpool y
    FUERA del lock de `fotos_estilo`. Nunca lanza."""
    if not url:
        return None
    try:
        datos = _leer_local(url, slug)
        if datos is not None:
            return datos
    except Exception:  # noqa: BLE001
        return None
    for base in bases_remotas():
        if ruta_relativa_canonica(url, base, slug) is not None:
            return _descargar(url)
    return None
