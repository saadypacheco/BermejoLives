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

from app.services import content_storage

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


#: Qué se le dice a quien intenta aprobar una pieza cuyas fuentes ya no valen (409).
MENSAJE_DE_BLOQUEO = {
    "consent_revoked": "El comercio retiró la autorización para redes",
    "comercio_inactivo": "Un comercio de la pieza ya no está activo",
    "asset_unavailable": "Una foto de la pieza ya no se puede usar en redes: cambiala con «Cambiar fotos»",
}


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


def comercios_de_pieza(pieza: dict, fuentes: list[dict]) -> set[str]:
    """Los comercios que aparecen en la pieza: el dueño (si es propia) y el de CADA fuente
    (el compilado de ofertas no tiene dueño, pero lleva fotos de varios comercios)."""
    ids = {pieza.get("comercio_id")} | {f.get("comercio_id") for f in fuentes}
    return {i for i in ids if i}


def motivo_de_comercios(crepo, pieza: dict, fuentes: list[dict] | None = None) -> str | None:
    """`consent_revoked` / `comercio_inactivo` si ALGÚN comercio de la pieza ya no tiene autorización
    vigente o se dio de baja; None si todos valen."""
    fuentes = crepo.list_sources(pieza["id"]) if fuentes is None else fuentes
    ids = sorted(comercios_de_pieza(pieza, fuentes))
    if not ids:
        return None
    vigentes = crepo.current_consents(ids)
    if any(not (vigentes.get(i) or {}).get("granted") for i in ids):
        return "consent_revoked"
    for i in ids:
        ficha = crepo.get_comercio_ficha(i)
        if not ficha or ficha.get("activo") is False:
            return "comercio_inactivo"
    return None


def fuentes_no_usables(crepo, fuentes: list[dict]) -> list[dict]:
    """Las fuentes del banco que se dieron de baja, se marcaron «no usar en redes» o dejaron de servir
    para un video DESPUÉS de armar la pieza. Se relee cada foto: lo que se copió al armarla no vale."""
    malas = []
    for f in fuentes:
        if f.get("source_type") != "asset" or not f.get("source_id"):
            continue
        a = crepo.get_asset(f["source_id"])
        if not a or not content_storage.asset_sirve(a):
            malas.append(f)
    return malas


def motivo_de_bloqueo(crepo, pieza: dict, fuentes: list[dict] | None = None) -> str | None:
    """Por qué una pieza NO se puede aprobar o renderizar ahora (o None)."""
    fuentes = crepo.list_sources(pieza["id"]) if fuentes is None else fuentes
    motivo = motivo_de_comercios(crepo, pieza, fuentes)
    if motivo:
        return motivo
    return "asset_unavailable" if fuentes_no_usables(crepo, fuentes) else None


def vigente_para_compartir(crepo, pieza: dict) -> bool:
    """¿La página pública de la pieza puede seguir abierta? Autorización vigente y comercio activo de cada
    comercio que aparece en ella."""
    return motivo_de_comercios(crepo, pieza) is None


def saltear_pieza(crepo, p: dict, actor: str, ahora: str, motivo: str = "consent_revoked") -> bool:
    nueva = crepo.update_piece(p["id"], {"status": "skipped", "skip_reason": motivo,
                                         "skipped_by": actor, "skipped_at": ahora}, if_status=PIEZA_ABIERTA)
    if not nueva:
        return False
    for post in crepo.list_posts([p["id"]]):
        if post.get("status") in ("pending", "claimed"):
            crepo.update_post(post["id"], {"status": "skipped", "claimed_by": None, "claimed_at": None,
                                           "skip_reason": "autorización retirada" if motivo == "consent_revoked"
                                           else "foto retirada"}, if_status=["pending", "claimed"])
    return True


def efectos_del_retiro(crepo, comercio_id: str, actor: str) -> dict:
    """Saltea lo que no salió y lista lo que ya está publicado.

    Alcanza a las piezas PROPIAS del comercio y a los COMPILADOS de ofertas (que no tienen dueño pero
    llevan sus fotos): de un compilado se quita sólo la parte de este comercio; si queda por debajo del
    mínimo, se saltea entero; si ya estaba renderizada, se vuelve a encolar el render. Las páginas
    públicas de lo ya publicado dejan de abrir (`share_expires_at`).

    Devuelve `{pieces_skipped, published_posts: [{network, post_url}]}`."""
    from app.services import content_selector            # ciclo: el selector importa este módulo

    ahora = _ahora().isoformat()
    saltadas = rearmadas = 0
    con_posteos_a_listar: list[str] = []              # piezas saltadas que ya salieron en alguna red
    ids_por_fuente = crepo.piece_ids_by_source_comercio(comercio_id)
    piezas = {p["id"]: p for p in crepo.list_pieces(statuses=PIEZA_ABIERTA, comercio_id=comercio_id, limit=500)}
    for pid in ids_por_fuente:
        p = piezas.get(pid) or crepo.get_piece(pid)
        if p and p["status"] in PIEZA_ABIERTA:
            piezas[pid] = p
    for p in piezas.values():
        if p.get("comercio_id") == comercio_id:
            if saltear_pieza(crepo, p, actor, ahora):
                saltadas += 1
                con_posteos_a_listar.append(p["id"])
            continue
        resultado = content_selector.quitar_comercio_de_compilado(crepo, p, comercio_id, actor)
        if resultado == "skipped":
            saltadas += 1
        elif resultado == "rebuilt":
            rearmadas += 1
        if resultado:
            con_posteos_a_listar.append(p["id"])
    publicados: list[dict] = []
    ya_publicadas = {p["id"]: p for p in crepo.list_pieces(statuses=["published"], comercio_id=comercio_id, limit=500)}
    for pid in ids_por_fuente:
        if pid not in ya_publicadas:
            p = crepo.get_piece(pid)
            if p and p["status"] == "published":
                ya_publicadas[pid] = p
    for p in ya_publicadas.values():
        if p.get("share_token"):                      # el link que se le dio al comerciante deja de abrir
            crepo.update_piece(p["id"], {"share_expires_at": ahora})
    a_listar = list(ya_publicadas) + con_posteos_a_listar
    for post in crepo.list_posts(a_listar) if a_listar else []:
        if post.get("status") == "posted":
            publicados.append({"network": post.get("network"), "post_url": post.get("post_url")})
    logger.info("content.consent_retirado", comercio=comercio_id, piezas_saltadas=saltadas,
                piezas_rearmadas=rearmadas, publicados=len(publicados), por=actor)
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
