#!/usr/bin/env python3
"""Agrega los rubros que los productos del comercio sugieren y no tiene.

Es el gemelo de limpiar_rubros.py, y va en la dirección contraria: aquel saca lo
que ningún producto respalda, éste agrega lo que los productos piden.

    regaleria    21 comercios   (BAZAR LIDIA, LOREDO CASTRILLO, TRAMONTINA…)
    deportes     12 comercios
    ferreteria   10 comercios

Un rubro faltante no ensucia ninguna búsqueda —a diferencia de uno de más— pero
deja al comercio afuera de un filtro donde debería estar: alguien filtra por
"regalería", el local vende regalos, y no aparece.

POR QUÉ ESTO SÍ SE AUTOMATIZA Y LO OTRO NO
==========================================

Quitar un rubro destruye información y hay que mirarlo de a uno. Agregarlo no:
el respaldo ya está escrito en la ficha del comercio —son SUS productos los que
lo sugieren— y si sobra, se saca desde el panel sin haber perdido nada.

Y sobre todo: esto NO usa el criterio de la IA, que es justamente el que falló.
Usa el diccionario `rubro_palabras`, que es texto contra texto y se corrige
agregando filas.

Lo elegido a mano no se toca: sólo se SUMAN rubros, nunca se reemplaza nada.

    # ver qué agregaría, sin escribir
    docker compose -f docker-compose.prod.yml exec -T backend \\
        python /app/scripts/completar_rubros.py

    # aplicarlo
    docker compose -f docker-compose.prod.yml exec -T -e APLICAR=1 backend \\
        python /app/scripts/completar_rubros.py

    # limitar a ciertos rubros
    docker compose -f docker-compose.prod.yml exec -T -e RUBROS=regaleria,deportes \\
        backend python /app/scripts/completar_rubros.py
"""
import os
import sys
from collections import defaultdict

sys.path.insert(0, "/app")

from app.db.repository import get_repo  # noqa: E402

# Un comercio con demasiados rubros no filtra: aparece en todas las categorías y
# ninguna dice nada de él. Si al sumarle los sugeridos pasa de acá, se saltea y
# queda para revisión humana — ya hay uno con 11 rubros en la base.
MAX_RUBROS = 6


def main() -> int:
    aplicar = os.environ.get("APLICAR") in {"1", "true", "si"}
    filtro = {s.strip() for s in os.environ.get("RUBROS", "").split(",") if s.strip()}

    repo = get_repo()
    comercios = {c["id"]: c for c in repo.list_todos_comercios(None, 5000)
                 if c.get("activo", True)}
    relaciones = repo.list_comercio_rubros_todos()

    actuales: dict[str, set[str]] = defaultdict(set)
    for rel in relaciones:
        if rel["comercio_id"] in comercios:
            actuales[rel["comercio_id"]].add(rel["slug"])

    agregar: list[tuple[dict, list[str]]] = []
    saltados = 0

    for cid, c in comercios.items():
        texto = " ".join(filter(None, (
            c.get("prod_det_ia"), c.get("subcategoria"),
            c.get("sinonimos"), c.get("nombre"))))
        sugeridos = {s for s in repo.sugerir_rubros_por_texto(texto) if s != "otros"}
        tiene = actuales.get(cid, set())
        faltan = sorted(sugeridos - tiene)
        if filtro:
            faltan = [s for s in faltan if s in filtro]
        if not faltan:
            continue
        if len(tiene | set(faltan)) > MAX_RUBROS:
            saltados += 1
            continue
        agregar.append((c, faltan))

    total = sum(len(f) for _, f in agregar)
    por_rubro: dict[str, int] = defaultdict(int)
    for _, faltan in agregar:
        for s in faltan:
            por_rubro[s] += 1

    print(f"Comercios activos:        {len(comercios)}")
    print(f"Comercios a completar:    {len(agregar)}")
    print(f"Rubros a agregar:         {total}")
    if saltados:
        print(f"Salteados por quedar con más de {MAX_RUBROS} rubros: {saltados}")

    print("\nPor rubro:")
    for slug, n in sorted(por_rubro.items(), key=lambda kv: -kv[1]):
        print(f"    {slug:18} {n:3} comercios")

    print("\nDetalle:")
    for c, faltan in agregar[:60]:
        print(f"  URUKU-{c.get('codigo','????')}  {(c.get('nombre') or '')[:22]:24} "
              f"+{', '.join(faltan)}")
        print(f"      vende: {(c.get('prod_det_ia') or '')[:70]}")
    if len(agregar) > 60:
        print(f"  … y {len(agregar) - 60} comercios más")

    if not aplicar:
        print("\nSimulación. Repetir con APLICAR=1 para agregarlos.")
        return 0

    hechos = 0
    for c, faltan in agregar:
        ids = [rid for rid in (repo.get_rubro_id(s) for s in faltan) if rid]
        if not ids:
            continue
        # set_comercio_rubros reemplaza el conjunto, así que se manda la unión:
        # mandar sólo los nuevos borraría los que ya tenía.
        actuales_ids = [rid for rid in
                        (repo.get_rubro_id(s) for s in actuales.get(c["id"], set())) if rid]
        repo.set_comercio_rubros(c["id"], list(dict.fromkeys(actuales_ids + ids)))
        hechos += len(ids)

    print(f"\nAPLICADO: {hechos} rubros agregados en {len(agregar)} comercios.")
    print("Volvé a correr verificar_rubros.sql para ver cómo quedó.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
