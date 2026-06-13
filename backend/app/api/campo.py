"""Modo agente de campo: alta rápida de comercios durante el recorrido.

El agente (un colaborador de confianza) carga nombre + celular + rubro +
modalidad, comparte el GPS y saca una foto del local. El comercio entra
'pendiente de verificar' (verificado=false), listo para que un moderador lo
confirme. La foto va a Supabase Storage (bucket público 'comercios').
"""
import secrets

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.core import auth
from app.core.config import settings
from app.core.text import slug_unico, slugify
from app.db.repository import Repo, get_repo
from app.db.session import get_supabase
from app.models.schemas import LoginBody

router = APIRouter()
logger = structlog.get_logger()

_MODALIDADES = {"mayorista", "minorista", "ambos"}


@router.post("/auth/campo/login")
def campo_login(body: LoginBody) -> dict:
    if body.email != settings.agente_email or body.password != settings.agente_password:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    return {"access_token": auth.make_agente_token(body.email), "agente": {"email": body.email}}


def _subir_foto(slug: str, foto: UploadFile, data: bytes) -> str | None:
    """Sube la foto al bucket público y devuelve su URL. No bloquea si falla."""
    try:
        path = f"{slug}/{secrets.token_hex(8)}.jpg"
        get_supabase().storage.from_(settings.comercios_bucket).upload(
            path, data, {"content-type": foto.content_type or "image/jpeg", "upsert": "true"}
        )
        return settings.public_photo_url(path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("campo.foto_error", error=str(exc))
        return None


@router.post("/campo/comercio")
async def alta_campo(
    nombre: str = Form(...),
    whatsapp: str = Form(...),
    rubro_slug: str = Form(...),
    modalidad: str = Form("mayorista"),
    direccion: str | None = Form(None),
    descripcion: str | None = Form(None),
    lat: float | None = Form(None),
    lng: float | None = Form(None),
    consentimiento: bool = Form(True),
    foto: UploadFile | None = File(None),
    _agente: dict = Depends(auth.require_agente),
    repo: Repo = Depends(get_repo),
) -> dict:
    if modalidad not in _MODALIDADES:
        raise HTTPException(status_code=400, detail=f"modalidad inválida: {modalidad}")
    if not nombre.strip() or not whatsapp.strip():
        raise HTTPException(status_code=400, detail="Faltan nombre y/o celular")

    slug = slug_unico(repo, slugify(nombre))

    portada_url = None
    if foto is not None:
        data = await foto.read()
        if data:
            portada_url = _subir_foto(slug, foto, data)

    comercio = repo.crear_comercio(
        {
            "slug": slug,
            "nombre": nombre.strip(),
            "descripcion": descripcion,
            "whatsapp": whatsapp.strip(),
            "rubro_id": repo.get_rubro_id(rubro_slug) if rubro_slug else None,
            "ciudad_id": repo.get_ciudad_id("bermejo"),  # el recorrido es en Bermejo
            "modalidad": modalidad,
            "direccion": direccion,
            "lat": lat,
            "lng": lng,
            "portada_url": portada_url,
            "plan": "gratis",
            "confiable": False,
            "verificado": False,         # entra pendiente de verificar
        }
    )
    logger.info("campo.alta", slug=slug, con_foto=bool(portada_url), con_gps=lat is not None,
                consentimiento=consentimiento)
    return {"ok": True, "comercio": {"id": comercio["id"], "nombre": comercio["nombre"], "slug": slug,
                                     "foto": bool(portada_url), "gps": lat is not None}}
