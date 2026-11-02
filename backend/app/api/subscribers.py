"""Cuidar a los suscriptores: tareas diarias, bienvenida, reporte y renovación
(docs/contenido-redes-tecnico.md §7.4 y §8.3).

El permiso es `pagos` o `difusion`. Los mensajes a los comerciantes NO se mandan desde acá ni por
WAHA: el backend arma el texto (plantillas M1 a M6 de `subscriber_messages`) y el panel abre
`wa.me` con el mensaje escrito; una persona lo manda, y después marca «lo mandé». Eso guarda el
texto que se mandó en `sent_text`.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.auth import require_alguno
from app.db.content_repository import ContentRepo, get_content_repo
from app.db.repository import Repo, get_repo
from app.services import cargas, content_consent, content_present, content_selector, subscriber_care, subscriber_messages

router = APIRouter()
logger = structlog.get_logger()

_permiso = require_alguno("pagos", "difusion")
#: Un vencido sigue en la lista este tiempo (para llamarlo): después se va solo.
DIAS_VENCIDO_EN_LISTA = 30


def _actor(claims: dict) -> str:
    return claims.get("email") or claims.get("sub") or "desconocido"


def _ciudad_id_o_400(crepo: ContentRepo, slug: str | None) -> str | None:
    if not slug:
        return None
    fila = next((c for c in crepo.list_ciudades() if c["slug"] == slug), None)
    if not fila:
        raise HTTPException(status_code=400, detail="Ciudad desconocida")
    return fila["id"]


def _planes_con_cuota(crepo: ContentRepo) -> tuple[dict, list[str]]:
    por_slug = {p["slug"]: p for p in crepo.list_planes()}
    return por_slug, [s for s, p in por_slug.items() if content_selector.cuota_del_plan(p) > 0]


def _en_la_lista(c: dict, plan: dict, hoy: date) -> bool:
    if content_selector.cuota_del_plan(plan) <= 0:
        return False
    if content_selector.es_suscriptor(c, plan, hoy) or c.get("suspendido"):
        return True
    hasta = content_present._fecha(c.get("paga_hasta"))
    return bool(hasta and hasta >= hoy - timedelta(days=DIAS_VENCIDO_EN_LISTA))


def _resumenes(crepo: ContentRepo, comercios: list[dict], por_slug: dict, hoy: date) -> list[dict]:
    """`SubscriberSummaryResponse` de cada comercio."""
    if not comercios:
        return []
    ids = [c["id"] for c in comercios]
    consentimientos = crepo.current_consents(ids)
    perfiles = crepo.list_profiles(ids)
    abiertas = crepo.list_tasks(status="open", due_to=hoy.isoformat(), limit=2000)
    propias = crepo.list_own_pieces_since((hoy - timedelta(days=90)).isoformat())
    out = []
    for c in comercios:
        cid = c["id"]
        plan = content_selector.plan_del(c, por_slug)
        inicio, fin = content_selector.ciclo_de(c, hoy)
        suyas = [p for p in propias if p["comercio_id"] == cid]
        mias = [t for t in abiertas if t["comercio_id"] == cid]
        proximas = sorted(p["scheduled_for"] for p in suyas if str(p["scheduled_for"])[:10] >= hoy.isoformat())
        estado = content_present.estado_de_suscripcion(c, hoy)
        perfil = perfiles.get(cid) or {}
        out.append({
            "comercio_id": cid, "nombre": c.get("nombre"), "slug": c.get("slug"), "whatsapp": c.get("whatsapp"),
            "ciudad_nombre": (c.get("ciudades") or {}).get("nombre"), "plan": c.get("plan") or "gratis",
            "plan_nombre": plan.get("nombre") or c.get("plan"), "plan_cortesia": bool(c.get("plan_cortesia")),
            "paga_hasta": c.get("paga_hasta"), "subscription_state": estado,
            "in_grace": estado == "vencido" and content_selector.en_gracia(c, hoy),
            "social_consent": content_consent.respuesta(consentimientos.get(cid)),
            "pieces": {"quota": content_selector.cuota_del_plan(plan),
                       "used": content_selector.usadas_en_ciclo(suyas, inicio),
                       "cycle_start": inicio.isoformat(), "cycle_end": fin.isoformat(),
                       "next_scheduled_for": proximas[0] if proximas else None},
            "tasks": {"due_today": sum(1 for t in mias if t["due_on"] == hoy.isoformat()),
                      "overdue": sum(1 for t in mias if t["due_on"] < hoy.isoformat())},
            "contact_person": perfil.get("contact_person"), "onboarding_started_at": perfil.get("onboarding_started_at"),
        })
    return out


def _tareas(crepo: ContentRepo, tareas: list[dict], firmante: str | None, hoy: date) -> list[dict]:
    """`SubscriberTaskResponse` de cada tarea, con su mensaje listo para `wa.me`."""
    if not tareas:
        return []
    ids = sorted({t["comercio_id"] for t in tareas})
    fichas = {c["id"]: c for c in crepo.list_comercios_activos(ids=ids)}
    perfiles = crepo.list_profiles(ids)
    reportes = crepo.get_reports([t["report_id"] for t in tareas if t.get("report_id")])
    out = []
    for t in tareas:
        c = fichas.get(t["comercio_id"]) or {"id": t["comercio_id"], "nombre": None}
        pieza = posts = None
        if t["kind"] == "piece_delivery" and t.get("piece_id"):
            pieza = crepo.get_piece(t["piece_id"])
            posts = crepo.list_posts([t["piece_id"]]) if pieza else None
        out.append(content_present.task_response(t, c, perfiles.get(t["comercio_id"]), firmante, hoy,
                                                 reportes.get(t.get("report_id")), pieza, posts))
    return out


@router.get("/admin/subscribers")
def list_subscribers(ciudad: str | None = Query(default=None, max_length=60),
                     filtro: str = Query(default="todos", max_length=20),
                     _claims: dict = Depends(_permiso), crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    if filtro not in ("tareas", "todos", "por_vencer"):
        raise HTTPException(status_code=400, detail="Filtro desconocido")
    ciudad_id = _ciudad_id_o_400(crepo, ciudad)
    hoy = cargas.hoy_bolivia()
    por_slug, con_cuota = _planes_con_cuota(crepo)
    comercios = crepo.list_comercios_activos(ciudad_id, planes=con_cuota) if con_cuota else []
    comercios = [c for c in comercios if _en_la_lista(c, content_selector.plan_del(c, por_slug), hoy)]
    items = _resumenes(crepo, comercios, por_slug, hoy)
    if filtro == "tareas":
        items = [i for i in items if i["tasks"]["due_today"] or i["tasks"]["overdue"]]
    elif filtro == "por_vencer":
        items = [i for i in items if i["subscription_state"] in ("por_vencer", "vencido")]
    items.sort(key=lambda i: (-i["tasks"]["overdue"], -i["tasks"]["due_today"], (i["nombre"] or "").lower()))
    return {"items": items, "total": len(items)}


@router.get("/admin/subscribers/tasks")
def list_tasks(cuando: str = Query(default="hoy", max_length=12), claims: dict = Depends(_permiso),
               crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    """Las tareas abiertas: de hoy, las atrasadas o las de la semana que viene."""
    hoy = cargas.hoy_bolivia()
    if cuando == "hoy":
        tareas = crepo.list_tasks(status="open", due_from=hoy.isoformat(), due_to=hoy.isoformat())
    elif cuando == "atrasadas":
        tareas = crepo.list_tasks(status="open", due_to=(hoy - timedelta(days=1)).isoformat())
    elif cuando == "semana":
        tareas = crepo.list_tasks(status="open", due_from=hoy.isoformat(), due_to=(hoy + timedelta(days=7)).isoformat())
    else:
        raise HTTPException(status_code=400, detail="Elegí hoy, atrasadas o semana")
    items = _tareas(crepo, tareas, claims.get("nombre"), hoy)
    return {"items": items, "total": len(items)}


def _suscriptor_o_404(crepo: ContentRepo, comercio_id: str) -> tuple[dict, dict]:
    """(ficha, planes por slug) de un comercio con plan de piezas; si no, 404 «No es un suscriptor»."""
    c = crepo.get_comercio_ficha(comercio_id)
    por_slug = {p["slug"]: p for p in crepo.list_planes()}
    if not c or c.get("activo") is False or content_selector.cuota_del_plan(content_selector.plan_del(c, por_slug)) <= 0:
        raise HTTPException(status_code=404, detail="No es un suscriptor")
    return c, por_slug


@router.get("/admin/subscribers/{comercio_id}")
def get_subscriber(comercio_id: str, claims: dict = Depends(_permiso),
                   crepo: ContentRepo = Depends(get_content_repo), repo: Repo = Depends(get_repo)) -> dict:
    hoy = cargas.hoy_bolivia()
    c, por_slug = _suscriptor_o_404(crepo, comercio_id)
    resumen = _resumenes(crepo, [c], por_slug, hoy)[0]
    tareas = crepo.list_tasks(status=None, comercio_id=comercio_id, limit=60)
    tareas.sort(key=lambda t: (t["status"] != "open", t["due_on"]))
    return {
        "summary": resumen,
        "profile_check": subscriber_care.checklist(repo, crepo, c, content_consent.vigente(crepo, comercio_id)),
        "tasks": _tareas(crepo, tareas, claims.get("nombre"), hoy),
        "pieces": [content_present.piece_summary(p) for p in crepo.list_pieces(comercio_id=comercio_id, limit=60)],
        "last_report": content_present.report_response(crepo.last_report(comercio_id)),
    }


class SubscriberProfileUpdate(BaseModel):
    contact_person: str | None = None
    notes: str | None = None


@router.patch("/admin/subscribers/{comercio_id}/profile")
def update_profile(comercio_id: str, body: SubscriberProfileUpdate, _claims: dict = Depends(_permiso),
                   crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    _suscriptor_o_404(crepo, comercio_id)
    patch: dict = {}
    for campo, tope, etiqueta in (("contact_person", 80, "La persona de contacto"), ("notes", 1000, "Las notas")):
        if campo not in body.model_fields_set:
            continue
        valor = (getattr(body, campo) or "").strip() or None
        if valor and len(valor) > tope:
            raise HTTPException(status_code=400, detail=f"{etiqueta} admite hasta {tope} caracteres")
        patch[campo] = valor
    if not patch:
        raise HTTPException(status_code=400, detail="No hay nada que cambiar")
    fila = crepo.upsert_profile(comercio_id, patch)
    return {"ok": True, "contact_person": fila.get("contact_person"), "notes": fila.get("notes")}


class SubscriberOnboardingCreate(BaseModel):
    force: bool = False


@router.post("/admin/subscribers/{comercio_id}/onboarding")
def start_onboarding(comercio_id: str, body: SubscriberOnboardingCreate | None = None, claims: dict = Depends(_permiso),
                     crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    """Arranca la bienvenida de un suscriptor (las cortesías y los de antes arrancan siempre a mano)."""
    _suscriptor_o_404(crepo, comercio_id)
    return subscriber_care.iniciar_bienvenida(crepo, comercio_id, _actor(claims), cargas.hoy_bolivia(),
                                              force=bool(body and body.force))


class SubscriberTaskDone(BaseModel):
    sent: bool = False
    outcome: str | None = None


class SubscriberTaskSkip(BaseModel):
    note: str | None = None


def _tarea_abierta_o_error(crepo: ContentRepo, task_id: str) -> dict:
    t = crepo.get_task(task_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    if t["status"] != "open":
        raise HTTPException(status_code=409, detail="La tarea ya está cerrada")
    return t


@router.post("/admin/subscribers/tasks/{task_id}/done")
def task_done(task_id: str, body: SubscriberTaskDone, claims: dict = Depends(_permiso),
              crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    """Marca la tarea como hecha. Con `sent`, guarda el texto que se iba a mandar (`sent_text`)."""
    hoy = cargas.hoy_bolivia()
    t = _tarea_abierta_o_error(crepo, task_id)
    resultado = (body.outcome or "").strip() or None
    if resultado and len(resultado) > 500:
        raise HTTPException(status_code=400, detail="Lo que te dijo admite hasta 500 caracteres")
    if t["kind"] in subscriber_messages.NECESITAN_RESULTADO and not resultado:
        raise HTTPException(status_code=400, detail="Contá qué te dijo")
    firmante = claims.get("nombre")
    patch = {"status": "done", "outcome": resultado, "done_by": _actor(claims),
             "done_at": datetime.now(timezone.utc).isoformat()}
    if body.sent:
        actual = _tareas(crepo, [t], firmante, hoy)[0]
        patch["sent_text"] = actual.get("message_text")
    nueva = crepo.update_task(task_id, patch, if_status="open")
    if not nueva:
        raise HTTPException(status_code=409, detail="La tarea ya está cerrada")
    return _tareas(crepo, [nueva], firmante, hoy)[0]


@router.post("/admin/subscribers/tasks/{task_id}/skip")
def task_skip(task_id: str, body: SubscriberTaskSkip, claims: dict = Depends(_permiso),
              crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    hoy = cargas.hoy_bolivia()
    _tarea_abierta_o_error(crepo, task_id)
    nota = (body.note or "").strip() or None
    if nota and len(nota) > 300:
        raise HTTPException(status_code=400, detail="La nota admite hasta 300 caracteres")
    nueva = crepo.update_task(task_id, {"status": "skipped", "note": nota, "done_by": _actor(claims),
                                        "done_at": datetime.now(timezone.utc).isoformat()}, if_status="open")
    if not nueva:
        raise HTTPException(status_code=409, detail="La tarea ya está cerrada")
    return _tareas(crepo, [nueva], claims.get("nombre"), hoy)[0]
