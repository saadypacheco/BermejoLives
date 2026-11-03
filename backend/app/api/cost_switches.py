"""Interruptores de costo: lo que cuesta plata se prende a propósito (docs/contenido-redes-tecnico.md §17.2).

- `GET /admin/cost-switches`: lo ve quien publica en las redes (`difusion`) o el dueño (`equipo`).
- `PUT /admin/cost-switches/{key}`: sólo el dueño (`equipo`). Prender exige confirmar que se sabe que tiene costo.

Apagar no pide confirmación. Sin fila = apagado.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth import require_alguno, require_permiso
from app.db.content_repository import ContentRepo, get_content_repo
from app.services import cost_switches

router = APIRouter()
logger = structlog.get_logger()

_ver = require_alguno("difusion", "equipo")
_cambiar = require_permiso("equipo")


class CostSwitchUpdate(BaseModel):
    enabled: bool
    confirm_cost: bool = False


@router.get("/admin/cost-switches")
def listar_interruptores(_claims: dict = Depends(_ver), crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    """`{items: [{key, label, what, cost, off_means, enabled, updated_by, updated_at}]}`."""
    return {"items": cost_switches.listar(crepo)}


@router.put("/admin/cost-switches/{key}")
def cambiar_interruptor(key: str, body: CostSwitchUpdate, claims: dict = Depends(_cambiar),
                        crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    """Prende o apaga un interruptor. Devuelve el item ya cambiado (el mismo shape que la lista)."""
    if key not in cost_switches.CATALOGO:
        raise HTTPException(status_code=404, detail="Ese servicio no existe")
    if body.enabled and not body.confirm_cost:
        raise HTTPException(status_code=400, detail="Confirmá que sabés que tiene costo")
    actor = claims.get("email") or claims.get("sub") or "desconocido"
    cost_switches.set(crepo, key, body.enabled, actor)
    return next(i for i in cost_switches.listar(crepo) if i["key"] == key)
