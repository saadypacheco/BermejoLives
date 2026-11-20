"""Admin › Platos típicos (docs/home-ciudades.md §15): listar, editar, aprobar y rechazar los platos de cada ciudad.

PERMISO: `contenido` (el del contenido que se publica en el sitio: cotización, videos, redes; lo tienen el admin y
el publicador). Los platos entran `pendiente` por `python -m app.services.importar_gastronomia` y el sitio sólo
muestra `estado = 'aprobado' and activo` (RLS, migración 0202).

No hay DELETE: quitar un plato es `activo = false` (borrado lógico) o `estado = 'rechazado'`.
"""
from __future__ import annotations

import uuid
from typing import Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.auth import require_permiso
from app.db.repository import Repo, get_repo
from app.services.importar_gastronomia import clave_nombre

logger = structlog.get_logger()
router = APIRouter()

MAX_NOMBRE = 120
MAX_DESCRIPCION = 800

Estado = Literal["pendiente", "aprobado", "rechazado"]


class PlatoPatch(BaseModel):
    """Lo que se puede cambiar de un plato. Lo que no viene no se toca."""
    nombre: str | None = Field(default=None, max_length=MAX_NOMBRE)
    descripcion: str | None = Field(default=None, max_length=MAX_DESCRIPCION)
    estado: Estado | None = None
    activo: bool | None = None


def _uuid_o_400(valor: str, etiqueta: str) -> str:
    """El id como uuid; si no lo es, 400 (la base lo rechazaría con un 500)."""
    try:
        return str(uuid.UUID(str(valor)))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=400, detail=f"{etiqueta} no es válido") from None


def _salida(p: dict) -> dict:
    return {k: p.get(k) for k in ("id", "ciudad_id", "tipo", "nombre", "descripcion", "fuente_url", "estado",
                                  "activo", "updated_at")}


@router.get("/admin/platos")
def listar_platos(
    ciudad_id: str | None = Query(default=None, max_length=64),
    estado: Estado | None = None,
    _admin: dict = Depends(require_permiso("contenido")),
    repo: Repo = Depends(get_repo),
) -> list[dict]:
    """Los platos típicos (de todos los estados, activos o no) de una ciudad, por tipo y nombre. `ciudad_id` y
    `estado` filtran; sin ellos salen todos (hasta 1000)."""
    if ciudad_id is not None:
        ciudad_id = _uuid_o_400(ciudad_id, "La ciudad")
    return [_salida(p) for p in repo.list_platos(ciudad_id, estado)]


@router.patch("/admin/platos/{plato_id}")
def editar_plato(
    plato_id: str,
    body: PlatoPatch,
    admin: dict = Depends(require_permiso("contenido")),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Edita el nombre o el texto, aprueba (`estado = 'aprobado'`), rechaza (`'rechazado'`) o da de baja
    (`activo = false`) un plato. Devuelve el plato actualizado. Aprobar exige que el plato tenga texto (el que ya
    tiene o el que viene en el mismo cuerpo): 400 si no. El id tiene que ser un uuid (400 si no)."""
    plato_id = _uuid_o_400(plato_id, "El plato")
    actual = repo.get_plato(plato_id)
    if not actual:
        raise HTTPException(status_code=404, detail="No existe ese plato")
    cambios = body.model_dump(exclude_unset=True)
    if not cambios:
        raise HTTPException(status_code=400, detail="Nada para actualizar")
    patch: dict = {}
    if "nombre" in cambios:
        nombre = " ".join((cambios["nombre"] or "").split())
        if not nombre:
            raise HTTPException(status_code=400, detail="El plato necesita un nombre")
        if clave_nombre(nombre) != clave_nombre(actual["nombre"]):
            otros = {clave_nombre(n) for n in repo.nombres_de_platos(actual["ciudad_id"])}
            if clave_nombre(nombre) in otros:
                raise HTTPException(status_code=409, detail="Ya hay un plato con ese nombre en la ciudad")
        patch["nombre"] = nombre
    if "descripcion" in cambios:
        patch["descripcion"] = " ".join((cambios["descripcion"] or "").split()) or None
    if cambios.get("estado") is not None:
        patch["estado"] = cambios["estado"]
    if cambios.get("activo") is not None:
        patch["activo"] = cambios["activo"]
    if not patch:
        raise HTTPException(status_code=400, detail="Nada para actualizar")
    # Un plato aprobado sale en el sitio: no puede quedar sin texto, ni al aprobarlo ni vaciándole el texto después.
    if patch.get("estado", actual.get("estado")) == "aprobado" and not (
            patch["descripcion"] if "descripcion" in patch else (actual.get("descripcion") or "")):
        raise HTTPException(status_code=400, detail="No se puede aprobar un plato sin texto.")
    try:
        nuevo = repo.update_plato(plato_id, patch)
    except Exception as exc:  # noqa: BLE001
        if "23505" in str(exc) or "duplicate key" in str(exc).lower():      # el único (ciudad_id, nombre)
            raise HTTPException(status_code=409, detail="Ya hay un plato con ese nombre en la ciudad") from exc
        raise
    if not nuevo:
        raise HTTPException(status_code=404, detail="No existe ese plato")
    logger.info("admin.plato_editado", plato=plato_id, campos=sorted(patch), estado=nuevo.get("estado"),
                by=admin["email"])
    return _salida(nuevo)
