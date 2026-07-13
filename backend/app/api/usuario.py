"""Cuenta liviana del comprador/visitante: solo celular + código por WhatsApp,
sin contraseña. Objetivo único: capturar el número con consentimiento para
avisos/ofertas, y permitir guardar comercios favoritos desde cualquier
dispositivo. No tiene nada que ver con las cuentas de comercio."""
import secrets
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core import auth
from app.core.config import settings
from app.db.repository import Repo, get_repo

router = APIRouter()
logger = structlog.get_logger()


class SolicitarCodigoBody(BaseModel):
    whatsapp: str


@router.post("/auth/usuario/solicitar-codigo")
def solicitar_codigo(body: SolicitarCodigoBody, repo: Repo = Depends(get_repo)) -> dict:
    """Crea el usuario si no existe (alta progresiva) y genera un código para
    que lo confirme mandando un WhatsApp entrante (no lo mandamos nosotros —
    ver docs/pendientes.md sección 0, evita riesgo de ban por envío saliente)."""
    if not body.whatsapp.strip():
        raise HTTPException(status_code=400, detail="Falta el número de WhatsApp")
    usuario = repo.get_usuario_por_whatsapp(body.whatsapp) or repo.crear_usuario(body.whatsapp)
    code = f"{secrets.randbelow(1_000_000):06d}"
    expira = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
    repo.set_reset_code_usuario(usuario["id"], code, expira)
    logger.info("usuario.solicitar_codigo", whatsapp=body.whatsapp)
    return {"ok": True, "codigo": code, "wa_link": settings.wa_link_confirmar(code)}


class VerificarBody(BaseModel):
    whatsapp: str
    codigo: str


@router.post("/auth/usuario/verificar")
def verificar(body: VerificarBody, repo: Repo = Depends(get_repo)) -> dict:
    """El frontend pollea esto después de mostrar el botón "Confirmar por
    WhatsApp" — falla con 400 hasta que el webhook marque el código como
    confirmado (mensaje entrante real), no alcanza con que el código matchee."""
    usuario = repo.get_usuario_por_whatsapp(body.whatsapp)
    if not usuario or not usuario.get("reset_code") or usuario["reset_code"] != body.codigo:
        raise HTTPException(status_code=400, detail="Código incorrecto")
    expira = usuario.get("reset_code_expira")
    if not expira or datetime.fromisoformat(expira) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="El código venció, pedí uno nuevo")
    if not usuario.get("reset_code_confirmado_at"):
        raise HTTPException(status_code=400, detail="Todavía no confirmaste por WhatsApp")
    repo.set_reset_code_usuario(usuario["id"], None, None)
    token = auth.make_usuario_token(usuario["id"], usuario["whatsapp"])
    logger.info("usuario.verificado", whatsapp=body.whatsapp)
    return {"access_token": token, "usuario": {"id": usuario["id"], "whatsapp": usuario["whatsapp"]}}


@router.get("/usuario/favoritos")
def listar_favoritos(claims: dict = Depends(auth.require_usuario), repo: Repo = Depends(get_repo)) -> dict:
    items = repo.list_favoritos(claims["usuario_id"])
    return {"items": [i["comercios"] for i in items if i.get("comercios")]}


class FavoritoBody(BaseModel):
    comercio_id: str


@router.post("/usuario/favoritos")
def agregar_favorito(body: FavoritoBody, claims: dict = Depends(auth.require_usuario), repo: Repo = Depends(get_repo)) -> dict:
    repo.agregar_favorito(claims["usuario_id"], body.comercio_id)
    return {"ok": True}


@router.delete("/usuario/favoritos/{comercio_id}")
def quitar_favorito(comercio_id: str, claims: dict = Depends(auth.require_usuario), repo: Repo = Depends(get_repo)) -> dict:
    repo.quitar_favorito(claims["usuario_id"], comercio_id)
    return {"ok": True}
