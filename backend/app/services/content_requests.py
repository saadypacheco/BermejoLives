"""Pedir un video a mano: de un negocio o de un rubro en una ciudad (docs/contenido-redes-tecnico.md §17.3).

Además de la semana automática (`content_selector`), alguien del panel puede pedir un video:

- `kind = comercio`: «el video de este negocio». Pieza `comercio_del_dia`, con 4 a 6 fotos del comercio.
- `kind = rubro`: «zapatillas en Bermejo». Pieza `rubro`: una foto por comercio (el chip es su nombre), 4 a 6 comercios.

Las piezas pedidas (`origin = 'pedido'`) NO cuentan cuota, NO crean tareas de suscriptor y NO ocupan un lugar
del calendario (`scheduled_for` = hoy). Se aprueban, publican y retiran igual que las demás: la autorización
de cada comercio se mira de todas las fuentes (`content_consent`).

Tope: no puede haber más de 5 pedidos armándose a la vez (429). Nada de lo que sale al público cuenta
cuántos comercios hay en un rubro: `eligible` es sólo para el panel interno.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date

import structlog
from fastapi import HTTPException

from app.services import cargas, content_captions, content_consent, content_selector as sel, content_video_texts

logger = structlog.get_logger()

#: Cuántos pedidos pueden estar `queued` o `rendering` a la vez.
MAX_ARMANDOSE = 5
#: Un video de rubro lleva de 4 a 6 comercios (una foto de cada uno).
MIN_COMERCIOS_RUBRO = sel.MIN_FOTOS
MAX_COMERCIOS_RUBRO = sel.MAX_FOTOS_COMERCIO

MSG_TOPE = "Ya hay 5 videos pedidos armándose; esperá a que terminen"
MSG_INACTIVO = "El comercio no está activo"
MSG_SIN_AUTORIZACION = "El comercio no tiene autorización vigente para aparecer en las redes"


def _msg_pocas_fotos(n: int) -> str:
    return f"Tiene {n} fotos que sirven: subí al menos 4 en Banco de contenido"


def _msg_pocos_comercios(n: int) -> str:
    return f"Hay {n} comercios de ese rubro con autorización y foto; hacen falta 4"


class _FotosPrecargadas:
    """Hace pasar por un repo a las fotos de un grupo de comercios leídas en lote, así `elegir_fotos` no consulta la
    base una vez por comercio (el panel mira la ciudad entera para contar los rubros)."""

    def __init__(self, crepo, comercio_ids: list[str]):
        self._assets: dict[str, list[dict]] = defaultdict(list)
        self._galeria: dict[str, list[dict]] = defaultdict(list)
        if comercio_ids:
            for a in crepo.list_assets(comercio_ids):
                self._assets[a["comercio_id"]].append(a)
            for g in crepo.gallery_photos(comercio_ids):
                self._galeria[g["comercio_id"]].append(g)

    def list_assets(self, comercio_ids, only_active=True):
        return [a for i in comercio_ids for a in self._assets.get(i, [])]

    def gallery_photos(self, comercio_ids):
        return [g for i in comercio_ids for g in self._galeria.get(i, [])]

    def list_offers(self, since_iso, comercio_id=None):
        return []


# ──────────────────────────────────────────────────────────── un negocio

def diagnostico_comercio(crepo, comercio: dict, hoy: date, usadas: set[tuple] | None = None) -> dict:
    """Si se puede pedir el video de este comercio: `{consent, usable_photos, ok, reason, fotos}`.

    `usable_photos` son las fotos que `elegir_fotos` daría hoy (con las mismas reglas que el selector, hasta 6).
    `reason` es el motivo del 422, o None si `ok`."""
    consent = content_consent.esta_autorizado(crepo, comercio["id"])
    usadas = sel.claves_usadas(crepo, hoy) if usadas is None else usadas
    fotos = sel.elegir_fotos(crepo, comercio, sel.MAX_FOTOS_COMERCIO, hoy, usadas)
    if comercio.get("activo") is False:
        motivo = MSG_INACTIVO
    elif not consent:
        motivo = MSG_SIN_AUTORIZACION
    elif len(fotos) < sel.MIN_FOTOS:
        motivo = _msg_pocas_fotos(len(fotos))
    else:
        motivo = None
    return {"consent": consent, "usable_photos": len(fotos), "ok": motivo is None, "reason": motivo, "fotos": fotos}


def _exigir_cupo(crepo) -> None:
    if crepo.count_pending_requests() >= MAX_ARMANDOSE:
        raise HTTPException(status_code=429, detail=MSG_TOPE)


def pedir_comercio(crepo, comercio_id: str, actor: str, ciudad_permitida: str | None = None,
                   hoy: date | None = None) -> dict:
    """El video de UN negocio. 404 si no existe (o es de otra ciudad para un agente), 429 si hay 5 pedidos
    armándose, 422 con el motivo si no se puede. Devuelve la pieza creada (`queued`)."""
    hoy = hoy or cargas.hoy_bolivia()
    comercio = crepo.get_comercio_ficha(comercio_id)
    if not comercio or (ciudad_permitida and (comercio.get("ciudades") or {}).get("slug") != ciudad_permitida):
        raise HTTPException(status_code=404, detail="Comercio no encontrado")
    _exigir_cupo(crepo)
    diag = diagnostico_comercio(crepo, comercio, hoy)
    if not diag["ok"]:
        raise HTTPException(status_code=422, detail=diag["reason"])
    fotos = diag["fotos"]
    facts = content_captions.build_facts_comercio(comercio)
    textos = content_captions.generate_captions(facts, crepo=crepo)
    prop = content_video_texts.proponer({"pillar": "comercio_del_dia", "facts": facts}, fotos, comercio, crepo=crepo)
    fotos, _ = content_video_texts.aplicar_en_memoria(fotos, prop, "comercio_del_dia")
    fila = sel._fila_de_pieza(sel.lunes_de(hoy), hoy, "comercio_del_dia", facts, textos, actor, comercio,
                              video=content_video_texts.campos_de_pieza("comercio_del_dia", facts, prop),
                              origin="pedido")
    pieza = sel._guardar_pieza(crepo, fila, fotos)
    if pieza is None:
        raise HTTPException(status_code=409, detail="No se pudo crear el pedido, probá de nuevo")
    logger.info("content.pedido_creado", kind="comercio", pieza=pieza["id"], comercio=comercio_id, por=actor,
                fotos=len(fotos))
    return pieza


# ───────────────────────────────────────────────────────────── un rubro

def _elegibles_de_ciudad(crepo, ciudad_id: str, hoy: date) -> tuple[list[dict], list[dict], dict[str, set[str]]]:
    """(comercios activos de la ciudad, los elegibles, rubros de cada elegible).

    Un elegible es un comercio activo de la ciudad con autorización vigente y al menos una foto que sirve (banco
    más reciente > portada > galería; las mismas reglas de tamaño, disco y repetición que el selector). Cada uno:
    `{comercio, foto, suscriptor}`. Los rubros de un comercio son el principal y los secundarios."""
    comercios = crepo.list_comercios_activos(ciudad_id=ciudad_id)
    autorizados = content_consent.autorizados(crepo)
    con_permiso = [c for c in comercios if c["id"] in autorizados]
    pre = _FotosPrecargadas(crepo, [c["id"] for c in con_permiso])
    usadas = sel.claves_usadas(crepo, hoy)
    planes = {p["slug"]: p for p in crepo.list_planes()}
    elegibles = []
    for c in con_permiso:
        fotos = sel.elegir_fotos(pre, c, 1, hoy, usadas, preferir_banco=True, con_ofertas=False)
        if fotos:
            elegibles.append({"comercio": c, "foto": fotos[0],
                              "suscriptor": sel.es_suscriptor(c, sel.plan_del(c, planes), hoy)})
    rubros_de: dict[str, set[str]] = {e["comercio"]["id"]: ({e["comercio"]["rubro_id"]} if e["comercio"].get("rubro_id") else set())
                                      for e in elegibles}
    if elegibles:
        for fila in crepo.list_comercio_rubros(list(rubros_de)):
            rubros_de[fila["comercio_id"]].add(fila["rubro_id"])
    return comercios, elegibles, rubros_de


def _ciudad_o_404(crepo, ciudad_slug: str) -> dict:
    ciudad = next((c for c in crepo.list_ciudades() if c["slug"] == ciudad_slug), None)
    if not ciudad:
        raise HTTPException(status_code=404, detail="Ciudad no encontrada")
    return ciudad


def opciones_de_ciudad(crepo, ciudad_slug: str, hoy: date | None = None) -> list[dict]:
    """`[{slug, nombre, eligible, eligible_count}]` de los rubros comerciales de la ciudad, para el modal de
    «Pedir un video».

    `eligible_count` = cuántos comercios cumplen las condiciones del video de rubro (autorización + foto que
    sirve) y `eligible` = alcanzan para el video (al menos 4). Sólo para el panel interno: NUNCA se muestran
    al público. Entran los rubros con algún comercio activo en la ciudad
    (de principal) o con algún elegible; los de más comercios elegibles, primero."""
    hoy = hoy or cargas.hoy_bolivia()
    ciudad = _ciudad_o_404(crepo, ciudad_slug)
    comercios, elegibles, rubros_de = _elegibles_de_ciudad(crepo, ciudad["id"], hoy)
    cuenta: dict[str, int] = defaultdict(int)
    for rubros in rubros_de.values():
        for rid in rubros:
            cuenta[rid] += 1
    presentes = {c["rubro_id"] for c in comercios if c.get("rubro_id")} | set(cuenta)
    out = [{"slug": r["slug"], "nombre": r["nombre"], "eligible": cuenta.get(r["id"], 0) >= MIN_COMERCIOS_RUBRO,
            "eligible_count": cuenta.get(r["id"], 0)}
           for r in crepo.list_rubros_comerciales() if r["id"] in presentes]
    return sorted(out, key=lambda r: (-r["eligible_count"], content_captions._plano(r["nombre"])))


def pedir_rubro(crepo, rubro_slug: str, ciudad_slug: str, actor: str, ciudad_permitida: str | None = None,
                hoy: date | None = None) -> dict:
    """El video de un rubro en una ciudad. 404 si el rubro o la ciudad no existen, 403 si un agente pide otra
    ciudad, 429 si hay 5 pedidos armándose, 422 con el motivo si no se puede. Devuelve la pieza creada (`queued`)."""
    hoy = hoy or cargas.hoy_bolivia()
    ciudad = _ciudad_o_404(crepo, ciudad_slug)
    if ciudad_permitida and ciudad["slug"] != ciudad_permitida:
        raise HTTPException(status_code=403, detail="Sólo podés pedir videos de tu ciudad")
    rubro = crepo.get_rubro_by_slug(rubro_slug)
    if not rubro:
        raise HTTPException(status_code=404, detail="Rubro no encontrado")
    if rubro.get("comercial") is False:
        raise HTTPException(status_code=422, detail="Ese rubro no es comercial: no tiene videos de comercios")
    _exigir_cupo(crepo)
    _, elegibles, rubros_de = _elegibles_de_ciudad(crepo, ciudad["id"], hoy)
    del_rubro = [e for e in elegibles if rubro["id"] in rubros_de[e["comercio"]["id"]]]
    if len(del_rubro) < MIN_COMERCIOS_RUBRO:
        raise HTTPException(status_code=422, detail=_msg_pocos_comercios(len(del_rubro)))
    # Suscriptores primero y, dentro de cada grupo, los de la foto más reciente.
    del_rubro.sort(key=lambda e: str(e["foto"].get("created_at") or ""), reverse=True)
    del_rubro.sort(key=lambda e: not e["suscriptor"])
    elegidos = del_rubro[:MAX_COMERCIOS_RUBRO]

    facts = content_captions.build_facts_rubro(
        {"nombre": rubro["nombre"], "slug": rubro["slug"]}, ciudad,
        [{"nombre": e["comercio"].get("nombre"), "slug": e["comercio"].get("slug")} for e in elegidos])
    fuentes = []
    for e, item in zip(elegidos, facts["items"]):
        nombre = item.get("nombre", "")
        f = e["foto"]
        fuentes.append({"source_type": f["source_type"], "source_id": f.get("source_id"), "comercio_id": e["comercio"]["id"],
                        "file_ref": f["file_ref"], "caption_fact": nombre[:80],
                        "chip_text": content_video_texts.chip_de_nombre(nombre)})
    textos = content_captions.generate_captions(facts, crepo=crepo)
    prop = content_video_texts.proponer({"pillar": "rubro", "facts": facts}, fuentes, crepo=crepo)
    fuentes, _ = content_video_texts.aplicar_en_memoria(fuentes, prop, "rubro")
    fila = sel._fila_de_pieza(sel.lunes_de(hoy), hoy, "rubro", facts, textos, actor, ciudad_id=ciudad["id"],
                              video=content_video_texts.campos_de_pieza("rubro", facts, prop),
                              origin="pedido", rubro_id=rubro["id"])
    pieza = sel._guardar_pieza(crepo, fila, fuentes)
    if pieza is None:
        raise HTTPException(status_code=409, detail="No se pudo crear el pedido, probá de nuevo")
    logger.info("content.pedido_creado", kind="rubro", pieza=pieza["id"], rubro=rubro_slug, ciudad=ciudad_slug,
                por=actor, comercios=len(fuentes))
    return pieza

