"""Ingesta de WhatsApp: convierte un mensaje del vendedor en una publicación
PENDIENTE de moderación. Idempotente por wa_message_id.

Flujo (el corazón del producto):
  vendedor manda por WhatsApp (oferta/video/novedad)
    -> WAHA dispara webhook
    -> guardamos el crudo en wa_inbox (fuente de verdad)
    -> asociamos/creamos el comercio por su número
    -> creamos publicacion estado='pendiente'
    -> el moderador aprueba -> aparece en el feed en vivo

Excepción a ese flujo: mensajes "CONFIRMAR-XXXXXX" (login/recuperación de
cuenta por WhatsApp entrante, ver docs/pendientes.md sección 0) — se
interceptan ANTES de la lógica de arriba, si no quedarían creando
comercios/publicaciones fantasma a partir de un mensaje que no es una oferta.
"""
import re

import structlog

from app.db.repository import Repo, get_repo
from app.models.whatsapp import WahaEvent, WahaMessagePayload

logger = structlog.get_logger()

_MESSAGE_EVENTS = {"message", "message.any"}
_RE_CONFIRMAR = re.compile(r"^\s*CONFIRMAR-(\d{6})\s*$", re.IGNORECASE)

# Heurística simple para clasificar el tipo de publicación a partir del texto.
_VIDEO_HINTS = ("tiktok.com", "video", "reel")


class IngestError(Exception):
    """Error recuperable de ingesta."""


def _classify_tipo(payload: WahaMessagePayload) -> str:
    text = (payload.body or "").lower()
    if payload.type in {"video"} or any(h in text for h in _VIDEO_HINTS):
        return "video"
    if payload.type in {"image"} or "oferta" in text or "$" in text or "bs" in text:
        return "oferta"
    return "novedad"


def _extract_tiktok(body: str | None) -> str | None:
    if not body:
        return None
    for token in body.split():
        if "tiktok.com" in token:
            return token.strip()
    return None


def _extract_location(raw: dict) -> tuple[float, float, str | None] | None:
    """Ubicación compartida por WhatsApp. Tolera varias formas de WAHA."""
    loc = raw.get("location") or {}
    lat = loc.get("latitude") or loc.get("lat") or raw.get("latitude") or raw.get("lat")
    lng = loc.get("longitude") or loc.get("lng") or raw.get("longitude") or raw.get("lng")
    if lat is None or lng is None:
        return None
    direccion = loc.get("address") or loc.get("name") or raw.get("address")
    try:
        return float(lat), float(lng), direccion
    except (TypeError, ValueError):
        return None


def _handle_confirmacion(payload: WahaMessagePayload, codigo: str, repo: Repo) -> dict:
    """Alguien mandó 'CONFIRMAR-XXXXXX' — probar contra usuarios (comprador)
    y comercio_usuarios (dueño de comercio). Solo uno de los dos va a
    matchear, si alguno; no hay ambigüedad real entre ambos flujos."""
    ok_usuario = repo.confirmar_reset_code_usuario(payload.phone, codigo)
    ok_comercio = False if ok_usuario else repo.confirmar_reset_code_comercio(payload.phone, codigo)
    confirmado = ok_usuario or ok_comercio
    logger.info("ingest.confirmacion", phone=payload.phone, confirmado=confirmado,
                tipo="usuario" if ok_usuario else ("comercio" if ok_comercio else None))
    return {"captured": True, "confirmacion": True, "confirmado": confirmado}


def handle_message(event_dict: dict, repo: Repo | None = None) -> dict:
    repo = repo or get_repo()
    event = WahaEvent.model_validate(event_dict)

    if event.event not in _MESSAGE_EVENTS:
        return {"captured": False, "ignored": event.event}

    payload = WahaMessagePayload.model_validate(event.payload)
    if not payload.id:
        raise IngestError("payload sin 'id' (no se puede deduplicar)")
    if payload.from_me:
        return {"captured": False, "reason": "mensaje saliente"}

    match_confirmacion = _RE_CONFIRMAR.match(payload.body or "")
    if match_confirmacion:
        return _handle_confirmacion(payload, match_confirmacion.group(1), repo)

    # 1) Bitácora cruda (idempotente)
    inserted_inbox = repo.insert_wa_inbox(
        {
            "wa_message_id": payload.id,
            "wa_jid": payload.from_ or "",
            "phone": payload.phone,
            "tipo": payload.type,
            "body": payload.body,
            "media_url": payload.media_url,
            "raw": event.payload,
        }
    )
    if not inserted_inbox:
        logger.info("ingest.duplicado", wa_message_id=payload.id)
        return {"captured": True, "duplicate": True}

    # 2) Asociar / crear comercio por número (alta progresiva)
    comercio = repo.upsert_comercio_by_jid(payload.from_ or "", payload.phone)

    # 2.b) ¿Compartió su ubicación por WhatsApp? -> actualizamos el comercio y listo.
    #      (forma simple para vendedores con poca tecnología: tocar "compartir ubicación")
    loc = _extract_location(event.payload)
    if payload.type == "location" or loc:
        if loc:
            repo.actualizar_ubicacion_comercio(comercio["id"], loc[0], loc[1], loc[2])
        logger.info("ingest.ubicacion", comercio=comercio["slug"], ok=bool(loc))
        return {"captured": True, "comercio": comercio["slug"], "ubicacion_actualizada": bool(loc)}

    # 3) Crear publicación. Comercio confiable -> publica directo; si no, a moderación.
    from datetime import datetime, timezone

    confiable = bool(comercio.get("confiable"))
    now = datetime.now(timezone.utc).isoformat()
    tipo = _classify_tipo(payload)
    row = {
        "comercio_id": comercio["id"],
        "tipo": tipo,
        "titulo": (payload.body or "").split("\n")[0][:120] or None,
        "descripcion": payload.body,
        "imagen_url": payload.media_url if payload.type == "image" else None,
        "tiktok_url": _extract_tiktok(payload.body),
        "estado": "aprobado" if confiable else "pendiente",
        "approved_at": now if confiable else None,
        "moderado_por": "auto-confiable" if confiable else None,
        "moderado_at": now if confiable else None,
        "origen": "whatsapp",
        "wa_message_id": payload.id,
        "raw": event.payload,
    }
    repo.insert_publicacion(row)

    estado = row["estado"]
    logger.info("ingest.publicacion", comercio=comercio["slug"], tipo=tipo, estado=estado)
    return {"captured": True, "comercio": comercio["slug"], "tipo": tipo, "estado": estado}
