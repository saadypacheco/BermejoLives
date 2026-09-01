"""Cuánto pesan las fotos en disco, y recomprimir las que se fueron de rango.

Todo lo que sube por el backend ya pasa por `procesar_imagen` (1280px / q80),
así que en teoría no hay nada pesado. En teoría. Esto existe para poder MIRAR
en vez de suponer: archivos que entraron por otro camino, un `max_side` que
alguna vez fue 1600, y sobre todo los VIDEOS, que se guardan crudos tal como
salen del celular y son el único lugar donde de verdad hay decenas de megas.
"""
from __future__ import annotations

import os
from pathlib import Path

import structlog

logger = structlog.get_logger()

_EXT_IMAGEN = {".jpg", ".jpeg", ".png", ".webp"}
_EXT_VIDEO = {".mp4", ".webm", ".mov", ".3gp"}


def _recorrer(raiz: Path):
    for carpeta, _dirs, archivos in os.walk(raiz):
        for nombre in archivos:
            ruta = Path(carpeta) / nombre
            try:
                yield ruta, ruta.stat().st_size
            except OSError:
                continue


def medir(fotos_dir: str, top: int = 20) -> dict:
    """Resumen del volumen de fotos: cuánto pesa, en qué, y cuáles son las peores."""
    raiz = Path(fotos_dir)
    if not raiz.exists():
        return {"existe": False, "dir": str(raiz)}

    imagenes: list[tuple[str, int]] = []
    videos: list[tuple[str, int]] = []
    otros_n, otros_bytes = 0, 0

    for ruta, size in _recorrer(raiz):
        rel = str(ruta.relative_to(raiz)).replace("\\", "/")
        ext = ruta.suffix.lower()
        if ext in _EXT_IMAGEN:
            imagenes.append((rel, size))
        elif ext in _EXT_VIDEO:
            videos.append((rel, size))
        else:
            otros_n += 1
            otros_bytes += size

    def resumen(items: list[tuple[str, int]]) -> dict:
        total = sum(s for _, s in items)
        return {
            "n": len(items),
            "bytes": total,
            # El promedio solo miente cuando hay pocos archivos enormes, que es
            # justamente el caso que buscamos. Por eso va también el top.
            "promedio_kb": round(total / len(items) / 1024, 1) if items else 0,
            "top": [{"path": p, "kb": round(s / 1024, 1)}
                    for p, s in sorted(items, key=lambda x: -x[1])[:top]],
        }

    return {
        "existe": True,
        "dir": str(raiz),
        "imagenes": resumen(imagenes),
        "videos": resumen(videos),
        "otros": {"n": otros_n, "bytes": otros_bytes},
        "bytes_total": sum(s for _, s in imagenes) + sum(s for _, s in videos) + otros_bytes,
    }


def optimizar(fotos_dir: str, max_kb: int, limite: int, max_side: int = 1280,
              quality: int = 78) -> dict:
    """Recomprime las imágenes que pasan `max_kb`, en el mismo archivo.

    Tres reglas que hacen que esto sea seguro de correr:

    1. **Sólo imágenes.** Un video pasado por el procesador de imágenes se
       destruye, y son justamente los archivos más pesados: si el filtro
       fallara, el botón "reducir peso" borraría el material de redes.
    2. **Nunca escribe si el resultado no es más chico.** Recomprimir un JPEG ya
       comprimido a veces lo agranda. Sin esta guarda, apretar dos veces el
       botón dejaba todo más pesado que al principio.
    3. **Mismo nombre de archivo.** Las URLs están guardadas en la base; un
       nombre nuevo dejaría 800 fichas apuntando a fotos que ya no existen.

    Es IRREVERSIBLE: el original se pierde. Por eso el umbral es explícito y no
    tiene default en el endpoint.
    """
    from app.services.imagenes import procesar_imagen

    raiz = Path(fotos_dir)
    if not raiz.exists():
        return {"revisados": 0, "optimizados": 0, "ahorro_bytes": 0, "detalle": []}

    umbral = max_kb * 1024
    candidatos = [
        (ruta, size) for ruta, size in _recorrer(raiz)
        if ruta.suffix.lower() in _EXT_IMAGEN and size > umbral
    ]
    candidatos.sort(key=lambda x: -x[1])

    optimizados, ahorro, detalle = 0, 0, []
    for ruta, antes in candidatos[:limite]:
        try:
            nueva = procesar_imagen(ruta.read_bytes(), max_side, quality)
        except Exception as exc:  # noqa: BLE001
            logger.info("peso_fotos.no_es_imagen", path=str(ruta), error=str(exc))
            continue
        if len(nueva) >= antes:
            continue
        ruta.write_bytes(nueva)
        optimizados += 1
        ahorro += antes - len(nueva)
        detalle.append({
            "path": str(ruta.relative_to(raiz)).replace("\\", "/"),
            "antes_kb": round(antes / 1024, 1),
            "despues_kb": round(len(nueva) / 1024, 1),
        })

    logger.info("peso_fotos.optimizadas", n=optimizados, ahorro_kb=round(ahorro / 1024))
    return {
        "revisados": len(candidatos),
        "optimizados": optimizados,
        "ahorro_bytes": ahorro,
        # Cuántas quedaron sin tocar por el límite de esta tanda: sin este
        # número, "optimizadas 50" se lee como "listo" cuando faltan 300.
        "restantes": max(0, len(candidatos) - limite),
        "detalle": detalle[:20],
    }
