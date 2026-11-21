"""Fotos con estilo URUKU: la ventana «Fotos» de Admin › Comercios (docs/fotos-estilo-uruku.md §5).

Permiso `comercios.editar` (el uso de Gemini, `pagos`). Los endpoints de la PORTADA (`.../portada-diseno`) siguen en
`api/moderacion.py`; acá van el estado de la ventana, la galería y el resumen de usos.

    GET    /admin/comercio/{id}/fotos-estilo                          estado de la ventana (`PhotoStyleState`)
    POST   /admin/comercio/{id}/fotos/{foto_id}/diseno                {"method": "free" | "gemini"} -> propuesta
    POST   /admin/comercio/{id}/fotos/{foto_id}/diseno/externa        multipart `foto` -> propuesta
    PUT    /admin/comercio/{id}/fotos/{foto_id}/diseno                usar en la ficha
    DELETE /admin/comercio/{id}/fotos/{foto_id}/diseno/propuesta      descartar
    DELETE /admin/comercio/{id}/fotos/{foto_id}/diseno                volver a la original
    GET    /admin/fotos-estilo/usos?desde=&hasta=                     lo gastado con IA (`pagos`)

Todo lo que se arma corre en el threadpool y toma el lock de `fotos_estilo` (una transformación a la vez).
"""
from __future__ import annotations

from typing import Literal

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.core.auth import require_permiso
from app.db.content_repository import ContentRepo, get_content_repo
from app.db.repository import Repo, get_repo
from app.services import fotos_estilo

router = APIRouter()
logger = structlog.get_logger()

class DisenoBody(BaseModel):
    """Cuerpo de `POST .../diseno`: por qué camino se arma."""
    method: Literal["free", "gemini"] = "free"


def _comercio_o_404(repo: Repo, comercio_id: str) -> dict:
    comercio = repo.get_comercio(comercio_id)
    if not comercio:
        raise HTTPException(status_code=404, detail="Comercio no encontrado")
    return comercio


def _http(exc: fotos_estilo.EstiloError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=exc.detail)


@router.get("/admin/comercio/{comercio_id}/fotos-estilo")
def admin_fotos_estilo(
    comercio_id: str,
    _mod: dict = Depends(require_permiso("comercios.editar")),
    repo: Repo = Depends(get_repo),
    crepo: ContentRepo = Depends(get_content_repo),
) -> dict:
    """Lo que necesita la ventana «Fotos»: la portada, la galería, si la IA se puede usar, lo gastado y las instrucciones."""
    return fotos_estilo.estado(repo, crepo, _comercio_o_404(repo, comercio_id))


@router.post("/admin/comercio/{comercio_id}/fotos/{foto_id}/diseno")
async def admin_armar_diseno_foto(
    comercio_id: str,
    foto_id: str,
    body: DisenoBody | None = None,
    mod: dict = Depends(require_permiso("comercios.editar")),
    repo: Repo = Depends(get_repo),
    crepo: ContentRepo = Depends(get_content_repo),
) -> dict:
    """Arma el diseño de una foto de la galería y lo deja como PROPUESTA (privada hasta «Usar en la ficha»)."""
    comercio = _comercio_o_404(repo, comercio_id)
    try:
        return await run_in_threadpool(fotos_estilo.proponer_galeria, repo, crepo, comercio, foto_id,
                                       metodo=body.method if body else "free", externa=None, actor=mod["email"])
    except fotos_estilo.EstiloError as exc:
        raise _http(exc) from exc


@router.post("/admin/comercio/{comercio_id}/fotos/{foto_id}/diseno/externa")
async def admin_armar_diseno_foto_externa(
    comercio_id: str,
    foto_id: str,
    foto: UploadFile = File(...),
    mod: dict = Depends(require_permiso("comercios.editar")),
    repo: Repo = Depends(get_repo),
    crepo: ContentRepo = Depends(get_content_repo),
) -> dict:
    """El diseño de una foto de la galería a partir de una imagen hecha afuera (ChatGPT)."""
    comercio = _comercio_o_404(repo, comercio_id)
    try:
        data = await fotos_estilo.leer_subida(foto)
        return await run_in_threadpool(fotos_estilo.proponer_galeria, repo, crepo, comercio, foto_id,
                                       metodo="external", externa=data, actor=mod["email"])
    except fotos_estilo.EstiloError as exc:
        raise _http(exc) from exc


@router.put("/admin/comercio/{comercio_id}/fotos/{foto_id}/diseno")
def admin_usar_diseno_foto(
    comercio_id: str,
    foto_id: str,
    mod: dict = Depends(require_permiso("comercios.editar")),
    repo: Repo = Depends(get_repo),
) -> dict:
    """«Usar en la ficha»: la propuesta pasa a ser el diseño público de la foto."""
    comercio = _comercio_o_404(repo, comercio_id)
    try:
        return fotos_estilo.usar_diseno(repo, comercio, foto_id, actor=mod["email"])
    except fotos_estilo.EstiloError as exc:
        raise _http(exc) from exc


@router.delete("/admin/comercio/{comercio_id}/fotos/{foto_id}/diseno/propuesta")
def admin_descartar_propuesta_foto(
    comercio_id: str,
    foto_id: str,
    mod: dict = Depends(require_permiso("comercios.editar")),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Descarta la propuesta (no toca el diseño vigente)."""
    comercio = _comercio_o_404(repo, comercio_id)
    try:
        return fotos_estilo.descartar_propuesta(repo, comercio, foto_id, actor=mod["email"])
    except fotos_estilo.EstiloError as exc:
        raise _http(exc) from exc


@router.delete("/admin/comercio/{comercio_id}/fotos/{foto_id}/diseno")
def admin_quitar_diseno_foto(
    comercio_id: str,
    foto_id: str,
    mod: dict = Depends(require_permiso("comercios.editar")),
    repo: Repo = Depends(get_repo),
) -> dict:
    """«Volver a la original»: la ficha deja de usar el diseño de esta foto. La foto original no se toca."""
    comercio = _comercio_o_404(repo, comercio_id)
    try:
        return fotos_estilo.volver_a_la_original(repo, comercio, foto_id, actor=mod["email"])
    except fotos_estilo.EstiloError as exc:
        raise _http(exc) from exc


@router.get("/admin/fotos-estilo/usos")
def admin_usos_fotos_estilo(
    desde: str | None = Query(None, description="AAAA-MM-DD (día de Bolivia); por defecto el 1 del mes"),
    hasta: str | None = Query(None, description="AAAA-MM-DD (día de Bolivia); por defecto hoy"),
    _mod: dict = Depends(require_permiso("pagos")),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Lo gastado con Gemini entre dos fechas (inclusive), en total y por comercio (`UsesSummary`)."""
    try:
        return fotos_estilo.resumen_usos(repo, desde, hasta)
    except fotos_estilo.EstiloError as exc:
        raise _http(exc) from exc
