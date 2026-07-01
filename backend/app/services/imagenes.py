"""Procesamiento de imágenes subidas (validar + reorientar + resize + recomprimir).

Lección KB fotos-resize: reorientar por EXIF, limitar a 1600px y JPEG 70.
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
    img.save(out, format="JPEG", quality=70, optimize=True)
    return out.getvalue()


def subir_foto_comercio(slug: str, data: bytes) -> str | None:
    """Procesa y sube la portada de un comercio al bucket público. No bloquea
    el alta si falla (devuelve None y el caller sigue sin foto)."""
    from app.core.config import settings
    from app.db.session import get_supabase

    try:
        procesada = procesar_imagen(data)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("El archivo no es una imagen válida") from exc
    try:
        path = f"{slug}/{secrets.token_hex(8)}.jpg"
        get_supabase().storage.from_(settings.comercios_bucket).upload(
            path, procesada, {"content-type": "image/jpeg", "upsert": "true"}
        )
        return settings.public_photo_url(path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("subir_foto_comercio.error", error=str(exc))
        return None
