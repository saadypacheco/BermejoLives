"""Quién es quién en WhatsApp: números, LID y «número propio».

POR QUÉ EXISTE
==============
WhatsApp está reemplazando el teléfono por un identificador oculto (`…@lid`) en
grupos y comunidades. El mensaje trae, cuando puede, el número al lado
(`participantAlt` en grupos, `remoteJidAlt` en chats 1-a-1). Cada vez que llegan
los dos juntos se guarda el par en `wa_lid_map`: es gratis y es lo que después
permite saber QUIÉN es un LID sin preguntarle nada a WAHA.

Todo lo de acá es de LECTURA: no escribe, no manda ni agrega a nadie en
WhatsApp. La única llamada a WAHA (`GET /lids/{lid}`) está apagada por defecto
(`WA_LID_LOOKUP`) y tiene tope por hora.

Nada de esto lanza: que no se pueda learn o resolve un LID no puede
tumbar la ingesta de un mensaje.
"""
import threading
import time
from collections import deque

import structlog

from app.core.config import settings
from app.core.telefono import normalizar_whatsapp

logger = structlog.get_logger()

#: Claves donde WAHA puede traer el número junto al LID de un participante.
#: **A verificar** con lo que llegue de verdad (por eso se guarda el evento crudo).
_CAMPOS_NUMERO = ("phoneNumber", "phone_number", "pn", "phone", "jidAlt", "participantAlt", "alt")


def is_lid(jid: str | None) -> bool:
    return bool(jid) and str(jid).endswith("@lid")


def phone_of_jid(jid: str | None) -> str | None:
    """El teléfono (E.164 sin '+') detrás de un `…@c.us` / `…@s.whatsapp.net`.
    Un LID NO es un teléfono: devuelve None."""
    if not jid or is_lid(jid):
        return None
    base = str(jid).split("@")[0].split(":")[0]
    return normalizar_whatsapp(base)


def _lid_normalizado(lid: str | None) -> str | None:
    if not lid or not is_lid(lid):
        return None
    digitos = str(lid).split("@")[0].split(":")[0]
    return f"{digitos}@lid" if digitos.isdigit() else None


def _id_de(participante) -> str | None:
    """El `id` de un participante, sea un texto o un objeto."""
    if isinstance(participante, dict):
        pid = participante.get("id")
        if isinstance(pid, dict):
            pid = pid.get("_serialized")
        return str(pid) if pid else None
    return str(participante) if participante else None


# ───────────────────────────────────────────────────────────── learn

def learn(repo, lid: str | None, alternativo: str | None, origen: str = "message") -> bool:
    """Guarda el par LID <-> número si el JID es un LID y vino el número al lado.
    Devuelve si guardó. Nunca lanza."""
    try:
        lid_ok = _lid_normalizado(lid)
        numero = phone_of_jid(alternativo)
        if not lid_ok or not numero:
            return False
        repo.upsert_wa_lid(lid_ok, numero, origen)
        return True
    except Exception:  # noqa: BLE001 — learn es un extra, nunca puede romper la ingesta
        logger.warning("wa_identity.aprender_fallo", exc_info=True)
        return False


def learn_from_message(repo, payload) -> bool:
    """El remitente del mensaje (grupo: `participant`; 1-a-1: `from`) es un LID y
    WAHA trajo su número en `participantAlt` / `remoteJidAlt`."""
    jid = payload.remitente_jid if payload.es_grupo else payload.from_
    return learn(repo, jid, payload.remitente_alt, "message")


def learn_from_participant(repo, participante) -> bool:
    """Un participante de un evento de grupo: `{"id": "…@lid", "phoneNumber": "…"}`."""
    if not isinstance(participante, dict):
        return False
    pid = _id_de(participante)
    for campo in _CAMPOS_NUMERO:
        valor = participante.get(campo)
        if valor and learn(repo, pid, str(valor), "event"):
            return True
    return False


# ───────────────────────────────────────────────────────────── resolve

_consultas: deque = deque()
_candado = threading.Lock()


def _hay_cupo_de_consulta() -> bool:
    """Tope por hora de consultas a WAHA (pocas y espaciadas)."""
    ahora = time.time()
    with _candado:
        while _consultas and ahora - _consultas[0] > 3600:
            _consultas.popleft()
        if len(_consultas) >= max(0, settings.wa_lid_lookup_max_per_hour):
            return False
        _consultas.append(ahora)
        return True


def reset_quota() -> None:
    with _candado:
        _consultas.clear()


def query_waha(lid: str) -> str | None:
    """`GET /api/default/lids/{lid}` -> `{lid, pn}`. SÓLO LECTURA. None si no sabe."""
    if not settings.wa_lid_lookup or not settings.waha_base_url:
        return None
    if not _hay_cupo_de_consulta():
        logger.info("wa_identity.lookup_sin_cupo", tope=settings.wa_lid_lookup_max_per_hour)
        return None
    import httpx

    digitos = lid.split("@")[0]
    try:
        headers = {"X-Api-Key": settings.waha_api_key} if settings.waha_api_key else {}
        r = httpx.get(f"{settings.waha_base_url.rstrip('/')}/api/default/lids/{digitos}",
                      headers=headers, timeout=10)
        r.raise_for_status()
        pn = (r.json() or {}).get("pn")
    except Exception as exc:  # noqa: BLE001
        logger.warning("wa_identity.lookup_fallo", error=str(exc))
        return None
    return phone_of_jid(str(pn)) if pn else None


def resolve(repo, participante) -> str | None:
    """El número de un participante (`"…@c.us"`, `"…@lid"` o `{"id":…, "phoneNumber":…}`).

    1. `@c.us` / `@s.whatsapp.net` -> el número. Si el objeto trae el número al
       lado, se usa.
    2. `@lid` -> `wa_lid_map`; si no está y `WA_LID_LOOKUP` -> WAHA (y se guarda).
    3. Si nadie sabe: None.
    """
    try:
        if isinstance(participante, dict):
            for campo in _CAMPOS_NUMERO:
                if participante.get(campo):
                    n = phone_of_jid(str(participante[campo]))
                    if n:
                        return n
        pid = _id_de(participante)
        if not pid:
            return None
        if not is_lid(pid):
            return phone_of_jid(pid)
        lid = _lid_normalizado(pid)
        if not lid:
            return None
        guardado = repo.get_wa_lid(lid)
        if guardado:
            return guardado
        n = query_waha(lid)
        if n:
            repo.upsert_wa_lid(lid, n, "waha_api")
        return n
    except Exception:  # noqa: BLE001
        logger.warning("wa_identity.resolver_fallo", exc_info=True)
        return None


# ───────────────────────────────────────────────────────────── «propio»

def is_own(repo, numero_o_jid: str | None) -> bool:
    """¿Es un número de URUKU (`WA_NUMEROS_PROPIOS`)? También cuando llega como LID
    que ya se sabe que es de uno de ellos (el Samsung llegó como LID el 11/9)."""
    if not numero_o_jid:
        return False
    if is_lid(numero_o_jid):
        n = resolve(repo, numero_o_jid)
        return bool(n) and settings.es_numero_propio(n)
    return settings.es_numero_propio(numero_o_jid)


def sender_number(repo, payload) -> str | None:
    """El número real de quien escribió (E.164 sin '+'), o None si llegó como LID y
    no se sabe cuál es.

    Un `…@c.us` es su número. Un LID se resuelve con el número que WAHA trajo al lado
    (`participantAlt` / `remoteJidAlt`) o con el par ya aprendido (`wa_lid_map`, y WAHA si
    `WA_LID_LOOKUP`). Si nada lo sabe es None: `payload.phone` en ese caso son los
    dígitos del LID, que NO son un teléfono, y no puede usarse para autorizar a nadie."""
    jid = payload.remitente_jid if payload.es_grupo else payload.from_
    if not is_lid(jid):
        return payload.phone or None
    alt = phone_of_jid(payload.remitente_alt)
    if alt:
        return alt
    return resolve(repo, jid)


def number_of_inbox_row(repo, fila: dict) -> str | None:
    """El número del remitente de una fila de `wa_inbox`, sin salir a WAHA.

    Para la bandeja «sin dueño»: una fila de un LID cuyo `phone` son los dígitos del
    propio LID no tiene número; si el par se aprendió después, está en `wa_lid_map`."""
    jid = fila.get("wa_jid") or ""
    phone = fila.get("phone") or ""
    if not is_lid(jid):
        return phone or None
    if phone and phone != jid.split("@")[0].split(":")[0]:
        return phone                         # WAHA trajo el número al lado cuando llegó
    lid = _lid_normalizado(jid)
    return repo.get_wa_lid(lid) if lid else None


def sender_is_own(repo, payload) -> bool:
    """El que escribió este mensaje es un número de URUKU, aunque haya llegado como LID."""
    if settings.es_numero_propio(payload.phone):
        return True
    jid = payload.remitente_jid if payload.es_grupo else payload.from_
    return is_lid(jid) and is_own(repo, jid)
