"""Importa el rol de turnos de las farmacias (docs/farmacias-de-turno.md).

    # en el contenedor (el JSON viaja en la imagen, en /app/data)
    docker compose -f docker-compose.prod.yml exec -T backend \\
        python -m app.scripts.importar_turnos_farmacia data/turnos_farmacia/bermejo-2026-10-04_2026-12-12.json

    # o con el archivo por la entrada estándar
    cat rol.json | docker compose ... exec -T backend python -m app.scripts.importar_turnos_farmacia -

Es idempotente: correrlo dos veces no duplica fichas ni turnos. Crea las farmacias que faltan,
completa teléfono y dirección de las que ya están SÓLO si estaban vacíos, y guarda los turnos de
08:00 a 08:00 (hora de La Paz). Imprime el resumen; sale con código 1 si el rol no cierra y en
ese caso no escribe nada.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from app.db.repository import Repo
from app.services import turnos_farmacia


def _leer(ruta: str) -> dict:
    if ruta == "-":
        return json.loads(sys.stdin.read())
    return json.loads(Path(ruta).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None, repo: Repo | None = None) -> int:
    ap = argparse.ArgumentParser(prog="importar_turnos_farmacia", description=__doc__.split("\n")[0])
    ap.add_argument("archivo", help="ruta del JSON del rol (o - para leerlo de la entrada estándar)")
    args = ap.parse_args(argv)

    try:
        data = _leer(args.archivo)
    except (OSError, ValueError) as exc:
        print(f"No se pudo leer {args.archivo}: {exc}", file=sys.stderr)
        return 1

    if repo is None:
        from app.db.repository import get_repo
        repo = get_repo()
    try:
        resumen = turnos_farmacia.importar(repo, data)
    except (ValueError, ValidationError) as exc:      # ValidationError es un ValueError, se deja explícito
        print(f"El rol no se importó: {exc}", file=sys.stderr)
        return 1

    print(f"Farmacias creadas:      {resumen['creadas']}")
    print(f"Farmacias actualizadas: {resumen['actualizadas']} "
          f"(con datos completados: {resumen['datos_completados']})")
    print(f"Turnos guardados:       {resumen['turnos']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
