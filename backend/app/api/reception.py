"""Recepción de WhatsApp: lo que llegó de quien todavía no sabemos de quién es.

Cuatro cosas, todas con el permiso `whatsapp`:

  - la foto guardada de un desconocido (la miniatura del admin);
  - la lista «sin dueño»: números con fotos/mensajes 1-a-1 y grupos sin atar;
  - «Es de…» sobre un MENSAJE: autoriza el número de su remitente para un comercio y
    reprocesa lo retenido de ese número;
  - «Es de…» sobre un GRUPO: ata el grupo a un comercio y reprocesa lo retenido.

La foto vive en el disco PRIVADO `WA_RECEIVED_DIR` (nunca bajo /fotos, que es
público): sale únicamente por acá, con token.

EL TELÉFONO DE UN TERCERO NO VIAJA AL PANEL. La lista sólo trae el número enmascarado
y una clave opaca (el id del mensaje más reciente); el número completo lo resuelve el
backend, de la fila de la bandeja, cuando se asigna.
"""
import re
import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response

from app.core.auth import require_permiso
from app.core.config import settings
from app.core.telefono import normalizar_whatsapp, validar_whatsapp
from app.db.repository import Repo, get_repo
from app.services import wa_identity, wa_received

router = APIRouter()
logger = structlog.get_logger()

#: Cuántos mensajes se listan por número (los más nuevos); `count` dice cuántos hay.
_MENSAJES_POR_ITEM = 50
#: Los JID de grupo: dígitos, y a veces `-` + más dígitos (grupos viejos).
_RE_GRUPO = re.compile(r"^\d+(-\d+)?@g\.us$")


def _enmascarar(telefono: str | None) -> str | None:
    """`59171234567` -> `+591 7•••• 567`. Un teléfono de un tercero no se muestra
    entero en una captura de pantalla."""
    d = "".join(ch for ch in (telefono or "") if ch.isdigit())
    if len(d) < 8:
        return "••••" if d else None
    return f"+{d[:3]} {d[3]}•••• {d[-3:]}"


def _error(status: int, codigo: str, mensaje: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"codigo": codigo, "mensaje": mensaje})


@router.get("/admin/whatsapp/inbox/{wa_message_id}/media")
async def admin_wa_media(
    wa_message_id: str,
    _admin: dict = Depends(require_permiso("whatsapp")),
    repo: Repo = Depends(get_repo),
) -> Response:
    """La foto de un mensaje que quedó sin dueño. 404 si no hay o se purgó."""
    fila = await run_in_threadpool(repo.get_wa_inbox, wa_message_id)
    if not fila or not fila.get("media_path") or fila.get("media_purged_at"):
        raise HTTPException(status_code=404, detail="Esa foto no está (no existe o ya se borró)")
    datos = await run_in_threadpool(wa_received.read, fila["media_path"])
    if not datos:
        raise HTTPException(status_code=404, detail="Esa foto no está (no existe o ya se borró)")
    return Response(content=datos, media_type="image/jpeg", headers={
        # Foto de un desconocido que nadie moderó: ni caché compartida ni sniffing.
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
    })


def _mensaje(fila: dict) -> dict:
    return {
        "wa_message_id": fila["wa_message_id"],
        "at": fila.get("created_at"),
        "body": fila.get("body"),
        # Hay foto que mirar: guardada y todavía sin purgar.
        "has_media": bool(fila.get("media_path")) and not fila.get("media_purged_at"),
    }


def _es_asignable(numero: str | None) -> bool:
    """¿Se puede decir «es de…» sobre este número? Hace falta saber cuál es, que sea
    un celular válido y que no sea de URUKU (propio o explorador)."""
    if not numero or validar_whatsapp(numero):
        return False
    return not (settings.es_numero_propio(numero) or settings.es_numero_explorador(numero))


def _numero_de_fila(repo: Repo, fila: dict, cache: dict) -> str | None:
    """El número del remitente de la fila, con caché por JID (la lista repite remitentes)."""
    clave = (fila.get("wa_jid"), fila.get("phone"))
    if clave not in cache:
        cache[clave] = wa_identity.number_of_inbox_row(repo, fila)
    return cache[clave]


@router.get("/admin/whatsapp/unknown")
async def admin_wa_unknown(
    days: int = Query(default=30, ge=1, le=90),
    _admin: dict = Depends(require_permiso("whatsapp")),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Lo que entró y no se sabe de quién es, agrupado por número (chat 1-a-1) o por
    grupo sin atar. `kind`: `phone` | `group` (E2 suma `community_join`).

    Un `phone` lleva el número ENMASCARADO (null si no se sabe: llegó como LID y nadie
    aprendió el número) y `assignable`; la `key` es el id del mensaje más reciente,
    que es lo que se manda a `POST /admin/whatsapp/inbox/{key}/assign`. Nunca viaja el
    número completo ni el LID."""
    filas = await run_in_threadpool(repo.list_wa_inbox_sin_dueno, days, None, False)

    def armar() -> list[dict]:
        cache: dict = {}
        grupos: dict[tuple, dict] = {}
        for f in filas:                      # vienen lo más nuevo primero
            jid = f.get("wa_jid") or ""
            if jid.endswith("@g.us"):
                clave, tipo, numero = jid, "group", None
            else:
                numero = _numero_de_fila(repo, f, cache)
                clave, tipo = (numero or jid), "phone"
            if not clave:
                continue
            item = grupos.get((tipo, clave))
            if item is None:
                item = {"kind": tipo, "at": f.get("created_at"), "count": 0, "messages": []}
                if tipo == "group":
                    item["key"] = jid
                    item["group_jid"] = jid
                else:
                    item["key"] = f["wa_message_id"]
                    item["phone_masked"] = _enmascarar(numero)
                    item["assignable"] = _es_asignable(numero)
                grupos[(tipo, clave)] = item
            item["count"] += 1
            if len(item["messages"]) < _MENSAJES_POR_ITEM:
                item["messages"].append(_mensaje(f))
        return sorted(grupos.values(), key=lambda i: str(i["at"] or ""), reverse=True)

    return {"items": await run_in_threadpool(armar)}


def _uuid_valido(valor: str) -> str:
    try:
        return str(uuid.UUID(str(valor)))
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError("comercio_id no es un UUID válido") from exc


class AssignBody(BaseModel):
    comercio_id: str = Field(min_length=1)
    label: str | None = Field(default=None, max_length=80)

    valida_uuid = field_validator("comercio_id")(classmethod(lambda cls, v: _uuid_valido(v)))


class GroupAssignBody(BaseModel):
    comercio_id: str = Field(min_length=1)

    valida_uuid = field_validator("comercio_id")(classmethod(lambda cls, v: _uuid_valido(v)))


async def _comercio_activo(repo: Repo, comercio_id: str) -> dict:
    comercio = await run_in_threadpool(repo.get_comercio, comercio_id)
    if not comercio or comercio.get("activo") is False:
        raise HTTPException(status_code=404, detail="Ese comercio no existe")
    return comercio


def _filas_para_reprocesar(repo: Repo, numero: str) -> list[dict]:
    """Lo `sin_comercio` de los últimos 30 días cuyo remitente es `numero`, con el crudo.

    Dos caminos: las filas cuyo `phone` ya es el número (incluye las de un LID que traía
    el número al lado) y las de un LID que se aprendió DESPUÉS. Sólo chats 1-a-1: lo
    que el mismo número mandó a un grupo sin atar sigue sin dueño hasta que se ate el grupo."""
    por_id: dict[str, dict] = {}
    for f in repo.list_wa_inbox_sin_dueno(30, numero, True):
        if not (f.get("wa_jid") or "").endswith("@g.us"):
            por_id[f["wa_message_id"]] = f
    cache: dict = {}
    for f in repo.list_wa_inbox_sin_dueno(30, None, False):
        jid = f.get("wa_jid") or ""
        if f["wa_message_id"] in por_id or not jid.endswith("@lid"):
            continue
        if _numero_de_fila(repo, f, cache) == numero:
            completa = repo.get_wa_inbox(f["wa_message_id"])
            if completa:
                por_id[f["wa_message_id"]] = completa
    return list(por_id.values())


@router.post("/admin/whatsapp/inbox/{wa_message_id}/assign")
async def admin_wa_assign(
    wa_message_id: str,
    body: AssignBody,
    admin: dict = Depends(require_permiso("whatsapp")),
    repo: Repo = Depends(get_repo),
) -> dict:
    """«Es de…»: el remitente de ESTE mensaje es de este comercio. El backend resuelve
    el número de la fila de la bandeja (o del par LID aprendido): el panel nunca lo
    manda ni lo recibe. Lo autoriza y reprocesa, con la foto del disco privado, todo lo
    que ese número mandó en los últimos 30 días sin dueño. Lo reprocesado entra siempre
    a la cola de moderación.

    400 `own_number` (es de URUKU), `explorer_message` (las fotos del explorador se
    publican sólo por código), `lid_not_assignable` (número oculto y desconocido),
    `invalid_number`; 409 `phone_owned_by_other`; 404 mensaje o comercio inexistente."""
    fila = await run_in_threadpool(repo.get_wa_inbox, wa_message_id)
    if not fila:
        raise HTTPException(status_code=404, detail="Ese mensaje no existe")
    if (fila.get("wa_jid") or "").endswith("@g.us"):
        raise _error(400, "invalid_number",
                     "Ese mensaje es de un grupo: se asigna atando el grupo a un comercio")

    numero = await run_in_threadpool(wa_identity.number_of_inbox_row, repo, fila)
    if not numero:
        raise _error(400, "lid_not_assignable",
                     "WhatsApp escondió el número de quien lo mandó y todavía no se sabe cuál es: "
                     "no se puede asignar. Cuando vuelva a escribir con su número se podrá")
    if settings.es_numero_explorador(numero):
        raise _error(400, "explorer_message",
                     "Es un mensaje del explorador: sus fotos se publican sólo mandándolas con el código del local")
    if settings.es_numero_propio(numero):
        raise _error(400, "own_number", "Ese es un número de URUKU: no puede ser de un comercio")
    if validar_whatsapp(numero):
        raise _error(400, "invalid_number", "Ese número no es un celular válido")
    numero = normalizar_whatsapp(numero) or numero

    comercio = await _comercio_activo(repo, body.comercio_id)

    quien = admin.get("email") or admin.get("sub") or "admin"
    etiqueta = (body.label or "").strip() or None
    resultado = await run_in_threadpool(
        repo.authorize_phone_if_free, comercio["id"], numero, etiqueta, quien)
    if resultado == "owned_by_other":
        otro = await run_in_threadpool(repo.get_comercio_por_numero, numero) or {}
        logger.info("reception.numero_de_otro_comercio", comercio=comercio.get("slug"))
        raise HTTPException(status_code=409, detail={
            "codigo": "phone_owned_by_other",
            "mensaje": f"Ese número ya es de {otro.get('nombre') or 'otro comercio'}",
            "comercio": {"nombre": otro.get("nombre")},
        })

    filas = await run_in_threadpool(_filas_para_reprocesar, repo, numero)
    cuenta = await run_in_threadpool(wa_received.reprocess, repo, filas, quien)
    logger.info("reception.numero_asignado", comercio=comercio.get("slug"), autorizacion=resultado, **cuenta)
    return {"numero_masked": _enmascarar(numero), **cuenta}


@router.post("/admin/whatsapp/groups/{group_jid}/assign")
async def admin_wa_assign_group(
    group_jid: str,
    body: GroupAssignBody,
    admin: dict = Depends(require_permiso("whatsapp")),
    repo: Repo = Depends(get_repo),
) -> dict:
    """«Es de…» sobre un grupo sin atar: lo ata al comercio (origen `admin`, `created_by`
    = quien lo hizo) y reprocesa lo retenido de ese grupo en los últimos 30 días, siempre
    a la cola y sin cuota. 409 `group_owned_by_other` si ya está atado a otro comercio
    activo; nunca se lo roba."""
    if not _RE_GRUPO.match(group_jid):
        raise HTTPException(status_code=422, detail="El identificador del grupo no es válido")
    comercio = await _comercio_activo(repo, body.comercio_id)
    quien = admin.get("email") or admin.get("sub") or "admin"

    def conflicto(otro: dict | None) -> HTTPException:
        return _error(409, "group_owned_by_other",
                      f"Ese grupo ya es de {(otro or {}).get('nombre') or 'otro comercio'}")

    previo = await run_in_threadpool(repo.get_comercio_por_grupo, group_jid, True)
    if previo and previo.get("id") != comercio["id"]:
        # También si el otro está de baja: soltar el vínculo hoy es un DELETE físico
        # (`desvincular_grupo`) y AGENTS.md no lo permite. Se suelta a mano desde la
        # ficha del comercio dado de baja; E3 trae la baja lógica de grupos.
        raise conflicto(previo)
    if previo is None:
        await run_in_threadpool(repo.vincular_grupo_comercio, group_jid, comercio["id"], None, "admin", quien)
        # El vínculo ignora duplicados: si otro lo ató en el medio, quedó el de él.
        ahora = await run_in_threadpool(repo.get_comercio_por_grupo, group_jid, True)
        if not ahora or ahora.get("id") != comercio["id"]:
            raise conflicto(ahora)

    filas = await run_in_threadpool(repo.list_wa_inbox_sin_dueno, 30, None, True, group_jid)
    cuenta = await run_in_threadpool(wa_received.reprocess, repo, filas, quien)
    logger.info("reception.grupo_asignado", comercio=comercio.get("slug"), **cuenta)
    return cuenta
