"""«Qué hay acá» (docs/que-hay-aca.md): lo que el backend le arma a la primera pantalla del agente.

Tres cosas, todas sin precios:

  · `estado_plan`  — el sello de cada comercio (al día · de cortesía · gratis · vencido).
  · `fotos_count`  — cuántas fotos de galería tiene (alimenta «Le falta» sin pedir nada más).
  · `ejemplos`     — hasta 3 comercios COMPLETOS de la ciudad para mostrarle al dueño cómo se
                     ve un local bien cargado.

Y la regla de «completo» (`es_completo`), escrita una sola vez para que el frontend la copie.
"""
from __future__ import annotations

from datetime import date
from typing import Iterable

from app.services import cargas

#: Los cuatro sellos. Es todo lo que sale del backend: nunca el plan, el precio ni `paga_hasta`.
ESTADOS_PLAN = ("al_dia", "cortesia", "gratis", "vencido")

#: Fotos de galería mínimas para que un local cuente como completo.
MIN_FOTOS_COMPLETO = 3

#: Cuántos ejemplos se devuelven como máximo.
MAX_EJEMPLOS = 3

#: Columnas del comercio que sirven para calcular el plan y NO se devuelven al agente.
_COLUMNAS_PRIVADAS = ("plan", "plan_cortesia", "paga_hasta", "suspendido")


def _fecha(valor) -> date | None:
    if not valor:
        return None
    try:
        return date.fromisoformat(str(valor)[:10])
    except ValueError:
        return None


def estado_plan(comercio: dict, plan_pago: bool, hoy: date | None = None) -> str:
    """El sello de plan de un comercio: `al_dia`, `cortesia`, `gratis` o `vencido`.

    Es la misma regla que la estrella (migración 0143) y que Admin › Suscripciones:

        plan pago  = el plan tiene `precio_mes > 0`  (`plan_pago`, lo resuelve quien llama)
        al día     = plan_cortesia  OR  (paga_hasta >= hoy de Bolivia  AND  NOT suspendido)

      - plan NO pago                                   -> `gratis`
      - plan pago + suspendido                         -> `vencido` (suspendido nunca está al día,
                                                          tampoco la cortesía)
      - plan pago + `plan_cortesia`                    -> `cortesia` (sin cobro y sin vencimiento)
      - plan pago + `paga_hasta` de hoy en adelante    -> `al_dia`
      - plan pago + `paga_hasta` anterior a hoy        -> `vencido`
      - plan pago sin `paga_hasta` (nunca pagó)        -> `gratis`  (en Suscripciones: «sin plan»)

    «Hoy» es el de Bolivia, no el del servidor. No devuelve ni usa precios.
    """
    if not plan_pago:
        return "gratis"
    if comercio.get("suspendido"):
        return "vencido"
    if comercio.get("plan_cortesia"):
        return "cortesia"
    hasta = _fecha(comercio.get("paga_hasta"))
    if hasta is None:
        return "gratis"
    return "al_dia" if hasta >= (hoy or cargas.hoy_bolivia()) else "vencido"


def rubro_de(comercio: dict) -> tuple[str | None, str | None]:
    """(slug, nombre) del rubro principal. `rubros` llega como objeto embebido
    (`rubros!comercios_rubro_id_fkey(nombre, slug)`); si llegara como lista de slugs, el primero."""
    r = comercio.get("rubros")
    if isinstance(r, dict):
        return (r.get("slug") or None), (r.get("nombre") or None)
    if isinstance(r, list) and r and isinstance(r[0], str):
        return r[0], None
    return None, None


def _lleno(valor) -> bool:
    return bool(str(valor).strip()) if valor is not None else False


def es_completo(comercio: dict, fotos_count: int) -> bool:
    """¿Es un comercio «completo» para usarlo de ejemplo?

    Es el mismo criterio que «Le falta» de Completar comercio, exigiendo además galería:

      1. portada            `portada_url` con valor
      2. WhatsApp           `whatsapp` con valor (no alcanza el `telefono`)
      3. horario            `horario` con valor
      4. galería            `fotos_count >= 3`
      5. lo que vende       `prod_obs_human` con valor, o si no `descripcion`

    Un texto de puros espacios cuenta como vacío. Los cinco, todos: con uno solo que falte
    no es completo. (El comercio tiene que estar además activo y no suspendido; eso lo
    filtra la consulta de candidatos, no esta función.)
    """
    return (
        _lleno(comercio.get("portada_url"))
        and _lleno(comercio.get("whatsapp"))
        and _lleno(comercio.get("horario"))
        and int(fotos_count or 0) >= MIN_FOTOS_COMPLETO
        and (_lleno(comercio.get("prod_obs_human")) or _lleno(comercio.get("descripcion")))
    )


def _plan_pago_de(repo, slugs: Iterable[str | None]) -> dict[str, bool]:
    """slug del plan -> ¿es pago (`precio_mes > 0`)? Una lectura de `planes` y, sólo para un
    slug que no esté entre los activos (plan dado de baja), una por slug."""
    def pago(plan: dict | None) -> bool:
        try:
            return float((plan or {}).get("precio_mes") or 0) > 0
        except (TypeError, ValueError):
            return False

    por_slug = {p["slug"]: pago(p) for p in repo.list_planes()}
    for slug in {(s or "gratis") for s in slugs}:
        if slug not in por_slug:
            por_slug[slug] = pago(repo.get_plan(slug))
    return por_slug


def enriquecer(repo, comercios: list[dict]) -> list[dict]:
    """Copia de cada comercio con `estado_plan`, `fotos_count` y `rubro_slug`, SIN las columnas
    que usó para calcularlas (`plan`, `plan_cortesia`, `paga_hasta`, `suspendido`).

    Rendimiento: es la lista de toda la ciudad. Los planes se leen una vez y las fotos se
    cuentan en UNA consulta agrupada (`contar_fotos_comercios`), no una por comercio."""
    if not comercios:
        return []
    hoy = cargas.hoy_bolivia()
    pagos = _plan_pago_de(repo, (c.get("plan") for c in comercios))
    fotos = repo.contar_fotos_comercios([c["id"] for c in comercios])
    salida = []
    for c in comercios:
        limpio = {k: v for k, v in c.items() if k not in _COLUMNAS_PRIVADAS}
        limpio["estado_plan"] = estado_plan(c, pagos.get(c.get("plan") or "gratis", False), hoy)
        limpio["fotos_count"] = int(fotos.get(str(c["id"]), 0))
        limpio["rubro_slug"] = rubro_de(c)[0]
        salida.append(limpio)
    return salida


def _item_ejemplo(c: dict) -> dict:
    return {
        "id": c["id"],
        "slug": c.get("slug"),
        "nombre": c.get("nombre"),
        "rubro_nombre": rubro_de(c)[1],
        "portada_thumb_url": c.get("portada_thumb_url") or c.get("portada_url"),
    }


def ejemplos(repo, ciudad_id: str, rubro_slug: str | None = None,
             excluir_id: str | None = None, limite: int = MAX_EJEMPLOS) -> list[dict]:
    """Hasta `limite` comercios COMPLETOS (ver `es_completo`) de la ciudad, para mostrar de ejemplo.

    Prefiere los del mismo rubro; si no alcanzan, completa con los de otros rubros. Nunca
    devuelve `excluir_id` (el comercio que el agente tiene abierto)."""
    elegidos: list[dict] = []
    vistos = {str(excluir_id)} if excluir_id else set()

    def sumar(candidatos: list[dict]) -> None:
        nuevos = [c for c in candidatos if str(c["id"]) not in vistos]
        if not nuevos:
            return
        fotos = repo.contar_fotos_comercios([c["id"] for c in nuevos])
        for c in nuevos:
            vistos.add(str(c["id"]))
            if len(elegidos) < limite and es_completo(c, fotos.get(str(c["id"]), 0)):
                elegidos.append(c)

    rubro_id = repo.get_rubro_id(rubro_slug) if rubro_slug else None
    if rubro_id:
        sumar(repo.list_ejemplos_candidatos(ciudad_id, rubro_id))
    if len(elegidos) < limite:
        sumar(repo.list_ejemplos_candidatos(ciudad_id, None))
    return [_item_ejemplo(c) for c in elegidos]
