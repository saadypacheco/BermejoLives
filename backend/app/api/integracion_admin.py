"""Admin de la integración: qué comercios están en el alcance de un cliente de integración.

Los administra el admin de Uruku (permiso `equipo`), NO el sistema de marketing: así el alcance —y con él la marca de
"comercio gestionado"— lo decide quien es dueño de los comercios.

Las claves (emitir / rotar / revocar) NO pasan por HTTP: se hacen con `python -m scripts.integracion_clave` en el
servidor, para que un secreto no viaje nunca por la API ni quede en un log de pedidos.

Nada de lo que devuelve esto incluye el código URUKU-XXXX ni teléfonos. Sí muestra nombre y slug, que son públicos.
"""
from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.auth import require_admin
from app.db.repository import Repo, get_repo

logger = structlog.get_logger()

router = APIRouter(prefix="/admin/integracion", tags=["integracion-admin"])


class ComerciosBody(BaseModel):
    comercio_ids: list[str] = Field(min_length=1, max_length=200)


def _cliente_o_404(repo: Repo, grupo_id: str) -> dict:
    try:
        grupo_id = str(uuid.UUID(grupo_id))
    except ValueError:
        raise HTTPException(404, "cliente de integración no encontrado") from None
    cliente = repo.integracion_get_cliente(grupo_id)
    # El alcance cuelga de la PRIMERA clave del cliente (su grupo): `grupo_id == id`.
    if not cliente or cliente.get("grupo_id") != cliente.get("id"):
        raise HTTPException(404, "cliente de integración no encontrado")
    return cliente


def _evento(repo: Repo, tipo: str, cliente_id: str, comercio_id: str | None, admin: dict, detalle: dict | None = None) -> None:
    repo.integracion_registrar_evento({"tipo": tipo, "cliente_id": cliente_id, "comercio_id": comercio_id,
                                       "actor": admin.get("email") or admin.get("sub"), "detalle": detalle})


def _publico(c: dict) -> dict:
    return {k: c.get(k) for k in ("id", "grupo_id", "key_id", "nombre", "scopes", "activo", "created_at",
                                  "last_used_at", "rotada_de", "revocada_at")}


@router.get("/clientes")
def listar_clientes(_admin: dict = Depends(require_admin), repo: Repo = Depends(get_repo)) -> dict:
    """Las claves de integración (nunca el hash ni el secreto), agrupadas por cliente (`grupo_id`)."""
    return {"items": [_publico(c) for c in repo.integracion_listar_clientes()]}


@router.get("/clientes/{grupo_id}/comercios")
def listar_comercios(grupo_id: str, _admin: dict = Depends(require_admin), repo: Repo = Depends(get_repo)) -> dict:
    cliente = _cliente_o_404(repo, grupo_id)
    filas = repo.integracion_comercios_de(cliente["id"], solo_activos=False)
    info = {i["id"]: i for i in repo.integracion_info_comercios([f["comercio_id"] for f in filas])}
    return {"cliente": _publico(cliente), "items": [
        {"comercio_id": f["comercio_id"], "nombre": (info.get(f["comercio_id"]) or {}).get("nombre"),
         "slug": (info.get(f["comercio_id"]) or {}).get("slug"), "en_alcance": bool(f["activo"]), "desde": f.get("desde")}
        for f in filas]}


@router.post("/clientes/{grupo_id}/comercios")
def agregar_comercios(grupo_id: str, body: ComerciosBody, admin: dict = Depends(require_admin),
                      repo: Repo = Depends(get_repo)) -> dict:
    """Agrega comercios al alcance (o los reactiva). Desde ese momento son «gestionados»: sus publicaciones nuevas
    quedan pendientes hasta que las apruebe la integración."""
    cliente = _cliente_o_404(repo, grupo_id)
    agregados, ya_estaban = [], []
    for cid in dict.fromkeys(body.comercio_ids):
        try:
            cid = str(uuid.UUID(cid))
        except ValueError:
            raise HTTPException(422, f"comercio_id inválido: {cid!r}") from None
        if not repo.get_comercio(cid):
            raise HTTPException(404, f"no existe el comercio {cid}")
        previo = [f for f in repo.integracion_comercios_de(cliente["id"]) if f["comercio_id"] == cid]
        if previo:
            ya_estaban.append(cid)
            continue
        repo.integracion_set_comercio(cliente["id"], cid, True, admin.get("email"))
        _evento(repo, "alcance_agregado", cliente["id"], cid, admin)
        agregados.append(cid)
    logger.info("integracion.alcance_agregado", cliente=cliente["id"], n=len(agregados), by=admin.get("email"))
    return {"agregados": agregados, "ya_estaban": ya_estaban}


@router.delete("/clientes/{grupo_id}/comercios/{comercio_id}")
def quitar_comercio(grupo_id: str, comercio_id: str, admin: dict = Depends(require_admin),
                    repo: Repo = Depends(get_repo)) -> dict:
    """Saca un comercio del alcance (baja lógica). Deja de ser «gestionado»: vuelve a su flujo de siempre."""
    cliente = _cliente_o_404(repo, grupo_id)
    try:
        comercio_id = str(uuid.UUID(comercio_id))
    except ValueError:
        raise HTTPException(404, "ese comercio no está en el alcance") from None
    if not any(f["comercio_id"] == comercio_id for f in repo.integracion_comercios_de(cliente["id"])):
        raise HTTPException(404, "ese comercio no está en el alcance")
    repo.integracion_set_comercio(cliente["id"], comercio_id, False, admin.get("email"))
    _evento(repo, "alcance_quitado", cliente["id"], comercio_id, admin)
    logger.info("integracion.alcance_quitado", cliente=cliente["id"], comercio=comercio_id, by=admin.get("email"))
    return {"ok": True}


@router.post("/clientes/{grupo_id}/comercios/verificados")
def agregar_verificados(grupo_id: str, simular: bool = Query(default=False, description="sólo cuenta, no agrega"),
                        admin: dict = Depends(require_admin), repo: Repo = Depends(get_repo)) -> dict:
    """Agrega al alcance, de una vez, todos los comercios ACTIVOS y VERIFICADOS que todavía no están.

    Es la forma de armar el piloto sin que `verificado` salga por la API de integración: el admin decide el
    alcance acá (donde ya ve ese dato) y la integración sólo ve «los comercios que me asignaron». Con
    `simular=true` devuelve a quiénes alcanzaría sin tocar nada."""
    cliente = _cliente_o_404(repo, grupo_id)
    ya = {f["comercio_id"] for f in repo.integracion_comercios_de(cliente["id"])}
    nuevos = [c for c in repo.integracion_comercios_verificados() if c["id"] not in ya]
    if not simular:
        for c in nuevos:
            repo.integracion_set_comercio(cliente["id"], c["id"], True, admin.get("email"))
            _evento(repo, "alcance_agregado", cliente["id"], c["id"], admin, {"origen": "verificados"})
        logger.info("integracion.alcance_verificados", cliente=cliente["id"], n=len(nuevos), by=admin.get("email"))
    return {"simulado": simular, "agregados": len(nuevos), "ya_estaban": len(ya),
            "comercios": [{"id": c["id"], "nombre": c.get("nombre"), "slug": c.get("slug")} for c in nuevos]}
