"""Modo agente de campo: alta rápida de comercios durante el recorrido.

El agente (un colaborador de confianza) carga nombre + celular + rubro +
modalidad, comparte el GPS y saca una foto del local. El comercio entra
'pendiente de verificar' (verificado=false), listo para que un moderador lo
confirme. La foto va a Supabase Storage (bucket público 'comercios').
"""
import httpx
import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.core import auth
from app.core.config import settings
from app.core.text import slug_unico, slugify
from app.db.repository import Repo, get_repo
from app.models.schemas import LoginBody
from app.services.clasificador import sugerir_rubros
from app.services.imagenes import subir_foto_comercio, subir_foto_galeria, subir_video_comercio

router = APIRouter()
logger = structlog.get_logger()

_MODALIDADES = {"mayorista", "minorista", "ambos"}
_TIPOS_LEAD  = {"whatsapp", "telefono", "email", "web", "vista"}


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


def _subir_foto(slug: str, foto: UploadFile, data: bytes) -> tuple[str | None, str | None]:
    """Sube la portada y devuelve (url_grande, url_thumb)."""
    if len(data) > _MAX_FOTO_BYTES:
        raise HTTPException(status_code=413, detail="La foto supera los 15 MB")
    try:
        return subir_foto_galeria(slug, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/campo/comercio")
async def alta_campo(
    nombre: str = Form(""),
    whatsapp: str | None = Form(None),
    telefono: str | None = Form(None),
    ciudad_slug: str = Form("bermejo"),           # ciudad donde está el negocio
    rubro_slugs: list[str] = Form(default=[]),    # uno o varios rubros
    modalidad: str = Form("mayorista"),
    direccion: str | None = Form(None),
    lugar_id: str | None = Form(None),            # si está DENTRO de un mercado/galería
    puesto: str | None = Form(None),              # N° de puesto/local dentro del lugar
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
    foto: UploadFile | None = File(None),
    agente: dict = Depends(auth.require_agente),
    repo: Repo = Depends(get_repo),
) -> dict:
    if modalidad not in _MODALIDADES:
        raise HTTPException(status_code=400, detail=f"modalidad inválida: {modalidad}")
    if lat is None or lng is None:
        raise HTTPException(status_code=400, detail="Falta la ubicación")
    # Alta mínima: solo la ubicación es obligatoria; whatsapp/teléfono/descripción/foto opcionales.
    ciudad_id = repo.get_ciudad_id(ciudad_slug) or repo.get_ciudad_id("bermejo")

    # rubros: resuelve los slugs a ids; el 1º es el principal
    rubro_ids = [rid for rid in (repo.get_rubro_id(s) for s in rubro_slugs if s) if rid]

    # Nombre por defecto: si no lo cargan, usa el rubro elegido (ej. "Ferretería");
    # si tampoco hay rubro útil, queda "Comercio".
    if nombre and nombre.strip():
        nombre_final = nombre.strip()
    else:
        rubro_util = next((s for s in rubro_slugs if s and s != "otros"), None)
        nombre_final = (repo.get_rubro_nombre(rubro_util) if rubro_util else None) or "Comercio"

    slug = slug_unico(repo, slugify(nombre_final))

    portada_url, portada_thumb = None, None
    if foto is not None:
        data = await foto.read()
        if data:
            portada_url, portada_thumb = _subir_foto(slug, foto, data)

    def _none(v: str | None) -> str | None:
        return v.strip() if v and v.strip() else None

    comercio = repo.crear_comercio(
        {
            "slug": slug,
            "nombre": nombre_final,
            "descripcion": _none(descripcion),
            "whatsapp": _none(whatsapp),
            "telefono": _none(telefono),
            "email": _none(email),
            "tiktok_url": _none(tiktok_url),
            "facebook_url": _none(facebook_url),
            "instagram_url": _none(instagram_url),
            "sitio_web": _none(sitio_web),
            "rubro_id": rubro_ids[0] if rubro_ids else None,
            "ciudad_id": ciudad_id,
            "modalidad": modalidad,
            "direccion": _none(direccion),
            "lugar_id": _none(lugar_id),
            "puesto": _none(puesto),
            "lat": lat,
            "lng": lng,
            "portada_url": portada_url,
            "portada_thumb_url": portada_thumb,
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
            "comercio_id": comercio["id"], "tipo": "video", "titulo": nombre_final,
            "tiktok_url": vurl, "estado": "pendiente", "origen": "panel",
        })

    logger.info("campo.alta", slug=slug, ciudad=ciudad_slug, rubros=len(rubro_ids),
                con_foto=bool(portada_url), con_gps=lat is not None, con_video=bool(vurl),
                consentimiento=consentimiento, cargado_por=agente["email"])
    return {"ok": True, "comercio": {"id": comercio["id"], "nombre": comercio["nombre"], "slug": slug,
                                     "ciudad": ciudad_slug, "rubros": len(rubro_ids),
                                     "foto": bool(portada_url), "gps": lat is not None,
                                     "video": bool(vurl)}}


class LugarBody(BaseModel):
    nombre: str
    tipo: str = "mercado"
    ciudad_slug: str = "bermejo"
    lat: float | None = None
    lng: float | None = None


@router.get("/campo/lugares")
def listar_lugares(
    ciudad_slug: str = "bermejo",
    _agente: dict = Depends(auth.require_agente),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Mercados/galerías/paseos para el selector del alta (elegir dónde está el puesto)."""
    ciudad_id = repo.get_ciudad_id(ciudad_slug) or repo.get_ciudad_id("bermejo")
    return {"items": repo.list_lugares(ciudad_id)}


@router.post("/campo/lugares")
def crear_lugar(
    body: LugarBody,
    agente: dict = Depends(auth.require_agente),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Crea un mercado/galería en el momento (el agente lo carga la 1ª vez que lo encuentra)."""
    nombre = (body.nombre or "").strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="Falta el nombre del lugar")
    ciudad_id = repo.get_ciudad_id(body.ciudad_slug) or repo.get_ciudad_id("bermejo")
    lugar = repo.crear_lugar({
        "nombre": nombre, "tipo": body.tipo or "mercado", "ciudad_id": ciudad_id,
        "lat": body.lat, "lng": body.lng,
    })
    logger.info("campo.lugar_creado", lugar=lugar["id"], nombre=nombre, by=agente["email"])
    return {"ok": True, "lugar": lugar}


class LugarEditBody(BaseModel):
    nombre: str | None = None
    tipo: str | None = None


@router.patch("/campo/lugares/{lugar_id}")
def editar_lugar(
    lugar_id: str,
    body: LugarEditBody,
    agente: dict = Depends(auth.require_agente),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Corrige el nombre/tipo de un mercado/galería (ej. arreglar un typo)."""
    patch: dict = {}
    if body.nombre is not None and body.nombre.strip():
        patch["nombre"] = body.nombre.strip()
    if body.tipo is not None and body.tipo.strip():
        patch["tipo"] = body.tipo.strip()
    if not patch:
        raise HTTPException(status_code=400, detail="Nada para actualizar")
    return {"ok": True, "lugar": repo.update_lugar(lugar_id, patch)}


@router.post("/campo/lugares/{lugar_id}/portada")
async def lugar_portada(
    lugar_id: str,
    foto: UploadFile = File(...),
    agente: dict = Depends(auth.require_agente),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Sube/reemplaza la foto de portada del lugar (el agente, parado ahí)."""
    data = await foto.read()
    if not data:
        raise HTTPException(status_code=400, detail="Falta la foto")
    try:
        url, thumb = subir_foto_galeria(f"lugares/{lugar_id}", data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "lugar": repo.update_lugar(lugar_id, {"portada_url": url, "portada_thumb_url": thumb})}


@router.post("/campo/lugares/{lugar_id}/video")
async def lugar_video(
    lugar_id: str,
    video: UploadFile = File(...),
    agente: dict = Depends(auth.require_agente),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Sube el video de recorrido del lugar (crudo, se sirve por /fotos)."""
    if not (video.content_type or "").startswith("video/"):
        raise HTTPException(status_code=400, detail="El archivo no es un video")
    data = await video.read()
    if not data:
        raise HTTPException(status_code=400, detail="Falta el video")
    url = subir_video_comercio(f"lugares/{lugar_id}", data, video.content_type)
    return {"ok": True, "lugar": repo.update_lugar(lugar_id, {"video_url": url})}


@router.get("/campo/mis-comercios")
def mis_comercios(agente: dict = Depends(auth.require_agente), repo: Repo = Depends(get_repo)) -> dict:
    """Comercios que este agente dio de alta, para que vea su propio recorrido."""
    items = repo.list_comercios_por_agente(agente["email"])
    return {"items": items}


def _propio_o_404(repo: Repo, comercio_id: str, agente: dict) -> dict:
    comercio = repo.get_comercio(comercio_id)
    if not comercio or comercio.get("cargado_por") != agente["email"]:
        raise HTTPException(status_code=404, detail="Comercio no encontrado")
    return comercio


class _EditarComercioBody(BaseModel):
    nombre: str | None = None
    whatsapp: str | None = None
    email: str | None = None
    modalidad: str | None = None
    direccion: str | None = None
    descripcion: str | None = None
    rubro_slugs: list[str] | None = None


@router.patch("/campo/mis-comercios/{comercio_id}")
def editar_mi_comercio(
    comercio_id: str,
    body: _EditarComercioBody,
    agente: dict = Depends(auth.require_agente),
    repo: Repo = Depends(get_repo),
) -> dict:
    """El agente edita un comercio que él mismo cargó (no puede tocar otros)."""
    _propio_o_404(repo, comercio_id, agente)
    if body.modalidad is not None and body.modalidad not in _MODALIDADES:
        raise HTTPException(status_code=400, detail=f"modalidad inválida: {body.modalidad}")
    patch = body.model_dump(exclude_unset=True, exclude={"rubro_slugs"})
    if not patch and body.rubro_slugs is None:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")
    comercio = repo.update_comercio(comercio_id, patch, body.rubro_slugs)
    return {"ok": True, "comercio": comercio}


@router.post("/campo/mis-comercios/{comercio_id}/foto")
async def actualizar_foto_mi_comercio(
    comercio_id: str,
    foto: UploadFile = File(...),
    agente: dict = Depends(auth.require_agente),
    repo: Repo = Depends(get_repo),
) -> dict:
    """El agente re-sube la foto de un comercio que él mismo cargó."""
    comercio = _propio_o_404(repo, comercio_id, agente)
    data = await foto.read()
    if not data:
        raise HTTPException(status_code=400, detail="Falta la foto")
    portada_url, portada_thumb = _subir_foto(comercio["slug"], foto, data)
    if not portada_url:
        raise HTTPException(status_code=502, detail="No se pudo subir la foto, probá de nuevo")
    updated = repo.update_comercio(comercio_id, {"portada_url": portada_url, "portada_thumb_url": portada_thumb}, None)
    logger.info("campo.foto_update", comercio=comercio_id, agente=agente["email"])
    return {"ok": True, "comercio": updated}


@router.delete("/campo/mis-comercios/{comercio_id}")
def eliminar_mi_comercio(
    comercio_id: str,
    agente: dict = Depends(auth.require_agente),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Baja lógica (activo=false) — nunca se borra el registro."""
    _propio_o_404(repo, comercio_id, agente)
    repo.desactivar_comercio(comercio_id)
    return {"ok": True}


class _LeadIn(BaseModel):
    comercio_id: str
    tipo: str = "whatsapp"


@router.post("/lead")
def registrar_lead(body: _LeadIn, repo: Repo = Depends(get_repo)) -> dict:
    """Registra un click de contacto (WhatsApp, teléfono, email…) o una vista de ficha."""
    tipo = body.tipo if body.tipo in _TIPOS_LEAD else "whatsapp"
    repo.insert_lead({"comercio_id": body.comercio_id, "tipo": tipo})
    return {"ok": True}


class _BusquedaIn(BaseModel):
    query: str
    resultados: int = 0
    comercios: list[str] | None = None   # ids que aparecieron, en orden (para análisis)


@router.post("/busquedas/log")
def log_busqueda(body: _BusquedaIn, repo: Repo = Depends(get_repo)) -> dict:
    """Loguea una búsqueda (KPIs: qué se busca, qué no da resultados y a quién encontró)."""
    q = (body.query or "").strip()
    if len(q) >= 2:
        repo.insert_busqueda(q, max(0, int(body.resultados)), body.comercios)
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


# ============================================================
# Galería del comercio: hasta 10 fotos + 5 videos (<=60s c/u).
# Los archivos van al disco del backend; la base guarda la referencia.
# Todos scoped al agente dueño del comercio (_propio_o_404).
# ============================================================
_MAX_FOTOS = 10
_MAX_VIDEOS = 5
_MAX_VIDEO_BYTES = 50 * 1024 * 1024  # 50 MB


@router.get("/campo/mis-comercios/{comercio_id}/fotos")
async def listar_fotos(comercio_id: str, agente: dict = Depends(auth.require_agente), repo: Repo = Depends(get_repo)) -> dict:
    _propio_o_404(repo, comercio_id, agente)
    return {"items": repo.list_fotos_comercio(comercio_id)}


@router.post("/campo/mis-comercios/{comercio_id}/fotos")
async def agregar_foto(comercio_id: str, foto: UploadFile = File(...), agente: dict = Depends(auth.require_agente), repo: Repo = Depends(get_repo)) -> dict:
    comercio = _propio_o_404(repo, comercio_id, agente)
    if repo.count_fotos_comercio(comercio_id) >= _MAX_FOTOS:
        raise HTTPException(status_code=409, detail=f"Máximo {_MAX_FOTOS} fotos por comercio")
    data = await foto.read()
    if not data:
        raise HTTPException(status_code=400, detail="Falta la foto")
    if len(data) > _MAX_FOTO_BYTES:
        raise HTTPException(status_code=413, detail="La foto supera los 15 MB")
    try:
        url, thumb = subir_foto_galeria(comercio["slug"], data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not url:
        raise HTTPException(status_code=502, detail="No se pudo subir la foto, probá de nuevo")
    row = repo.add_foto_comercio({
        "comercio_id": comercio_id, "url": url, "thumb_url": thumb,
        "orden": repo.count_fotos_comercio(comercio_id),
    })
    logger.info("campo.foto_add", comercio=comercio_id, agente=agente["email"])
    return {"ok": True, "foto": row}


@router.delete("/campo/mis-comercios/{comercio_id}/fotos/{foto_id}")
async def borrar_foto(comercio_id: str, foto_id: str, agente: dict = Depends(auth.require_agente), repo: Repo = Depends(get_repo)) -> dict:
    _propio_o_404(repo, comercio_id, agente)
    if not repo.delete_foto_comercio(foto_id, comercio_id):
        raise HTTPException(status_code=404, detail="Foto no encontrada")
    return {"ok": True}


@router.get("/campo/mis-comercios/{comercio_id}/videos")
async def listar_videos(comercio_id: str, agente: dict = Depends(auth.require_agente), repo: Repo = Depends(get_repo)) -> dict:
    _propio_o_404(repo, comercio_id, agente)
    return {"items": repo.list_videos_comercio(comercio_id)}


@router.post("/campo/mis-comercios/{comercio_id}/videos")
async def agregar_video(
    comercio_id: str,
    video: UploadFile = File(...),
    duracion_seg: int | None = Form(None),
    agente: dict = Depends(auth.require_agente),
    repo: Repo = Depends(get_repo),
) -> dict:
    comercio = _propio_o_404(repo, comercio_id, agente)
    if repo.count_videos_comercio(comercio_id) >= _MAX_VIDEOS:
        raise HTTPException(status_code=409, detail=f"Máximo {_MAX_VIDEOS} videos por comercio")
    if not (video.content_type or "").lower().startswith("video/"):
        raise HTTPException(status_code=400, detail="El archivo no es un video")
    data = await video.read()
    if not data:
        raise HTTPException(status_code=400, detail="Falta el video")
    if len(data) > _MAX_VIDEO_BYTES:
        raise HTTPException(status_code=413, detail="El video supera los 50 MB")
    url = subir_video_comercio(comercio["slug"], data, video.content_type)
    if not url:
        raise HTTPException(status_code=502, detail="No se pudo subir el video, probá de nuevo")
    row = repo.add_video_comercio({
        "comercio_id": comercio_id, "url": url, "duracion_seg": duracion_seg,
        "orden": repo.count_videos_comercio(comercio_id),
    })
    logger.info("campo.video_add", comercio=comercio_id, agente=agente["email"])
    return {"ok": True, "video": row}


@router.delete("/campo/mis-comercios/{comercio_id}/videos/{video_id}")
async def borrar_video(comercio_id: str, video_id: str, agente: dict = Depends(auth.require_agente), repo: Repo = Depends(get_repo)) -> dict:
    _propio_o_404(repo, comercio_id, agente)
    if not repo.delete_video_comercio(video_id, comercio_id):
        raise HTTPException(status_code=404, detail="Video no encontrado")
    return {"ok": True}
