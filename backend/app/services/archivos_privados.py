"""Archivos que NO se publican: comprobantes de pago y fotos del trámite «Cambié de número».

Antes iban a `FOTOS_DIR` (lo sirve /fotos, público y cacheado un año): bastaba una captura con la URL de
un comprobante para que cualquiera lo abriera sin login. Ahora se guardan en un disco PRIVADO, igual que
las fotos de desconocidos (`services/wa_received.py`), y se ven sólo por un endpoint con permiso:

  - comprobante de pago:   GET /admin/pagos/{id}/comprobante                     (permiso `pagos`)
  - foto de cambio de nº:  GET /admin/solicitudes-cambio-numero/{id}/foto        (permiso `comercios.cuenta`)

En la base la columna (`pagos.comprobante_url`, `solicitudes_cambio_numero.foto_url`) guarda una REFERENCIA
`privado:<ruta relativa>` en vez de una URL. Las filas viejas, con una URL pública, las pasa
`python -m app.scripts.mover_privados`.

El directorio es `PRIVADOS_DIR`; vacío = la subcarpeta `privados/` de `WA_RECEIVED_DIR` (que ya es un
volumen privado: no hace falta montar otro). NUNCA debe quedar bajo `FOTOS_DIR`.
"""
from __future__ import annotations

import secrets
from pathlib import Path

import structlog

from app.core.config import settings

logger = structlog.get_logger()

PREFIJO = "privado:"


def raiz() -> Path:
    if (settings.privados_dir or "").strip():
        return Path(settings.privados_dir)
    return Path(settings.wa_received_dir) / "privados"


def dir_seguro() -> bool:
    """El directorio privado NO está dentro del de fotos públicas ni al revés."""
    try:
        r, f = raiz().resolve(), Path(settings.fotos_dir).resolve()
        return r != f and f not in r.parents and r not in f.parents
    except OSError:
        return False


def es_referencia(valor: str | None) -> bool:
    return bool(valor) and str(valor).startswith(PREFIJO)


def _relativa(ref: str | None) -> str | None:
    if not es_referencia(ref):
        return None
    return str(ref)[len(PREFIJO):] or None


def ruta_segura(ref: str | None) -> Path | None:
    """La ruta absoluta de una referencia, sólo si queda DENTRO del directorio privado (un valor
    adulterado en la base, `privado:../../etc/passwd`, devuelve None)."""
    rel = _relativa(ref)
    if not rel:
        return None
    try:
        base = raiz().resolve()
        destino = (base / rel).resolve()
        if destino == base or base not in destino.parents:
            logger.warning("privados.ruta_fuera_del_directorio")
            return None
        return destino
    except Exception:  # noqa: BLE001
        return None


def guardar(carpeta: str, nombre_base: str, data: bytes) -> str | None:
    """Guarda `data` (una imagen ya procesada) en `<carpeta>/<nombre_base>/<azar>.jpg` y devuelve la
    REFERENCIA para la base, o None si no se pudo (nunca lanza). `carpeta` y `nombre_base` los pone el
    código (un id de comercio), no el usuario."""
    if not dir_seguro():
        logger.error("privados.dir_inseguro", privados_dir=str(raiz()), fotos_dir=settings.fotos_dir)
        return None
    try:
        ref = f"{PREFIJO}{carpeta}/{nombre_base}/{secrets.token_hex(8)}.jpg"
        destino = ruta_segura(ref)
        if destino is None:
            return None
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(data)
        return ref
    except Exception:  # noqa: BLE001
        logger.warning("privados.guardar_fallo", exc_info=True)
        return None


def leer(ref: str | None) -> bytes | None:
    ruta = ruta_segura(ref)
    if ruta is None:
        return None
    try:
        return ruta.read_bytes() if ruta.is_file() else None
    except OSError:
        logger.warning("privados.lectura_fallo", exc_info=True)
        return None


def ruta_api_pago(pago_id: str) -> str:
    return f"/admin/pagos/{pago_id}/comprobante"


def ruta_api_cambio(solicitud_id: str) -> str:
    return f"/admin/solicitudes-cambio-numero/{solicitud_id}/foto"
