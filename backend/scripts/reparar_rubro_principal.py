#!/usr/bin/env python3
"""Pone el rubro principal a los comercios que quedaron mostrando "Otros".

Qué pasó: el análisis por fotos clasificó bien 160 comercios y guardó sus rubros
en `comercio_rubros`, pero el rubro PRINCIPAL (comercios.rubro_id) no se
actualizó. La condición preguntaba "¿no tiene rubro principal?" mirando sólo
NULL, y en el alta todos reciben rubro_id = otros como descarte — nunca es NULL,
así que la condición no se cumplía jamás.

Consecuencia: el buscador sí los encontraba (usa comercio_rubros), pero en la
ficha, en el color del pin del mapa y en el filtro por categoría seguían
apareciendo como "Otros (a clasificar)".

Esto lo arregla SIN volver a llamar a la IA: los rubros ya están guardados, sólo
hay que elegir cuál es el principal.

    docker compose -f docker-compose.prod.yml exec -T backend python - \\
        < backend/scripts/reparar_rubro_principal.py
    docker compose -f docker-compose.prod.yml exec -T -e APLICAR=1 backend python - \\
        < backend/scripts/reparar_rubro_principal.py

Sin APLICAR=1 sólo informa qué haría.
"""
import os
import sys

sys.path.insert(0, "/app")

from app.db.repository import get_repo  # noqa: E402
from app.services.rubros import SLUG_DESCARTE  # noqa: E402


def main() -> int:
    aplicar = os.environ.get("APLICAR") in {"1", "true", "si"}
    repo = get_repo()

    id_descarte = repo.get_rubro_id(SLUG_DESCARTE)
    orden = {r["slug"]: i for i, r in enumerate(repo.list_rubros())}

    comercios = repo.list_todos_comercios(None, 5000)
    cambios, sin_datos = [], 0

    for c in comercios:
        if not c.get("activo", True):
            continue
        actual = c.get("rubro_id")
        if actual and actual != id_descarte:
            continue                      # ya tiene un principal de verdad

        slugs = [s for s in repo.get_comercio_rubros(c["id"]) if s != SLUG_DESCARTE]
        if not slugs:
            sin_datos += 1
            continue

        # El principal es el de menor `orden` en la taxonomía: es el criterio con
        # el que están pensados los 42 rubros (los más específicos primero).
        elegido = sorted(slugs, key=lambda s: orden.get(s, 999))[0]
        nuevo_id = repo.get_rubro_id(elegido)
        if not nuevo_id:
            continue

        cambios.append((c.get("slug"), c.get("nombre"), elegido))
        if aplicar:
            repo.update_comercio(c["id"], {"rubro_id": nuevo_id}, None)

    print(f"Comercios revisados: {len(comercios)}")
    print(f"  con principal a corregir: {len(cambios)}")
    print(f"  sin rubros para elegir:   {sin_datos}")
    for slug, nombre, elegido in cambios[:25]:
        print(f"    {(nombre or slug)[:34]:36} -> {elegido}")
    if len(cambios) > 25:
        print(f"    … y {len(cambios) - 25} más")

    print("\nAPLICADO" if aplicar else "\nSimulación. Repetir con APLICAR=1 para escribir.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
