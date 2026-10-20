"""Recepción de WhatsApp: lo que llegó de quien todavía no sabemos de quién es.

Tres cosas, todas con el permiso `whatsapp`:

  - la foto guardada de un desconocido (la miniatura del admin);
  - la lista «sin dueño»: números con fotos/mensajes 1-a-1 y grupos sin atar;
  - «Es de…»: autorizar el número para un comercio y reprocesar lo retenido.

La foto vive en el disco PRIVADO `WA_RECEIVED_DIR` (nunca bajo /fotos, que es
público): sale únicamente por acá, con token.
"""
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
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


def _enmascarar(telefono: str | None) -> str | None:
    """`59171234567` -> `+591 7•••• 567`. Un teléfono de un tercero no se muestra
    entero en una captura de pantalla."""
    d = "".join(ch for ch in (telefono or "") if ch.isdigit())
    if len(d) < 8:
        return "••••" if d else None
    return f"+{d[:3]} {d[3]}•••• {d[-3:]}"


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


@router.get("/admin/whatsapp/unknown")
async def admin_wa_unknown(
    days: int = Query(default=30, ge=1, le=90),
    _admin: dict = Depends(require_permiso("whatsapp")),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Lo que entró y no se sabe de quién es, agrupado por número (chat 1-a-1) o por
    grupo sin atar. `kind`: `phone` | `group` (E2 suma `community_join`).

    Un remitente que llegó como LID y no se sabe su número sale con `phone: null` y
    `lid`: se puede mirar pero no asignar hasta que se aprenda su número."""
    filas = await run_in_threadpool(repo.list_wa_inbox_sin_dueno, days, None, False)
    grupos: dict[str, dict] = {}
    for f in filas:                      # vienen lo más nuevo primero
        jid = f.get("wa_jid") or ""
        es_lid = jid.endswith("@lid")
        # Un LID sin número al lado: WAHA deja los dígitos del LID como «teléfono».
        numero = None if (es_lid and (f.get("phone") or "") == jid.split("@")[0]) else (f.get("phone") or None)
        if jid.endswith("@g.us"):
            clave, tipo = jid, "group"
        else:
            clave, tipo = (numero or jid), "phone"
        if not clave:
            continue
        item = grupos.get((tipo, clave))
        if item is None:
            item = {"kind": tipo, "key": clave, "at": f.get("created_at"), "count": 0, "messages": []}
            if tipo == "group":
                item["group_jid"] = jid
            else:
                item["phone"] = numero
                item["phone_masked"] = _enmascarar(numero)
                item["lid"] = jid if es_lid else None
            grupos[(tipo, clave)] = item
        item["count"] += 1
        if len(item["messages"]) < _MENSAJES_POR_ITEM:
            item["messages"].append(_mensaje(f))
    items = sorted(grupos.values(), key=lambda i: str(i["at"] or ""), reverse=True)
    return {"items": items}


class AssignBody(BaseModel):
    comercio_id: str = Field(min_length=1)
    label: str | None = Field(default=None, max_length=80)


@router.post("/admin/whatsapp/numbers/{phone}/assign")
async def admin_wa_assign(
    phone: str,
    body: AssignBody,
    admin: dict = Depends(require_permiso("whatsapp")),
    repo: Repo = Depends(get_repo),
) -> dict:
    """«Es de…»: este número es de este comercio. Lo autoriza y reprocesa, con la
    foto del disco privado, todo lo que mandó en los últimos 30 días sin dueño.

    Nunca mueve un número que ya es de otro comercio activo (409), ni autoriza un
    número de URUKU (400)."""
    error = validar_whatsapp(phone)
    if error:
        raise HTTPException(status_code=400, detail=error)
    numero = normalizar_whatsapp(phone) or ""
    if settings.es_numero_propio(numero):
        raise HTTPException(status_code=400, detail="Ese es un número de URUKU: no puede ser de un comercio")

    comercio = await run_in_threadpool(repo.get_comercio, body.comercio_id)
    if not comercio or comercio.get("activo") is False:
        raise HTTPException(status_code=404, detail="Ese comercio no existe")

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
            "comercio": {"id": otro.get("id"), "nombre": otro.get("nombre")},
        })

    filas = await run_in_threadpool(repo.list_wa_inbox_sin_dueno, 30, numero, True)
    # Sólo chats 1-a-1: un mensaje del mismo número en un grupo sin atar sigue
    # sin dueño hasta que se ate el grupo.
    filas = [f for f in filas if not (f.get("wa_jid") or "").endswith("@g.us")]
    cuenta = await run_in_threadpool(wa_received.reprocess, repo, filas, quien)
    logger.info("reception.numero_asignado", comercio=comercio.get("slug"), autorizacion=resultado, **cuenta)
    return {"numero": numero, **cuenta}
