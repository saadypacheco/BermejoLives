"""El selector semanal de piezas (docs/contenido-redes-tecnico.md §7).

QUÉ HACE
========
El domingo a las 20:00 (Bolivia) arma la semana que arranca mañana: martes, miércoles y viernes
«comercio del día» (un suscriptor, que consume su cuota), jueves «ofertas de la semana» (un
compilado de hasta 6 ofertas de una ciudad). El lunes y el sábado se suman sólo si lo que se debe
a los suscriptores lo pide. Sin autorización de redes vigente nadie entra; sin 4 fotos que sirvan
tampoco (y queda una tarea `photo_refresh` para pedirlas).

IDEMPOTENTE
===========
Un lugar del calendario es una pieza viva (`uq_content_pieces_slot`): correrlo dos veces no
duplica, y lo que quedó sin cubrir se puede completar corriéndolo de nuevo (recuperación). Una
pieza `skipped` o `failed` no ocupa el lugar y no consume cuota: la semana siguiente se vuelve a ofrecer.

EL CICLO DE LA CUOTA
====================
`quota_cycle_start` es el ciclo de cobro al que se imputa la pieza (lección `cuota-snapshot`).
Sale de `planes.inicio_del_ciclo` cuando el comercio tiene `paga_hasta`. Sin `paga_hasta`
(cortesía) ese ciclo se movería todos los días y la cuota nunca se agotaría: se usa el mes calendario.
"""
from __future__ import annotations

import re
import time
from datetime import date, datetime, timedelta, timezone

import structlog
from fastapi import HTTPException

from app.core.codigo import _RE_CON_PREFIJO
from app.core.config import settings
from app.services import (cargas, content_captions, content_consent, content_posts, content_storage,
                          content_video_texts, fotos_galeria, planes)

logger = structlog.get_logger()

MIN_FOTOS = 4
#: El video v2 lleva de 4 a 6 fotos (§16.4).
MAX_FOTOS_COMERCIO = 6
MAX_OFERTAS = 6
MIN_OFERTAS = 4
#: Las fotos que salieron en una pieza no se repiten durante estos días.
NO_REPETIR_DIAS = 60
#: Una oferta tiene que ser de los últimos 10 días para entrar al compilado.
OFERTA_DIAS = 10
SEPARACION_DIAS = 14
SEPARACION_URGENTE_DIAS = 5
#: Un día que se debe tanto como esto abre el sábado (>3) o el lunes (>4).
UMBRAL_SABADO = 3
UMBRAL_LUNES = 4

# Lunes = 0. (día, pilar, condición)
CALENDARIO = ((1, "comercio_del_dia", "siempre"), (2, "comercio_del_dia", "siempre"),
              (3, "ofertas", "siempre"), (4, "comercio_del_dia", "siempre"),
              (5, "comercio_del_dia", "sabado"), (0, "comercio_del_dia", "lunes"))

DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


def lunes_de(d: date) -> date:
    return d - timedelta(days=d.weekday())


# ───────────────────────────────────────────────────── cuándo planificar

def week_to_plan(ahora: datetime | None = None, planned: set[str] | None = None) -> date | None:
    """El lunes de la semana a planificar AHORA, o None si no toca.

    El domingo desde las 20:00 (hora de Bolivia): la semana que arranca mañana. Cualquier otro
    momento: la semana actual (recuperación: «los días que faltan desde hoy»), si todavía no tiene
    piezas creadas por el selector. El domingo antes de las 20:00 no hay lugares de esta semana
    que planificar."""
    ahora_bo = (ahora or cargas.ahora_utc()).astimezone(cargas.BOLIVIA)
    hoy = ahora_bo.date()
    lunes = lunes_de(hoy)
    planned = planned or set()
    if hoy.weekday() == settings.content_planning_weekday and ahora_bo.hour >= settings.content_planning_hour:
        objetivo = lunes + timedelta(days=7)
    elif hoy.weekday() == settings.content_planning_weekday:
        return None
    else:
        objetivo = lunes
    return None if objetivo.isoformat() in planned else objetivo


def is_planning_due(ahora: datetime | None = None, planned: set[str] | None = None) -> bool:
    return week_to_plan(ahora, planned) is not None


#: Último intento por semana: el selector puede no crear nada (sin candidatos) y no tiene que
#: repetir toda la consulta cada 15 minutos.
_ultimo_intento: dict[str, float] = {}
ESPERA_ENTRE_INTENTOS_SEG = 3600


def planner_tick(repo, crepo, ahora: datetime | None = None) -> dict | None:
    """Una vuelta del loop de planificación. Devuelve el resumen del plan si corrió."""
    ahora = ahora or cargas.ahora_utc()
    hoy = cargas.hoy_bolivia(ahora)
    planned = crepo.weeks_planned_by_selector((lunes_de(hoy) - timedelta(days=7)).isoformat())
    semana = week_to_plan(ahora, planned)
    if semana is None:
        return None
    clave = semana.isoformat()
    if time.monotonic() - _ultimo_intento.get(clave, -1e9) < ESPERA_ENTRE_INTENTOS_SEG:
        return None
    _ultimo_intento[clave] = time.monotonic()
    resumen = plan_week(repo, crepo, semana, "selector", ahora)
    logger.info("content.planificacion", semana=clave, creadas=resumen["created"],
                vacios=len(resumen["slots_left_empty"]), tareas=resumen["tasks_created"])
    return resumen


def reiniciar_intentos() -> None:
    _ultimo_intento.clear()


# ─────────────────────────────────────────────────────────── suscriptores

def cuota_del_plan(plan: dict | None) -> int:
    try:
        return max(0, int((plan or {}).get("social_pieces_per_month") or 0))
    except (TypeError, ValueError):
        return 0


def plan_del(comercio: dict, planes_por_slug: dict) -> dict:
    slug = (comercio.get("plan") or "gratis").strip() or "gratis"
    return planes_por_slug.get(slug) or planes_por_slug.get("gratis") or {}


def en_gracia(comercio: dict, hoy: date) -> bool:
    """Vencido hace menos de `CONTENT_GRACE_DAYS`: todavía se le arma la pieza del mes."""
    hasta = _fecha(comercio.get("paga_hasta"))
    return hasta is not None and hasta >= hoy - timedelta(days=settings.content_grace_days)


def es_suscriptor(comercio: dict, plan: dict, hoy: date) -> bool:
    """Activo, no suspendido, con piezas en su plan y al día (o dentro de la gracia)."""
    if comercio.get("activo") is False or comercio.get("suspendido"):
        return False
    if cuota_del_plan(plan) <= 0:
        return False
    return fotos_galeria.al_dia(comercio, hoy) or en_gracia(comercio, hoy)


def ciclo_de(comercio: dict, hoy: date) -> tuple[date, date]:
    """(inicio, fin) del ciclo de cobro. Ver el docstring del módulo.

    En GRACIA (vencido hace menos de `CONTENT_GRACE_DAYS`) el ciclo es el que TERMINA en `paga_hasta`: la
    pieza que se le está armando es la cuota pendiente del ciclo que ya pagó. Si se usara el ciclo "de
    hoy" (que arranca el día del vencimiento), la cuota se reiniciaría y se le agendaría otra de más."""
    if comercio.get("paga_hasta"):
        hasta = _fecha(comercio.get("paga_hasta"))
        if hasta and hasta < hoy and en_gracia(comercio, hoy) and not comercio.get("plan_cortesia"):
            return hasta - timedelta(days=30), hasta
        inicio = planes.inicio_del_ciclo(comercio, hoy)
        return inicio, inicio + timedelta(days=30)
    inicio = hoy.replace(day=1)
    siguiente = (inicio + timedelta(days=32)).replace(day=1)
    return inicio, siguiente


def _fecha(valor) -> date | None:
    try:
        return date.fromisoformat(str(valor)[:10])
    except (TypeError, ValueError):
        return None


def usadas_en_ciclo(piezas_propias: list[dict], inicio: date) -> int:
    """Cuántas piezas del comercio ya consumen la cuota del ciclo que arrancó en `inicio`.
    `piezas_propias`: las piezas vivas de UN comercio (`list_own_pieces_since`)."""
    return sum(1 for p in piezas_propias
               if p.get("counts_for_quota") and p.get("quota_cycle_start") == inicio.isoformat())


def ultimo_dia_agendable(comercio: dict) -> date | None:
    """Hasta cuándo se le puede agendar una pieza: `paga_hasta` + la gracia. None si no tiene vencimiento
    (cortesía o sin pagar): ahí no hay tope."""
    if comercio.get("plan_cortesia"):
        return None
    hasta = _fecha(comercio.get("paga_hasta"))
    return hasta + timedelta(days=settings.content_grace_days) if hasta else None


def evaluar_suscriptores(crepo, hoy: date, autorizados: set[str] | None = None) -> list[dict]:
    """Todos los suscriptores de hoy con su cuota, lo usado y lo que se debe.

    Cada item: `{comercio, plan, cuota, ciclo_inicio, ciclo_fin, usadas, debe, ultima, dias_restantes,
    autorizado}`."""
    por_slug = {p["slug"]: p for p in crepo.list_planes()}
    con_cuota = [s for s, p in por_slug.items() if cuota_del_plan(p) > 0]
    if not con_cuota:
        return []
    comercios = crepo.list_comercios_activos(planes=con_cuota)
    propias = crepo.list_own_pieces_since((hoy - timedelta(days=90)).isoformat())
    out = []
    for c in comercios:
        plan = plan_del(c, por_slug)
        if not es_suscriptor(c, plan, hoy):
            continue
        inicio, fin = ciclo_de(c, hoy)
        mias = [p for p in propias if p["comercio_id"] == c["id"]]
        usadas = usadas_en_ciclo(mias, inicio)
        ultima = max((p["scheduled_for"] for p in mias), default=None)
        cuota = cuota_del_plan(plan)
        out.append({"comercio": c, "plan": plan, "cuota": cuota, "ciclo_inicio": inicio, "ciclo_fin": fin,
                    "usadas": usadas, "debe": max(0, cuota - usadas), "ultima": ultima,
                    "dias_restantes": (fin - hoy).days,
                    "autorizado": True if autorizados is None else c["id"] in autorizados})
    return out


# ───────────────────────────────────────────────────────── elegir fotos

def _clave_de_uso(c: dict) -> tuple:
    return (c["source_type"], c.get("source_id") or c.get("file_ref"))


def claves_usadas(crepo, hoy: date) -> set[tuple]:
    return {_clave_de_uso({"source_type": s["source_type"], "source_id": s.get("source_id"),
                           "file_ref": s.get("file_ref")})
            for s in crepo.recent_sources((hoy - timedelta(days=NO_REPETIR_DIAS)).isoformat())}


def elegir_fotos(crepo, comercio: dict, maximo: int, hoy: date, usadas: set[tuple],
                 excluir: set[tuple] | None = None, *, preferir_banco: bool = False,
                 con_ofertas: bool = True) -> list[dict]:
    """Las fotos para una pieza de este comercio, en este orden: portada, banco (más nuevas primero),
    galería (sin las que son copia de una del banco) y ofertas aprobadas de los últimos 90 días.

    Se descartan las usadas en una pieza viva o publicada en los últimos 60 días y las de lado menor
    < 720 px (leído del encabezado, sin decodificar). Una foto que no está en el disco no sirve.
    Cada item: `{source_type, source_id, file_ref, comercio_id, created_at}` (`created_at` es de la foto del
    banco o de la galería; null en la portada y en las ofertas).

    `preferir_banco` y `con_ofertas=False` son del video de rubro (§17.3): el orden pasa a ser banco más
    reciente, portada, galería, y las ofertas no entran."""
    cid = comercio["id"]
    candidatas: list[dict] = []
    portada = ([{"source_type": "cover", "source_id": None, "file_ref": comercio["portada_url"], "created_at": None}]
               if comercio.get("portada_url") else [])
    todos = crepo.list_assets([cid])
    assets = [a for a in todos if a.get("usable_for_social")
              and (not a.get("has_people") or a.get("people_ok"))
              and min(a.get("width") or 0, a.get("height") or 0) >= content_storage.LADO_MENOR_MINIMO]
    assets.sort(key=lambda a: str(a.get("created_at") or ""), reverse=True)
    del_banco = [{"source_type": "asset", "source_id": a["id"], "file_ref": a["file_path"],
                  "created_at": a.get("created_at")} for a in assets]
    copias = {a.get("gallery_photo_id") for a in todos if a.get("gallery_photo_id")}
    galeria = [{"source_type": "gallery", "source_id": g["id"], "file_ref": g["url"], "created_at": g.get("created_at")}
               for g in sorted(crepo.gallery_photos([cid]), key=lambda x: str(x.get("created_at") or ""), reverse=True)
               if g["id"] not in copias]
    candidatas += (del_banco + portada) if preferir_banco else (portada + del_banco)
    candidatas += galeria
    if con_ofertas:
        desde = (datetime.combine(hoy, datetime.min.time(), tzinfo=timezone.utc) - timedelta(days=90)).isoformat()
        for o in crepo.list_offers(desde, cid):
            candidatas.append({"source_type": "offer", "source_id": o["id"], "file_ref": o["imagen_url"],
                               "created_at": None})

    elegidas: list[dict] = []
    vistos: set = set()
    prohibidas = (usadas or set()) | (excluir or set())
    for c in candidatas:
        if len(elegidas) >= maximo:
            break
        if _clave_de_uso(c) in prohibidas or c["file_ref"] in vistos:
            continue
        ruta = content_storage.resolver_fuente(c["source_type"], c["file_ref"])
        if ruta is None:
            continue
        if c["source_type"] != "asset":
            lado = content_storage.lado_menor(ruta)
            if lado is None or lado < content_storage.LADO_MENOR_MINIMO:
                continue
        vistos.add(c["file_ref"])
        elegidas.append({**c, "comercio_id": cid})
    return elegidas


# ─────────────────────────────────────────────────────────── el plan

def _slots_de_la_semana(week_start: date, hoy: date, deuda_urgente: int) -> list[tuple[date, str]]:
    slots = []
    for dia, pilar, condicion in CALENDARIO:
        if condicion == "sabado" and deuda_urgente <= UMBRAL_SABADO:
            continue
        if condicion == "lunes" and deuda_urgente <= UMBRAL_LUNES:
            continue
        d = week_start + timedelta(days=dia)
        if d >= hoy:
            slots.append((d, pilar))
    return sorted(slots)


def _crear_tarea(crepo, comercio_id: str, kind: str, due_on: date, note: str | None = None) -> bool:
    return bool(crepo.insert_task({"comercio_id": comercio_id, "kind": kind, "due_on": due_on.isoformat(),
                                   "note": note}))


def _pedir_fotos(crepo, c: dict, ciclo_inicio: date, hoy: date) -> bool:
    """Una tarea `photo_refresh` por ciclo."""
    previas = crepo.list_tasks(status=None, due_from=ciclo_inicio.isoformat(), comercio_id=c["id"],
                               kinds=["photo_refresh"])
    return False if previas else _crear_tarea(crepo, c["id"], "photo_refresh", hoy)


def _guardar_pieza(crepo, row: dict, fuentes: list[dict]) -> dict | None:
    pieza = crepo.insert_piece(row)
    if pieza is None:
        return None
    crepo.insert_sources([{"piece_id": pieza["id"], "position": i, "source_type": f["source_type"],
                           "source_id": f.get("source_id"), "comercio_id": f["comercio_id"],
                           "file_ref": f["file_ref"], "caption_fact": f.get("caption_fact"),
                           "chip_text": f.get("chip_text"), "photo_flags": f.get("photo_flags") or [],
                           "focus_y": f.get("focus_y")}
                          for i, f in enumerate(fuentes)])
    return pieza


def _fila_de_pieza(week_start: date, dia: date, pilar: str, facts: dict, textos: dict, actor: str,
                   comercio: dict | None = None, ciudad_id: str | None = None,
                   ciclo_inicio: date | None = None, video: dict | None = None,
                   origin: str = "selector", rubro_id: str | None = None) -> dict:
    """La fila de una pieza nueva. Siempre v2 (`template_version = 2`, §16.5); `video` son las columnas de los
    textos del video que salen de `content_video_texts.campos_de_pieza`. Un `origin = 'pedido'` (§17.3) nunca
    cuenta cuota; `rubro_id` es del pilar `rubro`."""
    return {
        "week_start": week_start.isoformat(), "scheduled_for": dia.isoformat(), "pillar": pilar,
        "comercio_id": comercio["id"] if comercio else None,
        "ciudad_id": ciudad_id or (comercio or {}).get("ciudad_id"),
        "origin": origin, "rubro_id": rubro_id,
        "counts_for_quota": bool(comercio) and origin == "selector",
        "quota_cycle_start": ciclo_inicio.isoformat() if ciclo_inicio else None,
        "status": "queued", "facts": facts, "template": pilar, "template_version": 2,
        "caption_tiktok": textos["caption_tiktok"], "caption_ig": textos["caption_ig"],
        "caption_channel": textos["caption_channel"], "hashtags": textos["hashtags"],
        "caption_engine": textos["caption_engine"], "caption_checks": textos["caption_checks"],
        "created_by": actor, **(video or {}),
    }


def plan_week(repo, crepo, week_start: date, actor: str = "selector", ahora: datetime | None = None) -> dict:
    """Arma las piezas de la semana que arranca el lunes `week_start` (desde hoy en adelante).

    Devuelve `{week_start, created, slots_left_empty: [{date, pillar, reason}], tasks_created}`."""
    ahora = ahora or cargas.ahora_utc()
    hoy = cargas.hoy_bolivia(ahora)
    resumen = {"week_start": week_start.isoformat(), "created": 0, "slots_left_empty": [], "tasks_created": 0}

    consentidos = content_consent.autorizados(crepo)
    suscriptores = evaluar_suscriptores(crepo, hoy, consentidos)
    candidatos = [s for s in suscriptores if s["autorizado"] and s["debe"] > 0]
    deuda_urgente = sum(s["debe"] for s in candidatos if s["dias_restantes"] <= 14)
    slots = _slots_de_la_semana(week_start, hoy, deuda_urgente)

    ocupados = {(p["scheduled_for"], p["pillar"]) for p in crepo.list_pieces(
        date_from=week_start.isoformat(), date_to=(week_start + timedelta(days=6)).isoformat())
        if p.get("status") not in ("skipped", "failed")}
    usadas = claves_usadas(crepo, hoy)

    for dia, pilar in slots:
        if (dia.isoformat(), pilar) in ocupados:
            continue
        if pilar == "ofertas":
            motivo = _plan_ofertas(repo, crepo, week_start, dia, actor, hoy, consentidos, suscriptores, usadas, resumen)
        else:
            motivo = _plan_comercio(crepo, week_start, dia, actor, hoy, candidatos, usadas, resumen)
        if motivo:
            resumen["slots_left_empty"].append({"date": dia.isoformat(), "pillar": pilar, "reason": motivo})
    return resumen


def _orden_de_candidatos(candidatos: list[dict]) -> list[dict]:
    """Los que más se les acaba el ciclo, los que más deben y los que hace más que no salen."""
    return sorted(candidatos, key=lambda s: (s["dias_restantes"], -s["debe"], s["ultima"] or "0000-00-00"))


def _plan_comercio(crepo, week_start: date, dia: date, actor: str, hoy: date, candidatos: list[dict],
                   usadas: set[tuple], resumen: dict) -> str | None:
    """Cubre un lugar `comercio_del_dia`. Devuelve el motivo si quedó vacío."""
    for s in _orden_de_candidatos([c for c in candidatos if c["debe"] > 0]):
        c = s["comercio"]
        tope = ultimo_dia_agendable(c)
        if tope is not None and dia > tope:
            continue                      # la pieza saldría después de que se le acabó la gracia
        if s["ultima"]:
            sep = SEPARACION_URGENTE_DIAS if s["dias_restantes"] <= 10 else SEPARACION_DIAS
            if abs((dia - date.fromisoformat(str(s["ultima"])[:10])).days) < sep:
                continue
        fotos = elegir_fotos(crepo, c, MAX_FOTOS_COMERCIO, hoy, usadas)
        if len(fotos) < MIN_FOTOS:
            if _pedir_fotos(crepo, c, s["ciclo_inicio"], hoy):
                resumen["tasks_created"] += 1
            continue
        facts = content_captions.build_facts_comercio(c)
        textos = content_captions.generate_captions(facts, crepo=crepo)
        # Las frases del video, mirando las fotos (§16.5). Nunca frena la cola: sin Gemini salen los textos fijos.
        prop = content_video_texts.proponer({"pillar": "comercio_del_dia", "facts": facts}, fotos, c, crepo=crepo)
        fotos, _ = content_video_texts.aplicar_en_memoria(fotos, prop, "comercio_del_dia")
        pieza = _guardar_pieza(
            crepo, _fila_de_pieza(week_start, dia, "comercio_del_dia", facts, textos, actor, c,
                                  ciclo_inicio=s["ciclo_inicio"],
                                  video=content_video_texts.campos_de_pieza("comercio_del_dia", facts, prop)), fotos)
        if pieza is None:
            return None            # alguien ocupó el lugar mientras tanto
        resumen["created"] += 1
        s["debe"] -= 1
        s["usadas"] += 1
        s["ultima"] = dia.isoformat()
        usadas.update(_clave_de_uso(f) for f in fotos)
        return None
    return "no_candidates"


def limpiar_titulo(texto: str | None) -> str:
    """El título corto de una oferta para la banda del video: sin emojis ni código, hasta 40 caracteres."""
    t = _RE_CON_PREFIJO.sub("", content_captions.sin_emojis(texto))
    t = re.sub(r"\s+", " ", t).strip(" -·,.")
    if len(t) <= 40:
        return t
    corte = t[:40].rsplit(" ", 1)[0] if " " in t[:40] else t[:40]
    return corte.rstrip(" -·,.")


def _compilado_de_ciudad(candidatas: list[dict], ids_suscriptores: set[str]) -> list[dict]:
    """Hasta `MAX_OFERTAS` ofertas de una ciudad: primero las de suscriptores y, de las demás, las que
    entren con la regla «no suscriptores <= piso(total / 3)» sobre el compilado ya armado."""
    subs = [x for x in candidatas if x["comercio"]["id"] in ids_suscriptores][:MAX_OFERTAS]
    otros = [x for x in candidatas if x["comercio"]["id"] not in ids_suscriptores]
    elegidas = list(subs)
    k = 0
    while otros and len(elegidas) < MAX_OFERTAS and (k + 1) <= (len(subs) + k + 1) // 3:
        elegidas.append(otros.pop(0))
        k += 1
    return elegidas


def _plan_ofertas(repo, crepo, week_start: date, dia: date, actor: str, hoy: date, consentidos: set[str],
                  suscriptores: list[dict], usadas: set[tuple], resumen: dict) -> str | None:
    """Arma el compilado del jueves. Devuelve el motivo si quedó vacío."""
    desde = (datetime.combine(hoy, datetime.min.time(), tzinfo=timezone.utc) - timedelta(days=OFERTA_DIAS)).isoformat()
    ofertas = crepo.list_offers(desde)
    ya_en_compilado = {s["source_id"] for s in crepo.recent_sources(
        (hoy - timedelta(days=NO_REPETIR_DIAS)).isoformat()) if s["source_type"] == "offer" and s.get("pillar") == "ofertas"}
    ids = sorted({o["comercio_id"] for o in ofertas if o.get("comercio_id") in consentidos})
    if not ids:
        return "not_enough_offers"
    fichas = {c["id"]: c for c in crepo.list_comercios_activos(ids=ids)}
    ids_suscriptores = {s["comercio"]["id"] for s in suscriptores}
    ciudades = {c["id"]: c for c in crepo.list_ciudades()}

    por_ciudad: dict[str, list[dict]] = {}
    visto: set[str] = set()
    for o in ofertas:                                    # de la más nueva a la más vieja
        cid = o.get("comercio_id")
        c = fichas.get(cid)
        if not c or cid in visto or o["id"] in ya_en_compilado:
            continue
        ruta = content_storage.resolver_fuente("offer", o.get("imagen_url"))
        lado = content_storage.lado_menor(ruta) if ruta else None
        if lado is None or lado < content_storage.LADO_MENOR_MINIMO:
            continue
        visto.add(cid)
        por_ciudad.setdefault(c.get("ciudad_id") or "", []).append({"oferta": o, "comercio": c})
    if not por_ciudad:
        return "not_enough_offers"
    # El compilado de CADA ciudad con el tope de no suscriptores aplicado; gana el más grande que sirva.
    armados = {cid: _compilado_de_ciudad(cands, ids_suscriptores) for cid, cands in por_ciudad.items()}
    validos = {cid: e for cid, e in armados.items() if len(e) >= MIN_OFERTAS}
    if not validos:
        return "not_enough_offers"
    ciudad_id = max(validos, key=lambda k: (len(validos[k]), k))
    elegidas = validos[ciudad_id]

    items, fuentes = [], []
    for x in elegidas:
        o, c = x["oferta"], x["comercio"]
        # Sin precio (§16.1): ni en el video ni en los textos. «Consulte precio directo con el local».
        item = {"nombre": c.get("nombre"), "titulo_corto": limpiar_titulo(o.get("titulo") or o.get("descripcion"))}
        items.append(item)
    ciudad = ciudades.get(ciudad_id) or (elegidas[0]["comercio"].get("ciudades") or {})
    facts = content_captions.build_facts_ofertas(ciudad, items)
    for x, item in zip(elegidas, facts["items"]):
        o, c = x["oferta"], x["comercio"]
        nombre = item.get("nombre", "")
        fuentes.append({"source_type": "offer", "source_id": o["id"], "comercio_id": c["id"],
                        "file_ref": o["imagen_url"], "caption_fact": nombre[:80],
                        "chip_text": content_video_texts.chip_de_nombre(nombre)})
    textos = content_captions.generate_captions(facts, crepo=crepo)
    # El chip de cada foto es el nombre del comercio (de la base); Gemini propone sólo el gancho y las marcas.
    prop = content_video_texts.proponer({"pillar": "ofertas", "facts": facts}, fuentes, crepo=crepo)
    fuentes, _ = content_video_texts.aplicar_en_memoria(fuentes, prop, "ofertas")
    pieza = _guardar_pieza(crepo, _fila_de_pieza(
        week_start, dia, "ofertas", facts, textos, actor, ciudad_id=ciudad_id or None,
        video=content_video_texts.campos_de_pieza("ofertas", facts, prop)), fuentes)
    if pieza is None:
        return None
    resumen["created"] += 1
    usadas.update(_clave_de_uso(f) for f in fuentes)
    return None


# ──────────────────────────────────────────────────── cambiar las fotos

def cambiar_fotos(crepo, pieza: dict, remove_positions: list[int], hoy: date | None = None) -> dict:
    """«Cambiar fotos» desde Revisión: quita las fotos marcadas, busca reemplazos del mismo comercio y
    deja la pieza en `queued` para rearmarla. 409 `no_more_photos` si no quedan 4 que sirvan."""
    hoy = hoy or cargas.hoy_bolivia()
    activas = crepo.list_sources(pieza["id"])
    quitar = {int(p) for p in remove_positions}
    if not quitar or not quitar <= {f["position"] for f in activas}:
        raise HTTPException(status_code=400, detail="Elegí fotos de la pieza para quitar")
    quedan = [f for f in activas if f["position"] not in quitar]
    removidas = [f for f in activas if f["position"] in quitar]
    if pieza.get("comercio_id"):
        comercio = crepo.get_comercio_ficha(pieza["comercio_id"])
        # Las que ya se quitaron antes (inactivas) tampoco vuelven.
        excluir = {_clave_de_uso(f) for f in crepo.list_sources(pieza["id"], only_active=False)}
        nuevas = elegir_fotos(crepo, comercio, MAX_FOTOS_COMERCIO - len(quedan), hoy,
                              claves_usadas(crepo, hoy) - {_clave_de_uso(f) for f in activas}, excluir)
    else:
        nuevas = []
    if len(quedan) + len(nuevas) < MIN_FOTOS:
        pedir_fotos_si_faltan(crepo, pieza, hoy)
        raise HTTPException(status_code=409, detail={
            "codigo": "no_more_photos",
            "mensaje": "No hay más fotos que sirvan de este comercio. Pedile fotos: la tarea quedó creada."})
    # `unique (piece_id, position)` cuenta TAMBIÉN las fuentes ya dadas de baja: la posición nueva sale de todas.
    siguiente = max((f["position"] for f in crepo.list_sources(pieza["id"], only_active=False)), default=-1) + 1
    # Primero se suman los reemplazos y recién después se da de baja lo viejo: si el insert falla, no se pierde nada.
    insertadas = crepo.insert_sources([
        {"piece_id": pieza["id"], "position": siguiente + i, "source_type": n["source_type"],
         "source_id": n.get("source_id"), "comercio_id": n["comercio_id"],
         "file_ref": n["file_ref"], "caption_fact": n.get("caption_fact")}
        for i, n in enumerate(nuevas)])
    for f in removidas:
        crepo.deactivate_source(pieza["id"], f["position"])
    # Sólo la frase, la marca y el encuadre de la foto NUEVA (§16.5); los textos de la pieza no se tocan. Después de
    # dar de baja las viejas: así la cuenta de «quedan 4 sin marca» es la de verdad. No frena el cambio si falla.
    content_video_texts.proponer_para_nuevas(crepo, pieza, insertadas)
    return {"quitadas": len(removidas), "agregadas": len(nuevas)}


def pedir_fotos_si_faltan(crepo, pieza: dict, hoy: date | None = None) -> None:
    """Usado cuando «Cambiar fotos» no encuentra reemplazos: deja la tarea de pedir fotos."""
    hoy = hoy or cargas.hoy_bolivia()
    if pieza.get("comercio_id"):
        c = crepo.get_comercio_ficha(pieza["comercio_id"])
        if c:
            inicio, _ = ciclo_de(c, hoy)
            _pedir_fotos(crepo, c, inicio, hoy)


# ───────────────────────────── cuando una fuente deja de valer (autorización retirada, foto dada de baja)

#: Piezas que todavía se pueden corregir y volver a armar.
PIEZA_REARMABLE = ("queued", "rendering", "ready_for_review", "approved")


def _ya_salio_en_alguna_red(crepo, pieza: dict) -> bool:
    """Una pieza `approved` con una red ya publicada no se puede rehacer: se cierran las redes que faltan
    (se saltean) y la pieza queda `published`. True si era ese caso."""
    if pieza["status"] != "approved":
        return False
    posts = crepo.list_posts([pieza["id"]])
    if not any(p["status"] == "posted" for p in posts):
        return False
    for post in posts:
        if post["status"] in ("pending", "claimed"):
            crepo.update_post(post["id"], {"status": "skipped", "skip_reason": "fuente retirada", "claimed_by": None,
                                           "claimed_at": None}, if_status=["pending", "claimed"])
    content_posts.cerrar_pieza_si_corresponde(crepo, pieza["id"])
    return True


def _volver_a_la_cola(crepo, pieza: dict, extra: dict | None = None) -> dict | None:
    """La pieza vuelve a `queued` para armar el video de nuevo (se borra el video viejo, que mostraba lo que
    ya no vale). Sus redes pendientes quedan: al aprobarla otra vez no se duplican."""
    patch = {"status": "queued", "render_attempts": 0, "render_error": None, "render_started_at": None,
             "render_next_at": datetime.now(timezone.utc).isoformat(), "video_path": None, "cover_path": None,
             **(extra or {})}
    viejos = (pieza.get("video_path"), pieza.get("cover_path"))        # antes del update: el repo puede mutar `pieza`
    nueva = crepo.update_piece(pieza["id"], patch, if_status=list(PIEZA_REARMABLE))
    if not nueva:
        return None
    for ruta in viejos:
        content_storage.borrar(ruta)
    for post in crepo.list_posts([pieza["id"]]):
        if post["status"] == "claimed":
            crepo.update_post(post["id"], {"status": "pending", "claimed_by": None, "claimed_at": None},
                              if_status="claimed")
    return nueva


def quitar_comercio_de_compilado(crepo, pieza: dict, comercio_id: str, actor: str) -> str | None:
    """Un comercio retiró su autorización y aparece en un compilado (ofertas o video de rubro): se le quita su parte.

    `skipped` si el compilado queda por debajo del mínimo (se saltea entero), `rebuilt` si se rearmó sin
    ese comercio (textos nuevos de plantilla y el render vuelve a la cola), `closed` si ya había salido en
    alguna red, None si no había nada que hacer."""
    activas = crepo.list_sources(pieza["id"])
    quitar = [f for f in activas if f.get("comercio_id") == comercio_id]
    if not quitar:
        return None
    if _ya_salio_en_alguna_red(crepo, pieza):
        return "closed"
    facts = pieza.get("facts") or {}
    items = facts.get("items") or []
    alineado = len(items) == len(activas)              # el item i es de la fuente i (así se crea)
    if len(activas) - len(quitar) < MIN_OFERTAS or not alineado:
        ahora = datetime.now(timezone.utc).isoformat()
        return "skipped" if content_consent.saltear_pieza(crepo, pieza, actor, ahora) else None
    posiciones = {f["position"] for f in quitar}
    nuevos = [it for f, it in zip(activas, items) if f["position"] not in posiciones]
    if facts.get("pillar") == "rubro":
        nuevos_facts = content_captions.build_facts_rubro(
            {"nombre": facts.get("rubro"), "slug": facts.get("rubro_slug")},
            {"nombre": facts.get("ciudad"), "slug": facts.get("ciudad_slug"), "departamento": facts.get("departamento")},
            nuevos)
    else:
        nuevos_facts = content_captions.build_facts_ofertas(
            {"nombre": facts.get("ciudad"), "departamento": facts.get("departamento")}, nuevos)
    textos = content_captions.template_captions(nuevos_facts)
    checks = content_captions.validate_piece(nuevos_facts, textos["caption_tiktok"], textos["caption_ig"],
                                             textos["caption_channel"], textos["hashtags"])
    for f in quitar:
        crepo.deactivate_source(pieza["id"], f["position"])
    nueva = _volver_a_la_cola(crepo, pieza, {
        "facts": nuevos_facts, "caption_tiktok": textos["caption_tiktok"], "caption_ig": textos["caption_ig"],
        "caption_channel": textos["caption_channel"], "hashtags": textos["hashtags"], "caption_engine": "template",
        "caption_checks": checks, "caption_edited": False})
    logger.info("content.compilado_rearmado", pieza=pieza["id"], sin_comercio=comercio_id, por=actor)
    return "rebuilt" if nueva else None


def retirar_asset_de_piezas(crepo, asset_id: str, actor: str, hoy: date | None = None) -> dict:
    """Una foto del banco se dio de baja o se marcó «no usar en redes»: las piezas vivas que la usan buscan
    un reemplazo y vuelven a la cola; si no hay reemplazo se saltean (y queda la tarea de pedir fotos).

    Devuelve `{replaced, skipped}`."""
    hoy = hoy or cargas.hoy_bolivia()
    resumen = {"replaced": 0, "skipped": 0}
    for pid in crepo.piece_ids_by_source_asset(asset_id):
        pieza = crepo.get_piece(pid)
        if not pieza or pieza["status"] not in PIEZA_REARMABLE or _ya_salio_en_alguna_red(crepo, pieza):
            continue
        posiciones = [f["position"] for f in crepo.list_sources(pid)
                      if f.get("source_type") == "asset" and f.get("source_id") == asset_id]
        try:
            cambiar_fotos(crepo, pieza, posiciones, hoy)
        except HTTPException:
            ahora = datetime.now(timezone.utc).isoformat()
            if content_consent.saltear_pieza(crepo, pieza, actor, ahora, "asset_removed"):
                resumen["skipped"] += 1
            continue
        if _volver_a_la_cola(crepo, pieza):
            resumen["replaced"] += 1
    logger.info("content.asset_retirado", asset=asset_id, por=actor, **resumen)
    return resumen
