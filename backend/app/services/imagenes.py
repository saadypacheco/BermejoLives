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


def procesar_imagen(data: bytes, max_side: int = 1600, quality: int = 82) -> bytes:
    from PIL import Image, ImageOps

    img = Image.open(BytesIO(data))
    img.verify()                       # valida que sea una imagen real
    img = Image.open(BytesIO(data))    # reabrir tras verify()
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((max_side, max_side))
    out = BytesIO()
    img.save(out, format="JPEG", quality=quality, optimize=True)
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


def subir_foto_galeria(slug: str, data: bytes) -> tuple[str | None, str | None]:
    """Procesa una foto de galería: guarda la grande (1280px) y una miniatura
    (400px) para las tarjetas/mapa. Devuelve (url, thumb_url).
    Lanza ValueError si el archivo no es una imagen válida.

    Grande a 1280px/q80 (antes 1600/82): en un celular se ve igual y pesa ~40%
    menos (≈140-330KB vs 230-540KB). La grande solo carga cuando el comprador
    abre la foto en pantalla completa; el mapa/tarjetas usan siempre el thumb."""
    try:
        grande = procesar_imagen(data, 1280, 80)
        chica = procesar_imagen(data, 400, 80)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("El archivo no es una imagen válida") from exc
    token = secrets.token_hex(8)
    url = guardar_foto_local(f"{slug}/{token}.jpg", grande)
    thumb = guardar_foto_local(f"{slug}/{token}_t.jpg", chica)
    return url, thumb


# Videos: se guardan tal cual (sin procesar) en el mismo volumen, servidos por
# /fotos/... — son material crudo para redes, no se reproducen en la ficha aún.
_VIDEO_EXT = {"video/mp4": "mp4", "video/webm": "webm", "video/quicktime": "mov", "video/3gpp": "3gp"}


def subir_video_comercio(slug: str, data: bytes, content_type: str | None) -> str | None:
    ext = _VIDEO_EXT.get((content_type or "").lower(), "mp4")
    path = f"{slug}/videos/{secrets.token_hex(8)}.{ext}"
    return guardar_foto_local(path, data)
