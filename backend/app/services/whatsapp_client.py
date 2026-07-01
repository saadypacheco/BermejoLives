"""Envío saliente de WhatsApp vía WAHA (mismo bridge que la ingesta en ingest.py).

Requiere que WAHA esté desplegado y con una sesión real escaneada — hasta que
eso pase, `enviar_texto` no puede entregar nada y devuelve False sin romper
el flujo que lo llama (ver services/tienda_client.py para el mismo patrón
"modo stub si no hay configuración").
"""
import re

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger()


def _to_jid(telefono: str) -> str:
    digitos = re.sub(r"\D", "", telefono)
    return f"{digitos}@c.us"


def enviar_texto(telefono: str, texto: str) -> bool:
    """Manda un mensaje de texto por WhatsApp. Best-effort: nunca levanta excepción."""
    if not settings.waha_base_url or not settings.waha_api_key:
        logger.warning("whatsapp.no_configurado", telefono=telefono)
        return False
    try:
        r = httpx.post(
            f"{settings.waha_base_url.rstrip('/')}/api/sendText",
            json={"chatId": _to_jid(telefono), "text": texto, "session": "default"},
            headers={"X-Api-Key": settings.waha_api_key},
            timeout=10,
        )
        r.raise_for_status()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("whatsapp.envio_error", telefono=telefono, error=str(exc))
        return False
