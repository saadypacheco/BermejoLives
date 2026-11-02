"""Los mensajes a los suscriptores (plantillas M1 a M6, docs/contenido-redes-tecnico.md §8.4).

FUNCIONES PURAS: reciben los datos ya resueltos y devuelven el texto. WAHA NO MANDA NADA: el
backend sólo arma el texto y el panel abre `wa.me` con el mensaje ya escrito; quien lo manda es una
persona, desde su WhatsApp, y puede editarlo antes de enviar (T-10).

Sin emojis, sin precios, sin el código del comercio. `{persona}` es la persona de contacto o,
si no hay, el nombre del comercio; `{firmante}` es quien abre la pantalla o «el equipo».
"""
from __future__ import annotations

from datetime import date

from app.core.config import settings

#: Tarea -> plantilla (las que llevan mensaje).
PLANTILLA_POR_TAREA = {"welcome": "M1", "monthly_report": "M3",
                       "photo_refresh": "M4", "renewal_before": "M5", "renewal_overdue": "M6"}

ETIQUETA_TAREA = {
    "welcome": "Bienvenida", "profile_check": "Revisar la ficha", "first_offer": "Primera oferta",
    "photo_session": "Sesión de fotos", "first_piece": "Primer video", "week1_checkin": "¿Cómo te fue la semana?",
    "piece_delivery": "Entregar el video a mano", "photo_refresh": "Pedir fotos nuevas", "monthly_report": "Reporte del mes",
    "renewal_before": "Renovación: vence mañana", "renewal_overdue": "Pago atrasado", "churn_call": "Llamada: ¿seguimos?",
}

#: Las tareas que piden anotar qué dijo la persona antes de cerrarse.
NECESITAN_RESULTADO = ("week1_checkin", "churn_call")

GUION_LLAMADA = ["¿Te sirvió URUKU este mes?", "¿Qué te faltó?", "¿Seguimos?"]

RED_ETIQUETA = {"tiktok": "TikTok", "instagram": "Instagram", "facebook": "Facebook", "wa_channel": "el canal de WhatsApp"}


def _fecha(d: date | str | None) -> str:
    if not d:
        return ""
    if isinstance(d, str):
        d = date.fromisoformat(d[:10])
    return d.strftime("%d/%m")


def persona(contact_person: str | None, comercio_nombre: str | None) -> str:
    return (contact_person or "").strip() or (comercio_nombre or "").strip() or "hola"


def firmante(nombre: str | None) -> str:
    return (nombre or "").strip() or "el equipo"


def ficha_url(slug: str | None) -> str:
    return f"{settings.sitio_url.rstrip('/')}/comercios/{slug}" if slug else settings.sitio_url.rstrip("/")


def m1_bienvenida(persona_: str, firmante_: str, comercio: str, slug: str | None) -> str:
    return (f"Hola {persona_}, soy {firmante_} de URUKU. Gracias por sumarte con {comercio}. Esta semana dejamos "
            f"tu ficha completa y te armamos tu primer video para las redes. ¿Qué día te queda bien que pasemos "
            f"a sacar unas fotos del local? Tu ficha: {ficha_url(slug)}")


def m2_entrega(persona_: str, comercio: str, redes: list[str], link_post: str | None, share_token: str) -> str:
    """DORMIDA desde el 2/11 (§15): al comerciante no se le escribe por WhatsApp, así que ninguna tarea
    arma este texto ni el link a `/pieza/<token>`. Queda por si se retoma la entrega por mensaje."""
    donde = " y ".join(RED_ETIQUETA.get(r, r) for r in redes) or "las redes de URUKU"
    sitio = settings.sitio_url.rstrip("/")
    salio = f"{donde}: {link_post}" if link_post else donde
    return (f"{persona_}, ya está el video de {comercio} en {salio}. Acá lo podés bajar para subirlo a tu estado "
            f"o a tu TikTok: {sitio}/pieza/{share_token}. Si algo no te gusta, decime y lo cambiamos.")


def m3_reporte(persona_: str, comercio: str, datos: dict, vence: date | str | None) -> str:
    visitas, whatsapp = int(datos.get("visits") or 0), int(datos.get("whatsapp") or 0)
    if visitas == 0 and whatsapp == 0:
        return (f"Hola {persona_}, este mes la ficha de {comercio} todavía tuvo poco movimiento; publicamos "
                f"{int(datos.get('pieces_published') or 0)} videos tuyos y {int(datos.get('offers_approved') or 0)} ofertas. "
                f"Para el mes que viene te proponemos mandar fotos de lo nuevo al grupo. ¿Lo hacemos?")
    terminos = [t for t in (datos.get("terms") or []) if t][:2]
    frase = ""
    if len(terminos) == 2:
        frase = f" Te encontraron buscando «{terminos[0]}» y «{terminos[1]}»."
    elif len(terminos) == 1:
        frase = f" Te encontraron buscando «{terminos[0]}»."
    cierre = f" Tu plan se renueva el {_fecha(vence)}." if vence else ""
    return (f"Hola {persona_}, te paso cómo le fue a {comercio} este mes en URUKU: {visitas} personas vieron tu ficha "
            f"y {whatsapp} te escribieron por WhatsApp desde ahí.{frase}{cierre} ¿Tenés algo nuevo que quieras "
            f"mostrar el mes que viene?")


def m4_fotos(persona_: str, comercio: str) -> str:
    return (f"{persona_}, ¿nos mandás 3 o 4 fotos de lo nuevo que tengas, al grupo de {comercio}? Con eso armamos "
            f"tu video de este mes. Si preferís, coordinamos y pasamos nosotros.")


def m5_vence_manana(persona_: str, vence: date | str | None) -> str:
    return (f"{persona_}, tu plan de URUKU vence mañana, {_fecha(vence)}. ¿Seguimos? Podés pagar con el QR de "
            f"{settings.sitio_url.rstrip('/')}/pagar y mandarnos el comprobante por acá. Cualquier duda, escribime.")


def m6_atrasado(persona_: str) -> str:
    return (f"{persona_}, quedó pendiente el pago de URUKU de este mes. Tu ficha sigue igual unos días más. Podés "
            f"pagar con el QR de {settings.sitio_url.rstrip('/')}/pagar. Y si algo no te convenció, contame qué y lo vemos.")


def week1_checkin(persona_: str) -> str:
    return (f"Hola {persona_}, ¿cómo te fue esta primera semana con URUKU? ¿Te escribió alguien desde la ficha? "
            f"Contame qué te preguntaron así lo mejoramos.")


def mensaje_de_tarea(kind: str, *, persona_: str, firmante_: str, comercio: str, slug: str | None = None,
                     paga_hasta: date | str | None = None, reporte: dict | None = None,
                     pieza: dict | None = None) -> str | None:
    """El texto de una tarea, o None si no lleva mensaje (checklist y llamada).

    `piece_delivery` NO lleva mensaje (§15): el video se entrega a mano, desde la descarga del panel."""
    if kind == "welcome":
        return m1_bienvenida(persona_, firmante_, comercio, slug)
    if kind == "monthly_report":
        return m3_reporte(persona_, comercio, reporte or {}, paga_hasta)
    if kind == "photo_refresh":
        return m4_fotos(persona_, comercio)
    if kind == "renewal_before":
        return m5_vence_manana(persona_, paga_hasta)
    if kind == "renewal_overdue":
        return m6_atrasado(persona_)
    if kind == "week1_checkin":
        return week1_checkin(persona_)
    return None
