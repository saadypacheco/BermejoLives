"""La autorización de un comercio para aparecer en las redes de URUKU (§3, T-03).

Es una BITÁCORA (`comercio_social_consents`): cada alta o retiro es una fila nueva con la fecha,
la vía y quién la registró. La vigente de cada comercio sale de la vista
`comercio_social_consent_current`. Un retiro no borra la historia, y no toca `comercios`.

Retirar la autorización TIENE EFECTOS: las piezas del comercio que todavía no salieron pasan a
`skipped` (y sus redes pendientes también), y se devuelve la lista de lo que ya está publicado,
que alguien tiene que borrar a mano de cada red.
"""
from __future__ import annotations

from datetime import datetime, timezone

import structlog
from fastapi import HTTPException

logger = structlog.get_logger()

#: Quién puede registrarla desde cada lugar.
VIAS_PANEL = ("admin", "whatsapp_reply", "subscription")
VIA_AGENTE_ALTA = "agent_signup"
VIA_AGENTE_VISITA = "agent_visit"
VIA_COMERCIO = "merchant_panel"

#: Una pieza en estos estados todavía no salió: si se retira la autorización, se saltea.
PIEZA_ABIERTA = ["queued", "rendering", "ready_for_review", "approved"]


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def respuesta(fila: dict | None) -> dict:
    """`SocialConsentResponse`: todo en null si nunca se registró nada."""
    if not fila:
        return {"granted": None, "via": None, "recorded_at": None, "recorded_by": None, "note": None}
    return {"granted": bool(fila.get("granted")), "via": fila.get("via"), "recorded_at": fila.get("recorded_at"),
            "recorded_by": fila.get("recorded_by"), "note": fila.get("note")}


def vigente(crepo, comercio_id: str) -> dict | None:
    return crepo.current_consents([comercio_id]).get(comercio_id)


def esta_autorizado(crepo, comercio_id: str) -> bool:
    fila = vigente(crepo, comercio_id)
    return bool(fila and fila.get("granted"))


def autorizados(crepo) -> set[str]:
    """Los comercios con autorización vigente (para el selector)."""
    return {cid for cid, f in crepo.current_consents().items() if f.get("granted")}


def registrar(crepo, comercio_id: str, granted: bool, via: str, recorded_by: str,
              note: str | None = None) -> dict:
    """Anota un alta o un retiro. Devuelve la fila registrada. Al retirar, llamar a `efectos_del_retiro`."""
    nota = (note or "").strip() or None
    if nota and len(nota) > 300:
        raise HTTPException(status_code=400, detail="La nota admite hasta 300 caracteres")
    fila = crepo.add_consent({"comercio_id": comercio_id, "granted": bool(granted), "via": via,
                              "recorded_by": recorded_by, "note": nota,
                              "recorded_at": _ahora().isoformat()})
    logger.info("content.consent_registrado", comercio=comercio_id, granted=bool(granted), via=via, por=recorded_by)
    return fila


def efectos_del_retiro(crepo, comercio_id: str, actor: str) -> dict:
    """Saltea lo que no salió y lista lo que ya está publicado.

    Devuelve `{pieces_skipped, published_posts: [{network, post_url}]}`."""
    ahora = _ahora().isoformat()
    saltadas = 0
    for p in crepo.list_pieces(statuses=PIEZA_ABIERTA, comercio_id=comercio_id, limit=500):
        nueva = crepo.update_piece(p["id"], {"status": "skipped", "skip_reason": "consent_revoked",
                                             "skipped_by": actor, "skipped_at": ahora}, if_status=PIEZA_ABIERTA)
        if not nueva:
            continue
        saltadas += 1
        for post in crepo.list_posts([p["id"]]):
            if post.get("status") in ("pending", "claimed"):
                crepo.update_post(post["id"], {"status": "skipped", "skip_reason": "autorización retirada",
                                               "claimed_by": None, "claimed_at": None},
                                  if_status=["pending", "claimed"])
    publicados: list[dict] = []
    publicadas = crepo.list_pieces(statuses=["published"], comercio_id=comercio_id, limit=500)
    for post in crepo.list_posts([p["id"] for p in publicadas]) if publicadas else []:
        if post.get("status") == "posted":
            publicados.append({"network": post.get("network"), "post_url": post.get("post_url")})
    logger.info("content.consent_retirado", comercio=comercio_id, piezas_saltadas=saltadas,
                publicados=len(publicados), por=actor)
    return {"pieces_skipped": saltadas, "published_posts": publicados}


def aplicar(crepo, comercio_id: str, granted: bool, via: str, recorded_by: str,
            note: str | None = None) -> dict:
    """Registra y, si es un retiro, aplica los efectos. Devuelve `SocialConsentResponse`, o
    `SocialConsentRevokeResponse` al retirar."""
    fila = registrar(crepo, comercio_id, granted, via, recorded_by, note)
    if granted:
        return respuesta(fila)
    efectos = efectos_del_retiro(crepo, comercio_id, recorded_by)
    return {"consent": respuesta(fila), **efectos}
