"""Contenido editable de la home Inicio: cotizaciones, clima y videos
promocionales ("Recorrimos Bermejo"). Lo gestiona el rol `publicador` (o admin).
La LECTURA la hace el frontend vía anon (RLS público); acá solo va la escritura."""
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.core import auth
from app.core.config import settings
from app.db.repository import Repo, get_repo
from app.models.schemas import LoginBody
from app.services.clima import fetch_clima_bermejo
from app.services.imagenes import subir_video_comercio

router = APIRouter()
logger = structlog.get_logger()

_MAX_VIDEO_BYTES = 100 * 1024 * 1024  # promo puede pesar más que la galería


@router.post("/auth/publicador/login")
def publicador_login(body: LoginBody, repo: Repo = Depends(get_repo)) -> dict:
    """La misma puerta que el panel, con la cuenta del `.env` de respaldo
    (0126). Lo que puede hacer adentro lo deciden sus permisos."""
    from app.api.auth import entrar
    r = entrar(repo, body.email, body.password, "publicador")
    if not r:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    return {**r, "publicador": r["user"]}


# ---- Cotizaciones ----
class CotizacionUpdate(BaseModel):
    valor: float


@router.put("/contenido/cotizaciones/{clave}")
def editar_cotizacion(clave: str, body: CotizacionUpdate, _pub: dict = Depends(auth.require_publicador), repo: Repo = Depends(get_repo)) -> dict:
    row = repo.update_cotizacion(clave, body.valor)
    if not row:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    logger.info("contenido.cotizacion", clave=clave, valor=body.valor)
    return {"ok": True, "cotizacion": row}


# ---- La frontera hoy ----
class FronteraIn(BaseModel):
    puente: str | None = None       # normal | demoras | cerrado
    chalanas: str | None = None     # operando | limitadas | suspendidas
    rio: str | None = None          # normal | crecido
    nota: str | None = None
    # El horario de hoy de las chalanas ("7:00 a 18:00", "sólo de mañana").
    # Vacío = se borra: no se deja un horario viejo diciendo cualquier cosa.
    chalanas_horario: str | None = None
    # De qué frontera es este estado. Cada ciudad tiene el suyo (0124).
    ciudad: str | None = None


# "no_aplica": esta frontera no tiene chalanas o no tiene río (Villazón cruza
# por un puente peatonal y no hay chalana que valga).
_FRONTERA_VALORES = {"puente": {"normal", "demoras", "cerrado"},
                     "chalanas": {"operando", "limitadas", "suspendidas", "no_aplica"},
                     "rio": {"normal", "crecido", "no_aplica"}}


@router.get("/contenido/frontera")
def frontera_estado(ciudad: str = "bermejo", repo: Repo = Depends(get_repo)) -> dict:
    """Cómo está el paso hoy, en ESA frontera. Público: es lo primero que
    pregunta el que está por cruzar, y no hay ninguna fuente automática — lo
    carga una persona, una por ciudad (0124)."""
    return repo.get_frontera_estado(ciudad)


@router.put("/contenido/frontera")
def editar_frontera(body: FronteraIn, pub: dict = Depends(auth.require_publicador), repo: Repo = Depends(get_repo)) -> dict:
    patch = {}
    for k in ("puente", "chalanas", "rio"):
        v = getattr(body, k)
        if v is None:
            continue
        if v not in _FRONTERA_VALORES[k]:
            raise HTTPException(status_code=400, detail=f"{k}: valor inválido")
        patch[k] = v
    if body.nota is not None:
        patch["nota"] = body.nota.strip()[:300] or None
    if body.chalanas_horario is not None:
        patch["chalanas_horario"] = body.chalanas_horario.strip()[:80] or None
    if not patch:
        raise HTTPException(status_code=400, detail="No hay nada que cambiar")
    patch["actualizado_por"] = pub.get("email")
    row = repo.update_frontera_estado(patch, body.ciudad or "bermejo")
    logger.info("contenido.frontera", **{k: v for k, v in patch.items() if k != "actualizado_por"})
    return {"ok": True, "frontera": row}


# ---- Clima ----
class ClimaOverride(BaseModel):
    temp_c: float | None = None
    descripcion: str | None = None
    icono: str | None = None
    horas: int = 12  # cuánto dura el override antes de que open-meteo vuelva a pisar


@router.put("/contenido/clima")
def override_clima(body: ClimaOverride, _pub: dict = Depends(auth.require_publicador), repo: Repo = Depends(get_repo)) -> dict:
    patch = {k: v for k, v in body.model_dump(exclude_unset=True).items() if k != "horas"}
    patch["fuente"] = "manual"
    patch["override_hasta"] = (datetime.now(timezone.utc) + timedelta(hours=body.horas)).isoformat()
    return {"ok": True, "clima": repo.update_clima(patch)}


@router.post("/contenido/clima/refresh")
async def refrescar_clima(_pub: dict = Depends(auth.require_publicador), repo: Repo = Depends(get_repo)) -> dict:
    data = await fetch_clima_bermejo()
    if not data:
        raise HTTPException(status_code=502, detail="No se pudo obtener el clima")
    data["override_hasta"] = None
    return {"ok": True, "clima": repo.update_clima(data)}


# ---- Videos promocionales ("Recorrimos Bermejo") ----
@router.get("/contenido/videos-promo")
def listar_videos_promo(_pub: dict = Depends(auth.require_publicador), repo: Repo = Depends(get_repo)) -> dict:
    return {"items": repo.list_videos_promo()}


@router.post("/contenido/videos-promo")
async def subir_video_promo(
    video: UploadFile = File(...),
    titulo: str | None = Form(None),
    _pub: dict = Depends(auth.require_publicador),
    repo: Repo = Depends(get_repo),
) -> dict:
    if not (video.content_type or "").lower().startswith("video/"):
        raise HTTPException(status_code=400, detail="El archivo no es un video")
    data = await video.read()
    if not data:
        raise HTTPException(status_code=400, detail="Falta el video")
    if len(data) > _MAX_VIDEO_BYTES:
        raise HTTPException(status_code=413, detail="El video supera los 100 MB")
    url = subir_video_comercio("promocionales", data, video.content_type)
    if not url:
        raise HTTPException(status_code=502, detail="No se pudo subir el video")
    row = repo.add_video_promo({"titulo": titulo or None, "url": url, "orden": len(repo.list_videos_promo())})
    logger.info("contenido.video_promo_add")
    return {"ok": True, "video": row}


@router.delete("/contenido/videos-promo/{video_id}")
def borrar_video_promo(video_id: str, _pub: dict = Depends(auth.require_publicador), repo: Repo = Depends(get_repo)) -> dict:
    if not repo.delete_video_promo(video_id):
        raise HTTPException(status_code=404, detail="Video no encontrado")
    return {"ok": True}


# ---- Redes sociales ----
class RedUpdate(BaseModel):
    url: str | None = None


@router.put("/contenido/redes/{clave}")
def editar_red(clave: str, body: RedUpdate, _pub: dict = Depends(auth.require_publicador), repo: Repo = Depends(get_repo)) -> dict:
    row = repo.update_red(clave, (body.url or "").strip() or None)
    if not row:
        raise HTTPException(status_code=404, detail="Red no encontrada")
    return {"ok": True, "red": row}
