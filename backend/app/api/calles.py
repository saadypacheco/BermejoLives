"""Mapa de calles recorridas (docs/mapa-calles.md): el admin y el agente de campo.

La cuenta de qué calle está recorrida vive en `app/services/calles_mapa.py`; acá sólo están los
endpoints, los permisos y el 404 para el agente que mira una ciudad que no es la suya.
"""
from typing import Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core import auth
from app.core.auth import require_permiso
from app.db.repository import Repo, get_repo
from app.services import calles_mapa

router = APIRouter()
logger = structlog.get_logger()


class ImportarCallesBody(BaseModel):
    ciudad: str = Field(min_length=1, max_length=80)        # slug


class MarcaCalleBody(BaseModel):
    estado: Literal["recorrida", "sin_comercios", "pendiente"]
    nota: str | None = Field(default=None, max_length=200)


def _ciudad_o_404(repo: Repo, slug: str) -> str:
    ciudad_id = repo.get_ciudad_id((slug or "").strip())
    if not ciudad_id:
        raise HTTPException(status_code=404, detail=f"Ciudad no encontrada: {slug}")
    return ciudad_id


def _ciudad_del_agente(repo: Repo, agente: dict) -> str | None:
    """La ciudad que el token del agente trae (la misma regla que `campo._ciudad_del_agente`)."""
    slug = (agente.get("ciudad") or "").strip()
    return repo.get_ciudad_id(slug) if slug else None


# ── admin ────────────────────────────────────────────────────────────────────

@router.post("/admin/calles/importar")
def importar_calles(
    body: ImportarCallesBody,
    admin: dict = Depends(require_permiso("lugares")),
    repo: Repo = Depends(get_repo),
    overpass=Depends(calles_mapa.get_overpass),
) -> dict:
    """Baja las calles de la ciudad de OpenStreetMap y las guarda como tramos. Se puede repetir:
    actualiza por `osm_way_id`, no duplica y no toca las marcas. Responde `{tramos, km}`."""
    ciudad_id = _ciudad_o_404(repo, body.ciudad)
    r = calles_mapa.importar(repo, ciudad_id, repo.get_ciudad(body.ciudad.strip()), overpass)
    logger.info("admin.calles_importadas", ciudad=body.ciudad, tramos=r["tramos"], by=admin.get("email"))
    return r


@router.get("/admin/calles/mapa")
def mapa_admin(
    ciudad: str = Query(min_length=1, max_length=80),
    _mod: dict = Depends(require_permiso("moderar")),
    repo: Repo = Depends(get_repo),
) -> dict:
    """`{tramos, resumen}` de la ciudad, con el estado calculado y la marca manual por encima."""
    return calles_mapa.mapa_de_ciudad(repo, _ciudad_o_404(repo, ciudad))


@router.post("/admin/calles/{tramo_id}/marca")
def marcar_calle_admin(
    tramo_id: str,
    body: MarcaCalleBody,
    mod: dict = Depends(require_permiso("moderar")),
    repo: Repo = Depends(get_repo),
) -> dict:
    tramo = repo.get_calle_tramo(tramo_id)
    if not tramo:
        raise HTTPException(status_code=404, detail="Calle no encontrada")
    marca = calles_mapa.registrar_marca(repo, tramo, body.estado, body.nota, mod.get("email"))
    return {"ok": True, "marca": marca}


# ── agente de campo ──────────────────────────────────────────────────────────

@router.get("/campo/calles")
def calles_del_agente(agente: dict = Depends(auth.require_agente), repo: Repo = Depends(get_repo)) -> dict:
    """Las calles de SU ciudad. Mismo cuerpo que el del admin, pero `quien` y `marca.actor` llevan
    sólo la parte antes de la @. Sin ciudad asignada: sin tramos."""
    ciudad_id = _ciudad_del_agente(repo, agente)
    if not ciudad_id:
        return {"tramos": [], "resumen": {"km_total": 0.0, "km_recorridos": 0.0, "km_sin_comercios": 0.0,
                                          "km_a_recorrer": 0.0, "pct": 0.0}}
    return calles_mapa.vista_agente(calles_mapa.mapa_de_ciudad(repo, ciudad_id))


@router.post("/campo/calles/{tramo_id}/marca")
def marcar_calle_agente(
    tramo_id: str,
    body: MarcaCalleBody,
    agente: dict = Depends(auth.require_agente),
    repo: Repo = Depends(get_repo),
) -> dict:
    """El agente marca un tramo de SU ciudad. De otra ciudad (o inexistente): 404, igual que con los comercios."""
    tramo = repo.get_calle_tramo(tramo_id)
    ciudad_id = _ciudad_del_agente(repo, agente)
    if not tramo or not ciudad_id or tramo.get("ciudad_id") != ciudad_id:
        raise HTTPException(status_code=404, detail="Calle no encontrada")
    marca = calles_mapa.registrar_marca(repo, tramo, body.estado, body.nota, agente.get("email"))
    return {"ok": True, "marca": {**marca, "actor": calles_mapa.antes_de_arroba(marca["actor"])}}
