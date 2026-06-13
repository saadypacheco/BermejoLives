"""Panel del comercio logueado: login, publicar (chatbot) y ver mis publicaciones.

Regla de negocio clave:
  - comercio.confiable = True  -> la publicación se publica DIRECTO (estado='aprobado').
  - comercio.confiable = False -> la publicación va a la cola de moderación.
"""
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException

from app.core import auth
from app.core.text import slug_unico, slugify
from app.db.repository import Repo, get_repo
from app.models.schemas import LoginBody, PublicarBody, RegistroBody

router = APIRouter()
logger = structlog.get_logger()

_TIPOS = {"oferta", "video", "novedad"}
_PLANES = {"gratis", "pro", "premium"}
_MODALIDADES = {"mayorista", "minorista", "ambos"}


@router.post("/auth/comercio/registro")
def comercio_registro(body: RegistroBody, repo: Repo = Depends(get_repo)) -> dict:
    """Alta self-service: crea comercio + cuenta y devuelve sesión (auto-login)."""
    if body.plan not in _PLANES:
        raise HTTPException(status_code=400, detail=f"plan inválido: {body.plan}")
    if body.modalidad not in _MODALIDADES:
        raise HTTPException(status_code=400, detail=f"modalidad inválida: {body.modalidad}")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres")

    if repo.get_comercio_usuario(body.email):
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese email")

    zona_id = repo.get_zona_id(body.zona_slug) if body.zona_slug else None
    rubro_id = repo.get_rubro_id(body.rubro_slug) if body.rubro_slug else None
    slug = slug_unico(repo, slugify(body.nombre))

    comercio = repo.crear_comercio(
        {
            "slug": slug,
            "nombre": body.nombre,
            "descripcion": body.descripcion,
            "whatsapp": body.whatsapp,
            "zona_id": zona_id,
            "rubro_id": rubro_id,
            "ciudad_id": repo.get_ciudad_id("bermejo"),
            "modalidad": body.modalidad,
            "plan": body.plan,
            "confiable": False,            # nuevo comercio NO publica directo hasta ser verificado
            "verificado": False,
        }
    )
    repo.crear_comercio_usuario(
        {
            "comercio_id": comercio["id"],
            "email": body.email,
            "password_hash": auth.hash_password(body.password),
            "nombre": body.nombre,
        }
    )

    token = auth.make_comercio_token(comercio["id"], body.email)
    logger.info("comercio.registro", slug=slug, plan=body.plan)
    return {
        "access_token": token,
        "comercio": {
            "id": comercio["id"],
            "nombre": comercio["nombre"],
            "slug": comercio["slug"],
            "confiable": False,
            "plan": body.plan,
        },
        # pro/premium quedan registrados pero el cobro real es F-007 (pagos).
        "pago_pendiente": body.plan != "gratis",
    }


@router.post("/auth/comercio/login")
def comercio_login(body: LoginBody, repo: Repo = Depends(get_repo)) -> dict:
    user = repo.get_comercio_usuario(body.email)
    if not user or not auth.verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    comercio = repo.get_comercio(user["comercio_id"])
    token = auth.make_comercio_token(user["comercio_id"], body.email)
    return {
        "access_token": token,
        "comercio": {
            "id": comercio["id"],
            "nombre": comercio["nombre"],
            "slug": comercio["slug"],
            "confiable": comercio.get("confiable", False),
        },
    }


@router.get("/comercio/mis-publicaciones")
def mis_publicaciones(
    claims: dict = Depends(auth.require_comercio), repo: Repo = Depends(get_repo)
) -> dict:
    items = repo.list_publicaciones_de_comercio(claims["comercio_id"])
    return {"items": items, "total": len(items)}


@router.post("/comercio/publicar")
def publicar(
    body: PublicarBody,
    claims: dict = Depends(auth.require_comercio),
    repo: Repo = Depends(get_repo),
) -> dict:
    if body.tipo not in _TIPOS:
        raise HTTPException(status_code=400, detail=f"tipo inválido: {body.tipo}")

    comercio = repo.get_comercio(claims["comercio_id"])
    if not comercio:
        raise HTTPException(status_code=404, detail="comercio no encontrado")

    confiable = bool(comercio.get("confiable"))
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "comercio_id": comercio["id"],
        "tipo": body.tipo,
        "titulo": body.titulo,
        "descripcion": body.descripcion,
        "precio": body.precio,
        "moneda": body.moneda,
        "imagen_url": body.imagen_url,
        "tiktok_url": body.tiktok_url,
        "origen": "panel",
        "estado": "aprobado" if confiable else "pendiente",
        "approved_at": now if confiable else None,
        "moderado_por": "auto-confiable" if confiable else None,
        "moderado_at": now if confiable else None,
    }
    pub = repo.insert_publicacion_directa(row)
    logger.info("comercio.publicar", comercio=comercio["slug"], estado=row["estado"], confiable=confiable)
    return {
        "ok": True,
        "estado": row["estado"],
        "publicado_directo": confiable,
        "publicacion": pub,
    }
