"""Procesamiento de imágenes subidas (validar + reorientar + resize + recomprimir).

Lección KB fotos-resize: reorientar por EXIF, limitar a 1600px y JPEG 82
(70 se veía borroso en las miniaturas chicas de la tarjeta del mapa — 82 es
el punto donde deja de notarse sin engordar mucho el archivo).
Lanza ValueError si el archivo no es una imagen válida.
"""
import secrets
from io import BytesIO

import structlog

logger = structlog.get_logger()


def procesar_imagen(data: bytes) -> bytes:
    from PIL import Image, ImageOps

    img = Image.open(BytesIO(data))
    img.verify()                       # valida que sea una imagen real
    img = Image.open(BytesIO(data))    # reabrir tras verify()
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((1600, 1600))
    out = BytesIO()
    img.save(out, format="JPEG", quality=82, optimize=True)
    return out.getvalue()


def guardar_foto_local(subpath: str, data: bytes) -> str | None:
    """Guarda una imagen ya procesada en el volumen de fotos del backend y
    devuelve la URL pública (servida por el propio backend vía StaticFiles).
    No bloquea al caller si falla (devuelve None).

    Reemplaza a Supabase Storage: el self-host no corre storage-api — como
    quien sube la foto es siempre el backend (nunca el navegador), alcanza
    con escribir a disco y servirlo como estático (un microservicio menos).
    """
    from pathlib import Path

    from app.core.config import settings

    try:
        full_path = Path(settings.fotos_dir) / subpath
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(data)
        return settings.public_photo_url(subpath)
    except Exception as exc:  # noqa: BLE001
        logger.warning("guardar_foto_local.error", error=str(exc))
        return None


def subir_foto_comercio(slug: str, data: bytes) -> str | None:
    """Procesa y guarda la portada de un comercio. No bloquea el alta si
    falla (devuelve None y el caller sigue sin foto)."""
    try:
        procesada = procesar_imagen(data)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("El archivo no es una imagen válida") from exc
    path = f"{slug}/{secrets.token_hex(8)}.jpg"
    return guardar_foto_local(path, procesada)
