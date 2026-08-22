#!/usr/bin/env python3
"""Revisa los rubros contra los productos que la IA vio en las vidrieras.

Los 54 rubros se escribieron antes de ver un solo comercio. Con 161 locales
relevados y sus productos detectados ya hay evidencia para juzgar esa lista:
cuál no usa nadie, cuál es tan grande que no filtra, qué productos no caen en
ninguno, cuáles se pisan.

NO ESCRIBE NADA. Cambiar la taxonomía reordena el mapa, los filtros y las
búsquedas de todos los comercios a la vez: las propuestas las decide una
persona.

    # ver la evidencia, sin llamar a la IA
    docker compose -f docker-compose.prod.yml exec -T backend \\
        python /app/scripts/revisar_taxonomia.py

    # pedirle a la IA que la revise (una sola llamada de texto)
    docker compose -f docker-compose.prod.yml exec -T -e APLICAR=1 backend \\
        python /app/scripts/revisar_taxonomia.py
"""
import os
import sys

sys.path.insert(0, "/app")

from app.db.repository import get_repo  # noqa: E402
from app.services.sinonimos import gemini_post  # noqa: E402
from app.services.taxonomia import armar_evidencia, revisar  # noqa: E402


def main() -> int:
    aplicar = os.environ.get("APLICAR") in {"1", "true", "si"}
    repo = get_repo()

    comercios = repo.list_todos_comercios(None, 5000)
    relaciones = repo.list_comercio_rubros_todos()
    rubros = repo.list_rubros()

    if not relaciones:
        print("ERROR: no se pudo leer comercio_rubros. Sin eso no hay evidencia.")
        return 1

    ev = armar_evidencia(comercios, relaciones, rubros)

    print(f"Comercios activos:      {ev['total_comercios']}")
    print(f"Rubros con comercios:   {len(ev['rubros'])}")
    print(f"Rubros vacíos:          {len(ev['vacios'])}")
    print(f"Términos sin rubro:     {len(ev['sin_rubro'])}")

    umbral = max(1, ev["total_comercios"] // 3)
    grandes = [r for r in ev["rubros"] if r["comercios"] >= umbral]
    if grandes:
        print(f"\nDEMASIADO GRANDES (más de un tercio de {ev['total_comercios']}):")
        for r in grandes:
            print(f"    {r['nombre'][:34]:36} {r['comercios']:3} comercios")

    if ev["vacios"]:
        print(f"\nSIN NINGÚN COMERCIO ({len(ev['vacios'])}):")
        print("    " + ", ".join(v["nombre"] for v in ev["vacios"]))

    if ev["sin_rubro"]:
        print("\nPRODUCTOS DE LOCALES SIN RUBRO (candidatos a rubro nuevo):")
        for h in ev["sin_rubro"][:20]:
            print(f"    {h['termino']:30} {h['veces']:3} veces")

    if not aplicar:
        print("\nSimulación. APLICAR=1 le pide a la IA que revise esta evidencia.")
        return 0

    print("\nPidiendo la revisión… (una llamada de texto)")
    prop = revisar(ev, gemini_post)
    if prop.get("error"):
        print(f"ERROR: {prop['error']}")
        return 1

    etiquetas = {"crear": "CREAR", "dividir": "DIVIDIR", "fusionar": "FUSIONAR",
                 "eliminar": "ELIMINAR", "renombrar": "RENOMBRAR"}
    hubo = False
    for clave, titulo in etiquetas.items():
        items = prop.get(clave) or []
        if not items:
            continue
        hubo = True
        print(f"\n──── {titulo} ────")
        for it in items:
            cabeza = (it.get("nombre") or it.get("slug") or it.get("slugs") or "")
            destino = it.get("en") or it.get("a") or ""
            estimado = it.get("comercios_estimados")
            linea = f"  {cabeza}"
            if destino:
                linea += f"  ->  {destino}"
            if estimado:
                linea += f"  (~{estimado} comercios)"
            print(linea)
            if it.get("productos"):
                print(f"      productos: {it['productos']}")
            print(f"      {it.get('porque', '')}")

    if not hubo:
        print("\nLa IA no propuso cambios: la taxonomía describe bien lo relevado.")

    print("\nNada de esto se escribió. Son propuestas para decidir.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
