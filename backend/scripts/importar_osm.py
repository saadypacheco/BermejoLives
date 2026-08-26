#!/usr/bin/env python3
"""Trae comercios de OpenStreetMap a `comercios_importados`, por ciudad.

    # ver qué traería, sin escribir
    docker compose -f docker-compose.prod.yml exec -T -e CIUDAD=la-paz backend \\
        python /app/scripts/importar_osm.py

    # aplicarlo
    docker compose -f docker-compose.prod.yml exec -T -e CIUDAD=la-paz -e APLICAR=1 backend \\
        python /app/scripts/importar_osm.py

    # radio distinto (por defecto 10 km del centro de la ciudad)
    ... -e CIUDAD=tarija -e RADIO=8000 ...

LO QUE ESTA FUENTE DA Y LO QUE NO
=================================

Medido el 2026-08-26 sobre 19.861 negocios: nombre y ubicación casi siempre,
teléfono el 9%, WhatsApp el 1%, **foto el 0,5%**. Es una lista de qué existe y
dónde — sirve para salir a la calle, no para llenar el mapa.

Bermejo no vale la pena: OSM tiene 20 registros (bancos y gasolineras) contra
los 270 que el equipo relevó caminando.

NADA DE ESTO SE PUBLICA
=======================

Todo entra como `estado='nuevo'` y sólo se ve en el panel. Pasa al mapa cuando
una persona lo promueve, de a uno. Un registro de OSM puede estar cerrado hace
dos años y no hay forma de saberlo desde acá.

REIMPORTAR ES SEGURO
====================

El upsert actualiza los datos pero NO toca `estado`: los descartados siguen
descartados y los promovidos siguen promovidos. Si pisara eso, cada corrida
resucitaría lo ya revisado y el trabajo humano se perdería.
"""
import os
import sys
import unicodedata
from math import asin, cos, radians, sin, sqrt

sys.path.insert(0, "/app")

from app.db.repository import get_repo  # noqa: E402
from app.services.importador import normalizar, traer_de_overpass  # noqa: E402

# A menos de esto, y con el nombre parecido, es casi seguro el mismo local. Se
# marca como duplicado en vez de esconderlo: el que revisa decide, pero no
# tiene que mirar doscientas fichas que ya tiene cargadas.
METROS_DUPLICADO = 120


def _sin_tildes(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower())
                   if unicodedata.category(c) != "Mn")


def _clave(nombre: str) -> set[str]:
    """Las palabras que distinguen un nombre, sin las que no dicen nada.

    "Comercial Pérez" y "Comercial Gómez" comparten "comercial" y no son el
    mismo local; compararlos por el texto entero los daría parecidos.
    """
    vacias = {"de", "la", "el", "los", "las", "y", "del", "comercial", "tienda",
              "casa", "super", "mini", "market", "shop", "store"}
    return {p for p in _sin_tildes(nombre).replace(".", " ").split() if p not in vacias and len(p) > 2}


def _metros(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000
    dlat, dlng = radians(lat2 - lat1), radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * r * asin(sqrt(a))


def main() -> int:
    slug = os.environ.get("CIUDAD", "").strip()
    if not slug:
        print("Falta CIUDAD. Ej: -e CIUDAD=la-paz")
        return 2
    aplicar = os.environ.get("APLICAR") in {"1", "true", "si"}
    radio = int(os.environ.get("RADIO", "10000"))

    repo = get_repo()
    ciudad = repo.get_ciudad(slug)
    if not ciudad:
        print(f"No existe la ciudad «{slug}».")
        return 2
    if ciudad.get("lat") is None or ciudad.get("lng") is None:
        print(f"La ciudad «{slug}» no tiene coordenadas: sin centro no hay dónde buscar.")
        return 2

    print(f"Ciudad: {ciudad['nombre']}  ({ciudad['lat']}, {ciudad['lng']})  radio {radio} m")
    print("Consultando Overpass… (puede tardar un par de minutos)")
    elementos = traer_de_overpass(ciudad["lat"], ciudad["lng"], radio)
    print(f"Elementos crudos: {len(elementos)}")

    filas, sin_nombre = [], 0
    for el in elementos:
        fila = normalizar(el)
        if fila is None:
            sin_nombre += 1
            continue
        fila["ciudad_id"] = ciudad["id"]
        filas.append(fila)

    # Duplicados contra lo YA cargado en URUKU.
    ya = [c for c in repo.comercios_con_coords(ciudad["id"])
          if c.get("lat") is not None and c.get("lng") is not None]
    dups = 0
    for fila in filas:
        clave = _clave(fila["nombre"])
        for c in ya:
            if _metros(fila["lat"], fila["lng"], c["lat"], c["lng"]) > METROS_DUPLICADO:
                continue
            if clave and clave & _clave(c.get("nombre") or ""):
                fila["duplicado_de"] = c["id"]
                dups += 1
                break

    con_tel = sum(1 for f in filas if f["telefono"])
    con_wa = sum(1 for f in filas if f["whatsapp"])
    con_dir = sum(1 for f in filas if f["direccion"])
    con_rubro = sum(1 for f in filas if f["rubro_slug"])

    print(f"\nUtilizables (con nombre y coordenadas): {len(filas)}")
    print(f"  descartados por no tener nombre:      {sin_nombre}")
    print(f"  con teléfono:                         {con_tel}")
    print(f"  con whatsapp:                         {con_wa}")
    print(f"  con dirección:                        {con_dir}")
    print(f"  con rubro reconocido:                 {con_rubro}"
          f"  ({len(filas) - con_rubro} quedan sin rubro, se resuelve en el panel)")
    print(f"  posibles duplicados de lo ya cargado: {dups}")

    print("\nMuestra:")
    for f in filas[:12]:
        marca = " ⚠ ya cargado" if f.get("duplicado_de") else ""
        print(f"  {f['nombre'][:34]:36} {f['categoria'][:18]:20} "
              f"{f['rubro_slug'] or '—':16} {f['telefono'] or ''}{marca}")

    if not aplicar:
        print("\nSimulación. Repetir con APLICAR=1 para guardarlos.")
        return 0

    nuevos = actualizados = 0
    for f in filas:
        try:
            if repo.upsert_importado(f):
                nuevos += 1
            else:
                actualizados += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  error con {f['fuente_id']}: {exc}")

    print(f"\nAPLICADO: {nuevos} nuevos, {actualizados} actualizados.")
    print("Nada se publicó: se revisan en Admin › Importados y se promueven de a uno.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
