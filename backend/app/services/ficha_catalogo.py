"""«Lo que suma» en la ficha del comercio: validación de los datos y catálogo en PDF.

Lo comparten el comerciante (Mi comercio) y el agente (Completar comercio): los
dos cargan lo mismo, así que la regla vive acá y no escrita dos veces.

EL CATÁLOGO ES UN ARCHIVO NUESTRO O UN ENLACE AJENO
===================================================

`comercios.catalogo_url` guarda las dos cosas. Si apunta a
`<fotos_public_base_url>/catalogos/<comercio_id>/<token>.pdf` es un archivo que
guardamos nosotros, y como cualquier archivo nuestro hay que borrarlo cuando se
reemplaza o se quita: si no, el disco crece sin que nadie lo note. Si es un
enlace (Drive, una tienda) no es nuestro y no se toca.

LA CARPETA ES EL ID DEL COMERCIO, NO EL SLUG
============================================

El slug cambia (se rearma al renombrar) y se reutiliza (un comercio dado de baja
libera el suyo). Con el slug como carpeta, un comercio nuevo que heredara un slug
liberado podía apuntar `catalogo_url` al PDF viejo y hacerlo borrar. El id no se
reutiliza nunca.

LA DECISIÓN DE «¿ES NUESTRO?»
=============================

El borrado parte de un texto que el propio comercio puede escribir
(`catalogo_url` se edita a mano). `archivo_propio` es estricto a propósito: sólo
la carpeta de ESE comercio, un único archivo `<hex>.pdf`, sin `..`, y la ruta ya
resuelta tiene que colgar de `fotos_dir/catalogos`.

CARRERAS
========

Un `asyncio.Lock` por comercio envuelve subir y quitar (uvicorn corre un solo
proceso, así que alcanza). Y después de actualizar la base se borra TODO lo que
haya en la carpeta menos el archivo vigente: aunque algo falle a mitad de camino,
la carpeta converge a un solo PDF.
"""
import asyncio
import os
import re
import secrets
import time
import weakref
from collections import defaultdict, deque
from pathlib import Path

import structlog
from fastapi import HTTPException, Request
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.services import enlaces

logger = structlog.get_logger()

MAX_BYTES = 8 * 1024 * 1024
CARPETA = "catalogos"
MAX_PEDIDO_MINIMO = 120
#: Cuánto puede pesar el multipart por encima del archivo (cabeceras, el nombre).
_HOLGURA_MULTIPART = 256 * 1024
_TROZO = 1024 * 1024
#: Subidas de catálogo por comercio por hora. Un catálogo se sube pocas veces;
#: más que eso es un error del cliente o alguien llenando el disco de a 8 MB.
MAX_SUBIDAS_POR_HORA = 10
_VENTANA_SEG = 3600

_ID_OK = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
_ARCHIVO_OK = re.compile(r"[0-9a-f]{8,64}\.pdf")

_MSG_NO_PDF = "El catálogo tiene que ser un PDF."
_MSG_PESADO = "El catálogo puede pesar hasta 8 MB."
_MSG_FALTA = "Falta el archivo del catálogo."
_MSG_MUCHAS = "Subiste muchos catálogos seguidos. Probá de nuevo en un rato."

_ETIQUETA_CANAL = "El enlace del canal de WhatsApp"
_ETIQUETA_CATALOGO = "El enlace del catálogo"
_MSG_CANAL = "El canal tiene que ser un enlace de WhatsApp."


# ── Datos de la ficha ────────────────────────────────────────────────────────
def normalizar_enlace(valor: str | None, etiqueta: str) -> str | None:
    """Un enlace http(s) limpio, o None si vino vacío. ValueError si no sirve.

    Estricto: sin usuario antes del dominio, sin IP escrita a mano, sin hosts
    internos. Es un enlace que se abre tal cual desde la ficha."""
    if valor is None:
        return None
    limpio = str(valor).strip()
    if not limpio:
        return None
    return enlaces.validar_http(limpio, etiqueta, estricto=True)


def _normalizar_catalogo(valor: str | None) -> str | None:
    """Como `normalizar_enlace`, pero el PDF que subimos nosotros se reenvía
    tal cual desde el formulario (Mi comercio manda de vuelta lo que recibió) y
    en desarrollo vive en `localhost`, que el chequeo estricto rechazaría."""
    if valor is not None and str(valor).strip().startswith(settings.fotos_public_base_url.rstrip("/") + "/"):
        return enlaces.validar_http(str(valor).strip(), _ETIQUETA_CATALOGO)
    return normalizar_enlace(valor, _ETIQUETA_CATALOGO)


def _es_de_whatsapp(enlace: str) -> bool:
    """Si el enlace (ya validado) apunta a whatsapp.com, *.whatsapp.com o wa.me."""
    from urllib.parse import urlsplit

    host = (urlsplit(enlace).hostname or "").lower().rstrip(".")
    return host in ("whatsapp.com", "wa.me") or host.endswith(".whatsapp.com")


def normalizar_ficha(patch: dict) -> None:
    """Deja en `patch` (in situ) los datos de «Lo que suma» listos para guardar.

    - Un texto vacío borra el dato (None), no se guarda como "".
    - Los enlaces: sólo http(s). Si no, ValueError con el mensaje en español.
    - El canal, además, tiene que ser de WhatsApp.
    - `pedido_minimo`: hasta 120 caracteres.
    - Un booleano en null no se toca: son columnas not null / con default.
    """
    if "canal_wa_url" in patch:
        canal = normalizar_enlace(patch["canal_wa_url"], _ETIQUETA_CANAL)
        if canal is not None and not _es_de_whatsapp(canal):
            raise ValueError(_MSG_CANAL)
        patch["canal_wa_url"] = canal
    if "catalogo_url" in patch:
        patch["catalogo_url"] = _normalizar_catalogo(patch["catalogo_url"])
    if "pedido_minimo" in patch:
        texto = (patch["pedido_minimo"] or "").strip()
        if len(texto) > MAX_PEDIDO_MINIMO:
            raise ValueError(f"El pedido mínimo puede tener hasta {MAX_PEDIDO_MINIMO} caracteres.")
        patch["pedido_minimo"] = texto or None
    for campo in ("tiene_pasero", "envios_internacionales", "tiene_factura", "talles_especiales"):
        if campo in patch and patch[campo] is None:
            del patch[campo]


# ── Archivos del catálogo ────────────────────────────────────────────────────
def _carpeta_de(comercio_id: str) -> Path:
    return Path(settings.fotos_dir) / CARPETA / comercio_id


def archivo_propio(url: str | None, comercio_id: str | None) -> Path | None:
    """La ruta en disco de un catálogo NUESTRO de este comercio, o None.

    None también para un enlace externo, para el catálogo de otro comercio y
    para cualquier cosa que intente salirse de `fotos_dir/catalogos/<id>/`.
    """
    if not url or not comercio_id or not _ID_OK.fullmatch(comercio_id):
        return None
    base = settings.fotos_public_base_url.rstrip("/") + "/"
    if not url.startswith(base):
        return None
    relativa = url[len(base):]
    if any(c in relativa for c in "?#%\\\x00"):
        return None
    partes = relativa.split("/")
    if len(partes) != 3 or partes[0] != CARPETA or partes[1] != comercio_id:
        return None
    if not _ARCHIVO_OK.fullmatch(partes[2]):
        return None
    try:
        raiz = (Path(settings.fotos_dir) / CARPETA).resolve()
        ruta = (Path(settings.fotos_dir) / relativa).resolve()
    except (OSError, ValueError):
        return None
    # La última palabra: aunque todo lo anterior fallara, lo que no cuelga de
    # fotos_dir/catalogos/ no se toca.
    if not ruta.is_relative_to(raiz) or ruta == raiz:
        return None
    return ruta


def _borrar_si_es_nuestro(url: str | None, comercio_id: str | None) -> int | None:
    """Borra el archivo si `url` es un catálogo nuestro y devuelve cuántos bytes
    pesaba; None si no era nuestro o no se pudo. Un archivo que ya no está no es
    un error: el objetivo era que no esté."""
    ruta = archivo_propio(url, comercio_id)
    if ruta is None:
        return None
    try:
        try:
            tam = ruta.stat().st_size
        except FileNotFoundError:
            return 0
        ruta.unlink(missing_ok=True)
        return tam
    except OSError as exc:
        logger.warning("comercio.catalogo_borrado_fallo", ruta=str(ruta), error=str(exc))
        return None


def _barrer(carpeta: Path, vigente: str | None) -> int:
    """Borra de la carpeta del comercio todo PDF (y temporal) menos `vigente`.
    Devuelve los bytes liberados. Es lo que deja la carpeta en un solo archivo
    pase lo que pase con las subidas anteriores."""
    liberado = 0
    try:
        hijos = list(carpeta.iterdir())
    except OSError:
        return 0
    for p in hijos:
        if p.name == vigente or p.suffix not in (".pdf", ".tmp"):
            continue
        try:
            if p.is_symlink() or p.is_file():
                tam = p.lstat().st_size
                p.unlink()
                liberado += tam
        except OSError as exc:
            logger.warning("comercio.catalogo_barrido_fallo", ruta=str(p), error=str(exc))
    return liberado


def soltar_catalogo_reemplazado(anterior: str | None, nuevo: str | None, comercio_id: str | None) -> None:
    """Si el catálogo cambió (por un enlace nuevo, o vaciado a mano) y el anterior
    era un archivo nuestro, se borra. Lo llaman el PUT del comerciante y el PATCH
    del agente: sin esto el PDF quedaría huérfano en el disco."""
    if anterior and anterior != nuevo:
        _borrar_si_es_nuestro(anterior, comercio_id)


# ── Candado y límite por comercio ────────────────────────────────────────────
#: Un candado por comercio. Débil: cuando nadie lo usa, el dict lo suelta solo
#: (si no, crecería con cada comercio que alguna vez subió algo).
_CANDADOS: "weakref.WeakValueDictionary[str, asyncio.Lock]" = weakref.WeakValueDictionary()
_SUBIDAS: dict[str, deque] = defaultdict(deque)


def _candado(comercio_id: str) -> asyncio.Lock:
    lock = _CANDADOS.get(comercio_id)
    if lock is None:
        lock = _CANDADOS[comercio_id] = asyncio.Lock()
    return lock


def _anotar_intento(comercio_id: str) -> None:
    """Cuenta una subida y corta con 429 a la undécima de la hora. En memoria: se
    reinicia con el servidor, y está bien (frena abuso, no es contabilidad)."""
    ahora = time.monotonic()
    ventana = _SUBIDAS[comercio_id]
    while ventana and ahora - ventana[0] > _VENTANA_SEG:
        ventana.popleft()
    if len(ventana) >= MAX_SUBIDAS_POR_HORA:
        raise HTTPException(status_code=429, detail=_MSG_MUCHAS)
    ventana.append(ahora)


def reiniciar_limites() -> None:
    """Sólo para los tests."""
    _SUBIDAS.clear()


# ── Recibir el PDF ───────────────────────────────────────────────────────────
async def _recibir_pdf(request: Request, carpeta: Path) -> tuple[Path, int]:
    """El PDF del campo multipart `archivo`, escrito POR TROZOS a un temporal en
    la carpeta de destino (así el `os.replace` final es atómico y nunca hay 8 MB
    juntos en memoria). Valida por contenido (`%PDF-`) y corta apenas pasa 8 MB.

    Se lee del `Request` a mano (y no con `File(...)`) para que la
    autenticación corra ANTES de tocar el cuerpo. Encima de esto, el middleware
    `LimiteCuerpoMiddleware` corta cualquier cuerpo que pase el tope de la ruta.
    Devuelve (temporal, bytes). Si falla, no deja el temporal.
    """
    declarado = request.headers.get("content-length", "")
    if declarado.isdigit() and int(declarado) > MAX_BYTES + _HOLGURA_MULTIPART:
        raise HTTPException(status_code=413, detail=_MSG_PESADO)
    try:
        form = await request.form()
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — multipart roto o ausente, o cuerpo cortado
        if request.scope.get("cuerpo_excedido"):
            raise HTTPException(status_code=413, detail=_MSG_PESADO) from exc
        raise HTTPException(status_code=400, detail=_MSG_FALTA) from exc
    tmp = carpeta / f".{secrets.token_hex(8)}.tmp"
    destino = None
    total = 0
    try:
        archivo = form.get("archivo")
        if archivo is None or not hasattr(archivo, "read"):
            raise HTTPException(status_code=400, detail=_MSG_FALTA)
        await run_in_threadpool(carpeta.mkdir, parents=True, exist_ok=True)
        destino = await run_in_threadpool(open, tmp, "wb")
        while True:
            trozo = await archivo.read(_TROZO)
            if not trozo:
                break
            if total == 0 and not trozo.startswith(b"%PDF-"):
                raise HTTPException(status_code=400, detail=_MSG_NO_PDF)
            total += len(trozo)
            if total > MAX_BYTES:
                raise HTTPException(status_code=413, detail=_MSG_PESADO)
            await run_in_threadpool(destino.write, trozo)
        if total == 0:
            raise HTTPException(status_code=400, detail=_MSG_FALTA)
    except BaseException as exc:
        if destino is not None:
            try:
                await run_in_threadpool(destino.close)
            except OSError:
                pass
            destino = None
        await run_in_threadpool(_quitar_temporal, tmp)
        if isinstance(exc, OSError):
            # Disco lleno, sin permiso…: no es culpa de quien sube.
            logger.warning("comercio.catalogo_guardado_fallo", error=str(exc))
            raise HTTPException(status_code=502, detail="No se pudo subir el catálogo, probá de nuevo.") from exc
        raise
    finally:
        if destino is not None:
            await run_in_threadpool(destino.close)
        await form.close()
    return tmp, total


def _quitar_temporal(ruta: Path) -> None:
    try:
        ruta.unlink(missing_ok=True)
    except OSError:
        pass


async def subir_catalogo(repo, comercio: dict, request: Request, actor: str | None = None) -> str:
    """Recibe el PDF, lo deja en `catalogos/<id>/<token>.pdf`, actualiza
    `catalogo_url` y recién ahí borra todo lo demás de la carpeta. Devuelve la
    URL pública.

    El orden importa: si algo falla antes de actualizar la base, el catálogo
    anterior queda como estaba; nunca se borra el viejo sin tener el nuevo.
    """
    cid = comercio["id"]
    if not _ID_OK.fullmatch(str(cid)):
        raise HTTPException(status_code=409, detail="Este comercio no tiene un identificador válido.")
    _anotar_intento(cid)
    carpeta = _carpeta_de(cid)
    async with _candado(cid):
        tmp, total = await _recibir_pdf(request, carpeta)
        nombre = f"{secrets.token_hex(8)}.pdf"
        final = carpeta / nombre
        try:
            await run_in_threadpool(os.replace, tmp, final)
        except OSError as exc:
            await run_in_threadpool(_quitar_temporal, tmp)
            logger.warning("comercio.catalogo_guardado_fallo", comercio=cid, error=str(exc))
            raise HTTPException(status_code=502, detail="No se pudo subir el catálogo, probá de nuevo.") from exc
        url = settings.public_photo_url(f"{CARPETA}/{cid}/{nombre}")
        try:
            await run_in_threadpool(repo.update_comercio, cid, {"catalogo_url": url}, None)
        except Exception:
            # No quedó anotado en la base: el archivo nuevo sería basura.
            await run_in_threadpool(_quitar_temporal, final)
            raise
        liberado = await run_in_threadpool(_barrer, carpeta, nombre)
    logger.info("comercio.catalogo_subido", comercio=cid, bytes=total,
                reemplazo=liberado > 0, bytes_liberados=liberado, actor=actor)
    return url


async def quitar_catalogo(repo, comercio: dict, actor: str | None = None) -> None:
    """Deja `catalogo_url` en null y borra los PDF del comercio. Si era un enlace
    externo sólo se limpia la columna (la carpeta no tiene nada que borrar)."""
    cid = comercio["id"]
    if not _ID_OK.fullmatch(str(cid)):
        raise HTTPException(status_code=409, detail="Este comercio no tiene un identificador válido.")
    async with _candado(cid):
        await run_in_threadpool(repo.update_comercio, cid, {"catalogo_url": None}, None)
        liberado = await run_in_threadpool(_barrer, _carpeta_de(cid), None)
    logger.info("comercio.catalogo_quitado", comercio=cid, archivo_borrado=liberado > 0,
                bytes=liberado, actor=actor)
