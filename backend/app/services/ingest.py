"""Ingesta de WhatsApp: convierte un mensaje del vendedor en una publicación
PENDIENTE de moderación. Idempotente por wa_message_id.

Flujo (el corazón del producto):
  vendedor manda por WhatsApp (oferta/video/novedad)
    -> WAHA dispara webhook
    -> guardamos el crudo en wa_inbox (fuente de verdad)
    -> asociamos/creamos el comercio por su número
    -> creamos publicacion estado='pendiente'
    -> el moderador aprueba -> aparece en el feed en vivo
"""
import structlog

from app.db.repository import Repo, get_repo
from app.models.whatsapp import WahaEvent, WahaMessagePayload

logger = structlog.get_logger()

_MESSAGE_EVENTS = {"message", "message.any"}

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
