"""Eventos de grupo de WAHA: entrar, salir, ascender, cambiar el nombre.

E1 (esta entrega) sólo GUARDA. Cada evento queda crudo en `wa_group_events`
—idempotente— y, si el participante trae su número junto al LID, se aprende el
par. No decide nada: atar grupos y contar miembros de una comunidad llegan en las
entregas siguientes, detrás de `WA_EVENTS_ACT`.

POR QUÉ GUARDAR CRUDO PRIMERO
=============================
Las formas que WAHA manda para las comunidades NO están documentadas (qué JID
trae un ingreso a una comunidad, si el participante llega como número o como
LID). Hay que ver los eventos reales antes de escribir reglas sobre ellos; para
eso está `raw`. Esta capa es tolerante a propósito con la forma: busca el grupo y
los participantes donde WAHA los pone en cada versión.

WAHA acá sólo RECIBE: este módulo no manda ni agrega a nadie.
"""
import hashlib
import json

import structlog

from app.core.config import settings
from app.services import wa_identity

logger = structlog.get_logger()

EVENTOS_DE_GRUPO = frozenset({
    "group.v2.join", "group.v2.leave", "group.v2.participants", "group.v2.update",
})


def _jid(valor) -> str | None:
    if isinstance(valor, dict):
        valor = valor.get("_serialized") or valor.get("id")
    return str(valor) if valor else None


def _participantes(payload: dict, grupo: dict) -> list[dict]:
    """Los participantes como lista de objetos `{"id": …}`, vengan donde vengan."""
    crudos = payload.get("participants")
    if not isinstance(crudos, list):
        crudos = grupo.get("participants")
    salida: list[dict] = []
    for p in crudos if isinstance(crudos, list) else []:
        if isinstance(p, dict):
            pid = _jid(p.get("id"))
            salida.append({**p, "id": pid} if pid else dict(p))
        elif p:
            salida.append({"id": str(p)})
    return salida


def extraer(evento: dict) -> dict:
    """Lo que interesa de un evento, sea cual sea su forma exacta."""
    payload = evento.get("payload") or {}
    grupo = payload.get("group") if isinstance(payload.get("group"), dict) else payload
    group_jid = (_jid(grupo.get("id")) or _jid(payload.get("groupId")) or _jid(payload.get("chatId"))
                 or _jid(payload.get("id")))
    cambio = payload.get("type") or None
    if cambio is None and evento.get("event") in {"group.v2.join", "group.v2.leave"}:
        cambio = evento["event"].rsplit(".", 1)[-1]
    return {
        "event": evento.get("event"),
        "group_jid": group_jid,
        "change_type": cambio,
        "participants": _participantes(payload, grupo),
        "timestamp": payload.get("timestamp") or evento.get("timestamp"),
        "subject": grupo.get("subject"),
    }


def dedupe_key(datos: dict) -> str:
    """sha256(evento|grupo|tipo|participantes ordenados|timestamp): el mismo evento
    entregado dos veces (WAHA reintenta) es una sola fila."""
    ids = sorted(str(p.get("id") or "") for p in datos["participants"])
    base = "|".join([
        str(datos["event"] or ""), str(datos["group_jid"] or ""), str(datos["change_type"] or ""),
        ",".join(ids), str(datos["timestamp"] or ""),
        # Sin timestamp ni participantes (un cambio de nombre), el asunto distingue.
        str(datos["subject"] or "") if not datos["timestamp"] else "",
    ])
    return hashlib.sha256(base.encode()).hexdigest()


def handle(evento: dict, repo) -> dict:
    """Guarda el evento crudo y aprende los LID que traiga. Idempotente.

    Con `WA_EVENTS_ACT=false` (E1) no hace nada más. Devuelve un dict chico para
    la respuesta del webhook y los tests."""
    nombre = evento.get("event")
    if nombre not in EVENTOS_DE_GRUPO:
        return {"stored": False, "ignored": nombre}

    datos = extraer(evento)
    fila = {
        "dedupe_key": dedupe_key(datos),
        "event": nombre,
        "group_jid": datos["group_jid"],
        "change_type": datos["change_type"],
        "participants": datos["participants"] or None,
        "raw": json.loads(json.dumps(evento, default=str)),
        "result": "captured",
    }
    if not repo.insert_wa_group_event(fila):
        logger.info("wa_events.duplicado", evento=nombre, grupo=datos["group_jid"])
        return {"stored": False, "duplicate": True, "event": nombre}

    aprendidos = sum(1 for p in datos["participants"] if wa_identity.learn_from_participant(repo, p))
    logger.info("wa_events.guardado", evento=nombre, grupo=datos["group_jid"],
                cambio=datos["change_type"], participantes=len(datos["participants"]),
                lid_aprendidos=aprendidos, actua=settings.wa_events_act)
    return {"stored": True, "event": nombre, "group": datos["group_jid"], "learned": aprendidos}
