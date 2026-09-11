"""¿Está viva la sesión de WhatsApp? Preguntárselo a WAHA, y gritar si no.

POR QUÉ EXISTE
==============
La sesión estuvo caída TRES DÍAS y nadie se enteró. WhatsApp la desvinculó
(`conflict · device_removed`) y del lado de URUKU no hubo ningún error: todo
seguía configurado, el sitio andaba, el panel andaba — y no entraba una sola
oferta. Se descubrió porque alguien pidió un comando por curiosidad.

Es la forma exacta en que este proyecto falla: silencio con apariencia de
normalidad. Con comercios de verdad mandando fotos, cada hora de esa ventana
es una oferta que el comerciante cree publicada y no está.

SE PREGUNTA EN VIVO, NO SE GUARDA
=================================
WAHA sabe el estado real ahora mismo; guardarlo en la base sería tener dos
verdades y que la vieja gane. El panel lo pide cada vez que se abre, y un
worker lo revisa cada pocos minutos para dejar el aviso en los registros —
que es lo que alguien va a mirar cuando algo raro pase, aunque nadie haya
abierto el panel.
"""
from __future__ import annotations

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger()

_TIMEOUT = 8.0

# Lo único que significa "funciona". Todo lo demás es que no entra nada.
ESTADO_OK = "WORKING"


def estado(sesion: str = "default") -> dict:
    """El estado de la sesión tal como lo ve WAHA, aplanado para el panel.

    Nunca lanza. Si WAHA no contesta, eso también es un estado —y de los
    peores—: `alcanzable: False`.
    """
    if not settings.waha_base_url or not settings.waha_api_key:
        return {"alcanzable": False, "estado": "SIN_CONFIGURAR", "ok": False,
                "numero": None, "nombre": None, "sesion": sesion}
    try:
        r = httpx.get(f"{settings.waha_base_url.rstrip('/')}/api/sessions/{sesion}",
                      headers={"X-Api-Key": settings.waha_api_key}, timeout=_TIMEOUT)
        if r.status_code == 404:
            return {"alcanzable": True, "estado": "NO_EXISTE", "ok": False,
                    "numero": None, "nombre": None, "sesion": sesion}
        r.raise_for_status()
        datos = r.json() or {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("wa_sesion.inalcanzable", sesion=sesion, error=str(exc))
        return {"alcanzable": False, "estado": "WAHA_NO_RESPONDE", "ok": False,
                "numero": None, "nombre": None, "sesion": sesion}

    me = datos.get("me") or {}
    st = str(datos.get("status") or "DESCONOCIDO")
    return {
        "alcanzable": True,
        "estado": st,
        "ok": st == ESTADO_OK,
        "numero": (me.get("id") or "").split("@")[0] or None,
        "nombre": me.get("pushName"),
        "sesion": sesion,
    }


def vigilar(sesion: str = "default") -> dict:
    """Lo que corre el worker: mira, y si no está bien lo deja escrito FUERTE.

    `error` y no `warning` a propósito: los registros se filtran por nivel, y
    esto es lo único de todo el sistema que, cuando falla, hace que se pierdan
    ofertas sin que nada más se rompa.
    """
    e = estado(sesion)
    if e["ok"]:
        return e
    logger.error("wa_sesion.CAIDA", sesion=sesion, estado=e["estado"],
                 alcanzable=e["alcanzable"],
                 detalle="no entra ninguna oferta por WhatsApp hasta que vuelva a WORKING")
    return e
