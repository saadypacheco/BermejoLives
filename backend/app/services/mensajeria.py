"""Una sola puerta para mandar y recibir WhatsApp, sea WAHA o la API oficial.

POR QUÉ, Y QUÉ CAMBIA CUANDO LLEGUE EL VOLUMEN
==============================================
WAHA es automatización no oficial: sirve para arrancar y no es sobre lo que se
construye una operación de miles de comercios. El día que haya que pasar a la
API oficial de Meta, lo que no puede pasar es reescribir la ingesta — que es la
parte más probada del sistema.

Acá se normaliza en los dos sentidos: lo que entra se traduce a la forma que la
ingesta ya entiende, y lo que sale elige proveedor por configuración. Cambiar de
proveedor pasa a ser una línea del `.env`.

LA DIFERENCIA QUE NO SE ARREGLA CON CÓDIGO: LA API OFICIAL NO TIENE GRUPOS
==========================================================================
Meta nunca soportó grupos en su API de negocios, y no hay señales de que lo vaya
a hacer. O sea que el modelo de "un grupo por comercio" **no migra**: en la API
oficial es conversación uno a uno con cada comerciante.

No es una mala noticia. La atribución por número de remitente ya existe y es más
confiable que la del código, un chat directo pesa muchísimo menos que un grupo
en la sesión, y no hay que agregar a nadie a nada — que es justo la operación
que dispara los baneos. Lo que se pierde son los respaldos "mirando" desde
adentro del grupo, que en la API oficial no hacen falta: ahí no hay cuenta que
banear.

Conviene saberlo AHORA y no el día de la migración: cada grupo que se crea hoy
es trabajo que no se transporta.
"""
from __future__ import annotations

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger()

_TIMEOUT = 20.0
_GRAPH = "https://graph.facebook.com/v20.0"


def proveedor() -> str:
    return (settings.whatsapp_provider or "waha").strip().lower()


def usa_cloud() -> bool:
    return proveedor() in {"cloud", "cloud_api", "meta"}


# ───────────────────────────────────────────────────────────────── salida

def enviar_texto(chat: str, texto: str) -> bool:
    """Un mensaje de texto. `chat` es el JID (WAHA) o el teléfono (Cloud).

    Nunca lanza: quien avisa no puede romperse por avisar.
    """
    try:
        return _cloud_texto(chat, texto) if usa_cloud() else _waha_texto(chat, texto)
    except Exception as exc:  # noqa: BLE001
        logger.warning("mensajeria.envio_error", chat=chat, error=str(exc))
        return False


def enviar_imagen(chat: str, imagen_url: str, texto: str = "") -> bool:
    try:
        return (_cloud_imagen(chat, imagen_url, texto) if usa_cloud()
                else _waha_imagen(chat, imagen_url, texto))
    except Exception as exc:  # noqa: BLE001
        logger.warning("mensajeria.envio_error", chat=chat, error=str(exc))
        return False


def _waha_texto(chat: str, texto: str) -> bool:
    if not settings.waha_base_url or not settings.waha_api_key:
        logger.warning("mensajeria.waha_sin_config")
        return False
    r = httpx.post(f"{settings.waha_base_url.rstrip('/')}/api/sendText",
                   json={"chatId": chat, "text": texto, "session": "default"},
                   headers={"X-Api-Key": settings.waha_api_key}, timeout=_TIMEOUT)
    r.raise_for_status()
    return True


def _waha_imagen(chat: str, imagen_url: str, texto: str) -> bool:
    if not settings.waha_base_url or not settings.waha_api_key:
        return False
    r = httpx.post(f"{settings.waha_base_url.rstrip('/')}/api/sendImage",
                   json={"chatId": chat, "caption": texto, "session": "default",
                         "file": {"url": imagen_url}},
                   headers={"X-Api-Key": settings.waha_api_key}, timeout=_TIMEOUT)
    r.raise_for_status()
    return True


def _cloud_destino(chat: str) -> str:
    """La API oficial quiere el teléfono pelado, no el JID."""
    return (chat or "").split("@")[0].lstrip("+")


def _cloud_texto(chat: str, texto: str) -> bool:
    if not settings.whatsapp_cloud_phone_id or not settings.whatsapp_cloud_token:
        logger.warning("mensajeria.cloud_sin_config")
        return False
    r = httpx.post(
        f"{_GRAPH}/{settings.whatsapp_cloud_phone_id}/messages",
        json={"messaging_product": "whatsapp", "to": _cloud_destino(chat),
              "type": "text", "text": {"body": texto}},
        headers={"Authorization": f"Bearer {settings.whatsapp_cloud_token}"},
        timeout=_TIMEOUT)
    r.raise_for_status()
    return True


def _cloud_imagen(chat: str, imagen_url: str, texto: str) -> bool:
    if not settings.whatsapp_cloud_phone_id or not settings.whatsapp_cloud_token:
        return False
    r = httpx.post(
        f"{_GRAPH}/{settings.whatsapp_cloud_phone_id}/messages",
        json={"messaging_product": "whatsapp", "to": _cloud_destino(chat),
              "type": "image", "image": {"link": imagen_url, "caption": texto}},
        headers={"Authorization": f"Bearer {settings.whatsapp_cloud_token}"},
        timeout=_TIMEOUT)
    r.raise_for_status()
    return True


# ───────────────────────────────────────────────────────────────── entrada

def normalizar_entrante(evento: dict) -> dict | None:
    """Traduce un webhook de Meta a la forma de WAHA, que es la que la ingesta
    ya entiende. `None` si el evento no trae ningún mensaje.

    POR QUÉ TRADUCIR EN VEZ DE ENSEÑARLE LOS DOS FORMATOS A LA INGESTA
    ==================================================================
    La ingesta es la parte más probada del sistema —atribución, códigos,
    números propios, explorador, cuotas— y todas esas reglas son independientes
    del proveedor. Meterle un `if` por formato adentro duplicaría cada una de
    esas ramas y las pondría a divergir con el tiempo. Traducir en la puerta
    deja una sola implementación de las reglas.

    Un webhook de Meta puede traer VARIOS mensajes en una tanda. Devuelve el
    primero; el resto va en `_extra`, y el webhook los procesa uno por uno. Es
    la clase de detalle que, ignorado, pierde mensajes en silencio los días de
    mucho movimiento.
    """
    if evento.get("event"):
        return evento                      # ya viene en forma WAHA

    if evento.get("object") != "whatsapp_business_account":
        return None

    mensajes: list[dict] = []
    for entry in evento.get("entry") or []:
        for cambio in entry.get("changes") or []:
            valor = cambio.get("value") or {}
            for m in valor.get("messages") or []:
                traducido = _mensaje_de_meta(m)
                if traducido:
                    mensajes.append(traducido)

    if not mensajes:
        # Los avisos de entrega y lectura también llegan por acá. No son
        # mensajes y no tienen que ensuciar la bandeja.
        return None

    return {"event": "message", "session": "cloud",
            "payload": mensajes[0], "_extra": mensajes[1:]}


_TIPOS_CON_MEDIA = ("image", "video", "document", "audio")


def _mensaje_de_meta(m: dict) -> dict | None:
    tipo = m.get("type") or "text"
    cuerpo = (m.get("text") or {}).get("body")

    media_id = None
    if tipo in _TIPOS_CON_MEDIA:
        media = m.get(tipo) or {}
        media_id = media.get("id")
        cuerpo = media.get("caption") or cuerpo

    telefono = m.get("from") or ""
    return {
        "id": m.get("id"),
        # La API oficial no tiene grupos: siempre es una persona, así que el
        # sufijo es @c.us. Poner @g.us acá haría que la ingesta buscara un
        # grupo que no existe.
        "from": f"{telefono}@c.us" if telefono else None,
        "fromMe": False,
        "body": cuerpo,
        "type": "image" if tipo == "image" else ("video" if tipo == "video" else "text"),
        "timestamp": int(m["timestamp"]) if str(m.get("timestamp") or "").isdigit() else None,
        "hasMedia": bool(media_id),
        # El identificador del archivo, no una URL: en la API oficial se pide
        # aparte y con el token. `descargar_media` sabe distinguirlos.
        "mediaUrl": f"cloud-media:{media_id}" if media_id else None,
        "_data": m,
    }


def descargar_media_cloud(media_id: str) -> bytes | None:
    """Baja un archivo de la API oficial: primero la URL, después el archivo.

    Son dos llamadas porque Meta devuelve una URL firmada y de vida corta, y
    ambas piden el token. Nunca lanza.
    """
    token = settings.whatsapp_cloud_token
    if not token:
        return None
    cab = {"Authorization": f"Bearer {token}"}
    try:
        r = httpx.get(f"{_GRAPH}/{media_id}", headers=cab, timeout=_TIMEOUT)
        r.raise_for_status()
        url = (r.json() or {}).get("url")
        if not url:
            return None
        r2 = httpx.get(url, headers=cab, timeout=_TIMEOUT, follow_redirects=True)
        r2.raise_for_status()
        return r2.content
    except Exception as exc:  # noqa: BLE001
        logger.warning("mensajeria.cloud_media_error", media=media_id, error=str(exc))
        return None
