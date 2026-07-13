"""Envío de código OTP por WhatsApp — proveedor intercambiable vía
WHATSAPP_PROVIDER (env var), sin tocar los endpoints que lo llaman.

- WAHA (hoy): sesión de WhatsApp Web self-hosted. Rápido de levantar y
  gratis, pero corre riesgo real de ban de Meta si se usa en volumen — ver
  docs/pendientes.md, sección 0. Texto libre, no necesita plantilla.
- Cloud API (después): WhatsApp Business Platform, la oficial de Meta.
  Requiere número verificado + una plantilla de categoría "Authentication"
  ya aprobada en el Meta Business Manager — sin eso, no manda nada. No
  acepta texto libre, solo los parámetros de la plantilla.

Ambos proveedores son best-effort: nunca levantan excepción, el caller
solo recibe True/False (igual que antes de esta capa).
"""
import re
from typing import Protocol

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger()


class WhatsAppProvider(Protocol):
    def enviar_codigo_otp(self, telefono: str, codigo: str, contexto: str) -> bool: ...


def _to_jid(telefono: str) -> str:
    digitos = re.sub(r"\D", "", telefono)
    return f"{digitos}@c.us"


_TEXTOS_POR_CONTEXTO = {
    "login": "Tu código de Encontralo: {codigo}\nVence en 15 minutos.",
    "recuperar_comercio": "Tu código para recuperar el acceso a Encontralo: {codigo}\nVence en 15 minutos.",
}


class WAHAProvider:
    def enviar_codigo_otp(self, telefono: str, codigo: str, contexto: str = "login") -> bool:
        if not settings.waha_base_url or not settings.waha_api_key:
            logger.warning("whatsapp.waha_no_configurado", telefono=telefono)
            return False
        plantilla = _TEXTOS_POR_CONTEXTO.get(contexto, _TEXTOS_POR_CONTEXTO["login"])
        try:
            r = httpx.post(
                f"{settings.waha_base_url.rstrip('/')}/api/sendText",
                json={"chatId": _to_jid(telefono), "text": plantilla.format(codigo=codigo), "session": "default"},
                headers={"X-Api-Key": settings.waha_api_key},
                timeout=10,
            )
            r.raise_for_status()
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("whatsapp.waha_envio_error", telefono=telefono, error=str(exc))
            return False


class CloudAPIProvider:
    """WhatsApp Business Platform. La plantilla se arma con un solo parámetro
    de texto (el código) en el body — ajustar `components` acá si la
    plantilla real aprobada en Meta usa otra estructura (ej. botón de
    "copiar código", que va como componente aparte)."""

    def enviar_codigo_otp(self, telefono: str, codigo: str, contexto: str = "login") -> bool:
        if not settings.whatsapp_cloud_phone_id or not settings.whatsapp_cloud_token:
            logger.warning("whatsapp.cloud_no_configurado", telefono=telefono)
            return False
        digitos = re.sub(r"\D", "", telefono)
        try:
            r = httpx.post(
                f"https://graph.facebook.com/v20.0/{settings.whatsapp_cloud_phone_id}/messages",
                json={
                    "messaging_product": "whatsapp",
                    "to": digitos,
                    "type": "template",
                    "template": {
                        "name": settings.whatsapp_cloud_template_otp,
                        "language": {"code": "es"},
                        "components": [
                            {"type": "body", "parameters": [{"type": "text", "text": codigo}]},
                        ],
                    },
                },
                headers={"Authorization": f"Bearer {settings.whatsapp_cloud_token}"},
                timeout=10,
            )
            r.raise_for_status()
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("whatsapp.cloud_envio_error", telefono=telefono, error=str(exc))
            return False


_PROVIDERS: dict[str, type] = {"waha": WAHAProvider, "cloud_api": CloudAPIProvider}


def get_whatsapp_provider() -> WhatsAppProvider:
    cls = _PROVIDERS.get(settings.whatsapp_provider, WAHAProvider)
    return cls()


def enviar_codigo_otp(telefono: str, codigo: str, contexto: str = "login") -> bool:
    """Punto de entrada único — a los endpoints no les importa qué proveedor
    está activo, solo si el envío salió bien."""
    return get_whatsapp_provider().enviar_codigo_otp(telefono, codigo, contexto)
