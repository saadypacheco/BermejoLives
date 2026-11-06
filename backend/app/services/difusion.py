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

from datetime import datetime, timezone

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
    """Falló el envío a una red. El motivo se guarda en la cola.

    `ig_container_id`: si Instagram ya había creado el contenedor, viaja con el error para guardarlo
    (el reintento lo consulta antes de crear otro)."""

    ig_container_id: str | None = None

    def __init__(self, mensaje: str = "", ig_container_id: str | None = None):
        super().__init__(mensaje)
        self.ig_container_id = ig_container_id


class DifusionIncierta(DifusionError):
    """Se mandó y NO se sabe si salió (timeout, corte tras enviar, 5xx de Meta). La fila queda `incierto`:
    se consulta a Meta antes de reintentar, porque reintentar a ciegas puede duplicar el posteo."""


class Publicado(str):
    """Lo que devuelve un envío: la URL del posteo (puede ser "") más los ids que dio la red."""

    external_post_id: str | None = None
    ig_container_id: str | None = None
    permalink: str | None = None

    def __new__(cls, url: str | None = None, external_post_id: str | None = None,
                ig_container_id: str | None = None, permalink: str | None = None):
        obj = super().__new__(cls, url or "")
        obj.external_post_id = external_post_id
        obj.ig_container_id = ig_container_id
        obj.permalink = permalink
        return obj


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


# El `?ref=` que lleva el enlace según por dónde sale: es lo que después
# separa, en Admin › Panel › Llegadas, lo que trajo Facebook de lo que trajo
# Instagram o el canal (0114).
_REF_POR_DESTINO = {"facebook": "fb", "instagram": "ig", "wa_canal": "canal"}


def _pie(comercio: dict | None, destino: str | None, ciudad: dict | None) -> list[str]:
    """El pie estándar: dónde está el comercio y el enlace a su ficha (con el `?ref=` de la red)."""
    nombre = (comercio or {}).get("nombre") or ""
    slug = (comercio or {}).get("slug") or ""
    partes: list[str] = []
    if nombre:
        embebida = (comercio or {}).get("ciudades")
        fila_ciudad = ciudad or (embebida if isinstance(embebida, dict) else None) or {}
        nombre_ciudad = (fila_ciudad.get("nombre") or "").strip()
        partes.append(f"📍 {nombre}, {nombre_ciudad}" if nombre_ciudad else f"📍 {nombre}")
    if slug:
        ref = _REF_POR_DESTINO.get(destino or "")
        partes.append(f"{settings.sitio_url.rstrip('/')}/comercios/{slug}" + (f"?ref={ref}" if ref else ""))
    return partes


def texto_de(pub: dict, comercio: dict | None, destino: str | None = None,
             ciudad: dict | None = None) -> str:
    """El texto que se publica. Mismo cuerpo para las tres redes.

    Lleva SIEMPRE el nombre del comercio y el enlace a su ficha. Sin el nombre,
    la oferta parece de URUKU y el comerciante no recibe nada de lo que se le
    prometió; sin el enlace, quien la ve no tiene cómo llegar y el posteo es
    decoración.

    La ciudad sale de `ciudad` (la fila de `ciudades`) o, si el comercio ya
    viene con ella embebida (`ciudades`), de ahí. Si no se puede saber, el
    renglón lleva sólo el nombre: antes decía «Bermejo» para todos, y una
    oferta de Tarija salía en las redes como si fuera de otra ciudad.
    """
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
    partes.extend(_pie(comercio, destino, ciudad))

    return "\n\n".join(partes).strip()


def pie_de(comercio: dict | None, destino: str | None = None, ciudad: dict | None = None) -> str:
    """El pie estándar como texto (lo que E2 informa como `broadcast_footer`)."""
    return "\n\n".join(_pie(comercio, destino, ciudad))


def texto_con_pie(texto: str, comercio: dict | None, destino: str | None = None,
                  ciudad: dict | None = None) -> str:
    """El texto que aprobó una persona (integración) + el pie estándar de Uruku, igual que `texto_de`."""
    return "\n\n".join([(texto or "").strip(), *_pie(comercio, destino, ciudad)]).strip()


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


def _a_meta(metodo: str, ruta: str, *, datos: dict | None = None, campos: str | None = None) -> dict:
    """Una llamada a la Graph API, con la versión configurada (`GRAPH_API_VERSION`).

    Traduce los fallos a lo que importa para no duplicar posteos:
      - no se pudo ni conectar, o Meta contestó 4xx  → `DifusionError` (definitivo: NO salió);
      - timeout / corte tras enviar / 5xx            → `DifusionIncierta` (puede haber salido).
    Las lecturas (GET) llevan el token en el header, no en la URL, y piden sólo los `fields` que usan."""
    url = f"{settings.graph_base()}/{ruta}"
    token = settings.facebook_page_token.strip()
    try:
        if metodo == "GET":
            r = httpx.get(url, params={"fields": campos} if campos else None,
                          headers={"Authorization": f"Bearer {token}"}, timeout=_TIMEOUT)
        else:
            r = httpx.post(url, data={**(datos or {}), "access_token": token}, timeout=_TIMEOUT)
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout) as exc:
        raise DifusionError(f"no se pudo conectar con Meta ({type(exc).__name__})") from exc
    except httpx.HTTPError as exc:
        raise DifusionIncierta(f"sin respuesta de Meta ({type(exc).__name__}): puede haber salido") from exc
    if r.status_code >= 500:
        raise DifusionIncierta(f"Meta respondió HTTP {r.status_code}: puede haber salido")
    if r.status_code >= 400:
        raise DifusionError(f"Meta respondió HTTP {r.status_code}: {r.text[:300]}")
    try:
        return r.json() or {}
    except ValueError as exc:
        raise DifusionIncierta("Meta contestó algo que no es JSON: puede haber salido") from exc


def _enviar_facebook(texto: str, imagen_url: str | None) -> str | None:
    """Con foto va a /photos y sin foto a /feed: son endpoints distintos, y
    mandar una foto al de texto la pierde sin dar error."""
    pid = settings.facebook_page_id.strip()
    if imagen_url:
        cuerpo = _a_meta("POST", f"{pid}/photos", datos={"url": imagen_url, "caption": texto})
    else:
        cuerpo = _a_meta("POST", f"{pid}/feed", datos={"message": texto})
    # /photos devuelve `id` (la foto) y `post_id` (el posteo); /feed devuelve `id` (el posteo).
    post = cuerpo.get("post_id") or cuerpo.get("id")
    return Publicado(f"https://www.facebook.com/{post}" if post else None, external_post_id=post)


def _mismo_texto(a: str | None, b: str | None) -> bool:
    """Compara el comienzo de dos textos ignorando espacios (Meta puede normalizar saltos de línea)."""
    def norm(t):
        return " ".join((t or "").split())[:80]
    return bool(norm(a)) and norm(a) == norm(b)


def _buscar_en_facebook(texto: str) -> Publicado | None:
    pid = settings.facebook_page_id.strip()
    cuerpo = _a_meta("GET", f"{pid}/posts", campos="id,message,permalink_url,created_time")
    # `limit` no se manda: la página por defecto (25) alcanza para lo último que se posteó.
    for post in cuerpo.get("data") or []:
        if _mismo_texto(post.get("message"), texto):
            return Publicado(post.get("permalink_url") or f"https://www.facebook.com/{post['id']}",
                             external_post_id=post["id"], permalink=post.get("permalink_url"))
    return None


def _buscar_en_instagram(texto: str) -> Publicado | None:
    uid = settings.instagram_user_id.strip()
    cuerpo = _a_meta("GET", f"{uid}/media", campos="id,caption,permalink,timestamp")
    for media in cuerpo.get("data") or []:
        if _mismo_texto(media.get("caption"), texto):
            return Publicado(media.get("permalink"), external_post_id=media["id"], permalink=media.get("permalink"))
    return None


def _enviar_instagram(texto: str, imagen_url: str | None, contenedor: str | None = None) -> str | None:
    """Instagram va en dos pasos: se crea el contenedor y después se publica.

    Y no acepta publicaciones sin imagen. No es una restricción nuestra: la API
    de contenido de Instagram exige una foto o un video. Una oferta que llegó
    sin foto se corta acá con ese motivo, en vez de reintentarse contra un error
    que nunca va a cambiar.

    `contenedor`: el de un intento anterior que no terminó. Se CONSULTA su `status_code` antes de crear
    otro: FINISHED ⇒ se publica ese mismo; PUBLISHED ⇒ ya salió (se busca el posteo, no se repite);
    IN_PROGRESS ⇒ todavía no se puede decir; ERROR/EXPIRED ⇒ nunca salió, se crea uno nuevo.
    """
    if not imagen_url:
        raise DifusionError("Instagram no publica sin imagen")

    uid = settings.instagram_user_id.strip()

    if contenedor:
        estado = (_a_meta("GET", contenedor, campos="status_code").get("status_code") or "").upper()
        if estado == "PUBLISHED":
            hallado = _buscar_en_instagram(texto)
            if hallado:
                hallado.ig_container_id = contenedor
                return hallado
            raise DifusionIncierta("el contenedor de Instagram figura como publicado pero no encontré el posteo: revisalo a mano",
                                   ig_container_id=contenedor)
        if estado == "IN_PROGRESS":
            raise DifusionIncierta("el contenedor de Instagram todavía se está procesando", ig_container_id=contenedor)
        if estado != "FINISHED":                    # ERROR / EXPIRED / desconocido: nunca llegó a publicarse
            contenedor = None

    if not contenedor:
        contenedor = (_a_meta("POST", f"{uid}/media", datos={"image_url": imagen_url, "caption": texto}) or {}).get("id")
        if not contenedor:
            raise DifusionError("Instagram no devolvió el contenedor")

    try:
        publicado = _a_meta("POST", f"{uid}/media_publish", datos={"creation_id": contenedor})
    except DifusionIncierta as exc:
        raise DifusionIncierta(str(exc), ig_container_id=contenedor) from exc
    except DifusionError as exc:
        # El contenedor quedó creado y sin publicar: se guarda para que el reintento lo consulte (no
        # se crea OTRO a ciegas: dos publicados es peor que ninguno).
        raise DifusionError(f"Instagram (publicar): {exc}", ig_container_id=contenedor) from exc
    media = publicado.get("id")
    return Publicado(None, external_post_id=media, ig_container_id=contenedor)


_ENVIOS = {
    "wa_canal": _enviar_wa_canal,
    "facebook": _enviar_facebook,
    "instagram": _enviar_instagram,
}


def enviar(destino: str, texto: str, imagen_url: str | None, contenedor: str | None = None) -> str | None:
    if destino not in _ENVIOS:
        raise DifusionError(f"destino desconocido: {destino}")
    if not configurado(destino):
        raise DifusionError(f"{NOMBRE[destino]} no está configurado")
    if contenedor and destino == "instagram":
        return _ENVIOS[destino](texto, imagen_url, contenedor=contenedor)
    return _ENVIOS[destino](texto, imagen_url)


# ─────────────────────────────────────────────────────────────────── la cola

def encolar(repo, publicacion_id: str, destinos: list[str] | None = None, extra: dict | None = None) -> int:
    """Anota la publicación para las tres redes. Devuelve cuántas filas creó.

    `destinos` / `extra` son de la integración: ya validó el plan y la configuración, así que se encolan
    EXACTAMENTE esos destinos (sin el filtro por plan) con `texto_override`, `imagen_url_override` y
    `solicitado_por` en cada fila.

    Encola incluso los destinos sin configurar: quedan esperando y se pueden
    mandar el día que haya token. Si no se anotaran, todo lo aprobado antes de
    configurar Facebook sería imposible de recuperar sin buscarlo a mano en la
    base.

    Nunca lanza. Es la regla que hace que aprobar una oferta no pueda romperse
    por un problema de redes.

    FACEBOOK E INSTAGRAM SON DE DESTACADO PARA ARRIBA. Es lo que se vende:
    Publica tiene el negocio digitalizado; Destacado, además, sale en las
    redes de URUKU. Un comercio del gratis o de Publica no se encola a las
    redes — su oferta sale en su ficha y en la búsqueda, que es lo suyo. Se
    decide por la función `redes` del plan, no por el nombre del plan.
    """
    from app.services import planes

    try:
        if destinos is not None:
            return repo.encolar_difusion(publicacion_id, list(destinos), extra)
        destinos = list(destinos_activos())
        pub = repo.get_publicacion(publicacion_id) or {}
        comercio = repo.get_comercio(pub["comercio_id"]) if pub.get("comercio_id") else None
        if comercio is not None and not planes.funcion(planes.plan_de(repo, comercio), "redes"):
            destinos = [d for d in destinos if d not in ("facebook", "instagram")]
        if not destinos:
            return 0
        return repo.encolar_difusion(publicacion_id, destinos)
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


def _ciudad_de(repo, comercio: dict | None) -> dict | None:
    if comercio and comercio.get("ciudad_id"):
        try:
            return repo.get_ciudad_por_id(comercio["ciudad_id"])
        except Exception:  # noqa: BLE001 — sin ciudad el texto sale igual, sólo sin ella
            logger.warning("difusion.ciudad_fallo", comercio=comercio.get("id"), exc_info=True)
    return None


def contenido_de(repo, fila: dict, pub: dict, comercio: dict | None) -> tuple[str, str | None]:
    """(texto, imagen) que sale en esa fila: lo que aprobó la integración (con el pie estándar de Uruku) o,
    si no hay, lo de siempre."""
    destino = fila["destino"]
    ciudad = _ciudad_de(repo, comercio)
    if fila.get("texto_override"):
        texto = texto_con_pie(fila["texto_override"], comercio, destino, ciudad)
    else:
        texto = texto_de(pub, comercio, destino, ciudad)
    return texto, (fila.get("imagen_url_override") or pub.get("imagen_url"))


def _ids_de(resultado, error: DifusionError | None = None) -> dict:
    """Las columnas de la cola que salen de un envío (o de su error): ids de Meta."""
    extra: dict = {}
    for col in ("external_post_id", "ig_container_id", "permalink"):
        valor = getattr(resultado, col, None) or getattr(error, col, None)
        if valor:
            extra[col] = valor
    return extra


def procesar(repo, fila: dict, *, reclamar: bool = False) -> dict:
    """Manda UNA fila de la cola y guarda el resultado.

    `reclamar=True` (lo usa la integración, E9): antes de llamar a Meta la fila pasa de `pendiente` a
    `incierto` con un UPDATE condicional. Así dos pedidos a la vez no mandan la misma fila, y si el proceso
    muere a mitad de la llamada la fila queda `incierto` —que es lo único que de verdad se sabe—."""
    destino = fila["destino"]
    pub = repo.get_publicacion(fila["publicacion_id"])
    if not pub:
        repo.marcar_difusion(fila["id"], "omitido", "la publicación ya no existe")
        return {"estado": "omitido"}

    # Una publicación archivada (activo = false: la bajó el comerciante, o el
    # tope de publicaciones guardadas del plan) no sale a las redes, aunque siga
    # 'aprobado'. `archivar_excedentes` ya descarta lo pendiente; esto cubre el
    # reintento a mano de una fila que quedó en error. `is False` y no `not`: una
    # fila sin la columna (un fake, una vista) no se trata como archivada.
    if pub.get("activo") is False:
        repo.marcar_difusion(fila["id"], "omitido", "la publicación está archivada")
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
    texto, imagen = contenido_de(repo, fila, pub, comercio)
    if reclamar and not repo.reclamar_difusion(fila["id"]):
        return {"estado": "omitido", "motivo": "otro proceso ya tomó esta fila"}
    try:
        url = enviar(destino, texto, imagen, fila.get("ig_container_id"))
    except DifusionIncierta as exc:
        repo.marcar_difusion(fila["id"], "incierto", str(exc), extra=_ids_de(None, exc))
        logger.warning("difusion.incierta", destino=destino, pub=pub["id"], motivo=str(exc))
        return {"estado": "incierto", "motivo": str(exc)}
    except DifusionError as exc:
        repo.marcar_difusion(fila["id"], "error", str(exc), extra=_ids_de(None, exc))
        logger.warning("difusion.error", destino=destino, pub=pub["id"], motivo=str(exc))
        return {"estado": "error", "motivo": str(exc)}
    except Exception as exc:  # noqa: BLE001
        # Con la fila reclamada no se sabe si llegó a salir: `incierto`, no `error` (que se reintenta a ciegas).
        estado = "incierto" if reclamar else "error"
        repo.marcar_difusion(fila["id"], estado, f"error inesperado: {exc}")
        logger.warning("difusion.error_inesperado", destino=destino, exc_info=True)
        return {"estado": estado, "motivo": str(exc)}

    repo.marcar_difusion(fila["id"], "enviado", None, url or None, extra=_ids_de(url))
    logger.info("difusion.enviado", destino=destino, pub=pub["id"])
    return {"estado": "enviado", "url": url}


def resolver_incierto(repo, fila: dict) -> dict:
    """Una fila `incierto`: se le pregunta a Meta qué pasó ANTES de reintentar.

    - Ya hay un posteo (se encuentra por su id o por su texto) ⇒ `enviado`, con sus ids.
    - Instagram con contenedor: se mira su `status_code` (ver `_enviar_instagram`).
    - Meta contesta y NO hay rastro ⇒ `pendiente` (se puede mandar: no salió).
    - Meta no contesta ⇒ sigue `incierto`.
    Nunca manda nada."""
    destino = fila["destino"]
    if destino not in ("facebook", "instagram") or not configurado(destino):
        return {"estado": fila.get("estado"), "motivo": "no se puede verificar este destino"}
    pub = repo.get_publicacion(fila["publicacion_id"]) or {}
    comercio = repo.get_comercio(pub["comercio_id"]) if pub.get("comercio_id") else None
    texto, _imagen = contenido_de(repo, fila, pub, comercio)
    try:
        if fila.get("external_post_id"):
            hallado = Publicado(None, external_post_id=fila["external_post_id"])
        elif destino == "facebook":
            hallado = _buscar_en_facebook(texto)
        elif fila.get("ig_container_id"):
            estado_cont = (_a_meta("GET", fila["ig_container_id"], campos="status_code").get("status_code") or "").upper()
            if estado_cont == "PUBLISHED":
                hallado = _buscar_en_instagram(texto)
                if hallado is None:
                    return {"estado": "incierto",
                            "motivo": "el contenedor figura publicado pero no encontré el posteo: revisalo a mano"}
            elif estado_cont == "IN_PROGRESS":
                return {"estado": "incierto", "motivo": "el contenedor de Instagram todavía se está procesando"}
            else:                       # FINISHED (se publica con ese mismo contenedor) / ERROR / EXPIRED
                hallado = None
        else:
            hallado = _buscar_en_instagram(texto)
    except DifusionError as exc:
        logger.warning("difusion.resolver_fallo", fila=fila["id"], motivo=str(exc))
        return {"estado": "incierto", "motivo": f"no pude consultar a Meta: {exc}"}
    if hallado is not None:
        repo.actualizar_difusion(fila["id"], {"estado": "enviado", "motivo": None, "url_publicada": str(hallado) or None,
                                              **_ids_de(hallado), "enviado_at": datetime.now(timezone.utc).isoformat()})
        return {"estado": "enviado", "url": str(hallado)}
    repo.actualizar_difusion(fila["id"], {"estado": "pendiente",
                                          "motivo": "se verificó en Meta que no había salido: se puede mandar"})
    return {"estado": "pendiente", "motivo": "no había salido"}


def verificar(repo, fila: dict) -> dict:
    """E10: relee el posteo en la Graph API con el token de Uruku y guarda `permalink` + `verificado_at`.

    Pide sólo `permalink_url` / `permalink` (la respuesta de publicar no lo trae). Lanza `DifusionError` si
    el posteo no existe o la fila no corresponde, y `DifusionIncierta` si Meta no contesta."""
    destino = fila["destino"]
    if destino not in ("facebook", "instagram"):
        raise DifusionError("este destino no se puede verificar desde acá")
    if fila.get("estado") != "enviado":
        raise DifusionError("la fila todavía no se envió")
    if not fila.get("external_post_id"):
        raise DifusionError("la fila no guardó el id del posteo: no hay qué verificar")
    if not configurado(destino):
        raise DifusionError(f"{NOMBRE[destino]} no está configurado")
    campo = "permalink_url" if destino == "facebook" else "permalink"
    cuerpo = _a_meta("GET", fila["external_post_id"], campos=f"id,{campo}")
    permalink = cuerpo.get(campo)
    if not cuerpo.get("id"):
        raise DifusionError("Meta no devolvió el posteo")
    parche = {"verificado_at": datetime.now(timezone.utc).isoformat()}
    if permalink:
        parche["permalink"] = permalink
    repo.actualizar_difusion(fila["id"], parche)
    return parche


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
