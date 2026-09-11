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
from app.services import mensajeria

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


def destinos_activos() -> tuple[str, ...]:
    """A qué redes se encola. Con WAHA en sólo lectura, el canal NO: se
    publica a mano desde la tablet, y encolarlo igual llenaría la cola de
    filas que nunca van a salir."""
    if settings.wa_solo_lectura and not mensajeria.usa_cloud():
        return tuple(d for d in DESTINOS if d != "wa_canal")
    return DESTINOS


def configurado(destino: str) -> bool:
    if destino == "wa_canal":
        if settings.wa_solo_lectura and not mensajeria.usa_cloud():
            return False
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
    chat = settings.wa_canal_id.strip()
    ok = (mensajeria.enviar_imagen(chat, imagen_url, texto) if imagen_url
          else mensajeria.enviar_texto(chat, texto))
    if not ok:
        raise DifusionError("no se pudo publicar en el canal (ver los registros)")
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
        return repo.encolar_difusion(publicacion_id, list(destinos_activos()))
    except Exception:  # noqa: BLE001
        logger.warning("difusion.encolar_fallo", pub=publicacion_id, exc_info=True)
        return 0


def _freno_del_canal(repo, comercio: dict | None) -> str | None:
    """¿Esta oferta entra hoy al canal? Devuelve el motivo si NO entra.

    POR QUÉ EL CANAL TIENE TOPE Y LAS OTRAS REDES NO
    ================================================
    Facebook e Instagram tienen algoritmo: publicar de más se paga en alcance,
    y el que no quiere ver una publicación sigue scrolleando. El canal de
    WhatsApp no: cada publicación es una notificación en el teléfono de cada
    seguidor. Treinta comercios del plan Publica son cincuenta notificaciones
    diarias, y eso no lo aguanta nadie.

    Los seguidores son lo único de todo el sistema que no se puede rehacer. Los
    grupos se recrean; el que se hartó y dejó de seguir no vuelve.
    """
    from app.services import planes

    if settings.difusion_canal_solo_planes:
        plan = planes.plan_de(repo, comercio or {})
        if not planes.funcion(plan, "canal_wa"):
            return f"el plan {plan.get('nombre')} no incluye lugar en el canal"

    tope = settings.difusion_canal_max_dia
    if tope and repo.contar_difusion_hoy("wa_canal") >= tope:
        return f"el canal ya publicó {tope} hoy; sale mañana"
    return None


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

    if destino == "wa_canal":
        freno = _freno_del_canal(repo, comercio)
        if freno:
            # Queda PENDIENTE, no omitida: mañana hay lugar de nuevo. Marcarla
            # como omitida la perdería para siempre, y una oferta que se
            # descarta por un tope de ayer es una oferta que el comerciante
            # nunca va a ver publicada.
            repo.marcar_difusion(fila["id"], "pendiente", freno)
            return {"estado": "pendiente", "motivo": freno}
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


def enviar_pendientes(repo, limite: int = 20, solo_auto: bool = True,
                      pausa: float | None = None) -> dict:
    """Manda lo que está esperando, de a uno y con pausa entre medio.

    `solo_auto` limita a los destinos que el `.env` marcó como automáticos. El
    panel manda con `solo_auto=False`: ése es el clic explícito de una persona
    que sabe lo que está soltando en el muro de la marca.

    LA PAUSA
    ========
    El canal de WhatsApp sale por WAHA, que es automatización no oficial. Lo que
    WhatsApp mira para banear son las ráfagas: si se aprueban veinte ofertas de
    golpe —que es lo que pasa después de una tanda de moderación— salen veinte
    publicaciones en cuatro segundos, y eso no se parece a una persona con un
    teléfono.

    El que se banearía es el OPERATIVO: el mismo número vinculado a WAHA, el que
    está en todos los grupos y el dueño del canal. Se caen las tres cosas
    juntas, así que la pausa es barata al lado de lo que evita.
    """
    import time

    espera = settings.difusion_pausa_seg if pausa is None else pausa
    autos = settings.destinos_automaticos()
    filas = repo.difusion_pendientes(limite * 3 if solo_auto else limite)
    hechos: dict[str, int] = {"enviado": 0, "error": 0, "omitido": 0, "pendiente": 0}
    salidas = []
    for fila in filas:
        if solo_auto and fila["destino"] not in autos:
            continue
        if len(salidas) >= limite:
            break
        # La pausa va ANTES del segundo envío y no después del último: esperar
        # al final retrasa la respuesta del panel sin proteger nada.
        if salidas and espera:
            time.sleep(espera)
        r = procesar(repo, fila)
        hechos[r["estado"]] = hechos.get(r["estado"], 0) + 1
        salidas.append({"destino": fila["destino"], **r})
    return {"procesados": len(salidas), "resumen": hechos, "detalle": salidas}
