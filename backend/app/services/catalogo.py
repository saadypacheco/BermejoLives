"""Qué hay cargado y qué falta: rubros, productos, y los huecos de cada uno.

El panel muestra bien lo que existe y es ciego a lo que no. Esta vista invierte
eso: al lado de cada rubro con comercios va la lista de los que están vacíos, y
al lado del vocabulario cargado van las palabras que la gente buscó y no
encontró.

Los dos huecos NO son lo mismo, y confundirlos lleva a trabajar al pepe:

- **Un rubro vacío** puede ser un negocio que en Bermejo no existe —y entonces
  la categoría sobra— o uno que existe y todavía no se relevó. Sólo lo sabe
  quien camina la ciudad; el sistema no puede distinguirlos, así que los
  muestra y no opina.

- **Un término buscado sin resultado** es distinto: alguien lo escribió. Eso es
  demanda medida, no supuesta, y es la mejor lista de a qué comercios salir a
  buscar.

Se arma en memoria a partir de lo que ya está cargado. Con 203 comercios y unos
cientos de términos, contar acá es más simple que mantener consultas agregadas,
y `informe()` avisa cuando el volumen crezca lo bastante como para que convenga
pasarlo a SQL.
"""
from __future__ import annotations

import re
from collections import Counter

from app.db.repository import Repo
from app.services.normalizar import sin_tildes

SLUG_DESCARTE = "otros"

# A partir de acá, contar en memoria deja de ser gratis y conviene una consulta
# agregada. Se avisa en la respuesta en vez de degradarse en silencio.
UMBRAL_AVISO = 5000


def _terminos(comercio: dict) -> list[str]:
    """Los productos y la subcategoría de un comercio, normalizados."""
    crudo = (comercio.get("prod_det_ia") or "") + "," + (comercio.get("subcategoria") or "")
    salida: list[str] = []
    for parte in crudo.split(","):
        t = re.sub(r"\s+", " ", sin_tildes(parte).strip().lower())
        if len(t) >= 3 and t not in salida:
            salida.append(t)
    return salida


def informe(repo: Repo, limite_productos: int = 120) -> dict:
    comercios = [c for c in repo.list_todos_comercios(None, 5000) if c.get("activo", True)]
    activos = {c["id"] for c in comercios}
    rubros = repo.list_rubros()
    relaciones = repo.list_comercio_rubros_todos()

    por_rubro: Counter = Counter()
    for rel in relaciones:
        if rel.get("comercio_id") in activos:
            por_rubro[rel["slug"]] += 1

    filas_rubros = [
        {
            "slug": r["slug"],
            "nombre": r.get("nombre", r["slug"]),
            "comercios": por_rubro.get(r["slug"], 0),
            "descarte": r["slug"] == SLUG_DESCARTE,
        }
        for r in rubros
    ]
    # Los vacíos primero dentro de su grupo: son los que piden una decisión.
    filas_rubros.sort(key=lambda x: (-x["comercios"], x["nombre"]))

    productos: Counter = Counter()
    for c in comercios:
        productos.update(_terminos(c))

    # Lo que se buscó y no encontró. Es la única lista de este informe que sale
    # de gente real y no de lo que nosotros cargamos.
    try:
        sin_resultado = repo.kpis_admin().get("sin_resultado") or []
    except Exception:  # noqa: BLE001 — el catálogo vale igual sin las búsquedas
        sin_resultado = []

    vacios = [r for r in filas_rubros if r["comercios"] == 0 and not r["descarte"]]

    return {
        "rubros": filas_rubros,
        "rubros_vacios": len(vacios),
        "productos": [{"termino": t, "comercios": n} for t, n in productos.most_common(limite_productos)],
        "productos_distintos": len(productos),
        # Un producto que aparece en un solo local no es un catálogo: es un dato
        # suelto. Se cuenta aparte porque cambia cómo se lee la lista de arriba.
        "productos_unicos": sum(1 for n in productos.values() if n == 1),
        "buscado_sin_resultado": sin_resultado,
        "comercios": len(comercios),
        "conviene_sql": len(comercios) > UMBRAL_AVISO,
    }
