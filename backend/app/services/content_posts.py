"""Aprobar una pieza y publicarla a mano, red por red (modo B, docs/contenido-redes-tecnico.md §8.3).

EL FLUJO
========
Revisión → «Aprobar» (nace una fila de `content_posts` por red de `CONTENT_NETWORKS`) → en el
«Paquete del día» alguien RECLAMA una red («la estoy publicando», 20 minutos), la publica a mano
desde la app de la red, y marca «salió» pegando el link (o «salió sin link»). Cuando la última red
queda `posted` o `skipped` (con al menos una `posted`), la pieza pasa a `published`, se genera el
`share_token` de la página del comerciante y, si es propia de un suscriptor, se crea la tarea de
entregársela.

Nada acá publica en una red: WAHA no manda nada y ninguna API de Meta ni TikTok se llama.
Todos los cambios de estado son UPDATE condicionales: dos personas apretando a la vez no pisan.
"""
from __future__ import annotations

import re
import secrets
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse

import structlog
from fastapi import HTTPException

from app.core.config import settings
from app.services import cargas, content_captions, content_consent

logger = structlog.get_logger()

#: Hosts válidos del link de cada red.
HOSTS = {"tiktok": ("tiktok.com", "vm.tiktok.com"), "instagram": ("instagram.com",),
         "facebook": ("facebook.com", "fb.watch", "m.facebook.com"), "wa_channel": ("whatsapp.com",)}
ETIQUETA_LINK = {"tiktok": "TikTok", "instagram": "Instagram", "facebook": "Facebook", "wa_channel": "el canal de WhatsApp"}


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _parse(ts) -> datetime | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def nombre_de(actor: str | None) -> str:
    """Cómo se muestra quien reclamó: la parte del correo antes de la arroba."""
    local = (actor or "").split("@")[0].replace(".", " ").replace("_", " ").strip()
    return local.title() or "alguien"


def reclamo_vigente(post: dict, ahora: datetime | None = None) -> bool:
    """¿Está reclamada y el reclamo no venció? A los 20 minutos se puede volver a tomar."""
    if post.get("status") != "claimed":
        return False
    desde = _parse(post.get("claimed_at"))
    if desde is None:
        return False
    return (ahora or _ahora()) < desde + timedelta(minutes=settings.content_claim_minutes)


def estado_efectivo(post: dict, ahora: datetime | None = None) -> str:
    """El estado que se muestra: un reclamo vencido cuenta como pendiente (se resuelve al leer)."""
    if post.get("status") == "claimed" and not reclamo_vigente(post, ahora):
        return "pending"
    return post.get("status") or "pending"


def _pieza_o_404(crepo, piece_id: str) -> dict:
    p = crepo.get_piece(piece_id)
    if not p:
        raise HTTPException(status_code=404, detail="Pieza no encontrada")
    return p


def _post_o_404(crepo, post_id: str) -> dict:
    p = crepo.get_post(post_id)
    if not p:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    return p


# ───────────────────────────────────────────────────────────── aprobar

def approve(crepo, piece_id: str, actor: str) -> dict:
    """Aprueba una pieza lista para revisar: pasa a `approved` y nacen las filas por red."""
    pieza = _pieza_o_404(crepo, piece_id)
    if pieza["status"] != "ready_for_review":
        raise HTTPException(status_code=409, detail="Sólo se aprueba una pieza lista para revisar")
    # Autorización vigente, comercio activo y fotos que sirven, de CADA fuente (el compilado trae varios comercios).
    motivo = content_consent.motivo_de_bloqueo(crepo, pieza)
    if motivo:
        raise HTTPException(status_code=409, detail=content_consent.MENSAJE_DE_BLOQUEO[motivo])
    nueva = crepo.update_piece(piece_id, {"status": "approved", "approved_by": actor,
                                          "approved_at": _ahora().isoformat()}, if_status="ready_for_review")
    if not nueva:
        raise HTTPException(status_code=409, detail="Sólo se aprueba una pieza lista para revisar")
    mmdd = date.fromisoformat(str(pieza["scheduled_for"])[:10]).strftime("%m%d")
    facts = pieza.get("facts") or {}
    crepo.insert_posts([{"piece_id": piece_id, "network": n, "ref_tag": content_captions.ref_tag(n, facts, mmdd)}
                        for n in settings.content_networks_list()])
    logger.info("content.pieza_aprobada", pieza=piece_id, por=actor)
    return nueva


def _objeciones_ahora(pieza: dict) -> list[str]:
    """El validador de hoy sobre los textos guardados (sin «números ajenos»: eso se miró al generarlos)."""
    return content_captions.validate_piece(pieza.get("facts") or {}, pieza.get("caption_tiktok"), pieza.get("caption_ig"),
                                           pieza.get("caption_channel"), pieza.get("hashtags"), ignorar_numeros=True)


def approve_batch(crepo, ids: list[str], actor: str) -> dict:
    """Aprueba varias. Sólo las que están en verde (sin objeciones del validador) y sin editar."""
    aprobadas, rechazadas = [], []
    for pid in ids:
        p = crepo.get_piece(pid)
        if not p:
            rechazadas.append({"id": pid, "motivo": "Pieza no encontrada"})
        elif p.get("caption_checks"):
            rechazadas.append({"id": pid, "motivo": "El validador tiene objeciones: revisala una por una"})
        elif p.get("caption_edited"):
            rechazadas.append({"id": pid, "motivo": "Tiene textos editados: revisala una por una"})
        elif _objeciones_ahora(p):
            # Los textos se vuelven a pasar por el validador de HOY: uno armado con un validador más flojo
            # (o con datos libres del comercio) no se aprueba en lote.
            rechazadas.append({"id": pid, "motivo": "El validador tiene objeciones: revisala una por una"})
        else:
            try:
                approve(crepo, pid, actor)
                aprobadas.append(pid)
            except HTTPException as exc:
                rechazadas.append({"id": pid, "motivo": str(exc.detail)})
    return {"approved": aprobadas, "refused": rechazadas}


# ───────────────────────────────────────────────────── reclamar y soltar

def claim(crepo, post_id: str, actor: str) -> dict:
    """«Voy a publicar»: reclama la red por 20 minutos."""
    post = _post_o_404(crepo, post_id)
    ahora = _ahora()
    if post["status"] == "posted":
        raise HTTPException(status_code=409, detail="Esta red ya está publicada")
    if post["status"] == "skipped":
        raise HTTPException(status_code=409, detail="Esta red se salteó")
    if reclamo_vigente(post, ahora) and (post.get("claimed_by") or "").lower() != actor.lower():
        minutos = max(1, int((ahora - _parse(post["claimed_at"])).total_seconds() // 60))
        raise HTTPException(status_code=409, detail={
            "codigo": "claimed",
            "mensaje": f"La está publicando {nombre_de(post.get('claimed_by'))} desde hace {minutos} min"})
    # La condición va EN el UPDATE: si dos reclamos llegan juntos, la base deja pasar a uno solo.
    corte = ahora - timedelta(minutes=settings.content_claim_minutes)
    nueva = crepo.claim_post(post_id, actor, ahora.isoformat(), corte.isoformat())
    if nueva:
        return nueva
    actual = crepo.get_post(post_id) or post
    if actual["status"] == "posted":
        raise HTTPException(status_code=409, detail="Esta red ya está publicada")
    if actual["status"] == "skipped":
        raise HTTPException(status_code=409, detail="Esta red se salteó")
    if actual["status"] == "claimed":
        desde = _parse(actual.get("claimed_at")) or ahora
        minutos = max(1, int((ahora - desde).total_seconds() // 60))
        raise HTTPException(status_code=409, detail={
            "codigo": "claimed",
            "mensaje": f"La está publicando {nombre_de(actual.get('claimed_by'))} desde hace {minutos} min"})
    raise HTTPException(status_code=409, detail="Esta red ya no se puede reclamar")


def release(crepo, post_id: str, actor: str) -> dict:
    post = _post_o_404(crepo, post_id)
    if post["status"] != "claimed" or (post.get("claimed_by") or "").lower() != actor.lower():
        raise HTTPException(status_code=409, detail="No la tenías reclamada vos")
    nueva = crepo.update_post(post_id, {"status": "pending", "claimed_by": None, "claimed_at": None},
                              if_status="claimed")
    if not nueva:
        raise HTTPException(status_code=409, detail="No la tenías reclamada vos")
    return nueva


# ─────────────────────────────────────────────────────────────── salió

def validar_link(network: str, url: str | None) -> str:
    """El link normalizado, o 400 «Ese link no es de {red}». Sólo `https://` y los hosts de esa red."""
    limpio = (url or "").strip()
    try:
        u = urlparse(limpio)
    except ValueError:
        u = None
    host = (u.hostname or "").lower() if u else ""
    valido = bool(u and u.scheme == "https" and host and any(host == h or host.endswith("." + h)
                                                            for h in HOSTS[network]))
    if valido and network == "wa_channel" and not (u.path or "").startswith("/channel/"):
        valido = False
    if not valido:
        raise HTTPException(status_code=400, detail=f"Ese link no es de {ETIQUETA_LINK[network]}")
    return limpio[:500]


def mark_posted(crepo, post_id: str, actor: str, post_url: str | None, without_link: bool) -> dict:
    post = _post_o_404(crepo, post_id)
    if post["status"] == "posted":
        raise HTTPException(status_code=409, detail="Esta red ya está publicada")
    if post["status"] == "skipped":
        raise HTTPException(status_code=409, detail="Esta red se salteó")
    if reclamo_vigente(post) and (post.get("claimed_by") or "").lower() != actor.lower():
        raise HTTPException(status_code=409, detail={
            "codigo": "claimed", "mensaje": f"La está publicando {nombre_de(post.get('claimed_by'))}"})
    if post_url and post_url.strip():
        url = validar_link(post["network"], post_url)
        sin_link = False
    elif without_link:
        url, sin_link = None, True
    else:
        raise HTTPException(status_code=400, detail="Pegá el link o marcá que salió sin link")
    nueva = crepo.update_post(post_id, {"status": "posted", "posted_by": actor, "posted_at": _ahora().isoformat(),
                                        "post_url": url, "posted_without_link": sin_link},
                              if_status=["pending", "claimed"])
    if not nueva:
        raise HTTPException(status_code=409, detail="Esta red ya está publicada")
    cerrar_pieza_si_corresponde(crepo, post["piece_id"])
    return nueva


def skip_post(crepo, post_id: str, actor: str, reason: str) -> dict:
    post = _post_o_404(crepo, post_id)
    if post["status"] == "posted":
        raise HTTPException(status_code=409, detail="Ya está publicada")
    motivo = (reason or "").strip()
    if not 1 <= len(motivo) <= 200:
        raise HTTPException(status_code=400, detail="Contá por qué se saltea (hasta 200 caracteres)")
    nueva = crepo.update_post(post_id, {"status": "skipped", "skip_reason": motivo, "claimed_by": None,
                                        "claimed_at": None}, if_status=["pending", "claimed", "skipped"])
    if not nueva:
        raise HTTPException(status_code=409, detail="Ya está publicada")
    cerrar_pieza_si_corresponde(crepo, post["piece_id"])
    return nueva


def cerrar_pieza_si_corresponde(crepo, piece_id: str) -> dict | None:
    """Si todas las redes quedaron `posted` o `skipped` y al menos una `posted`: la pieza pasa a
    `published`, con el `share_token` (60 días) y la tarea de entregársela al comerciante."""
    posts = crepo.list_posts([piece_id])
    if not posts or any(p["status"] in ("pending", "claimed") for p in posts):
        return None
    if not any(p["status"] == "posted" for p in posts):
        return None
    ahora = _ahora()
    pieza = crepo.update_piece(piece_id, {
        "status": "published", "published_at": ahora.isoformat(), "share_token": secrets.token_urlsafe(16),
        "share_expires_at": (ahora + timedelta(days=settings.content_share_days)).isoformat(),
    }, if_status="approved")
    if not pieza:
        return None
    logger.info("content.pieza_publicada", pieza=piece_id, redes=[p["network"] for p in posts if p["status"] == "posted"])
    cid = pieza.get("comercio_id")
    if cid:
        hoy = cargas.hoy_bolivia(ahora)
        crepo.insert_task({"comercio_id": cid, "kind": "piece_delivery", "due_on": hoy.isoformat(),
                           "piece_id": piece_id})
        for t in crepo.list_tasks(status="open", comercio_id=cid, kinds=["first_piece"]):
            crepo.update_task(t["id"], {"status": "done", "auto_closed": True, "done_by": "sistema",
                                        "done_at": ahora.isoformat()}, if_status="open")
    return pieza


def link_de_post(piece: dict, post: dict) -> str:
    """El link que lleva el texto de esta red (sólo Facebook y el canal)."""
    return content_captions.link_de(piece.get("facts") or {}, post["ref_tag"])


def texto_de_post(piece: dict, post: dict) -> str:
    return content_captions.caption_text(piece, post["network"], post["ref_tag"])


_RE_TOKEN = re.compile(r"^[A-Za-z0-9_-]{22,64}$")


def token_valido(token: str | None) -> bool:
    return bool(token and _RE_TOKEN.match(token))
