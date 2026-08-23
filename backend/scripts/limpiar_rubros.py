#!/usr/bin/env python3
"""Saca los rubros que ningún producto del comercio respalda.

La verificación mostró un patrón, no errores sueltos: dos rubros amplios se
usaron como cajón de sastre encima de los específicos que ya estaban bien.

    Supermercado y alimentos   22 de 25 sin respaldo   (lencerías, jugueterías)
    Hogar, blanco y decoración 15 de 25 sin respaldo   (ollas, termos → es bazar)

Un rubro de más no es un dato extra: es un local apareciendo en una búsqueda que
no le corresponde. El comprador filtra por "alimentos", recibe una lencería, y
deja de confiar en el filtro.

LO QUE ESTE SCRIPT NO TOCA, Y POR QUÉ
=====================================

Los rubros de SERVICIO están excluidos a propósito. Un servicio no tiene
mercadería en la vidriera, así que por construcción nunca va a tener "respaldo
en los productos" — el 100% sin respaldo de Cambio de moneda, Peluquería,
Restaurantes y Gomería es un defecto de la verificación, no de la clasificación.

De hecho "cambio de moneda" en una tienda de ropa es muy probable que esté BIEN:
Bermejo es frontera y la IA vio el cartel de compra/venta de pesos. Borrarlo
sería destruir un dato correcto con una regla que no aplica.

El comercio nunca queda sin rubros: si sacarlos todos lo dejaría vacío, se
saltea. Es preferible un rubro dudoso a un local invisible.

    # ver qué sacaría, sin escribir
    docker compose -f docker-compose.prod.yml exec -T backend \\
        python /app/scripts/limpiar_rubros.py

    # aplicarlo
    docker compose -f docker-compose.prod.yml exec -T -e APLICAR=1 backend \\
        python /app/scripts/limpiar_rubros.py

    # otros rubros (coma), si la verificación muestra otro caso
    docker compose -f docker-compose.prod.yml exec -T -e RUBROS=alimentos,hogar,bebes \\
        backend python /app/scripts/limpiar_rubros.py
"""
import os
import sys

sys.path.insert(0, "/app")

from app.db.repository import get_repo  # noqa: E402

# Los dos que la verificación señaló. Se puede cambiar con RUBROS=...
POR_DEFECTO = ["alimentos", "hogar"]

# Servicios: no tienen productos que puedan respaldarlos. Nunca se limpian
# automáticamente, aunque se los pasen por RUBROS.
SERVICIOS = {"cambio", "peluqueria", "restaurantes", "gomeria", "comida-rapida",
             "cafeteria", "farmacia", "panaderia", "rotiseria"}


def main() -> int:
    aplicar = os.environ.get("APLICAR") in {"1", "true", "si"}
    pedidos = [s.strip() for s in os.environ.get("RUBROS", "").split(",") if s.strip()]
    objetivo = [s for s in (pedidos or POR_DEFECTO)]

    protegidos = [s for s in objetivo if s in SERVICIOS]
    objetivo = [s for s in objetivo if s not in SERVICIOS]
    if protegidos:
        print(f"No se tocan (son servicios, no tienen productos que los respalden): "
              f"{', '.join(protegidos)}\n")
    if not objetivo:
        print("No queda ningún rubro para revisar.")
        return 0

    repo = get_repo()
    comercios = {c["id"]: c for c in repo.list_todos_comercios(None, 5000)
                 if c.get("activo", True)}
    relaciones = repo.list_comercio_rubros_todos()

    por_comercio: dict[str, list[str]] = {}
    for rel in relaciones:
        if rel["comercio_id"] in comercios:
            por_comercio.setdefault(rel["comercio_id"], []).append(rel["slug"])

    print(f"Revisando: {', '.join(objetivo)}")
    print(f"Comercios activos: {len(comercios)}\n")

    quitar: list[tuple[dict, str, list[str]]] = []
    salteados = 0

    for cid, slugs in por_comercio.items():
        c = comercios[cid]
        texto = " ".join(filter(None, (
            c.get("prod_det_ia"), c.get("subcategoria"),
            c.get("sinonimos"), c.get("nombre"))))
        # Mismo criterio que el informe: se le pregunta al diccionario qué rubros
        # sugiere este texto. Si el rubro asignado no está entre ellos, no hay
        # nada en la ficha que lo justifique.
        sugeridos = set(repo.sugerir_rubros_por_texto(texto))

        for slug in slugs:
            if slug not in objetivo or slug in sugeridos:
                continue
            reales = [s for s in slugs if s != "otros" and s != slug]
            if not reales:
                # Sacarlo lo dejaría sin ninguna categoría: preferimos un rubro
                # dudoso a un comercio invisible.
                salteados += 1
                continue
            quitar.append((c, slug, reales))

    print(f"Asignaciones sin respaldo: {len(quitar)}")
    if salteados:
        print(f"Salteadas por dejar el comercio sin rubros: {salteados}")
    print()
    for c, slug, reales in quitar[:60]:
        print(f"  URUKU-{c.get('codigo','????')}  {(c.get('nombre') or '')[:22]:24} "
              f"-{slug:12} queda: {', '.join(reales)}")
        print(f"      vende: {(c.get('prod_det_ia') or '')[:70]}")
    if len(quitar) > 60:
        print(f"  … y {len(quitar) - 60} más")

    if not aplicar:
        print("\nSimulación. Repetir con APLICAR=1 para quitarlos.")
        return 0

    hechos = 0
    for c, slug, _reales in quitar:
        rid = repo.get_rubro_id(slug)
        if not rid:
            continue
        repo.quitar_rubro_comercio(c["id"], rid)
        hechos += 1
        # Si era el rubro PRINCIPAL, hay que elegir otro o la ficha queda
        # mostrando una categoría que el comercio ya no tiene.
        if c.get("rubro_id") == rid:
            nuevo = next((s for s in _reales), None)
            nid = repo.get_rubro_id(nuevo) if nuevo else None
            if nid:
                repo.update_comercio(c["id"], {"rubro_id": nid}, None)

    print(f"\nAPLICADO: {hechos} asignaciones quitadas.")
    print("Volvé a correr verificar_rubros.sql para ver cómo quedó.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
