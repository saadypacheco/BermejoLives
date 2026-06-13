"""Modo agente de campo: alta rápida de comercios durante el recorrido.

El agente (un colaborador de confianza) carga nombre + celular + rubro +
modalidad, comparte el GPS y saca una foto del local. El comercio entra
'pendiente de verificar' (verificado=false), listo para que un moderador lo
confirme. La foto va a Supabase Storage (bucket público 'comercios').
"""
import secrets
from io import BytesIO

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


_MAX_FOTO_BYTES = 15 * 1024 * 1024  # 15 MB de entrada


def _procesar_imagen(data: bytes) -> bytes:
    """Valida que sea imagen, la reorienta, redimensiona a 1600px y recomprime
    a JPEG 70 (lección KB fotos-resize). Lanza ValueError si no es imagen."""
    from PIL import Image, ImageOps

    img = Image.open(BytesIO(data))
    img.verify()                       # valida que sea una imagen real
    img = Image.open(BytesIO(data))    # reabrir tras verify()
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((1600, 1600))
    out = BytesIO()
    img.save(out, format="JPEG", quality=70, optimize=True)
    return out.getvalue()


def _subir_foto(slug: str, foto: UploadFile, data: bytes) -> str | None:
    """Procesa y sube la foto al bucket público. No bloquea el alta si falla."""
    if len(data) > _MAX_FOTO_BYTES:
        raise HTTPException(status_code=413, detail="La foto supera los 15 MB")
    try:
        procesada = _procesar_imagen(data)
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="El archivo no es una imagen válida")
    try:
        path = f"{slug}/{secrets.token_hex(8)}.jpg"
        get_supabase().storage.from_(settings.comercios_bucket).upload(
            path, procesada, {"content-type": "image/jpeg", "upsert": "true"}
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
