"""Modo agente de campo: alta rápida de comercios durante el recorrido.

El agente (un colaborador de confianza) carga nombre + celular + rubro +
modalidad, comparte el GPS y saca una foto del local. El comercio entra
'pendiente de verificar' (verificado=false), listo para que un moderador lo
confirme. La foto va a Supabase Storage (bucket público 'comercios').
"""
import secrets
from io import BytesIO

import httpx
import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.core import auth
from app.core.config import settings
from app.core.text import slug_unico, slugify
from app.db.repository import Repo, get_repo
from app.db.session import get_supabase
from app.models.schemas import LoginBody
from app.services.clasificador import sugerir_rubros

router = APIRouter()
logger = structlog.get_logger()

_MODALIDADES = {"mayorista", "minorista", "ambos"}
_TIPOS_LEAD  = {"whatsapp", "telefono", "email", "web"}


@router.post("/auth/campo/login")
def campo_login(body: LoginBody) -> dict:
    if body.email != settings.agente_email or body.password != settings.agente_password:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    return {"access_token": auth.make_agente_token(body.email), "agente": {"email": body.email}}


@router.post("/campo/transcribir")
async def transcribir(
    audio: UploadFile = File(...),
    _agente: dict = Depends(auth.require_agente),
) -> dict:
    """Audio del '¿qué vende?' → texto. OpenAI si hay key; si no, faster-whisper local."""
    data = await audio.read()
    if not data:
        raise HTTPException(status_code=400, detail="Audio vacío")
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio demasiado largo")

    # Self-hosted (gratis) cuando no hay key de OpenAI
    if not settings.openai_api_key:
        from starlette.concurrency import run_in_threadpool
        from app.services.transcription import transcribir_local
        try:
            texto = await run_in_threadpool(transcribir_local, data)
        except Exception as exc:  # noqa: BLE001
            logger.warning("transcribir.local_error", error=str(exc))
            raise HTTPException(status_code=502, detail="No se pudo transcribir") from exc
        return {"texto": texto}

    # OpenAI Whisper API
    files = {"file": (audio.filename or "audio.webm", data, audio.content_type or "audio/webm")}
    form = {"model": "whisper-1", "language": "es"}
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                data=form, files=files,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("transcribir.error", error=str(exc))
        raise HTTPException(status_code=502, detail="No se pudo transcribir") from exc
    if r.status_code != 200:
        logger.warning("transcribir.api", status=r.status_code, body=r.text[:200])
        raise HTTPException(status_code=502, detail="No se pudo transcribir")
    return {"texto": (r.json().get("text") or "").strip()}


class SugerirRubrosBody(BaseModel):
    descripcion: str
    rubros: list[dict]


@router.post("/campo/sugerir-rubros")
def campo_sugerir_rubros(body: SugerirRubrosBody, _agente: dict = Depends(auth.require_agente)) -> dict:
    """A partir del audio transcripto (o texto escrito), sugiere rubros para
    que el agente no tenga que elegirlos a mano."""
    return {"rubro_slugs": sugerir_rubros(body.descripcion, body.rubros)}


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
    ciudad_slug: str = Form("bermejo"),           # ciudad donde está el negocio
    rubro_slugs: list[str] = Form(default=[]),    # uno o varios rubros
    modalidad: str = Form("mayorista"),
    direccion: str | None = Form(None),
    descripcion: str | None = Form(None),
    email: str | None = Form(None),
    tiktok_url: str | None = Form(None),
    facebook_url: str | None = Form(None),
    instagram_url: str | None = Form(None),
    sitio_web: str | None = Form(None),
    video_url: str | None = Form(None),
    lat: float | None = Form(None),
    lng: float | None = Form(None),
    consentimiento: bool = Form(True),
    # Campos del diferencial fronterizo
    monedas_aceptadas: list[str] = Form(default=[]),
    envios_internacionales: bool = Form(False),
    origen_importacion: list[str] = Form(default=[]),
    pedido_minimo: str | None = Form(None),
    tiene_factura: bool = Form(False),
    horario: str | None = Form(None),
    tiene_stock: bool = Form(True),
    foto: UploadFile = File(...),
    agente: dict = Depends(auth.require_agente),
    repo: Repo = Depends(get_repo),
) -> dict:
    if modalidad not in _MODALIDADES:
        raise HTTPException(status_code=400, detail=f"modalidad inválida: {modalidad}")
    if not nombre.strip() or not whatsapp.strip():
        raise HTTPException(status_code=400, detail="Faltan nombre y/o celular")
    if not descripcion or not descripcion.strip():
        raise HTTPException(status_code=400, detail="Falta la descripción (audio o texto) de qué vende")
    if lat is None or lng is None:
        raise HTTPException(status_code=400, detail="Falta la ubicación")

    ciudad_id = repo.get_ciudad_id(ciudad_slug) or repo.get_ciudad_id("bermejo")

    # rubros: resuelve los slugs a ids; el 1º es el principal
    rubro_ids = [rid for rid in (repo.get_rubro_id(s) for s in rubro_slugs if s) if rid]

    slug = slug_unico(repo, slugify(nombre))

    portada_url = None
    if foto is not None:
        data = await foto.read()
        if data:
            portada_url = _subir_foto(slug, foto, data)

    def _none(v: str | None) -> str | None:
        return v.strip() if v and v.strip() else None

    comercio = repo.crear_comercio(
        {
            "slug": slug,
            "nombre": nombre.strip(),
            "descripcion": _none(descripcion),
            "whatsapp": whatsapp.strip(),
            "email": _none(email),
            "tiktok_url": _none(tiktok_url),
            "facebook_url": _none(facebook_url),
            "instagram_url": _none(instagram_url),
            "sitio_web": _none(sitio_web),
            "rubro_id": rubro_ids[0] if rubro_ids else None,
            "ciudad_id": ciudad_id,
            "modalidad": modalidad,
            "direccion": _none(direccion),
            "lat": lat,
            "lng": lng,
            "portada_url": portada_url,
            "plan": "gratis",
            "confiable": False,
            "verificado": False,
            # Campos fronterizos
            "monedas_aceptadas": [m for m in monedas_aceptadas if m] or [],
            "envios_internacionales": envios_internacionales,
            "origen_importacion": [o for o in origen_importacion if o] or [],
            "pedido_minimo": _none(pedido_minimo),
            "tiene_factura": tiene_factura,
            "horario": _none(horario),
            "tiene_stock": tiene_stock,
            "fuente": "campo",
            "cargado_por": agente["email"],
        }
    )
    if rubro_ids:
        repo.set_comercio_rubros(comercio["id"], rubro_ids)

    # video (link TikTok) opcional → publicación pendiente tipo video
    vurl = _none(video_url)
    if vurl:
        repo.insert_publicacion_directa({
            "comercio_id": comercio["id"], "tipo": "video", "titulo": nombre.strip(),
            "tiktok_url": vurl, "estado": "pendiente", "origen": "panel",
        })

    logger.info("campo.alta", slug=slug, ciudad=ciudad_slug, rubros=len(rubro_ids),
                con_foto=bool(portada_url), con_gps=lat is not None, con_video=bool(vurl),
                consentimiento=consentimiento, cargado_por=agente["email"])
    return {"ok": True, "comercio": {"id": comercio["id"], "nombre": comercio["nombre"], "slug": slug,
                                     "ciudad": ciudad_slug, "rubros": len(rubro_ids),
                                     "foto": bool(portada_url), "gps": lat is not None,
                                     "video": bool(vurl)}}


class _LeadIn(BaseModel):
    comercio_id: str
    tipo: str = "whatsapp"


@router.post("/lead")
def registrar_lead(body: _LeadIn, repo: Repo = Depends(get_repo)) -> dict:
    """Registra un click de contacto (WhatsApp, teléfono, email…)."""
    tipo = body.tipo if body.tipo in _TIPOS_LEAD else "whatsapp"
    repo.insert_lead({"comercio_id": body.comercio_id, "tipo": tipo})
    return {"ok": True}


class _ReclamoIn(BaseModel):
    nombre: str | None = None
    contacto: str | None = None
    comercio_id: str | None = None
    mensaje: str


@router.post("/reclamos")
def crear_reclamo(body: _ReclamoIn, repo: Repo = Depends(get_repo)) -> dict:
    """Deja un reclamo público (sobre un comercio o la plataforma en general)."""
    repo.crear_reclamo({
        "nombre": body.nombre,
        "contacto": body.contacto,
        "comercio_id": body.comercio_id,
        "mensaje": body.mensaje,
    })
    return {"ok": True}
