"""Completar los rubros que los productos de cada comercio sugieren.

Es la lógica que estaba dentro de `scripts/completar_rubros.py`. Se saca acá para
que el botón del panel y el script corran EXACTAMENTE lo mismo: dos copias de una
regla de clasificación se separan en semanas, y el día que difieran nadie va a
saber cuál de los dos informes creer.

El script sigue existiendo y ahora es una cáscara: en el servidor, con una
terminal, sigue siendo la forma más rápida de mirar esto sin abrir el navegador.
"""
from __future__ import annotations

from collections import defaultdict

import structlog

from app.db.repository import Repo

logger = structlog.get_logger()

# Un comercio con demasiados rubros no filtra: aparece en todas las categorías y
# ninguna dice nada de él. Si al sumarle los sugeridos pasa de acá, se saltea y
# queda para revisión humana.
MAX_RUBROS = 6

SLUG_DESCARTE = "otros"


class LecturaIncompleta(RuntimeError):
    """La lectura de `comercio_rubros` vino cortada.

    Es su propia excepción y no un campo más del informe porque NO se puede
    seguir: los comercios que quedaron afuera se leen como si no tuvieran
    ningún rubro, así que el informe les propone agregar de todo. Pasó — con
    1000 de 2440 filas, propuso 1295 rubros para 599 comercios que ya los
    tenían. Aplicar eso ensucia el filtro de los que estaban bien.
    """


def _texto_de(comercio: dict, con_sinonimos: bool) -> str:
    """Lo que se mira para clasificar.

    SIN `sinonimos` por defecto, y es la diferencia entre un informe usable y
    uno que hay que revisar entero. Los sinónimos existen para que el COMPRADOR
    encuentre —busca "polera" y aparece el que vende remeras—; clasificar es
    otra pregunta, y la respuesta ya está en `prod_det_ia`.

    Metidos acá arrastran por una palabra suelta de una frase entera: "ciclismo
    indoor" hacía de un gimnasio una bicicletería, "repuesto de celular" lo
    mandaba a repuestos de auto, "copa de vino" convertía una heladería en
    bebidas.
    """
    # `prod_obs_human` —lo que anotó el agente parado en la vereda— entró acá
    # para que este texto sea EL MISMO que usa el alta (`texto_para_rubros`).
    # Que difirieran es lo que hacía que la revisión juzgara los rubros con una
    # regla distinta de la que los había puesto.
    campos = [comercio.get("prod_det_ia"), comercio.get("subcategoria"),
              comercio.get("nombre"), comercio.get("prod_obs_human")]
    if con_sinonimos:
        campos.append(comercio.get("sinonimos"))
    return " ".join(filter(None, campos))


def analizar(repo: Repo, solo_rubros: set[str] | None = None,
             con_sinonimos: bool = False, tope_detalle: int = 200) -> dict:
    """Qué rubros agregaría, sin escribir nada.

    Lanza `LecturaIncompleta` si la lectura vino cortada. No devuelve un informe
    con una advertencia adentro: una advertencia se lee por arriba y el número
    grande se cree igual.
    """
    comercios = {c["id"]: c for c in repo.list_todos_comercios(None, 5000)
                 if c.get("activo", True)}
    relaciones = repo.list_comercio_rubros_todos()
    esperadas = repo.contar("comercio_rubros")
    if len(relaciones) < esperadas:
        raise LecturaIncompleta(
            f"Se leyeron {len(relaciones)} de {esperadas} asignaciones. Los comercios "
            "que quedaron afuera se leen como si no tuvieran ningún rubro, así que "
            "el informe propondría agregarles de todo.")

    actuales: dict[str, set[str]] = defaultdict(set)
    for rel in relaciones:
        if rel["comercio_id"] in comercios:
            actuales[rel["comercio_id"]].add(rel["slug"])

    agregar: list[dict] = []
    saltados = 0
    por_rubro: dict[str, int] = defaultdict(int)

    for cid, c in comercios.items():
        sugeridos = {s for s in repo.sugerir_rubros_por_texto(_texto_de(c, con_sinonimos))
                     if s != SLUG_DESCARTE}
        tiene = actuales.get(cid, set())
        faltan = sorted(sugeridos - tiene)
        if solo_rubros:
            faltan = [s for s in faltan if s in solo_rubros]
        if not faltan:
            continue
        if len(tiene | set(faltan)) > MAX_RUBROS:
            saltados += 1
            continue
        for s in faltan:
            por_rubro[s] += 1
        agregar.append({
            "comercio_id": cid,
            "codigo": c.get("codigo"),
            "nombre": c.get("nombre"),
            "vende": (c.get("prod_det_ia") or "")[:120],
            "tiene": sorted(tiene),
            "agregar": faltan,
        })

    return {
        "comercios": len(comercios),
        "asignaciones_leidas": len(relaciones),
        "asignaciones_en_tabla": esperadas,
        "comercios_a_completar": len(agregar),
        "rubros_a_agregar": sum(len(a["agregar"]) for a in agregar),
        "salteados": saltados,
        "por_rubro": sorted(({"slug": s, "comercios": n} for s, n in por_rubro.items()),
                            key=lambda x: -x["comercios"]),
        "detalle": agregar[:tope_detalle],
        # Cuántos quedaron fuera del detalle: sin este número, una lista de 200
        # se lee como "eso es todo" cuando son 600.
        "detalle_recortado": max(0, len(agregar) - tope_detalle),
        "_todos": agregar,
    }


def aplicar(repo: Repo, informe: dict) -> int:
    """Escribe lo que `analizar` propuso. Devuelve cuántos rubros se agregaron.

    Recibe el informe en vez de recalcular: así lo que se aplica es exactamente
    lo que se miró. Recalcular abre la ventana —chica pero real— de que alguien
    edite un comercio en el medio y se escriba algo que nadie revisó.
    """
    hechos = 0
    for item in informe["_todos"]:
        nuevos = [rid for rid in (repo.get_rubro_id(s) for s in item["agregar"]) if rid]
        if not nuevos:
            continue
        # `set_comercio_rubros` REEMPLAZA el conjunto, así que se manda la unión:
        # mandar sólo los nuevos borraría los que el comercio ya tenía.
        previos = [rid for rid in (repo.get_rubro_id(s) for s in item["tiene"]) if rid]
        repo.set_comercio_rubros(item["comercio_id"], list(dict.fromkeys(previos + nuevos)))
        hechos += len(nuevos)
    logger.info("rubros_auto.aplicado", rubros=hechos, comercios=len(informe["_todos"]))
    return hechos
