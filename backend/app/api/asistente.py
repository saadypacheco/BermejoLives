"""Uruku Ayuda por HTTP: la pregunta entra, la respuesta sale, y todo queda anotado.

Público:  POST /asistente/preguntar · POST /asistente/{id}/util
Admin:    lo que la gente preguntó y no tuvo respuesta, y el saber local.
Comercio: GET /comercio/asistente/preguntas — las de SUS clientes (Nivel 3 = el dueño).
"""
from __future__ import annotations

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core import auth
from app.core.config import settings
from app.db.repository import Repo, get_repo
from app.services import asistente, planes

logger = structlog.get_logger()
router = APIRouter()


class PreguntaIn(BaseModel):
    pregunta: str = Field(min_length=1, max_length=500)
    sesion: str = Field(min_length=6, max_length=80)
    comercio_id: str | None = None
    # La ciudad elegida en el sitio (slug). Sin ella, Bermejo.
    ciudad: str | None = None


class UtilIn(BaseModel):
    util: bool


def _comercio_con_asistente(repo: Repo, comercio_id: str) -> dict:
    """El comercio, si existe y su plan incluye el asistente. La función del
    plan es la puerta: no hay otra lista de quién puede."""
    c = repo.get_comercio(comercio_id)
    if not c or not c.get("activo", True):
        raise HTTPException(status_code=404, detail="Ese comercio no está en URUKU")
    if not planes.funcion(planes.plan_de(repo, c), "asistente_24_7"):
        raise HTTPException(status_code=403, detail="Este negocio no tiene el asistente activo")
    return c


@router.post("/asistente/preguntar")
def preguntar(body: PreguntaIn, repo: Repo = Depends(get_repo)) -> dict:
    if not settings.asistente_activo:
        raise HTTPException(status_code=503, detail="El asistente está apagado por ahora")
    if repo.contar_conversaciones_sesion_hoy(body.sesion) >= settings.asistente_max_por_sesion_dia:
        raise HTTPException(status_code=429, detail="Llegaste al máximo de preguntas por hoy. Mañana seguimos.")

    comercio = _comercio_con_asistente(repo, body.comercio_id) if body.comercio_id else None
    ciudad = repo.get_ciudad(body.ciudad) if body.ciudad else None
    r = asistente.responder(repo, body.pregunta, comercio=comercio,
                            ciudad={"slug": ciudad["slug"], "nombre": ciudad.get("nombre"),
                                    "guia_activa": ciudad.get("guia_activa", False),
                                    "paso_nombre": ciudad.get("paso_nombre")} if ciudad else None)
    fila = repo.insert_conversacion({
        "sesion": body.sesion,
        "canal": "ficha" if comercio else "sitio",
        "comercio_id": comercio["id"] if comercio else None,
        "pregunta": body.pregunta.strip(),
        "respuesta": r.texto,
        "nivel": r.nivel,
        "intent": r.intent,
        "fuentes": r.fuentes,
        "sin_respuesta": r.sin_respuesta,
    })
    logger.info("asistente.pregunta", nivel=r.nivel, intent=r.intent, sin_respuesta=r.sin_respuesta,
                comercio=comercio["id"] if comercio else None)
    return {
        "id": fila["id"], "texto": r.texto, "nivel": r.nivel, "intent": r.intent,
        "fuentes": r.fuentes, "sugerencias": r.sugerencias, "sin_respuesta": r.sin_respuesta,
    }


@router.post("/asistente/{conversacion_id}/util")
def marcar_util(conversacion_id: str, body: UtilIn, repo: Repo = Depends(get_repo)) -> dict:
    fila = repo.marcar_conversacion(conversacion_id, {"util": body.util})
    if not fila:
        raise HTTPException(status_code=404, detail="No existe")
    return {"ok": True}


# ------------------------------------------------------------------ admin

SECCIONES = ("aduana", "documentos", "frontera", "comercios", "transporte", "seguridad", "conectividad", "general")


class SaberIn(BaseModel):
    id: str | None = None
    pregunta: str = Field(min_length=3, max_length=300)
    respuesta: str = Field(min_length=3, max_length=2000)
    etiquetas: list[str] = Field(default_factory=list)
    seccion: str = "general"
    activo: bool = True
    # De qué frontera es esto. Vacío = vale para todas (la aduana boliviana,
    # cómo funciona URUKU). Con ciudad, es de esa ciudad (0124).
    ciudad: str | None = None


class ResponderIn(BaseModel):
    respuesta: str = Field(min_length=3, max_length=2000)
    etiquetas: list[str] = Field(default_factory=list)
    seccion: str = "general"
    ciudad: str | None = None
    # Por defecto la respuesta se guarda como saber local, que es el sentido
    # de contestar: que la próxima vez no haga falta. Se puede no guardar.
    guardar: bool = True


def _etiquetas(lista: list[str]) -> list[str]:
    return sorted({e.strip().lower() for e in lista if e and e.strip()})[:20]


@router.get("/admin/asistente/conversaciones")
def admin_conversaciones(filtro: str = "sin_respuesta", limite: int = 100,
                         _: dict = Depends(auth.require_permiso("ayuda")), repo: Repo = Depends(get_repo)) -> dict:
    if filtro not in ("sin_respuesta", "todas"):
        filtro = "sin_respuesta"
    return {"items": repo.list_conversaciones(filtro, limite)}


@router.post("/admin/asistente/conversaciones/{conversacion_id}/responder")
def admin_responder(conversacion_id: str, body: ResponderIn,
                    admin: dict = Depends(auth.require_permiso("ayuda")), repo: Repo = Depends(get_repo)) -> dict:
    conv = next((c for c in repo.list_conversaciones("todas", 500) if c["id"] == conversacion_id), None)
    if not conv:
        raise HTTPException(status_code=404, detail="No existe esa pregunta")
    saber = None
    if body.guardar:
        saber = repo.upsert_saber_local({
            "pregunta": conv["pregunta"], "respuesta": body.respuesta.strip(),
            "etiquetas": _etiquetas(body.etiquetas), "activo": True,
            "seccion": body.seccion if body.seccion in SECCIONES else "general",
            "ciudad_id": repo.get_ciudad_id(body.ciudad) if body.ciudad else None,
            "creado_por": admin.get("email") or "admin",
        })
    repo.marcar_conversacion(conversacion_id, {"resuelta_en": datetime.now(timezone.utc).isoformat()})
    return {"ok": True, "saber": saber}


@router.get("/admin/asistente/saber")
def admin_saber(_: dict = Depends(auth.require_permiso("ayuda")), repo: Repo = Depends(get_repo)) -> dict:
    return {"items": repo.list_saber_local(False)}


@router.post("/admin/asistente/saber")
def admin_saber_guardar(body: SaberIn, admin: dict = Depends(auth.require_permiso("ayuda")),
                        repo: Repo = Depends(get_repo)) -> dict:
    row = {"pregunta": body.pregunta.strip(), "respuesta": body.respuesta.strip(),
           "etiquetas": _etiquetas(body.etiquetas), "activo": body.activo,
           "seccion": body.seccion if body.seccion in SECCIONES else "general",
           "ciudad_id": repo.get_ciudad_id(body.ciudad) if body.ciudad else None,
           "creado_por": admin.get("email") or "admin"}
    if body.id:
        row["id"] = body.id
    return {"item": repo.upsert_saber_local(row)}


@router.delete("/admin/asistente/saber/{saber_id}")
def admin_saber_borrar(saber_id: str, _: dict = Depends(auth.require_permiso("ayuda")),
                       repo: Repo = Depends(get_repo)) -> dict:
    repo.borrar_saber_local(saber_id)
    return {"ok": True}


# ------------------------------------------------------------------ el dueño del local

@router.get("/comercio/asistente/preguntas")
def preguntas_de_mi_comercio(claims: dict = Depends(auth.require_comercio),
                             repo: Repo = Depends(get_repo)) -> dict:
    """Lo que los clientes le preguntaron al asistente de SU local. Las que
    quedaron sin respuesta son las que el dueño tiene que mirar: son ventas
    que el asistente no pudo cerrar."""
    items = repo.list_conversaciones(f"comercio:{claims['comercio_id']}", 200)
    return {"items": items, "sin_respuesta": len([i for i in items if i.get("sin_respuesta")])}
