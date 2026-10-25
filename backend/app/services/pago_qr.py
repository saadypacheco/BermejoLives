"""QR de cobro de URUKU: vive como ARCHIVO en el servidor, no en la base.

Decisión (docs/cobro-mensual.md, T7): el QR NO se cambia desde el panel. Cambiar
el QR es cambiar la cuenta donde entra la plata de todos los comercios; si se
pudiera subir desde el admin, una cuenta de admin robada redirigiría los cobros.
Se cambia copiando el archivo al VPS (scp) y el backend lo lee del disco.

Este módulo solo LEE: valida que la ruta configurada sea un archivo normal dentro
de su directorio, que sea una imagen válida y de tamaño razonable, la
re-codifica a PNG sin metadatos (EXIF) y calcula una huella para cache y para
detectar cambios. Sin QR configurado no se muestra nada.
"""
from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import structlog
from PIL import Image

from app.core.config import settings

logger = structlog.get_logger()

# Un QR de banco pesa decenas de KB; 5 MB de archivo y 4000x4000 px sobran y
# frenan una "bomba de descompresión" subida por error.
MAX_BYTES = 5 * 1024 * 1024
MAX_LADO_PX = 4000
EXTENSIONES = {".png", ".jpg", ".jpeg"}


@dataclass(frozen=True)
class QrCargado:
    png: bytes
    huella: str          # sha256 del archivo original, 12 caracteres
    actualizado: str     # iso, mtime del archivo


# Cache en memoria: se re-codifica sólo si el archivo cambió (ruta + mtime + tamaño).
_cache: dict[tuple, QrCargado | None] = {}
# Huella con la que arrancó el proceso (o la primera vista); un cambio dispara aviso.
_huella_base: str | None = None
_cambio_avisado: set[str] = set()


def _ruta_segura(ruta_cfg: str) -> Path | None:
    """Devuelve la ruta real del QR o None si no es segura/no existe.

    Rechaza: ".." en la ruta configurada, extensión no imagen, symlinks que
    salgan del directorio del QR, rutas bajo `fotos_dir` y todo lo que no sea
    un archivo normal.
    """
    if not ruta_cfg:
        return None
    crudo = Path(ruta_cfg)
    if ".." in crudo.parts or crudo.suffix.lower() not in EXTENSIONES:
        logger.warning("pago.qr_ruta_rechazada", motivo="ruta_insegura")
        return None
    try:
        base = crudo.parent.resolve(strict=True)
        real = crudo.resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    if real.parent != base:  # symlink hacia afuera del directorio del QR
        logger.warning("pago.qr_ruta_rechazada", motivo="fuera_del_directorio")
        return None
    # Nunca desde el disco que sirve /fotos (se expondría el archivo crudo).
    try:
        fotos = Path(settings.fotos_dir).resolve()
        if real == fotos or fotos in real.parents:
            logger.warning("pago.qr_ruta_rechazada", motivo="bajo_fotos")
            return None
    except OSError:
        pass
    if not real.is_file():
        return None
    return real


def _recodificar(datos: bytes) -> bytes | None:
    """PNG nuevo y sin metadatos, o None si no es una imagen válida."""
    try:
        with Image.open(io.BytesIO(datos)) as im:
            if im.format not in ("PNG", "JPEG"):
                return None
            if max(im.size) > MAX_LADO_PX or min(im.size) < 1:
                return None
            im.load()
            modo = "RGBA" if im.mode in ("RGBA", "LA", "PA") or "transparency" in im.info else "RGB"
            limpia = Image.new(modo, im.size)
            limpia.paste(im.convert(modo))  # copia sólo los píxeles: sin EXIF ni texto
        salida = io.BytesIO()
        limpia.save(salida, format="PNG", optimize=True)
        return salida.getvalue()
    except Exception:  # noqa: BLE001 — archivo corrupto/no imagen: simplemente no disponible
        return None


def cargar() -> QrCargado | None:
    """El QR listo para servir, o None si falta / no es válido."""
    real = _ruta_segura(settings.pago_qr_path)
    if real is None:
        return None
    try:
        st = real.stat()
        if st.st_size > MAX_BYTES or st.st_size == 0:
            return None
        clave = (str(real), st.st_mtime_ns, st.st_size)
        if clave in _cache:
            qr = _cache[clave]
        else:
            datos = real.read_bytes()
            png = _recodificar(datos)
            qr = None if png is None else QrCargado(
                png=png,
                huella=hashlib.sha256(datos).hexdigest()[:12],
                actualizado=datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
            )
            _cache.clear()
            _cache[clave] = qr
    except OSError:
        return None
    if qr is not None:
        _vigilar_cambio(qr.huella)
    return qr


def _vigilar_cambio(huella: str) -> None:
    global _huella_base
    if _huella_base is None:
        _huella_base = huella
    elif huella != _huella_base and huella not in _cambio_avisado:
        _cambio_avisado.add(huella)
        logger.warning("pago.qr_cambio", huella_arranque=_huella_base, huella_nueva=huella)


def registrar_arranque() -> None:
    """Fija la huella de referencia al arrancar el backend (si hay QR)."""
    global _huella_base
    _huella_base = None
    _cambio_avisado.clear()
    qr = cargar()
    logger.info("pago.qr_arranque", disponible=qr is not None, huella=qr.huella if qr else None)


def info() -> dict:
    qr = cargar()
    return {
        "disponible": qr is not None,
        "titular": settings.pago_titular or None,
        "banco": settings.pago_banco or None,
        "nota": settings.pago_nota or None,
        "actualizado": qr.actualizado if qr else None,
        "huella": qr.huella if qr else None,
        "whatsapp_comprobante": settings.wa_contacto_publico,
    }
