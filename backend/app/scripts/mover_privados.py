"""Pasa al disco PRIVADO los comprobantes de pago y las fotos de «Cambié de número» que se guardaron
cuando eran públicos (M-11).

Qué hace, por cada fila con una URL pública en `pagos.comprobante_url` o
`solicitudes_cambio_numero.foto_url`:
  1. busca el archivo en `FOTOS_DIR` (la parte de la URL que viene después de `/fotos/`),
  2. lo copia al directorio privado (`services/archivos_privados.py`),
  3. cambia la columna por la referencia `privado:<ruta>`,
  4. borra el original de `FOTOS_DIR` (recién DESPUÉS de que la base quedó actualizada).
Es idempotente (las filas que ya son `privado:` se saltean) y no borra nada de la base: sólo reescribe la
columna. Si el archivo ya no está, la fila se deja como estaba y se informa.

Uso (en el VPS, desde la carpeta del compose):

    docker compose -f docker-compose.prod.yml exec backend python -m app.scripts.mover_privados --dry-run
    docker compose -f docker-compose.prod.yml exec backend python -m app.scripts.mover_privados

Con `--dry-run` sólo cuenta lo que movería. Hacelo DESPUÉS de desplegar la versión que guarda en el disco
privado y que sirve `/admin/pagos/{id}/comprobante`.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from app.core.config import settings
from app.services import archivos_privados

#: (tabla, columna, carpeta privada donde cae lo que viene de una carpeta distinta)
_FUENTES = (
    ("pagos", "comprobante_url", None),
    ("solicitudes_cambio_numero", "foto_url", "cambio_numero"),
)


def subruta_publica(url: str | None) -> str | None:
    """La ruta de un archivo dentro de `FOTOS_DIR` a partir de su URL pública (lo que sigue al primer
    `/fotos/`). None si la URL no es de nuestras fotos, o si intenta salirse de la carpeta."""
    if not url or "/fotos/" not in url:
        return None
    sub = url.split("/fotos/", 1)[1].split("?", 1)[0].strip("/")
    partes = [p for p in sub.split("/") if p]
    if not partes or any(p in ("..", ".") for p in partes):
        return None
    return "/".join(partes)


def mover_archivo(url: str, carpeta_destino: str | None, dry_run: bool = False) -> tuple[str | None, str]:
    """(referencia nueva o None, motivo). Copia el archivo al privado; NO borra el original (eso lo
    hace quien llama después de actualizar la base)."""
    sub = subruta_publica(url)
    if not sub:
        return None, "la URL no es de las fotos del backend"
    origen = Path(settings.fotos_dir) / sub
    if not origen.is_file():
        return None, "el archivo ya no está en FOTOS_DIR"
    rel = f"{carpeta_destino}/{sub}" if carpeta_destino and not sub.startswith(carpeta_destino) else sub
    ref = archivos_privados.PREFIJO + rel
    if dry_run:
        return ref, "se movería"
    destino = archivos_privados.ruta_segura(ref)
    if destino is None or not archivos_privados.dir_seguro():
        return None, "el directorio privado no es seguro"
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(origen, destino)
    return ref, "copiado"


def mover(db, dry_run: bool = False) -> dict:
    """Recorre las dos tablas. Devuelve {"<tabla>": {"movidas": n, "omitidas": [(id, motivo)...]}}."""
    resumen: dict = {}
    for tabla, columna, carpeta in _FUENTES:
        movidas, omitidas = 0, []
        filas = db.table(tabla).select(f"id, {columna}").not_.is_(columna, "null").execute().data or []
        for fila in filas:
            url = fila.get(columna)
            if archivos_privados.es_referencia(url):
                continue                      # ya está en el privado
            ref, motivo = mover_archivo(url, carpeta, dry_run)
            if not ref:
                omitidas.append((fila["id"], motivo))
                continue
            if not dry_run:
                db.table(tabla).update({columna: ref}).eq("id", fila["id"]).execute()
                original = Path(settings.fotos_dir) / (subruta_publica(url) or "")
                try:
                    original.unlink(missing_ok=True)       # la base ya apunta al privado
                except OSError:
                    omitidas.append((fila["id"], "se movió, pero no se pudo borrar el original"))
            movidas += 1
        resumen[tabla] = {"movidas": movidas, "omitidas": omitidas}
    return resumen


def main() -> None:
    from app.db.session import get_supabase

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="sólo cuenta, no mueve nada")
    args = ap.parse_args()
    resumen = mover(get_supabase(), dry_run=args.dry_run)
    for tabla, r in resumen.items():
        print(f"{tabla}: {r['movidas']} {'por mover' if args.dry_run else 'movidas'}, {len(r['omitidas'])} omitidas")
        for id_, motivo in r["omitidas"]:
            print(f"   - {id_}: {motivo}")


if __name__ == "__main__":
    main()
