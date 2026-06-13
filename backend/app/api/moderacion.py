"""Panel de moderación: listar pendientes y aprobar/rechazar/pedir cambios.

Escrituras con service_role (backend). Requiere JWT de admin.
"""
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import require_admin
from app.db.repository import Repo, get_repo
from app.models.schemas import ModerarBody

router = APIRouter()
logger = structlog.get_logger()

_ESTADOS = {"aprobado", "rechazado", "cambios"}


@router.get("/moderacion/publicaciones")
def listar(
    estado: str | None = Query(default="pendiente"),
    _admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    items = repo.list_publicaciones(estado)
    return {"items": items, "total": len(items)}


@router.post("/moderacion/publicaciones/{pub_id}")
def moderar(
    pub_id: str,
    body: ModerarBody,
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    if body.estado not in _ESTADOS:
        raise HTTPException(status_code=400, detail=f"estado inválido: {body.estado}")
    updated = repo.set_estado_publicacion(pub_id, body.estado, body.motivo, admin["email"])
    if not updated:
        raise HTTPException(status_code=404, detail="publicación no encontrada")
    logger.info("moderacion.accion", pub=pub_id, estado=body.estado, by=admin["email"])
    return {"ok": True, "publicacion": updated}


# ---- Moderación de comercios (alta del agente de campo) ----
@router.get("/moderacion/comercios")
def listar_comercios(
    verificado: bool | None = Query(default=False),
    _admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    items = repo.list_comercios_admin(verificado)
    return {"items": items, "total": len(items)}


@router.post("/moderacion/comercios/{comercio_id}/verificar")
def verificar_comercio(
    comercio_id: str,
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    updated = repo.set_comercio_verificado(comercio_id, True)
    if not updated:
        raise HTTPException(status_code=404, detail="comercio no encontrado")
    logger.info("moderacion.comercio_verificado", comercio=comercio_id, by=admin["email"])
    return {"ok": True, "comercio": updated}


@router.post("/moderacion/comercios/{comercio_id}/rechazar")
def rechazar_comercio(
    comercio_id: str,
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    updated = repo.desactivar_comercio(comercio_id)
    if not updated:
        raise HTTPException(status_code=404, detail="comercio no encontrado")
    logger.info("moderacion.comercio_rechazado", comercio=comercio_id, by=admin["email"])
    return {"ok": True, "comercio": updated}
