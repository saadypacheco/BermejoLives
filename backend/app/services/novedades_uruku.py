"""Archivos de las novedades de URUKU (0150, docs/novedades-uruku.md).

Todo vive en el disco del backend bajo `uruku/novedades/<id>/` (portada, fotos, video
y póster) y lo sirve el mismo `/fotos/`. Este módulo sabe dos cosas: cuál es esa
carpeta y cómo borrar un archivo SIN poder salirse de ella (la URL que llega a
borrar viene de la base o de un parámetro del panel; nunca se confía en ella).
"""
from pathlib import Path

import structlog

from app.core.config import settings

logger = structlog.get_logger()

#: Las fotos de una novedad (la portada no cuenta).
MAX_FOTOS = 12


def carpeta(novedad_id: str) -> str:
    """Subcarpeta relativa al volumen de fotos."""
    return f"uruku/novedades/{novedad_id}"


def borrar_archivo(novedad_id: str, url: str | None) -> bool:
    """Borra del disco el archivo de esa URL si y sólo si es de la carpeta de ESA
    novedad. Nunca lanza. True si lo borró (o ya no estaba)."""
    if not url:
        return False
    try:
        base = settings.public_photo_url("")
        if not url.startswith(base):
            return False
        relativa = url[len(base):]
        if "\\" in relativa or ".." in relativa.split("/"):
            return False
        raiz = (Path(settings.fotos_dir) / carpeta(novedad_id)).resolve()
        ruta = (Path(settings.fotos_dir) / relativa).resolve()
        if not ruta.is_relative_to(raiz) or ruta == raiz:
            logger.info("novedad_uruku.archivo_no_se_borra", url=url, motivo="no es de la carpeta de la novedad")
            return False
        ruta.unlink(missing_ok=True)
        return True
    except Exception:  # noqa: BLE001
        logger.warning("novedad_uruku.archivo_borrar_fallo", url=url, exc_info=True)
        return False


def borrar_archivos(novedad_id: str, *urls: str | None) -> None:
    for u in urls:
        borrar_archivo(novedad_id, u)
