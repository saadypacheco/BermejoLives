"""Cuidado de los suscriptores: el job diario de las 07:00 (docs/contenido-redes-tecnico.md §7.4).

QUÉ HACE CADA DÍA
=================
- **Bienvenida automática**: un pago de los últimos 3 días de un comercio SIN pago anterior y sin
  bienvenida arrancada crea las tareas de bienvenida. Las renovaciones no disparan nada; las
  cortesías y los suscriptores de antes arrancan a mano («Iniciar bienvenida»).
- **Cierres automáticos**: `profile_check`, `first_offer`, `photo_session` y `first_piece` se
  cierran solas cuando la condición se cumple.
- **Reporte del mes**: 5 días antes de vencer, un snapshot de los números del ciclo (visitas, WhatsApp,
  cómo llegar, palabras) y la tarea `monthly_report`.
- **Renovación**: `renewal_before` el día anterior al vencimiento, `renewal_overdue` a los 3 días,
  `churn_call` a los 7. La cortesía no renueva.
- **Impago**: a los 8 días sin pago, las piezas propias que no salieron pasan a `skipped`.
- **Reclamos vencidos** y **limpieza** de archivos (§4.4).

Las tareas se crean el día que tocan (salvo la bienvenida, que se crea entera con sus fechas); la
unicidad `(comercio_id, kind, due_on)` hace al job idempotente: correrlo dos veces no duplica nada.
Los mensajes NO se mandan: salen por `wa.me`, a mano.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

import structlog
from fastapi import HTTPException

from app.core.config import settings
from app.services import cargas, content_consent, content_selector, content_storage, fotos_galeria

logger = structlog.get_logger()

#: Las tareas de la bienvenida y a cuántos días del arranque caen.
OFFSETS_BIENVENIDA = (("welcome", 0), ("profile_check", 0), ("first_offer", 1), ("photo_session", 2),
                      ("first_piece", 5), ("week1_checkin", 7))
#: Cuántas fotos del banco que sirven cierran `photo_session`.
FOTOS_SESION = 8
#: Un pago de los últimos N días dispara la bienvenida.
DIAS_PAGO_RECIENTE = 3
#: Cuántos días de los leads se muestran en el reporte cuando el ciclo recién arranca.
ORIGENES_REDES = ["tt-", "ig-", "fb-", "canal-", "st-"]


def _d(valor) -> date | None:
    try:
        return date.fromisoformat(str(valor)[:10])
    except (TypeError, ValueError):
        return None


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────────── el checklist

def _digitos(t: str | None) -> str:
    return re.sub(r"\D", "", t or "")


def checklist(repo, crepo, comercio: dict, consentimiento: dict | None) -> list[dict]:
    """La lista «Ficha lista» de un suscriptor: `[{key, label, ok, auto}]`. `auto=true` se tilda solo;
    si una lectura no se puede hacer, el ítem queda `auto=false` para tildar a mano."""
    cid = comercio["id"]

    def leer(fn):
        try:
            return True, bool(fn())
        except Exception:  # noqa: BLE001
            logger.warning("subscriber.checklist_lectura_fallo", comercio=cid, exc_info=True)
            return False, False

    redes = any(comercio.get(k) for k in ("instagram_url", "facebook_url", "tiktok_url", "sitio_web"))
    rubro = (comercio.get("rubros") or {}).get("slug")
    fotos = len(crepo.gallery_photos([cid]))
    items = [
        ("portada", "Portada", True, bool(comercio.get("portada_url"))),
        ("fotos", "6 fotos o más en la galería", True, fotos >= 6),
        ("horario", "Horario", True, bool(comercio.get("horario"))),
        ("mapa", "Pin en el mapa", True, comercio.get("lat") is not None and comercio.get("lng") is not None),
        ("whatsapp", "WhatsApp válido", True, len(_digitos(comercio.get("whatsapp"))) >= 8),
        ("rubro", "Rubro distinto de «otros»", True, bool(rubro) and rubro != "otros"),
        ("redes", "Al menos una red cargada", True, redes),
        ("autorizacion", "Autorización de redes", True, bool(consentimiento and consentimiento.get("granted"))),
    ]
    auto_cuenta, ok_cuenta = leer(lambda: repo.get_cuenta_comercio(cid))
    auto_grupo, ok_grupo = leer(lambda: repo.list_grupos_comercio(cid))
    items.append(("cuenta", "Cuenta de Mi comercio", auto_cuenta, ok_cuenta))
    items.append(("grupo", "Grupo de WhatsApp atado", auto_grupo, ok_grupo))
    return [{"key": k, "label": label, "ok": ok, "auto": auto} for k, label, auto, ok in items]


# ─────────────────────────────────────────────────────────── bienvenida

def iniciar_bienvenida(crepo, comercio_id: str, actor: str, hoy: date | None = None,
                       force: bool = False) -> dict:
    """Arranca la bienvenida de un suscriptor: crea sus 6 tareas con sus fechas y anota el arranque.

    409 si ya arrancó (salvo `force`). Devuelve `{created, started_at}`."""
    hoy = hoy or cargas.hoy_bolivia()
    perfil = crepo.get_profile(comercio_id)
    if perfil and perfil.get("onboarding_started_at") and not force:
        raise HTTPException(status_code=409, detail="La bienvenida ya arrancó el "
                            f"{_d(perfil['onboarding_started_at']).strftime('%d/%m/%Y')}")
    creadas = 0
    for kind, dias in OFFSETS_BIENVENIDA:
        if crepo.insert_task({"comercio_id": comercio_id, "kind": kind, "due_on": (hoy + timedelta(days=dias)).isoformat()}):
            creadas += 1
    ahora = _ahora().isoformat()
    crepo.upsert_profile(comercio_id, {"onboarding_started_at": ahora, "onboarding_started_by": actor})
    logger.info("subscriber.bienvenida_iniciada", comercio=comercio_id, por=actor, tareas=creadas, force=force)
    return {"created": creadas, "started_at": ahora}


def bienvenidas_automaticas(crepo, ahora: datetime, hoy: date) -> int:
    """Pagos de los últimos 3 días de comercios sin pago anterior y sin bienvenida arrancada."""
    desde = (ahora - timedelta(days=DIAS_PAGO_RECIENTE)).isoformat()
    n = 0
    for pago in crepo.payments_since(desde):
        cid = pago["comercio_id"]
        if crepo.count_payments_before(cid, pago["created_at"]) > 0:
            continue                                  # una renovación no dispara bienvenida
        perfil = crepo.get_profile(cid)
        if perfil and perfil.get("onboarding_started_at"):
            continue
        iniciar_bienvenida(crepo, cid, f"auto:pago:{pago['id']}", hoy)
        n += 1
    return n


# ───────────────────────────────────────────────────── cierres automáticos

def cierres_automaticos(repo, crepo, hoy: date, ahora: datetime) -> int:
    """Cierra solas las tareas cuya condición ya se cumplió. Devuelve cuántas cerró."""
    cerradas = 0
    # También las que todavía no vencen: si la condición ya se cumplió, no hay nada que esperar.
    abiertas = crepo.list_tasks(status="open", kinds=["profile_check", "first_offer", "photo_session", "first_piece"])
    for t in abiertas:
        cid = t["comercio_id"]
        c = crepo.get_comercio_ficha(cid)
        if not c:
            continue
        cumple = False
        perfil = crepo.get_profile(cid) or {}
        inicio = perfil.get("onboarding_started_at") or t.get("created_at")
        if t["kind"] == "profile_check":
            lista = checklist(repo, crepo, c, content_consent.vigente(crepo, cid))
            cumple = all(i["auto"] and i["ok"] for i in lista)
        elif t["kind"] == "first_offer":
            cumple = bool(inicio) and repo.contar_publicaciones_desde(cid, str(inicio)) > 0
        elif t["kind"] == "photo_session":
            buenas = [a for a in crepo.list_assets([cid]) if a.get("usable_for_social")
                      and min(a.get("width") or 0, a.get("height") or 0) >= content_storage.LADO_MENOR_MINIMO]
            cumple = len(buenas) >= FOTOS_SESION
        elif t["kind"] == "first_piece":
            cumple = any(p.get("status") == "published" for p in crepo.list_pieces(statuses=["published"], comercio_id=cid))
        if cumple and crepo.update_task(t["id"], {"status": "done", "auto_closed": True, "done_by": "sistema",
                                                  "done_at": ahora.isoformat()}, if_status="open"):
            cerradas += 1
    return cerradas


# ─────────────────────────────────────────────────────────────── reporte

def datos_del_reporte(repo, crepo, comercio: dict, inicio: date, hoy: date) -> dict:
    """Los números del período del ciclo (§7.5). Nunca de otros comercios."""
    cid = comercio["id"]
    desde = datetime.combine(inicio, datetime.min.time(), tzinfo=cargas.BOLIVIA).astimezone(timezone.utc).isoformat()
    dias = max(1, (hoy - inicio).days + 1)
    terminos = [t["query"] for t in (repo.terminos_de_comercio(cid, dias, 2) or [])][:2]
    publicadas = [p for p in crepo.list_pieces(statuses=["published"], comercio_id=cid)
                  if (p.get("published_at") or "")[:10] >= inicio.isoformat()]
    return {
        "visits": crepo.count_leads(cid, desde, tipo="vista"),
        "whatsapp": crepo.count_leads(cid, desde, tipo="whatsapp"),
        "directions": crepo.count_leads(cid, desde, tipo="mapa"),
        "calls": crepo.count_leads(cid, desde, tipo="telefono"),
        "from_social": crepo.count_leads(cid, desde, origen_prefixes=ORIGENES_REDES),
        "terms": terminos,
        "pieces_published": len(publicadas),
        "offers_approved": repo.contar_publicaciones_desde(cid, desde),
    }


# ─────────────────────────────────────────────────────────── el job diario

def _tarea(crepo, cid: str, kind: str, due: date, **extra) -> bool:
    return bool(crepo.insert_task({"comercio_id": cid, "kind": kind, "due_on": due.isoformat(), **extra}))


def tareas_de_renovacion(repo, crepo, s: dict, hoy: date) -> int:
    """Reporte, renovación y llamada de un suscriptor (que no sea de cortesía)."""
    c = s["comercio"]
    hasta = _d(c.get("paga_hasta"))
    if c.get("plan_cortesia") or hasta is None:
        return 0
    n = 0
    if hasta - timedelta(days=5) <= hoy <= hasta:
        inicio = s["ciclo_inicio"]
        if crepo.get_report(c["id"], inicio.isoformat()) is None:
            reporte = crepo.insert_report({"comercio_id": c["id"], "period_start": inicio.isoformat(),
                                           "period_end": hoy.isoformat(),
                                           "data": datos_del_reporte(repo, crepo, c, inicio, hoy)})
            if reporte and _tarea(crepo, c["id"], "monthly_report", hoy, report_id=reporte["id"]):
                n += 1
    if hasta - timedelta(days=1) <= hoy <= hasta and _tarea(crepo, c["id"], "renewal_before", hasta - timedelta(days=1)):
        n += 1
    if hoy >= hasta + timedelta(days=3) and _tarea(crepo, c["id"], "renewal_overdue", hasta + timedelta(days=3)):
        n += 1
    if hoy >= hasta + timedelta(days=7) and _tarea(crepo, c["id"], "churn_call", hasta + timedelta(days=7)):
        n += 1
    return n


def saltar_por_impago(crepo, hoy: date, ahora: datetime) -> int:
    """A los 8 días sin pago, las piezas propias que no salieron pasan a `skipped` (`unpaid`) y sus
    redes pendientes también."""
    vivas = crepo.list_pieces(statuses=["queued", "rendering", "ready_for_review", "approved"], limit=1000)
    propias = [p for p in vivas if p.get("comercio_id")]
    if not propias:
        return 0
    fichas = {c["id"]: c for c in crepo.list_comercios_activos(ids=sorted({p["comercio_id"] for p in propias}))}
    n = 0
    for p in propias:
        c = fichas.get(p["comercio_id"])
        hasta = _d((c or {}).get("paga_hasta"))
        if not c or c.get("plan_cortesia") or hasta is None or fotos_galeria.al_dia(c, hoy):
            continue
        if hoy < hasta + timedelta(days=8):
            continue
        nueva = crepo.update_piece(p["id"], {"status": "skipped", "skip_reason": "unpaid", "skipped_by": "sistema",
                                             "skipped_at": ahora.isoformat()},
                                   if_status=["queued", "rendering", "ready_for_review", "approved"])
        if not nueva:
            continue
        n += 1
        for post in crepo.list_posts([p["id"]]):
            if post.get("status") in ("pending", "claimed"):
                crepo.update_post(post["id"], {"status": "skipped", "skip_reason": "impago", "claimed_by": None,
                                               "claimed_at": None}, if_status=["pending", "claimed"])
    return n


def limpiar_archivos(crepo, ahora: datetime) -> dict:
    """La retención de archivos (§4.4). La fila queda siempre; sólo se borra el archivo."""
    piezas = assets = 0
    corte_pub = ahora - timedelta(days=settings.content_render_retention_days)
    corte_muerta = ahora - timedelta(days=14)
    for p in crepo.pieces_to_purge(corte_pub.isoformat(), corte_muerta.isoformat()):
        for rel in (p.get("video_path"), p.get("cover_path")):
            content_storage.borrar(rel)
        crepo.update_piece(p["id"], {"files_purged_at": ahora.isoformat()})
        piezas += 1
    corte_asset = ahora - timedelta(days=settings.content_asset_purge_days)
    for a in crepo.assets_to_purge(corte_asset.isoformat()):
        content_storage.borrar(a.get("file_path"))
        content_storage.borrar(a.get("thumb_path"))
        crepo.update_asset(a["id"], {"file_purged_at": ahora.isoformat()})
        assets += 1
    return {"pieces": piezas, "assets": assets}


def daily_job(repo, crepo, ahora: datetime | None = None) -> dict:
    """Todo el job diario. Cada paso corre aislado: uno que falla no frena a los otros."""
    ahora = ahora or _ahora()
    hoy = cargas.hoy_bolivia(ahora)
    r = {"welcomes": 0, "closed": 0, "tasks": 0, "unpaid_skipped": 0, "claims_released": 0, "purged": {}}

    def paso(nombre, fn, clave, suma=False):
        try:
            valor = fn()
            r[clave] = (r[clave] + valor) if suma else valor
        except Exception:  # noqa: BLE001
            logger.warning("subscriber.job_paso_fallo", paso=nombre, exc_info=True)

    paso("bienvenidas", lambda: bienvenidas_automaticas(crepo, ahora, hoy), "welcomes")
    try:
        consentidos = content_consent.autorizados(crepo)
        suscriptores = content_selector.evaluar_suscriptores(crepo, hoy, consentidos)
    except Exception:  # noqa: BLE001
        logger.warning("subscriber.job_suscriptores_fallo", exc_info=True)
        suscriptores = []
    for s in suscriptores:
        paso("renovacion", lambda s=s: tareas_de_renovacion(repo, crepo, s, hoy), "tasks", suma=True)
    paso("cierres", lambda: cierres_automaticos(repo, crepo, hoy, ahora), "closed")
    paso("impago", lambda: saltar_por_impago(crepo, hoy, ahora), "unpaid_skipped")
    paso("reclamos", lambda: crepo.release_expired_claims(
        (ahora - timedelta(minutes=settings.content_claim_minutes)).isoformat()), "claims_released")
    paso("limpieza", lambda: limpiar_archivos(crepo, ahora), "purged")
    logger.info("subscriber.job_diario", hoy=hoy.isoformat(), **{k: v for k, v in r.items() if k != "purged"})
    return r


_ultimo_dia: date | None = None


def daily_tick(repo, crepo, ahora: datetime | None = None) -> dict | None:
    """Una vuelta del loop: corre el job una vez por día, después de `CONTENT_CARE_HOUR` (hora de Bolivia)."""
    global _ultimo_dia
    ahora = ahora or _ahora()
    ahora_bo = ahora.astimezone(cargas.BOLIVIA)
    if ahora_bo.hour < settings.content_care_hour or _ultimo_dia == ahora_bo.date():
        return None
    _ultimo_dia = ahora_bo.date()
    return daily_job(repo, crepo, ahora)


def reiniciar_dia() -> None:
    global _ultimo_dia
    _ultimo_dia = None
