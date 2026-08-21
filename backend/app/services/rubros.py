"""Asignación de rubros a partir de lo que se cargó del negocio.

El problema real del campo: un local es amplio y el agente anota lo principal
que ve. Elegir rubros de una lista de 42 mientras se camina es inviable — en el
primer recorrido los 92 comercios quedaron en "Otros", y con eso la búsqueda por
categoría queda muerta.

La salida es invertir el orden: se carga lo que se ve (nombre + productos +
descripción) y el rubro se deduce de ahí. El vocabulario vive en la tabla
`rubro_palabras` y la deducción en la función SQL `rubros_sugeridos()`, así que
se puede corregir agregando filas, sin deploy.

Dos reglas que valen en todos los casos:

1. **Lo que eligió una persona nunca se pisa.** La deducción SUMA rubros, no
   reemplaza. Si en la segunda pasada el admin curó los rubros a mano, una
   reclasificación posterior no puede borrar ese trabajo.
2. **"otros" es un descarte, no un rubro.** Si se dedujo algo real, "otros" se
   saca: un comercio en "otros" no aparece en ninguna búsqueda por categoría.
"""
from __future__ import annotations

import structlog

from app.db.repository import Repo

logger = structlog.get_logger()

SLUG_DESCARTE = "otros"


def texto_para_rubros(comercio: dict) -> str:
    """El texto del que se deduce. Los tres campos juntos: da igual en cuál de
    ellos escribió el agente la palabra que importa."""
    return " ".join(filter(None, (
        comercio.get("nombre"),
        comercio.get("prod_obs_human"),
        comercio.get("prod_det_ia"),
        comercio.get("subcategoria"),
        comercio.get("descripcion"),
    )))


def resolver_rubros(repo: Repo, comercio: dict, elegidos: list[str] | None = None) -> list[str]:
    """Devuelve los slugs finales: los elegidos a mano + los deducidos del texto.

    Si no sale nada, cae a "otros" para no dejar el comercio sin rubro — pero es
    una señal de que la descripción no nombra productos concretos.
    """
    manuales = {s for s in (elegidos or []) if s and s != SLUG_DESCARTE}
    deducidos = set(repo.sugerir_rubros_por_texto(texto_para_rubros(comercio)))
    final = manuales | deducidos
    return sorted(final) if final else [SLUG_DESCARTE]


def aplicar_rubros(repo: Repo, comercio: dict, elegidos: list[str] | None = None) -> list[str]:
    """Resuelve y persiste. Devuelve los slugs que quedaron aplicados."""
    slugs = resolver_rubros(repo, comercio, elegidos)
    ids = [rid for rid in (repo.get_rubro_id(s) for s in slugs) if rid]
    if ids:
        repo.set_comercio_rubros(comercio["id"], ids)

    # Si se dedujo algo real, "otros" deja de tener sentido y molesta: hace que
    # el comercio figure en una categoría que no dice nada.
    if slugs != [SLUG_DESCARTE]:
        id_otros = repo.get_rubro_id(SLUG_DESCARTE)
        if id_otros:
            repo.quitar_rubro_comercio(comercio["id"], id_otros)

    # El rubro PRINCIPAL (comercios.rubro_id) es el que se ve en la ficha y en el
    # color del pin. Si el agente no eligió ninguno, queda el primero deducido:
    # sin esto el comercio se clasifica bien para el buscador pero se sigue
    # mostrando como "Otros" en pantalla.
    if not comercio.get("rubro_id") and slugs != [SLUG_DESCARTE]:
        principal = repo.get_rubro_id(slugs[0])
        if principal:
            repo.update_comercio(comercio["id"], {"rubro_id": principal}, None)

    logger.info("rubros.aplicados", comercio=comercio.get("slug") or comercio["id"], rubros=slugs)
    return slugs
