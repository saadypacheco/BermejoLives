"""Cómo se ve cada cosa en la API (los schemas de §8.2 de docs/contenido-redes-tecnico.md).

Funciones que arman los dicts de respuesta a partir de las filas. Los archivos se devuelven como
rutas FIRMADAS relativas (`/content/files/...`): el front les antepone la URL de la API. Nada
acá escribe en la base.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from app.core.config import settings
from app.services import cargas, content_captions, content_consent, content_posts, content_storage, subscriber_messages

PILLAR_LABEL = {"comercio_del_dia": "Comercio del día", "ofertas": "Ofertas de la semana"}
STATUS_LABEL = {"queued": "En cola", "rendering": "Armando el video", "ready_for_review": "Para revisar",
                "approved": "Aprobada", "published": "Publicada", "skipped": "Salteada", "failed": "Con problemas"}
POST_STATUS_LABEL = {"pending": "Pendiente", "claimed": "Publicando", "posted": "Publicada", "skipped": "Salteada"}
WEEKDAY_LABEL = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
#: Estados en los que el video de la pieza se puede ver.
CON_VIDEO = ("ready_for_review", "approved", "published")


def whatsapp_valido(numero: str | None) -> str | None:
    """El WhatsApp del comercio si tiene al menos 8 dígitos; si no, None (el front muestra «Copiar texto»)."""
    n = re.sub(r"\D", "", numero or "")
    return n if len(n) >= 8 else None


# ──────────────────────────────────────────────────────────────── fotos

def asset_response(a: dict) -> dict:
    ancho, alto = int(a.get("width") or 0), int(a.get("height") or 0)
    return {
        "id": a["id"], "comercio_id": a["comercio_id"], "width": ancho, "height": alto, "bytes": a.get("bytes"),
        "too_small": min(ancho, alto) < content_storage.LADO_MENOR_MINIMO,
        "usable_for_social": bool(a.get("usable_for_social")), "has_people": bool(a.get("has_people")),
        "people_ok": a.get("people_ok"), "use_count": int(a.get("use_count") or 0),
        "last_used_at": a.get("last_used_at"),
        "thumb_url": content_storage.ruta_firmada("asset", a["id"], "thumb"),
        "file_url": content_storage.ruta_firmada("asset", a["id"], "file"),
        "created_at": a.get("created_at"), "uploaded_by": a.get("uploaded_by"),
    }


def sirve_para_video(a: dict) -> bool:
    """Una foto del banco que el selector puede usar: autorizada para redes, sin personas sin
    consentimiento y con lado menor >= 720 px."""
    return content_storage.asset_sirve(a)


def asset_list_response(assets: list[dict]) -> dict:
    return {"items": [asset_response(a) for a in assets],
            "usable_for_video": sum(1 for a in assets if sirve_para_video(a)), "min_for_video": 4}


# ──────────────────────────────────────────────────────────────── piezas

def _url_de_archivo(p: dict, kind: str) -> str | None:
    ruta = p.get("video_path") if kind == "video" else p.get("cover_path")
    if not ruta or p.get("files_purged_at") or p.get("status") not in CON_VIDEO:
        return None
    return content_storage.ruta_firmada("piece", p["id"], kind)


def piece_summary(p: dict) -> dict:
    f = p.get("facts") or {}
    return {
        "id": p["id"], "scheduled_for": p["scheduled_for"], "pillar": p["pillar"],
        "pillar_label": PILLAR_LABEL.get(p["pillar"], p["pillar"]), "status": p["status"],
        "status_label": STATUS_LABEL.get(p["status"], p["status"]),
        "comercio": {"id": p["comercio_id"], "nombre": f.get("nombre"), "slug": f.get("slug")} if p.get("comercio_id") else None,
        "ciudad_nombre": f.get("ciudad"), "counts_for_quota": bool(p.get("counts_for_quota")),
        "cover_url": _url_de_archivo(p, "cover"), "duration_s": float(p["duration_s"]) if p.get("duration_s") is not None else None,
        "skip_reason": p.get("skip_reason"), "render_error": p.get("render_error"),
    }


def post_response(piece: dict, post: dict, ahora: datetime | None = None) -> dict:
    estado = content_posts.estado_efectivo(post, ahora)
    vigente = estado == "claimed"
    vence = None
    if vigente:
        desde = content_posts._parse(post.get("claimed_at"))
        vence = (desde + timedelta(minutes=settings.content_claim_minutes)).isoformat() if desde else None
    return {
        "id": post["id"], "network": post["network"], "network_label": content_captions.NETWORK_LABEL[post["network"]],
        "status": estado, "ref_tag": post["ref_tag"],
        "caption_text": content_captions.caption_text(piece, post["network"], post["ref_tag"]),
        "claimed_by": post.get("claimed_by") if vigente else None,
        "claimed_by_name": content_posts.nombre_de(post.get("claimed_by")) if vigente else None,
        "claimed_at": post.get("claimed_at") if vigente else None, "claim_expires_at": vence,
        "posted_by": post.get("posted_by"), "posted_at": post.get("posted_at"), "post_url": post.get("post_url"),
        "posted_without_link": bool(post.get("posted_without_link")), "skip_reason": post.get("skip_reason"),
    }


def source_response(s: dict, facts: dict) -> dict:
    if s["source_type"] == "asset":
        thumb = content_storage.ruta_firmada("asset", s["source_id"], "thumb") if s.get("source_id") else None
    else:
        thumb = s.get("file_ref")
    if facts.get("pillar") == "ofertas":
        nombre = (s.get("caption_fact") or "").split(" · ")[0] or None
    else:
        nombre = facts.get("nombre")
    return {"position": s["position"], "source_type": s["source_type"], "thumb_url": thumb,
            "caption_fact": s.get("caption_fact"), "comercio_nombre": nombre}


def piece_response(p: dict, fuentes: list[dict], posts: list[dict], ahora: datetime | None = None) -> dict:
    f = p.get("facts") or {}
    return {
        **piece_summary(p),
        "facts": f, "caption_tiktok": p.get("caption_tiktok"), "caption_ig": p.get("caption_ig"),
        "caption_channel": p.get("caption_channel"), "hashtags": p.get("hashtags") or [],
        "hashtags_allowed": f.get("hashtags_allowed") or [], "caption_engine": p.get("caption_engine"),
        "caption_checks": p.get("caption_checks") or [], "caption_edited": bool(p.get("caption_edited")),
        "sources": [source_response(s, f) for s in fuentes],
        "video_url": _url_de_archivo(p, "video"),
        "render": {"attempts": int(p.get("render_attempts") or 0), "next_at": p.get("render_next_at"),
                   "started_at": p.get("render_started_at"), "ms": p.get("render_ms")},
        "posts": [post_response(p, x, ahora) for x in posts],
        "approved_by": p.get("approved_by"), "approved_at": p.get("approved_at"),
    }


def cargar_pieza(crepo, p: dict, ahora: datetime | None = None) -> dict:
    return piece_response(p, crepo.list_sources(p["id"]), crepo.list_posts([p["id"]]), ahora)


def cargar_piezas(crepo, piezas: list[dict], ahora: datetime | None = None) -> list[dict]:
    """Varias piezas con sus fuentes y posteos (los posteos en una sola consulta)."""
    posts = crepo.list_posts([p["id"] for p in piezas]) if piezas else []
    por_pieza: dict[str, list[dict]] = {}
    for x in posts:
        por_pieza.setdefault(x["piece_id"], []).append(x)
    return [piece_response(p, crepo.list_sources(p["id"]), por_pieza.get(p["id"], []), ahora) for p in piezas]


# ───────────────────────────────────────────────────────── suscriptores

def estado_de_suscripcion(c: dict, hoy: date) -> str:
    """Los mismos valores que `list_suscripciones` (con `al_dia` en vez de `activo`)."""
    if c.get("suspendido"):
        return "suspendido"
    if c.get("plan_cortesia"):
        return "cortesia"
    hasta = _fecha(c.get("paga_hasta"))
    if hasta is None:
        return "sin_plan"
    if hasta < hoy:
        return "vencido"
    if hasta <= hoy + timedelta(days=5):
        return "por_vencer"
    return "al_dia"


def _fecha(v) -> date | None:
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def consent_response(fila: dict | None) -> dict:
    return content_consent.respuesta(fila)


def mensaje_de_tarea(task: dict, comercio: dict, perfil: dict | None, firmante: str | None,
                     reporte: dict | None = None, pieza: dict | None = None, posts: list[dict] | None = None) -> str | None:
    """El texto de una tarea armado con el nombre de quien la abre."""
    kind = task["kind"]
    datos_pieza = None
    if kind == "piece_delivery" and pieza and pieza.get("share_token"):
        posteadas = [x for x in (posts or []) if x.get("status") == "posted"]
        link = None
        for red in ("tiktok", "instagram", "facebook"):
            link = next((x.get("post_url") for x in posteadas if x["network"] == red and x.get("post_url")), None)
            if link:
                break
        datos_pieza = {"redes": [x["network"] for x in posteadas], "link_post": link, "share_token": pieza["share_token"]}
    return subscriber_messages.mensaje_de_tarea(
        kind, persona_=subscriber_messages.persona((perfil or {}).get("contact_person"), comercio.get("nombre")),
        firmante_=subscriber_messages.firmante(firmante), comercio=comercio.get("nombre") or "tu comercio",
        slug=comercio.get("slug"), paga_hasta=comercio.get("paga_hasta"),
        reporte=(reporte or {}).get("data") if reporte else None, pieza=datos_pieza)


def task_response(task: dict, comercio: dict, perfil: dict | None, firmante: str | None, hoy: date,
                  reporte: dict | None = None, pieza: dict | None = None, posts: list[dict] | None = None) -> dict:
    kind = task["kind"]
    texto = mensaje_de_tarea(task, comercio, perfil, firmante, reporte, pieza, posts)
    due = _fecha(task.get("due_on"))
    return {
        "id": task["id"], "comercio_id": task["comercio_id"], "comercio_nombre": comercio.get("nombre"),
        "kind": kind, "kind_label": subscriber_messages.ETIQUETA_TAREA.get(kind, kind), "due_on": task["due_on"],
        "status": task["status"], "overdue": bool(task["status"] == "open" and due and due < hoy),
        "message_template": subscriber_messages.PLANTILLA_POR_TAREA.get(kind) if texto else None,
        "message_text": texto, "whatsapp": whatsapp_valido(comercio.get("whatsapp")) if texto else None,
        "call_script": subscriber_messages.GUION_LLAMADA if kind == "churn_call" else None,
        "needs_outcome": kind in subscriber_messages.NECESITAN_RESULTADO,
        "piece_id": task.get("piece_id"), "report_id": task.get("report_id"), "outcome": task.get("outcome"),
        "done_by": task.get("done_by"), "done_at": task.get("done_at"), "auto_closed": bool(task.get("auto_closed")),
    }


def report_response(r: dict | None) -> dict | None:
    if not r:
        return None
    return {"id": r["id"], "period_start": r["period_start"], "period_end": r["period_end"], "data": r.get("data") or {}}


def hoy_bolivia() -> date:
    return cargas.hoy_bolivia()


def ahora_utc() -> datetime:
    return datetime.now(timezone.utc)
