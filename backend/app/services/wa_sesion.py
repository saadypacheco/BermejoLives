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


# ───────────────────────────────────────── el Plan B: la API oficial de Meta

_GRAPH = "https://graph.facebook.com/v20.0"


def _cloud_activo() -> bool:
    """¿El interruptor está en la API oficial? Lo que SALE va por ahí."""
    return (settings.whatsapp_provider or "").strip().lower() in {"cloud", "cloud_api", "meta"}


def _cloud(estado: str, ok: bool, configurado: bool = True, **extra) -> dict:
    base = {"configurado": configurado, "ok": ok, "estado": estado,
            "numero": None, "nombre": None, "calidad": None, "activo": _cloud_activo()}
    base.update(extra)
    return base


def estado_cloud() -> dict:
    """¿Está viva la API oficial? Se le pregunta a Meta con el token, sin
    mandar nada.

    Es el equivalente de `estado()` para el Plan B, y existe por lo mismo: un
    interruptor que nadie puede verificar es una promesa. Con esto, el panel
    dice si el token vale, a qué número corresponde y cómo lo califica Meta —
    antes de que haga falta apretar el interruptor.

    Nunca lanza.
    """
    pid = (settings.whatsapp_cloud_phone_id or "").strip()
    token = (settings.whatsapp_cloud_token or "").strip()
    if not pid or not token:
        return _cloud("SIN_CONFIGURAR", ok=False, configurado=False)
    try:
        r = httpx.get(f"{_GRAPH}/{pid}",
                      params={"fields": "display_phone_number,verified_name,quality_rating"},
                      headers={"Authorization": f"Bearer {token}"}, timeout=_TIMEOUT)
        if r.status_code in (400, 401):
            # Meta contesta 400 con error.code 190 cuando el token venció o
            # se revocó. Es el caso más común y merece nombre propio: se
            # arregla rehaciendo el token, no mirando la red.
            cuerpo = (r.json() or {}).get("error") or {}
            if r.status_code == 401 or cuerpo.get("code") == 190:
                return _cloud("TOKEN_INVALIDO", ok=False)
        r.raise_for_status()
        d = r.json() or {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("wa_sesion.cloud_inalcanzable", error=str(exc))
        return _cloud("META_NO_RESPONDE", ok=False)

    return _cloud("OK", ok=True,
                  numero=d.get("display_phone_number"),
                  nombre=d.get("verified_name"),
                  # GREEN / YELLOW / RED: cómo califica Meta la cuenta. RED es
                  # antesala de que la limiten, y conviene verlo antes de que pase.
                  calidad=d.get("quality_rating"))
