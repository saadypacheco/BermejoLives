"""Uruku Ayuda por HTTP: la pregunta entra, la respuesta sale, y todo queda anotado.

Público:  POST /asistente/preguntar · POST /asistente/{id}/util
Admin:    lo que la gente preguntó al asistente del SITIO y no tuvo respuesta, y el saber
          local. Aparte, /admin/asistente/respuestas-locales: lo que cargaron los
          comercios (salen directo, sin moderación; acá se leen y se desactivan).
Comercio: GET /comercio/asistente/preguntas — las de SUS clientes (Nivel 3 = el dueño).
          /comercio/asistente/respuestas — las respuestas que carga para SU chatbot
          (filas de saber_local con su comercio_id; docs/chatbot-comercios.md).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, StringConstraints

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
    # La IA del chatbot de un local es otra función de plan (Pro): sin ella, el
    # Destacado contesta sólo con la base y nunca llama a Gemini.
    con_ia = bool(comercio) and planes.funcion(planes.plan_de(repo, comercio), "asistente_ia")
    r = asistente.responder(repo, body.pregunta, comercio=comercio, con_ia=con_ia,
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
        # Sólo con chatbot de comercio, sin respuesta y con WhatsApp cargado.
        "derivar": r.derivar,
    }


def _es_uuid(valor: str | None) -> bool:
    """Los ids de la base son uuid: uno que no lo es no existe, y mandárselo a
    Postgres da un error 500 en vez de un 404."""
    try:
        uuid.UUID(str(valor))
    except ValueError:
        return False
    return True


@router.post("/asistente/{conversacion_id}/util")
def marcar_util(conversacion_id: str, body: UtilIn, repo: Repo = Depends(get_repo)) -> dict:
    if not _es_uuid(conversacion_id):
        raise HTTPException(status_code=404, detail="No existe")
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
    # Sólo lo que le preguntaron al asistente del SITIO: las de la ficha de un
    # local las contesta su dueño desde su cuenta, no el admin de URUKU.
    return {"items": repo.list_conversaciones(filtro, limite, solo_sitio=True)}


@router.post("/admin/asistente/conversaciones/{conversacion_id}/responder")
def admin_responder(conversacion_id: str, body: ResponderIn,
                    admin: dict = Depends(auth.require_permiso("ayuda")), repo: Repo = Depends(get_repo)) -> dict:
    conv = repo.get_conversacion(conversacion_id) if _es_uuid(conversacion_id) else None
    if not conv:
        raise HTTPException(status_code=404, detail="No existe esa pregunta")
    if conv.get("comercio_id"):
        # Si se guardara, pasaría a ser saber del SITIO con una pregunta de un
        # cliente de un local (y la respuesta del admin no sería la del dueño).
        raise HTTPException(status_code=409, detail="Esa pregunta la contesta el comercio desde su cuenta")
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
        _saber_del_sitio_o_404(repo, body.id)
        row["id"] = body.id
    return {"item": repo.upsert_saber_local(row)}


@router.delete("/admin/asistente/saber/{saber_id}")
def admin_saber_borrar(saber_id: str, _: dict = Depends(auth.require_permiso("ayuda")),
                       repo: Repo = Depends(get_repo)) -> dict:
    _saber_del_sitio_o_404(repo, saber_id)
    repo.borrar_saber_local(saber_id)
    return {"ok": True}


def _saber_del_sitio_o_404(repo: Repo, saber_id: str) -> dict:
    """Una fila del saber de URUKU (comercio_id NULL). Una respuesta de un
    local no se edita ni se borra desde acá: es del dueño, y el admin sólo la
    puede desactivar (respuestas-locales)."""
    fila = repo.get_saber_local(saber_id) if _es_uuid(saber_id) else None
    if not fila or fila.get("comercio_id"):
        raise HTTPException(status_code=404, detail="No existe ese saber")
    return fila


# Las respuestas de los locales, para que URUKU las lea y apague una que no
# corresponda. Salen directo, sin moderación previa (decisión del 5/10/2026):
# esta vista es el control a posteriori.

class ActivoIn(BaseModel):
    activo: bool


def _item_respuesta_admin(s: dict) -> dict:
    return {k: s.get(k) for k in ("id", "comercio_id", "comercio_nombre", "comercio_slug",
                                  "pregunta", "respuesta", "activo", "updated_at")}


@router.get("/admin/asistente/respuestas-locales")
def admin_respuestas_locales(q: str | None = Query(None, max_length=100), limite: int = Query(200, ge=1, le=500),
                             _: dict = Depends(auth.require_permiso("ayuda")), repo: Repo = Depends(get_repo)) -> dict:
    return {"items": [_item_respuesta_admin(s) for s in repo.list_respuestas_locales(q, limite)]}


@router.post("/admin/asistente/respuestas-locales/{respuesta_id}/activo")
def admin_respuesta_local_activo(respuesta_id: str, body: ActivoIn, admin: dict = Depends(auth.require_permiso("ayuda")),
                                 repo: Repo = Depends(get_repo)) -> dict:
    fila = repo.get_saber_local(respuesta_id) if _es_uuid(respuesta_id) else None
    if not fila or not fila.get("comercio_id"):
        raise HTTPException(status_code=404, detail="No existe esa respuesta")
    nueva = repo.upsert_saber_local({"id": fila["id"], "activo": body.activo})
    logger.info("asistente.respuesta_local_activo", respuesta=fila["id"], comercio=fila["comercio_id"],
                activo=body.activo, por=admin.get("email"))
    comercio = repo.get_comercio(fila["comercio_id"]) or {}
    return {"item": _item_respuesta_admin({**fila, **nueva, "comercio_nombre": comercio.get("nombre"),
                                           "comercio_slug": comercio.get("slug")})}


# ------------------------------------------------------------------ el dueño del local

@router.get("/comercio/asistente/preguntas")
def preguntas_de_mi_comercio(claims: dict = Depends(auth.require_comercio),
                             repo: Repo = Depends(get_repo)) -> dict:
    """Lo que los clientes le preguntaron al asistente de SU local. Las que
    quedaron sin respuesta son las que el dueño tiene que mirar: son ventas
    que el asistente no pudo cerrar."""
    items = repo.list_conversaciones(f"comercio:{claims['comercio_id']}", 200)
    # Una que el dueño ya contestó (resuelta_en) deja de contar como pendiente.
    return {"items": items,
            "sin_respuesta": len([i for i in items if i.get("sin_respuesta") and not i.get("resuelta_en")])}


# Las respuestas del local (0136). Siempre del comercio del TOKEN: el
# `comercio_id` nunca se acepta del body ni de la URL. Una respuesta de otro
# comercio es un 404, no un 403: no se confirma que exista.
MAX_RESPUESTAS_LOCAL = 200   # activas por comercio; el chatbot las lee todas
_Pregunta = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=300)]
_Respuesta = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=2000)]


class RespuestaLocalCreate(BaseModel):
    pregunta: _Pregunta
    respuesta: _Respuesta
    # Una pregunta de SUS clientes que quedó sin respuesta: al contestarla se
    # marca resuelta y deja de pedirle atención al dueño.
    conversacion_id: str | None = None


class RespuestaLocalUpdate(BaseModel):
    pregunta: _Pregunta | None = None
    respuesta: _Respuesta | None = None


def _item_respuesta(s: dict) -> dict:
    return {"id": s["id"], "pregunta": s.get("pregunta"), "respuesta": s.get("respuesta"),
            "updated_at": s.get("updated_at")}


@router.get("/comercio/asistente/respuestas")
def respuestas_de_mi_comercio(limite: int = Query(200, ge=1, le=500), desde: int = Query(0, ge=0),
                              claims: dict = Depends(auth.require_comercio),
                              repo: Repo = Depends(get_repo)) -> dict:
    """Las respuestas ACTIVAS que el dueño cargó para su chatbot."""
    filas = repo.list_respuestas_comercio(claims["comercio_id"], limite, desde)
    return {"items": [_item_respuesta(s) for s in filas]}


@router.post("/comercio/asistente/respuestas")
def crear_respuesta_de_mi_comercio(body: RespuestaLocalCreate, claims: dict = Depends(auth.require_comercio),
                                   repo: Repo = Depends(get_repo)) -> dict:
    comercio_id = claims["comercio_id"]
    conv = None
    if body.conversacion_id:
        conv = repo.get_conversacion(body.conversacion_id) if _es_uuid(body.conversacion_id) else None
        # Una conversación de otro comercio (o del sitio) no existe para este dueño.
        if not conv or conv.get("comercio_id") != comercio_id:
            raise HTTPException(status_code=404, detail="No existe esa pregunta")
    if repo.contar_respuestas_comercio(comercio_id) >= MAX_RESPUESTAS_LOCAL:
        raise HTTPException(status_code=409, detail=f"Llegaste al máximo de {MAX_RESPUESTAS_LOCAL} respuestas. "
                                                    "Borrá alguna que ya no uses para cargar otra.")
    fila = repo.upsert_saber_local({
        "pregunta": body.pregunta, "respuesta": body.respuesta, "etiquetas": [], "activo": True,
        "comercio_id": comercio_id,
        # Nunca el email del dueño: `creado_por` no es dato del público ni del admin.
        "creado_por": f"comercio:{comercio_id}",
    })
    if conv:
        repo.marcar_conversacion(conv["id"], {"resuelta_en": datetime.now(timezone.utc).isoformat()})
    logger.info("asistente.respuesta_local_creada", comercio=comercio_id, desde_conversacion=bool(conv))
    return {"item": _item_respuesta(fila)}


@router.put("/comercio/asistente/respuestas/{respuesta_id}")
def editar_respuesta_de_mi_comercio(respuesta_id: str, body: RespuestaLocalUpdate,
                                    claims: dict = Depends(auth.require_comercio),
                                    repo: Repo = Depends(get_repo)) -> dict:
    actual = repo.get_respuesta_comercio(claims["comercio_id"], respuesta_id) if _es_uuid(respuesta_id) else None
    if not actual:
        raise HTTPException(status_code=404, detail="No existe esa respuesta")
    cambios = body.model_dump(exclude_none=True)
    if not cambios:
        raise HTTPException(status_code=400, detail="No hay nada para cambiar")
    fila = repo.upsert_saber_local({"id": actual["id"], **cambios})
    return {"item": _item_respuesta(fila)}


@router.delete("/comercio/asistente/respuestas/{respuesta_id}")
def borrar_respuesta_de_mi_comercio(respuesta_id: str, claims: dict = Depends(auth.require_comercio),
                                    repo: Repo = Depends(get_repo)) -> dict:
    """Soft-delete: `activo = false`. La fila queda en la base."""
    actual = repo.get_respuesta_comercio(claims["comercio_id"], respuesta_id) if _es_uuid(respuesta_id) else None
    if not actual:
        raise HTTPException(status_code=404, detail="No existe esa respuesta")
    repo.upsert_saber_local({"id": actual["id"], "activo": False})
    return {"ok": True}
