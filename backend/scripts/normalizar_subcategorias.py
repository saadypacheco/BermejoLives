#!/usr/bin/env python3
"""Llena `subcategoria_norm` en los comercios ya analizados. NO llama a la IA.

Las 159 subcategorías que escribió el análisis por fotos ya están en la base;
sólo falta calcularles la forma canónica. Volver a llamar al modelo para esto
sería pagar tokens por algo que se resuelve con texto.

    docker compose -f docker-compose.prod.yml exec -T backend python - \\
        < backend/scripts/normalizar_subcategorias.py
    docker compose -f docker-compose.prod.yml exec -T -e APLICAR=1 backend python - \\
        < backend/scripts/normalizar_subcategorias.py

Sin APLICAR=1 sólo informa. Lo interesante del informe no son los cambios sino
los GRUPOS: qué variantes se fusionan y cuántos comercios gana cada una.
"""
import os
import sys
from collections import defaultdict

sys.path.insert(0, "/app")

from app.db.repository import get_repo  # noqa: E402
from app.services.normalizar import normalizar_subcategoria  # noqa: E402


def main() -> int:
    aplicar = os.environ.get("APLICAR") in {"1", "true", "si"}
    repo = get_repo()

    comercios = [c for c in repo.list_todos_comercios(None, 5000) if c.get("activo", True)]
    grupos: dict[str, set[str]] = defaultdict(set)
    con_subcategoria = 0
    escritos = 0

    for c in comercios:
        sub = (c.get("subcategoria") or "").strip()
        if not sub:
            continue
        norm = normalizar_subcategoria(sub)
        if not norm:
            continue
        grupos[norm].add(sub)
        con_subcategoria += 1
        if c.get("subcategoria_norm") != norm:
            escritos += 1
            if aplicar:
                repo.update_comercio(c["id"], {"subcategoria_norm": norm}, None)

    fusionados = {k: v for k, v in grupos.items() if len(v) > 1}

    # Tres números distintos, y confundirlos lleva a conclusiones equivocadas:
    # cuántos LOCALES tienen subcategoría, de cuántas FORMAS se escribió, y
    # cuántas categorías REALES son una vez agrupadas las variantes.
    print(f"Comercios con subcategoría:     {con_subcategoria}")
    print(f"  formas distintas escritas:    {sum(len(v) for v in grupos.values())}")
    print(f"  categorías reales (agrupadas): {len(grupos)}")
    print(f"  filas a escribir:             {escritos}")

    print(f"\nGRUPOS QUE SE FUSIONAN ({len(fusionados)}) — esto es lo que el "
          f"comprador dejaba de encontrar:")
    for norm, variantes in sorted(fusionados.items(), key=lambda kv: -len(kv[1])):
        print(f"    {norm:28} <- {' | '.join(sorted(variantes))}")

    print("\nAPLICADO" if aplicar else "\nSimulación. Repetir con APLICAR=1 para escribir.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
