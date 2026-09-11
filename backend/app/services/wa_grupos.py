"""Crear el grupo de WhatsApp de un comercio, desde el sistema.

POR QUÉ VALE LA PENA
====================

Armar el grupo a mano son cinco pasos por comercio: crear, ponerle nombre,
agregar al comerciante, agregar los respaldos, y después mandar `URUKU-XXXX`
adentro para que la ingesta sepa de quién es. Con setecientos comercios eso no
se hace nunca.

Y hay algo mejor que ahorrar tiempo: **cuando el grupo lo crea el sistema, el
identificador vuelve en la respuesta.** Se ata al comercio ahí mismo, sin
código, sin que nadie escriba nada y sin la ventana en la que un grupo existe
pero todavía no se sabe de quién es.

LOS PARTICIPANTES
=================

El número vinculado a WAHA no se agrega: es quien crea el grupo, así que queda
adentro y como administrador. Se agregan el comerciante y los respaldos
(`WA_NUMEROS_GRUPO`), que están ahí para el día que baneen al operativo —
ver docs/numeros-whatsapp-uruku.md.
"""
from __future__ import annotations

import httpx
import structlog

from app.core.config import settings
from app.core.telefono import normalizar_whatsapp

logger = structlog.get_logger()

_TIMEOUT = 30.0


class GrupoError(Exception):
    """No se pudo crear el grupo. El caller decide si eso frena el alta."""


def _jid(numero: str) -> str | None:
    n = normalizar_whatsapp(numero)
    return f"{n}@c.us" if n else None


def numeros_de_grupo() -> list[str]:
    """Los números de URUKU que se agregan a cada grupo (los respaldos)."""
    return [n.strip() for n in settings.wa_numeros_grupo.split(",") if n.strip()]


def crear_grupo(nombre: str, participantes: list[str]) -> dict:
    """Crea el grupo y devuelve la respuesta cruda de WAHA.

    Lanza `GrupoError` con el detalle. No se traga el error como hacen otros
    servicios: acá el caller SÍ necesita saber, porque un grupo a medias es
    peor que ninguno — el comerciante ya lo vio aparecer en su teléfono.
    """
    if settings.wa_solo_lectura:
        raise GrupoError("WAHA está en modo sólo lectura: los grupos se crean a mano "
                         "desde la tablet y se atan mandando URUKU-XXXX adentro")
    if not settings.waha_base_url or not settings.waha_api_key:
        raise GrupoError("WAHA no está configurado (falta URL o API key)")

    jids = [j for j in (_jid(p) for p in participantes) if j]
    if not jids:
        raise GrupoError("Ningún número válido para agregar al grupo")

    url = f"{settings.waha_base_url.rstrip('/')}/api/default/groups"
    cuerpo = {"name": nombre, "participants": [{"id": j} for j in jids]}
    try:
        r = httpx.post(url, json=cuerpo,
                       headers={"X-Api-Key": settings.waha_api_key}, timeout=_TIMEOUT)
    except Exception as exc:  # noqa: BLE001
        raise GrupoError(f"No se pudo hablar con WhatsApp: {exc}") from exc

    if r.status_code >= 400:
        # El cuerpo de la respuesta es lo único que explica por qué: número
        # inexistente en WhatsApp, sesión caída, permisos. Va al log entero.
        logger.warning("wa_grupo.error", status=r.status_code, respuesta=r.text[:400])
        raise GrupoError(f"WhatsApp rechazó la creación (HTTP {r.status_code}): {r.text[:200]}")

    datos = r.json()
    logger.info("wa_grupo.creado", nombre=nombre, participantes=len(jids),
                respuesta=str(datos)[:200])
    return datos


def id_del_grupo(respuesta: dict) -> str | None:
    """El identificador del grupo, tolerando cómo lo devuelva la versión.

    WAHA cambió la forma entre versiones (`id` suelto, `id.  _serialized`,
    `gid`). Si mañana cambia otra vez, esto sigue encontrándolo en vez de
    guardar un grupo sin identificador — que dejaría el grupo creado y sin atar,
    el peor de los dos mundos.
    """
    for clave in ("id", "gid", "groupId", "chatId"):
        v = respuesta.get(clave)
        if isinstance(v, str) and v.endswith("@g.us"):
            return v
        if isinstance(v, dict):
            s = v.get("_serialized") or v.get("id")
            if isinstance(s, str) and s.endswith("@g.us"):
                return s
    return None


def agregar_a_grupo(grupo_jid: str, numeros: list[str]) -> None:
    """Suma participantes a un grupo que YA existe.

    Es la salida para el problema de tiempo de los respaldos: el sistema los
    agrega solo a cada grupo que crea, así que un respaldo dado de alta después
    no está en ninguno de los grupos anteriores — y meterlo a mano en cien es
    trabajo que nadie hace. Peor: el día del baneo ya no se puede, porque una
    cuenta baneada no agrega a nadie.

    Lanza `GrupoError`. Que un grupo falle no puede pasar por exitoso: el caller
    los cuenta y muestra cuáles quedaron afuera, porque un respaldo "casi" en
    todos los grupos es un respaldo que no está donde haga falta.
    """
    if settings.wa_solo_lectura:
        raise GrupoError("WAHA está en modo sólo lectura: los respaldos se agregan a mano "
                         "desde la tablet")
    if not settings.waha_base_url or not settings.waha_api_key:
        raise GrupoError("WAHA no está configurado (falta URL o API key)")

    jids = [j for j in (_jid(n) for n in numeros) if j]
    if not jids:
        raise GrupoError("Ningún número válido para agregar")

    url = (f"{settings.waha_base_url.rstrip('/')}/api/default/groups/"
           f"{grupo_jid}/participants/add")
    try:
        r = httpx.post(url, json={"participants": [{"id": j} for j in jids]},
                       headers={"X-Api-Key": settings.waha_api_key}, timeout=_TIMEOUT)
    except Exception as exc:  # noqa: BLE001
        raise GrupoError(f"No se pudo hablar con WhatsApp: {exc}") from exc

    if r.status_code >= 400:
        logger.warning("wa_grupo.agregar_error", grupo=grupo_jid,
                       status=r.status_code, respuesta=r.text[:300])
        raise GrupoError(f"HTTP {r.status_code}: {r.text[:160]}")

    logger.info("wa_grupo.agregado", grupo=grupo_jid, participantes=len(jids))

def participantes_de_grupo(grupo_jid: str) -> list[str] | None:
    """Los números que ya están adentro. `None` si no se pudo averiguar.

    La distinción entre `[]` y `None` es todo el sentido de esta función: un
    grupo vacío y un grupo que no se pudo leer llevan a decisiones opuestas, y
    devolver `[]` en los dos casos sería decir "no está adentro" de algo que
    quizás sí está.

    Leer no cuenta para el baneo como agregar; se puede consultar cada grupo
    antes de tocarlo.
    """
    if not settings.waha_base_url or not settings.waha_api_key:
        return None
    url = (f"{settings.waha_base_url.rstrip('/')}/api/default/groups/"
           f"{grupo_jid}/participants")
    try:
        r = httpx.get(url, headers={"X-Api-Key": settings.waha_api_key}, timeout=_TIMEOUT)
        if r.status_code >= 400:
            return None
        datos = r.json()
    except Exception:  # noqa: BLE001
        logger.warning("wa_grupo.participantes_fallo", grupo=grupo_jid, exc_info=True)
        return None

    if not isinstance(datos, list):
        datos = datos.get("participants") if isinstance(datos, dict) else None
        if not isinstance(datos, list):
            return None

    nums: list[str] = []
    for p in datos:
        jid = p.get("id") if isinstance(p, dict) else p
        if isinstance(jid, dict):          # algunas versiones anidan {_serialized}
            jid = jid.get("_serialized") or jid.get("user")
        if isinstance(jid, str):
            nums.append(jid.split("@")[0].lstrip("+"))
    return nums
