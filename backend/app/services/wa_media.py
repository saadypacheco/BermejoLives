"""Bajar a disco propio la imagen que llegó por WhatsApp.

POR QUÉ EXISTE
==============

Hasta ahora la publicación guardaba `imagen_url = payload.media_url`, que es la
URL **interna y efímera** que sirve WAHA desde su propio volumen. Dos problemas,
y el segundo es el grave:

  1. Es una URL de la red privada de Docker (`http://waha:3000/...`): el
     navegador de un comprador no la alcanza nunca.
  2. Vive lo que vive el volumen de WAHA. Cuando se rota, se limpia o se
     recrea el contenedor, la foto desaparece — y **acá la foto ES la oferta**.
     Una publicación aprobada con la imagen rota es peor que no tenerla: ocupa
     el lugar de una oferta buena en el feed.

Así que se baja apenas llega, se procesa igual que cualquier foto del sitio
(reorientar por EXIF, 1280px, JPEG 80) y se guarda en el volumen de fotos del
backend, el mismo que sirve /fotos/... Desde ese momento la oferta no depende
de WAHA para nada.

Si falla, devuelve None y el caller sigue: una publicación sin imagen se puede
completar desde el panel; una ingesta que se cae pierde el mensaje entero.
"""
import secrets

import structlog

from app.core.config import settings

logger = structlog.get_logger()

_TIMEOUT = 20.0
_MAX_BYTES = 12 * 1024 * 1024   # 12 MB: arriba de eso no es una foto de vidriera


def _url_alcanzable(url: str) -> str:
    """Reescribe el host del mediaUrl al que el backend sí puede alcanzar.

    El `mediaUrl` lo arma WAHA con el host que tiene configurado, no con el que
    usa quien lo consume. Si nadie le setea `WHATSAPP_FILES_URL`, publica algo
    como `http://localhost:3000/api/files/...` — y ese `localhost` es el del
    contenedor de WAHA. El backend, que corre en otro contenedor, lo interpreta
    como el suyo, no encuentra nada, y la publicación entra sin imagen.

    Sería un error mudo: la ingesta sigue, la oferta se crea, y el síntoma
    aparece recién cuando alguien mira el feed y ve ofertas vacías. Por eso se
    corrige acá en vez de confiar en la configuración de WAHA: el backend ya
    sabe cómo llegar (`WAHA_BASE_URL`), y es el único que tiene que llegar.
    """
    from urllib.parse import urlparse, urlunparse

    base = urlparse(settings.waha_base_url)
    if not base.netloc:
        return url
    actual = urlparse(url)
    if actual.netloc == base.netloc:
        return url
    logger.info("wa_media.host_reescrito", de=actual.netloc, a=base.netloc)
    return urlunparse(actual._replace(scheme=base.scheme or actual.scheme,
                                      netloc=base.netloc))


def descargar_media(url: str | None) -> bytes | None:
    """Trae el archivo de WAHA. Devuelve None si no se puede (nunca lanza)."""
    if not url:
        return None
    import httpx

    url = _url_alcanzable(url)
    try:
        # La API key va igual que en whatsapp_client.py: WAHA protege /api y
        # también los archivos que sirve.
        headers = {"X-Api-Key": settings.waha_api_key} if settings.waha_api_key else {}
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.content
        if len(data) > _MAX_BYTES:
            logger.warning("wa_media.demasiado_grande", url=url, bytes=len(data))
            return None
        return data
    except Exception as exc:  # noqa: BLE001 — la publicación importa más que la foto
        logger.warning("wa_media.descarga_fallo", url=url, error=str(exc))
        return None


def guardar_imagen_publicacion(slug: str, media_url: str | None) -> str | None:
    """Baja la imagen de WAHA y la deja en el disco propio. Devuelve la URL
    pública, o None si no se pudo (y entonces la publicación va sin imagen).

    Se guarda bajo el slug del comercio, igual que las fotos de la ficha, así
    todo lo de un local queda junto y se borra junto.
    """
    from app.services.imagenes import guardar_foto_local, procesar_imagen

    data = descargar_media(media_url)
    if not data:
        return None
    try:
        procesada = procesar_imagen(data, 1280, 80)
    except Exception as exc:  # noqa: BLE001
        # Llegó algo que no es una imagen (un sticker raro, un archivo). No es
        # un error del sistema: es un mensaje que no traía foto publicable.
        logger.info("wa_media.no_es_imagen", error=str(exc))
        return None
    return guardar_foto_local(f"{slug}/ofertas/{secrets.token_hex(8)}.jpg", procesada)
