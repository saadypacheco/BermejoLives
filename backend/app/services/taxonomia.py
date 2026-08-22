"""Revisión de la taxonomía de rubros contra lo que se vio en las vidrieras.

Los 54 rubros se escribieron ANTES de ver un solo comercio. Ahora hay 161
locales con productos detectados por IA, y eso permite juzgar la lista con
evidencia en vez de con intuición: qué rubro nadie usa, cuál es tan grande que
no filtra, qué productos no caen en ninguno, cuáles se pisan entre sí.

La forma es la misma que funcionó con los sinónimos y por las mismas razones:

- **Sobre el vocabulario agregado, no comercio por comercio.** La pregunta
  "¿falta un rubro?" no se responde mirando un local; se responde viendo que
  quince locales venden lo mismo y ninguno tiene dónde ir. Agregado, además, es
  una llamada en vez de 161.
- **Sin imágenes.** Los productos ya están escritos. Cuesta centavos.
- **No escribe nada.** Devuelve propuestas para que una persona decida. Cambiar
  la taxonomía reordena el mapa, los filtros y las búsquedas de todos los
  comercios a la vez; no es algo que deba pasar sin que alguien lo mire.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict

import structlog

logger = structlog.get_logger()

# Un producto que aparece una sola vez no sostiene ninguna conclusión sobre la
# taxonomía: puede ser un local raro o un error de lectura de la IA.
MIN_VECES = 2

# Cuántos productos se mandan por rubro. Con más, el prompt crece sin aportar:
# la cola larga de cada rubro no cambia si el rubro está bien definido o no.
TOP_POR_RUBRO = 15


def _terminos(comercio: dict) -> list[str]:
    crudos = (comercio.get("prod_det_ia") or "") + "," + (comercio.get("subcategoria") or "")
    salida = []
    for parte in crudos.split(","):
        t = re.sub(r"\s+", " ", parte.strip().lower())
        if len(t) >= 3:
            salida.append(t)
    return salida


def armar_evidencia(comercios: list[dict], relaciones: list[dict],
                    rubros: list[dict]) -> dict:
    """Resume qué se vende en cada rubro y qué quedó sin rubro.

    Devuelve un dict listo para meter en el prompt y para mostrarle a una
    persona: los mismos números que ve el modelo son los que se imprimen, así
    una propuesta rara se puede contrastar sin tener que confiar.
    """
    activos = {c["id"]: c for c in comercios if c.get("activo", True)}
    por_comercio: dict[str, list[str]] = defaultdict(list)
    for rel in relaciones:
        if rel["comercio_id"] in activos and rel["slug"] != "otros":
            por_comercio[rel["comercio_id"]].append(rel["slug"])

    nombres = {r["slug"]: r.get("nombre", r["slug"]) for r in rubros}
    vocabulario: dict[str, Counter] = defaultdict(Counter)
    cuenta: Counter = Counter()
    huerfanos: Counter = Counter()

    for cid, comercio in activos.items():
        slugs = por_comercio.get(cid, [])
        terminos = _terminos(comercio)
        if not slugs:
            # Sin rubro real: su vocabulario es la evidencia más directa de qué
            # categoría falta.
            huerfanos.update(terminos)
            continue
        for slug in slugs:
            cuenta[slug] += 1
            vocabulario[slug].update(terminos)

    return {
        "rubros": [
            {
                "slug": slug,
                "nombre": nombres.get(slug, slug),
                "comercios": cuenta[slug],
                "productos": [t for t, n in vocabulario[slug].most_common(TOP_POR_RUBRO)
                              if n >= MIN_VECES],
            }
            for slug in sorted(cuenta, key=lambda s: -cuenta[s])
        ],
        "vacios": [{"slug": r["slug"], "nombre": r.get("nombre", r["slug"])}
                   for r in rubros if r["slug"] not in cuenta and r["slug"] != "otros"],
        "sin_rubro": [{"termino": t, "veces": n}
                      for t, n in huerfanos.most_common(40) if n >= MIN_VECES],
        "total_comercios": len(activos),
    }


def _prompt(ev: dict) -> str:
    def bloque(r):
        return (f"- {r['nombre']} ({r['slug']}): {r['comercios']} comercios. "
                f"Vende: {', '.join(r['productos']) or '(sin productos detectados)'}")

    usados = "\n".join(bloque(r) for r in ev["rubros"])
    vacios = "\n".join(f"- {v['nombre']} ({v['slug']})" for v in ev["vacios"]) or "(ninguno)"
    sueltos = ", ".join(f"{h['termino']} ({h['veces']})" for h in ev["sin_rubro"]) or "(ninguno)"

    return f"""Sos quien diseña las categorías de un directorio de comercios de
Bermejo, Bolivia. Abajo está la taxonomía actual y, al lado de cada categoría,
los productos que se vieron REALMENTE en las vidrieras de esos locales.

Total de comercios relevados: {ev['total_comercios']}.

CATEGORÍAS EN USO:
{usados}

CATEGORÍAS SIN NINGÚN COMERCIO:
{vacios}

PRODUCTOS DE LOCALES QUE NO ENTRARON EN NINGUNA CATEGORÍA:
{sueltos}

Revisá esta taxonomía y devolvé SOLO un JSON, sin markdown:
{{
  "crear":    [{{"nombre": "", "porque": "", "productos": "", "comercios_estimados": 0}}],
  "dividir":  [{{"slug": "", "en": "nombre A, nombre B", "porque": ""}}],
  "fusionar": [{{"slugs": "slug1, slug2", "en": "", "porque": ""}}],
  "eliminar": [{{"slug": "", "porque": ""}}],
  "renombrar":[{{"slug": "", "a": "", "porque": ""}}]
}}

Criterios:
- Una categoría existe para que el comprador REDUZCA la lista. Si tiene más de
  un tercio de los comercios, no reduce nada y hay que dividirla — pero sólo si
  los productos muestran grupos claros adentro.
- `crear`: sólo si los productos sueltos, o los de una categoría demasiado
  grande, muestran un grupo de negocios que hoy no tiene dónde ir. Estimá
  cuántos comercios irían: si son menos de 3, NO lo propongas.
- `eliminar`: una categoría sin comercios puede ser un error de diseño (ese
  negocio no existe en Bermejo) o un hueco de relevamiento (existe y no se
  cargó). Proponé eliminar sólo las del primer caso, y decí cuál creés que es.
- `fusionar`: si dos categorías tienen casi los mismos productos, el comprador
  no sabe cuál elegir y se reparten los locales.
- `renombrar`: si el nombre no describe lo que realmente hay adentro según los
  productos.
- Cada propuesta tiene que apoyarse en los productos o los números de arriba.
  En `porque` citá la evidencia concreta, no una razón general. Si algo está
  bien como está, no lo toques: una taxonomía que cambia todo el tiempo obliga
  a reclasificar todo y confunde al que ya la conocía.
- Listas vacías si no hay nada que proponer. Es una respuesta válida."""


def revisar(evidencia: dict, post) -> dict:
    """Pide la revisión. `post` llama al modelo (se inyecta para poder probar)."""
    try:
        crudo = post(_prompt(evidencia))
    except Exception as e:  # noqa: BLE001
        logger.warning("taxonomia.fallo", error=str(e)[:200])
        return {"error": str(e)[:300]}

    limpio = (crudo or "").strip().strip("`").strip()
    if limpio.lower().startswith("json"):
        limpio = limpio[4:].strip()
    m = re.search(r"\{.*\}", limpio, re.S)
    try:
        datos = json.loads(m.group(0) if m else limpio)
    except Exception:  # noqa: BLE001
        return {"error": "el modelo no devolvió JSON", "crudo": (crudo or "")[:600]}

    return {k: (datos.get(k) or []) for k in
            ("crear", "dividir", "fusionar", "eliminar", "renombrar")}
