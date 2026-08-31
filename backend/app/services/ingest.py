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

from app.core.config import settings
from app.db.repository import Repo, get_repo
from app.models.whatsapp import WahaEvent, WahaMessagePayload

logger = structlog.get_logger()

_MESSAGE_EVENTS = {"message", "message.any"}
_RE_CONFIRMAR = re.compile(r"^\s*CONFIRMAR-(\d{6})\s*$", re.IGNORECASE)

# Heurística simple para clasificar el tipo de publicación a partir del texto.
_VIDEO_HINTS = ("tiktok.com", "video", "reel")


class IngestError(Exception):
    """Error recuperable de ingesta."""


def _identificar_por_grupo(repo: Repo, payload) -> tuple[dict | None, str, str | None]:
    """Resuelve el comercio cuando el mensaje vino de un grupo.

    El modelo: UN grupo por comerciante, con tres participantes — el celular del
    comercio, un celular de URUKU y el testigo (el vinculado a WAHA). El grupo
    es lo estable: el comerciante puede cambiar de teléfono, o publicar desde el
    celular del hijo, y el contenido sigue llegando al local correcto.

    A diferencia del chat 1-a-1, acá **no se crea un comercio si no se sabe de
    quién es el grupo**. En 1-a-1 un número desconocido es un comerciante nuevo
    que escribió, y crear el borrador tiene sentido. Un grupo desconocido no es
    nadie: crear un comercio por cada grupo llenaría la base de fichas fantasma
    llamadas "Comercio 1234" que nadie cargó ni visitó.
    """
    from app.core.codigo import extraer_codigo

    grupo = payload.grupo_jid or ""

    atado = repo.get_comercio_por_grupo(grupo)
    if atado:
        return atado, "grupo", None

    # Grupo nuevo: se ata con el código del local, mandado adentro del grupo.
    # Reusa lo que ya funciona en el chat directo — un papel en el mostrador con
    # URUKU-XXXX — y evita tener que cargar el JID a mano en el admin.
    codigo = extraer_codigo(payload.body)
    if codigo:
        comercio = repo.get_comercio_por_codigo(codigo)
        if comercio:
            try:
                repo.vincular_grupo_comercio(
                    grupo, comercio["id"], None, "codigo", "ingest-grupo")
            except Exception:  # noqa: BLE001 — la publicación importa más que el vínculo
                logger.warning("ingest.vincular_grupo_fallo", grupo=grupo, exc_info=True)
            logger.info("ingest.grupo_vinculado", comercio=comercio["slug"], codigo=codigo)
            return comercio, "codigo", codigo
        logger.info("ingest.codigo_desconocido", codigo=codigo)

    logger.info("ingest.grupo_sin_comercio", grupo=grupo)
    return None, "grupo_desconocido", codigo


def _identificar_comercio(repo: Repo, payload) -> tuple[dict, str, str | None]:
    """Resuelve de qué comercio es este mensaje.

    Devuelve (comercio, identidad_origen, codigo_recibido).

    `identidad_origen` queda guardado en la publicación para que el panel sepa en
    qué se apoyó la atribución al momento de aprobar:
      - 'numero': el número del remitente ya estaba asociado al comercio.
      - 'codigo': el número era desconocido y el mensaje traía el código del local.
      - 'desconocido': ni número conocido ni código; se creó un borrador nuevo.
    """
    from app.core.codigo import extraer_codigo

    wa_jid = payload.from_ or ""

    conocido = repo.get_comercio_by_jid(wa_jid) or repo.get_comercio_por_numero(payload.phone)
    if conocido:
        return conocido, "numero", None

    codigo = extraer_codigo(payload.body)
    if codigo:
        por_codigo = repo.get_comercio_por_codigo(codigo)
        if por_codigo:
            # El número queda autorizado para este comercio: de acá en adelante ya
            # no hace falta repetir el código. El código es un vínculo de una vez
            # entre un local físico y un número, no una contraseña permanente.
            try:
                repo.agregar_numero_comercio(
                    por_codigo["id"], payload.phone, "se identificó con el código", "ingest-codigo")
                repo.vincular_wa_jid(por_codigo["id"], wa_jid)
            except Exception:  # noqa: BLE001 — la publicación importa más que el vínculo
                logger.warning("ingest.autorizar_numero_fallo", comercio=por_codigo["id"], exc_info=True)
            logger.info("ingest.identificado_por_codigo", comercio=por_codigo["slug"], codigo=codigo)
            return por_codigo, "codigo", codigo
        logger.info("ingest.codigo_desconocido", codigo=codigo)

    # Ni número conocido ni código válido: borrador nuevo, como siempre.
    return repo.upsert_comercio_by_jid(wa_jid, payload.phone), "desconocido", codigo


def _puede_publicar_por_whatsapp(comercio: dict) -> bool:
    """El gate por plan de la ingesta. Apagado por default (ver config)."""
    if not settings.ingesta_requiere_plan:
        return True
    permitidos = {p.strip() for p in settings.planes_con_ingesta.split(",") if p.strip()}
    return (comercio.get("plan") or "gratis") in permitidos


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


def _sin_codigo(texto: str | None) -> str | None:
    """Saca el código del texto para que no quede a la vista del comprador.

    El explorador escribe "URUKU-AQP5 zapatilla urbana Bs 180": el código es
    para el sistema, no para la oferta. Sin esto la descripción arrancaba con un
    código que al comprador no le dice nada."""
    if not texto:
        return None
    limpio = re.sub(r"\bURUKU[\s\-_.]*[A-Z0-9]{4}\b", "", texto, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", limpio).strip() or None


def _publicar_del_explorador(payload, event, repo: Repo) -> dict:
    """Una oferta que fotografió URUKU, publicada a nombre del comercio REAL.

    Acá el CÓDIGO manda, siempre. En el resto de la ingesta gana el grupo (o el
    número ya conocido) y el código sólo se mira cuando no hay nada atado — que
    es correcto para un comerciante, porque su celular es siempre el mismo local.
    Para el explorador es al revés: un mismo teléfono publica para cien locales
    distintos en una tarde. Sin esta rama, la segunda foto y todas las
    siguientes se habrían publicado bajo el comercio de la primera, sin ningún
    error a la vista.

    Nunca inventa ni adivina el comercio: sin código válido no publica. Adivinar
    sería poner la foto y el precio de un local en la ficha de otro.
    """
    from datetime import datetime, timezone

    from app.core.codigo import extraer_codigo

    codigo = extraer_codigo(payload.body)
    if not codigo:
        logger.info("ingest.explorador_sin_codigo", phone=payload.phone)
        return {"captured": True, "publicada": False,
                "motivo": "el explorador mandó una oferta sin el código del local"}

    comercio = repo.get_comercio_por_codigo(codigo)
    if not comercio:
        logger.info("ingest.explorador_codigo_desconocido", codigo=codigo)
        return {"captured": True, "publicada": False,
                "motivo": f"no hay ningún comercio con el código {codigo}", "codigo": codigo}

    slug = comercio.get("slug") or comercio.get("id") or "?"

    imagen_url = None
    if payload.type == "image" or payload.has_media:
        from app.services.wa_media import guardar_imagen_publicacion

        imagen_url = guardar_imagen_publicacion(slug, payload.media_url)

    texto = _sin_codigo(payload.body)

    # Siempre a moderación, aunque el comercio sea confiable: acá URUKU está
    # publicando el precio de un local que no lo pidió. La cola es donde una
    # persona corrige el título, el precio, y decide si eso se muestra.
    row = {
        "comercio_id": comercio["id"],
        "tipo": _classify_tipo(payload),
        "titulo": None if imagen_url else ((texto or "").split(chr(10))[0][:120] or None),
        "descripcion": texto,
        "imagen_url": imagen_url,
        "tiktok_url": _extract_tiktok(payload.body),
        "estado": "pendiente",
        "origen": "explorador",
        # Mientras el comercio no se sume, la consulta la recibe URUKU. Si el
        # número no está configurado queda NULL y el contacto va al comercio,
        # que es lo seguro: nunca mandar al comprador a un número que no está
        # escuchando.
        "contacto_whatsapp": settings.wa_contacto_explorador.strip() or None,
        "codigo_recibido": codigo,
        "identidad_origen": "explorador",
        "wa_message_id": payload.id,
        "raw": event.payload,
    }
    repo.insert_publicacion(row)
    logger.info("ingest.explorador_publicacion", comercio=slug, codigo=codigo, foto=bool(imagen_url))
    return {"captured": True, "comercio": slug, "origen": "explorador",
            "estado": "pendiente", "codigo": codigo}


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

    # 1.b) En un grupo, los mensajes de los NUESTROS no son ofertas.
    #      El testigo ya está cubierto por fromMe (es el número vinculado a
    #      WAHA), pero el celular de URUKU es otro teléfono y entra como
    #      cualquier participante: sin esto, cada "buen día" que escriba alguien
    #      de URUKU se publica a nombre del comerciante.
    # 1.c) El EXPLORADOR: URUKU sale a fotografiar ofertas de locales que
    #      todavía no publican. Va antes del descarte por número propio a
    #      propósito — el explorador también está en WA_NUMEROS_PROPIOS (para
    #      que siga siendo inofensivo el día que lo agreguen a un grupo de
    #      comerciante), así que si esta rama fuera después, sus fotos se
    #      tirarían como "mensaje de un número de URUKU".
    if settings.es_numero_explorador(payload.phone):
        return _publicar_del_explorador(payload, event, repo)

    if payload.es_grupo and settings.es_numero_propio(payload.phone):
        logger.info("ingest.mensaje_propio", grupo=payload.grupo_jid)
        return {"captured": True, "publicada": False, "motivo": "mensaje de un número de URUKU"}

    # 2) Identificar al comercio.
    #    En un GRUPO manda el grupo: está atado a un comercio y no cambia aunque
    #    el comerciante cambie de celular. En un chat 1-a-1 manda el número
    #    (registrado o ya visto) y, si es desconocido, el CÓDIGO del texto — es
    #    lo que le permite a un comercio sin número propio, sin login y sin
    #    pagar, mandar ofertas desde el celular de quien sea.
    if payload.es_grupo:
        comercio, identidad_origen, codigo_recibido = _identificar_por_grupo(repo, payload)
        if comercio is None:
            # El crudo ya quedó en wa_inbox, así que nada se pierde: cuando
            # alguien mande el código en ese grupo, o lo ate desde el admin, se
            # sabe qué llegó antes. Lo que NO se hace es inventar un comercio.
            return {"captured": True, "publicada": False,
                    "motivo": "el grupo no está asociado a ningún comercio",
                    "grupo": payload.grupo_jid}
    else:
        comercio, identidad_origen, codigo_recibido = _identificar_comercio(repo, payload)
    # Sólo para logs y respuesta: un comercio identificado por código puede venir
    # de una fila parcial, y una línea de log no puede tumbar la ingesta.
    slug = comercio.get("slug") or comercio.get("id") or "?"

    # 2.b) ¿Compartió su ubicación por WhatsApp? -> actualizamos el comercio y listo.
    #      (forma simple para vendedores con poca tecnología: tocar "compartir ubicación")
    loc = _extract_location(event.payload)
    if payload.type == "location" or loc:
        if loc:
            repo.actualizar_ubicacion_comercio(comercio["id"], loc[0], loc[1], loc[2])
        logger.info("ingest.ubicacion", comercio=slug, ok=bool(loc))
        return {"captured": True, "comercio": slug, "ubicacion_actualizada": bool(loc)}

    # 2.c) ¿Este comercio puede publicar por WhatsApp?
    #      Es una función del plan más caro, pero durante la captación conviene
    #      que cualquiera pueda mandar productos para que el catálogo tenga
    #      volumen: por eso el gate arranca apagado (ingesta_requiere_plan=False).
    #      El mensaje ya quedó guardado en wa_inbox, así que nada se pierde: si
    #      después el comercio contrata el plan, el crudo sigue estando.
    if not _puede_publicar_por_whatsapp(comercio):
        logger.info("ingest.plan_insuficiente", comercio=slug, plan=comercio.get("plan"))
        return {"captured": True, "comercio": slug, "publicada": False,
                "motivo": "el plan del comercio no incluye publicar por WhatsApp"}

    # 3) Crear publicación. Comercio confiable -> publica directo; si no, a moderación.
    from datetime import datetime, timezone

    # Un número nuevo que se identificó con el código NO hereda `confiable`: el
    # código está en un papel en el local y cualquiera que lo vea podría publicar
    # en nombre del comercio. La primera vez pasa por moderación siempre.
    confiable = bool(comercio.get("confiable")) and identidad_origen != "codigo"

    # En un grupo hay tres participantes y sólo uno publica. Si el mensaje vino
    # de un número que no es el del comercio ni uno nuestro, alguien agregó a un
    # cuarto: no se descarta en silencio —podría ser el mismo comerciante con
    # otro celular— pero no se publica solo. Va a moderación, que es donde una
    # persona puede mirar quién es.
    if payload.es_grupo:
        duenio = repo.get_comercio_por_numero(payload.phone)
        if not (duenio and duenio.get("id") == comercio["id"]):
            logger.info("ingest.remitente_ajeno", grupo=payload.grupo_jid, comercio=slug)
            confiable = False

    now = datetime.now(timezone.utc).isoformat()
    tipo = _classify_tipo(payload)

    # La imagen se baja a disco propio ACÁ, no se referencia la de WAHA: esa URL
    # es interna (el navegador del comprador no la alcanza) y efímera. Y en una
    # oferta la foto no es un adorno, es el contenido.
    imagen_url = None
    if payload.type == "image" or payload.has_media:
        from app.services.wa_media import guardar_imagen_publicacion

        imagen_url = guardar_imagen_publicacion(slug, payload.media_url)

    row = {
        "comercio_id": comercio["id"],
        "tipo": tipo,
        # Con imagen no se inventa un título: la oferta ES la foto y el texto
        # que vino va de descripción. Un "200 bs" de título no ayuda a nadie.
        # Sin imagen sí se usa la primera línea, o la fila queda en blanco en la
        # cola de moderación y no se puede saber qué es sin abrirla.
        "titulo": None if imagen_url else ((payload.body or "").split("\n")[0][:120] or None),
        "descripcion": payload.body,
        "imagen_url": imagen_url,
        "tiktok_url": _extract_tiktok(payload.body),
        "estado": "aprobado" if confiable else "pendiente",
        "approved_at": now if confiable else None,
        "moderado_por": "auto-confiable" if confiable else None,
        "moderado_at": now if confiable else None,
        "origen": "whatsapp",
        "codigo_recibido": codigo_recibido,
        "identidad_origen": identidad_origen,
        "wa_message_id": payload.id,
        "raw": event.payload,
    }
    repo.insert_publicacion(row)

    estado = row["estado"]
    logger.info("ingest.publicacion", comercio=slug, tipo=tipo, estado=estado)
    return {"captured": True, "comercio": slug, "tipo": tipo, "estado": estado}
