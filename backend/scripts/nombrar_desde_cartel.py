#!/usr/bin/env python3
"""Le pone nombre a los comercios que quedaron como "Comercio", leyendo el cartel.

Después de dos salidas al campo hay 100 comercios sin nombre sobre 203: la mitad
del catálogo aparece en las búsquedas con la tarjeta en blanco. El buscador los
encuentra bien —uno sale primero en "ferretería"— y el comprador ve un cartel
vacío. Encontrar y no poder mostrar es igual a no encontrar.

Volver a caminar 100 locales para copiar un cartel es un día entero. Y las
fotos ya están: el cartel está en la imagen, y la IA nunca lo leyó porque el
prompt no se lo pedía.

Este script re-analiza SÓLO los que no tienen nombre real. No toca a los demás,
así que ninguna lectura de foto puede pisar un nombre que tipeó una persona
parada en la puerta del local.

    # ver a cuáles les falta, sin llamar a nadie
    docker compose -f docker-compose.prod.yml exec -T backend \\
        python /app/scripts/nombrar_desde_cartel.py

    # leer los carteles y proponer (NO escribe)
    docker compose -f docker-compose.prod.yml exec -T -e LEER=1 backend \\
        python /app/scripts/nombrar_desde_cartel.py

    # escribir los nombres propuestos
    docker compose -f docker-compose.prod.yml exec -T -e LEER=1 -e APLICAR=1 backend \\
        python /app/scripts/nombrar_desde_cartel.py

Leer y escribir están separados a propósito: un nombre equivocado queda escrito
como si fuera cierto y nadie vuelve a revisarlo, así que conviene mirar la lista
antes de aplicarla.
"""
import os
import sys

sys.path.insert(0, "/app")

from app.db.repository import get_repo  # noqa: E402
from app.services.normalizar import es_nombre_generico  # noqa: E402
from app.services.vision import analizar_fotos  # noqa: E402


def main() -> int:
    leer = os.environ.get("LEER") in {"1", "true", "si"}
    aplicar = os.environ.get("APLICAR") in {"1", "true", "si"}
    repo = get_repo()

    rubros = repo.list_rubros()
    nombres_rubro = {r.get("nombre", "") for r in rubros}

    comercios = [c for c in repo.list_todos_comercios(None, 5000) if c.get("activo", True)]
    sin_nombre = [c for c in comercios if es_nombre_generico(c.get("nombre"), nombres_rubro)]

    print(f"Comercios activos:  {len(comercios)}")
    print(f"Sin nombre real:    {len(sin_nombre)}")

    if not sin_nombre:
        print("\nNo hay nada que hacer.")
        return 0

    if not leer:
        for c in sin_nombre[:30]:
            print(f"    URUKU-{c.get('codigo', '????')}  {c.get('nombre') or '(vacío)'}")
        if len(sin_nombre) > 30:
            print(f"    … y {len(sin_nombre) - 30} más")
        print("\nSimulación. LEER=1 lee los carteles de las fotos.")
        return 0

    leidos, vacios, fallos = [], 0, 0
    for i, c in enumerate(sin_nombre, 1):
        # La portada primero: suele ser la foto de la fachada, que es donde está
        # el cartel. Mismo orden que usa el análisis del panel.
        urls = [f["url"] for f in repo.list_fotos_comercio(c["id"]) if f.get("url")]
        if c.get("portada_url"):
            urls.insert(0, c["portada_url"])
        if not urls:
            vacios += 1
            continue

        prop = analizar_fotos(urls, rubros)
        if prop.get("error"):
            fallos += 1
            print(f"  [{i}/{len(sin_nombre)}] URUKU-{c.get('codigo')}: {prop['error'][:70]}")
            continue

        cartel = (prop.get("nombre_cartel") or "").strip()
        # El modelo devuelve "" cuando el cartel no se lee o cuando lo que ve es
        # un rubro. Se filtra igual acá: si escribió "ROPA", no es un nombre.
        if not cartel or es_nombre_generico(cartel, nombres_rubro):
            vacios += 1
            continue

        leidos.append((c, cartel, prop.get("confianza", 0)))
        print(f"  [{i}/{len(sin_nombre)}] URUKU-{c.get('codigo')}  ->  {cartel}"
              f"   (confianza {prop.get('confianza', 0):.2f})")

    print(f"\nCarteles leídos:      {len(leidos)}")
    print(f"Sin cartel legible:   {vacios}")
    if fallos:
        print(f"Fallaron:             {fallos}")

    if not aplicar:
        print("\nNo se escribió nada. Repetir con APLICAR=1 para guardar estos nombres.")
        return 0

    escritos = 0
    for c, cartel, _conf in leidos:
        # El slug se rearma solo al renombrar, si todavía era genérico.
        repo.update_comercio(c["id"], {"nombre": cartel}, None)
        escritos += 1

    print(f"\nAPLICADO: {escritos} comercios con nombre.")
    print("Los que quedaron sin cartel legible hay que verlos en persona o "
          "sacarles otra foto de la fachada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
