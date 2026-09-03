#!/usr/bin/env python3
"""Agrega los rubros que los productos del comercio sugieren y no tiene.

La lógica vive en `app/services/rubros_auto.py`, que es lo mismo que corre el
botón de Admin › Rubros. Este script es la cáscara de terminal: en el servidor,
con una sesión abierta, sigue siendo la forma más rápida de mirar esto sin
abrir el navegador.

Dos copias de una regla de clasificación se separan en semanas, y el día que
difieran nadie va a saber cuál de los dos informes creer. Por eso acá no hay
lógica, sólo impresión.

    # ver qué agregaría, sin escribir
    docker compose -f docker-compose.prod.yml exec -T backend \\
        python /app/scripts/completar_rubros.py

    # aplicarlo
    docker compose -f docker-compose.prod.yml exec -T -e APLICAR=1 backend \\
        python /app/scripts/completar_rubros.py

    # limitar a ciertos rubros
    docker compose -f docker-compose.prod.yml exec -T -e RUBROS=carniceria,limpieza \\
        backend python /app/scripts/completar_rubros.py

    # volver a incluir los sinónimos (para comparar los dos informes)
    docker compose -f docker-compose.prod.yml exec -T -e CON_SINONIMOS=1 \\
        backend python /app/scripts/completar_rubros.py
"""
import os
import sys

sys.path.insert(0, "/app")

from app.db.repository import get_repo  # noqa: E402
from app.services.rubros_auto import (  # noqa: E402
    MAX_RUBROS, LecturaIncompleta, analizar, aplicar,
)


def main() -> int:
    escribir = os.environ.get("APLICAR") in {"1", "true", "si"}
    filtro = {s.strip() for s in os.environ.get("RUBROS", "").split(",") if s.strip()}
    con_sinonimos = os.environ.get("CON_SINONIMOS") in {"1", "true", "si"}

    repo = get_repo()
    try:
        inf = analizar(repo, solo_rubros=filtro or None, con_sinonimos=con_sinonimos)
    except LecturaIncompleta as exc:
        print(f"\n  ⚠️  {exc}")
        print("      NO apliques nada: el informe estaría inflado y aplicarlo")
        print("      ensucia el filtro de los comercios que ya están bien.")
        return 1

    print(f"Comercios activos:        {inf['comercios']}")
    print(f"Asignaciones leídas:      {inf['asignaciones_leidas']} de "
          f"{inf['asignaciones_en_tabla']} en la tabla")
    print(f"Comercios a completar:    {inf['comercios_a_completar']}")
    print(f"Rubros a agregar:         {inf['rubros_a_agregar']}")
    if inf["salteados"]:
        print(f"Salteados por quedar con más de {MAX_RUBROS} rubros: {inf['salteados']}")

    print("\nPor rubro:")
    for fila in inf["por_rubro"]:
        print(f"    {fila['slug']:18} {fila['comercios']:3} comercios")

    print("\nDetalle:")
    for item in inf["detalle"][:60]:
        print(f"  URUKU-{item.get('codigo') or '????'}  {(item.get('nombre') or '')[:22]:24} "
              f"+{', '.join(item['agregar'])}")
        print(f"      vende: {item['vende'][:70]}")
    restantes = inf["comercios_a_completar"] - min(60, len(inf["detalle"]))
    if restantes > 0:
        print(f"  … y {restantes} comercios más")

    if not escribir:
        print("\nSimulación. Repetir con APLICAR=1 para agregarlos.")
        return 0

    hechos = aplicar(repo, inf)
    print(f"\nAPLICADO: {hechos} rubros agregados en {inf['comercios_a_completar']} comercios.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
