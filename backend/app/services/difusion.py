"""La oferta aprobada sale también a las redes de URUKU.

QUÉ RESUELVE
============
Las ofertas entran por los grupos de WhatsApp y terminan en el sitio. El sitio
hay que ir a buscarlo; las redes llegan solas. Copiar cada oferta a mano a
cuatro lugares es trabajo que se hace la primera semana y después no.

LO QUE SE PUEDE Y LO QUE NO — CONVIENE SABERLO ANTES DE ESPERARLO
================================================================
- **Canal de WhatsApp**: sale por WAHA, que ya está vinculado. Es el destino
  más valioso y el único que no depende de nadie más.
- **Facebook e Instagram**: salen por la API de Meta, con el token de la
  página. Instagram exige que la imagen esté en una URL pública —la nuestra lo
  está— y publica en dos pasos.
- **TikTok**: la API de publicación pide una app auditada por TikTok y está
  pensada para video. Una foto de oferta no entra por ahí. Se sigue subiendo a
  mano, y no es una limitación de este código.
- **YouTube**: sólo acepta video. Lo mismo.

Poner los cuatro en la lista y que dos fallen siempre en silencio sería peor que
no tenerlos: por eso los destinos son tres y los otros dos están escritos acá
como lo que son, trabajo manual.

CÓMO FALLA
==========
Nada de esto corre dentro del pedido que aprueba la publicación. Se encola, y
un envío que falla queda en la cola con el motivo — visible en el panel,
reintentable. Aprobar una oferta nunca puede romperse porque a Meta se le
venció un token.
"""
from __future__ import annotations

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger()

_TIMEOUT = 30.0

DESTINOS = ("wa_canal", "facebook", "instagram")

NOMBRE = {
    "wa_canal": "Canal de WhatsApp",
    "facebook": "Facebook",
    "instagram": "Instagram",
}


class DifusionError(Exception):
    """Falló el envío a una red. El motivo se guarda en la cola."""


def configurado(destino: str) -> bool:
    if destino == "wa_canal":
        return bool(settings.wa_canal_id.strip() and settings.waha_base_url
                    and settings.waha_api_key)
    if destino == "facebook":
        return bool(settings.facebook_page_id.strip() and settings.facebook_page_token.strip())
    if destino == "instagram":
        return bool(settings.instagram_user_id.strip() and settings.facebook_page_token.strip())
    return False


def _precio(pub: dict) -> str:
    precio, moneda = pub.get("precio"), (pub.get("moneda") or "BOB")
    if precio in (None, ""):
        return ""
    simbolo = {"BOB": "Bs", "USD": "US$", "ARS": "$"}.get(moneda, moneda)
    valor = float(precio)
    monto = f"{valor:,.0f}" if valor == int(valor) else f"{valor:,.2f}"
    return f"{simbolo} {monto.replace(',', '.')}"


def texto_de(pub: dict, comercio: dict | None) -> str:
    """El texto que se publica. Mismo cuerpo para las tres redes.

    Lleva SIEMPRE el nombre del comercio y el enlace a su ficha. Sin el nombre,
    la oferta parece de URUKU y el comerciante no recibe nada de lo que se le
    prometió; sin el enlace, quien la ve no tiene cómo llegar y el posteo es
    decoración.
    """
    nombre = (comercio or {}).get("nombre") or ""
    slug = (comercio or {}).get("slug") or ""
    partes: list[str] = []

    titulo = (pub.get("titulo") or "").strip()
    desc = (pub.get("descripcion") or "").strip()
    cuerpo = titulo or desc
    if titulo and desc and desc != titulo:
        cuerpo = f"{titulo}\n{desc}"
    if cuerpo:
        partes.append(cuerpo[:900])

    precio = _precio(pub)
    if precio:
        partes.append(precio)
    if nombre:
        partes.append(f"📍 {nombre}, Bermejo")
    if slug:
        partes.append(f"{settings.sitio_url.rstrip('/')}/comercios/{slug}")

    return "\n\n".join(partes).strip()


# ─────────────────────────────────────────────────── los envíos, uno por red

def _enviar_wa_canal(texto: str, imagen_url: str | None) -> str | None:
    """Al canal se le manda como a cualquier chat: el identificador termina en
    @newsletter en vez de @c.us. Es el mismo endpoint de siempre."""
    base = settings.waha_base_url.rstrip("/")
    cabeceras = {"X-Api-Key": settings.waha_api_key}
    chat = settings.wa_canal_id.strip()

    if imagen_url:
        url = f"{base}/api/sendImage"
        cuerpo = {"session": "default", "chatId": chat, "caption": texto,
                  "file": {"url": imagen_url}}
    else:
        url = f"{base}/api/sendText"
        cuerpo = {"session": "default", "chatId": chat, "text": texto}

    r = httpx.post(url, json=cuerpo, headers=cabeceras, timeout=_TIMEOUT)
    if r.status_code >= 400:
        raise DifusionError(f"WAHA respondió HTTP {r.status_code}: {r.text[:200]}")
    return None


def _enviar_facebook(texto: str, imagen_url: str | None) -> str | None:
    """Con foto va a /photos y sin foto a /feed: son endpoints distintos, y
    mandar una foto al de texto la pierde sin dar error."""
    pid = settings.facebook_page_id.strip()
    token = settings.facebook_page_token.strip()
    if imagen_url:
        url = f"https://graph.facebook.com/v20.0/{pid}/photos"
        datos = {"url": imagen_url, "caption": texto, "access_token": token}
    else:
        url = f"https://graph.facebook.com/v20.0/{pid}/feed"
        datos = {"message": texto, "access_token": token}

    r = httpx.post(url, data=datos, timeout=_TIMEOUT)
    if r.status_code >= 400:
        raise DifusionError(f"Facebook respondió HTTP {r.status_code}: {r.text[:300]}")
    cuerpo = r.json() or {}
    post = cuerpo.get("post_id") or cuerpo.get("id")
    return f"https://www.facebook.com/{post}" if post else None


def _enviar_instagram(texto: str, imagen_url: str | None) -> str | None:
    """Instagram va en dos pasos: se crea el contenedor y después se publica.

    Y no acepta publicaciones sin imagen. No es una restricción nuestra: la API
    de contenido de Instagram exige una foto o un video. Una oferta que llegó
    sin foto se corta acá con ese motivo, en vez de reintentarse contra un error
    que nunca va a cambiar.
    """
    if not imagen_url:
        raise DifusionError("Instagram no publica sin imagen")

    uid = settings.instagram_user_id.strip()
    token = settings.facebook_page_token.strip()

    r = httpx.post(f"https://graph.facebook.com/v20.0/{uid}/media",
                   data={"image_url": imagen_url, "caption": texto, "access_token": token},
                   timeout=_TIMEOUT)
    if r.status_code >= 400:
        raise DifusionError(f"Instagram (contenedor) HTTP {r.status_code}: {r.text[:300]}")
    contenedor = (r.json() or {}).get("id")
    if not contenedor:
        raise DifusionError("Instagram no devolvió el contenedor")

    r2 = httpx.post(f"https://graph.facebook.com/v20.0/{uid}/media_publish",
                    data={"creation_id": contenedor, "access_token": token},
                    timeout=_TIMEOUT)
    if r2.status_code >= 400:
        # El contenedor quedó creado y sin publicar. No se reintenta desde acá:
        # reintentar crea OTRO contenedor, y dos publicados es peor que ninguno.
        raise DifusionError(f"Instagram (publicar) HTTP {r2.status_code}: {r2.text[:300]}")
    return None


_ENVIOS = {
    "wa_canal": _enviar_wa_canal,
    "facebook": _enviar_facebook,
    "instagram": _enviar_instagram,
}


def enviar(destino: str, texto: str, imagen_url: str | None) -> str | None:
    if destino not in _ENVIOS:
        raise DifusionError(f"destino desconocido: {destino}")
    if not configurado(destino):
        raise DifusionError(f"{NOMBRE[destino]} no está configurado")
    return _ENVIOS[destino](texto, imagen_url)


# ─────────────────────────────────────────────────────────────────── la cola

def encolar(repo, publicacion_id: str) -> int:
    """Anota la publicación para las tres redes. Devuelve cuántas filas creó.

    Encola incluso los destinos sin configurar: quedan esperando y se pueden
    mandar el día que haya token. Si no se anotaran, todo lo aprobado antes de
    configurar Facebook sería imposible de recuperar sin buscarlo a mano en la
    base.

    Nunca lanza. Es la regla que hace que aprobar una oferta no pueda romperse
    por un problema de redes.
    """
    try:
        return repo.encolar_difusion(publicacion_id, list(DESTINOS))
    except Exception:  # noqa: BLE001
        logger.warning("difusion.encolar_fallo", pub=publicacion_id, exc_info=True)
        return 0


def procesar(repo, fila: dict) -> dict:
    """Manda UNA fila de la cola y guarda el resultado."""
    destino = fila["destino"]
    pub = repo.get_publicacion(fila["publicacion_id"])
    if not pub:
        repo.marcar_difusion(fila["id"], "omitido", "la publicación ya no existe")
        return {"estado": "omitido"}

    # Sólo sale lo aprobado. Es la guarda que impide que una foto que un
    # moderador todavía no miró aparezca en el muro de la marca — un error que
    # no se deshace con un "rechazar" en el panel.
    if pub.get("estado") != "aprobado":
        repo.marcar_difusion(fila["id"], "omitido",
                             f"la publicación quedó en '{pub.get('estado')}'")
        return {"estado": "omitido"}

    if not configurado(destino):
        repo.marcar_difusion(fila["id"], "pendiente", f"{NOMBRE[destino]} no está configurado")
        return {"estado": "pendiente", "motivo": "sin configurar"}

    comercio = repo.get_comercio(pub["comercio_id"]) if pub.get("comercio_id") else None
    texto = texto_de(pub, comercio)
    try:
        url = enviar(destino, texto, pub.get("imagen_url"))
    except DifusionError as exc:
        repo.marcar_difusion(fila["id"], "error", str(exc))
        logger.warning("difusion.error", destino=destino, pub=pub["id"], motivo=str(exc))
        return {"estado": "error", "motivo": str(exc)}
    except Exception as exc:  # noqa: BLE001
        repo.marcar_difusion(fila["id"], "error", f"error inesperado: {exc}")
        logger.warning("difusion.error_inesperado", destino=destino, exc_info=True)
        return {"estado": "error", "motivo": str(exc)}

    repo.marcar_difusion(fila["id"], "enviado", None, url)
    logger.info("difusion.enviado", destino=destino, pub=pub["id"])
    return {"estado": "enviado", "url": url}


def enviar_pendientes(repo, limite: int = 20, solo_auto: bool = True) -> dict:
    """Manda lo que está esperando.

    `solo_auto` limita a los destinos que el `.env` marcó como automáticos. El
    panel manda con `solo_auto=False`: ése es el clic explícito de una persona
    que sabe lo que está soltando en el muro de la marca.
    """
    autos = settings.destinos_automaticos()
    filas = repo.difusion_pendientes(limite * 3 if solo_auto else limite)
    hechos: dict[str, int] = {"enviado": 0, "error": 0, "omitido": 0, "pendiente": 0}
    salidas = []
    for fila in filas:
        if solo_auto and fila["destino"] not in autos:
            continue
        if len(salidas) >= limite:
            break
        r = procesar(repo, fila)
        hechos[r["estado"]] = hechos.get(r["estado"], 0) + 1
        salidas.append({"destino": fila["destino"], **r})
    return {"procesados": len(salidas), "resumen": hechos, "detalle": salidas}
