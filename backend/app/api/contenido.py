"""Contenido editable de la home Inicio: cotizaciones, clima y videos
promocionales ("Recorrimos Bermejo"). Lo gestiona el rol `publicador` (o admin).
La LECTURA la hace el frontend vía anon (RLS público); acá solo va la escritura."""
import secrets
from datetime import date, datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.core import auth
from app.core.config import settings
from app.db.repository import Repo, get_repo
from app.models.schemas import LoginBody
from app.services import novedades_uruku as novedades_svc
from app.services.clima import fetch_clima_bermejo
from app.services.enlaces import validar_http
from app.services.imagenes import guardar_foto_local, procesar_imagen, subir_foto_galeria, subir_video_comercio

router = APIRouter()
logger = structlog.get_logger()

_MAX_VIDEO_BYTES = 100 * 1024 * 1024  # promo puede pesar más que la galería
_MAX_FOTO_NOVEDAD_BYTES = 15 * 1024 * 1024
_VIDEOS_NOVEDAD = {"video/mp4", "video/webm", "video/quicktime"}


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
    # El horario de hoy de las chalanas, como lo diría una persona: entra la
    # frase entera porque el caso real no es una hora, son turnos —"6:00 a
    # 18:00 todas, hasta las 20:00 sólo una cooperativa"—. Vacío = se borra:
    # no se deja un horario viejo diciendo cualquier cosa.
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
        patch["chalanas_horario"] = body.chalanas_horario.strip()[:160] or None
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


# ---- Novedades de URUKU (0150, docs/novedades-uruku.md) ----
# Lo que URUKU cuenta en la sección «Novedades» del inicio. Mismo permiso que los videos
# promo (`contenido`). La lectura pública la hace el sitio con anon; acá, la escritura.
_MAX_TITULO = 120
_MAX_TEXTO = 2000


class NovedadIn(BaseModel):
    """Los campos son laxos a propósito: se validan a mano para contestar 400 en español
    (y no el 422 de pydantic). En el PATCH, lo que no viene no se toca; `texto`,
    `enlace_url` y `ciudad_slug` mandados vacíos o en null se borran (`ciudad_slug`
    vacío = «todas las ciudades»)."""
    titulo: str | None = None
    texto: str | None = None
    fecha: str | None = None            # AAAA-MM-DD
    ciudad_slug: str | None = None
    enlace_url: str | None = None
    destacada: bool | None = None


class NovedadPatch(NovedadIn):
    activo: bool | None = None


def _validar_novedad(body: NovedadIn, repo: Repo, *, nueva: bool) -> dict:
    """Devuelve las columnas a escribir (ya limpias) o lanza 400."""
    dado = body.model_fields_set
    out: dict = {}
    if nueva or body.titulo is not None:
        titulo = (body.titulo or "").strip()
        if not titulo:
            raise HTTPException(status_code=400, detail="Poné un título para la novedad.")
        if len(titulo) > _MAX_TITULO:
            raise HTTPException(status_code=400, detail=f"El título puede tener hasta {_MAX_TITULO} caracteres.")
        out["titulo"] = titulo
    if "texto" in dado:
        texto = (body.texto or "").strip()
        if len(texto) > _MAX_TEXTO:
            raise HTTPException(status_code=400, detail=f"El texto puede tener hasta {_MAX_TEXTO} caracteres.")
        out["texto"] = texto or None
    if body.fecha is not None:
        try:
            out["fecha"] = date.fromisoformat(body.fecha.strip()).isoformat()
        except ValueError:
            raise HTTPException(status_code=400, detail="La fecha tiene que ser AAAA-MM-DD.") from None
    if "enlace_url" in dado:
        enlace = (body.enlace_url or "").strip()
        if enlace:
            try:
                enlace = validar_http(enlace, "El enlace")
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from None
        out["enlace_url"] = enlace or None
    if "ciudad_slug" in dado:
        slug = (body.ciudad_slug or "").strip().lower()
        if slug:
            ciudad_id = repo.get_ciudad_id(slug)
            if not ciudad_id:
                raise HTTPException(status_code=400, detail="Esa ciudad no existe.")
            out["ciudad_id"] = ciudad_id
        else:
            out["ciudad_id"] = None
    if body.destacada is not None:
        out["destacada"] = body.destacada
    if isinstance(body, NovedadPatch) and body.activo is not None:
        out["activo"] = body.activo
    return out


def _novedad_publica(row: dict, repo: Repo) -> dict:
    """La fila para el panel: la de la base más `ciudad_slug` (null = todas)."""
    slug = None
    if row.get("ciudad_id"):
        slug = next((c.get("slug") for c in repo.list_ciudades() if c.get("id") == row["ciudad_id"]), None)
    return {**row, "ciudad_slug": slug}


def _novedad_o_404(repo: Repo, novedad_id: str) -> dict:
    row = repo.get_novedad_uruku(novedad_id)
    if not row:
        raise HTTPException(status_code=404, detail="Novedad no encontrada")
    return row


def _respuesta_novedad(row: dict, repo: Repo) -> dict:
    """La novedad plana (como pide la spec) y también bajo `novedad` (como los videos promo)."""
    n = _novedad_publica(row, repo)
    return {**n, "ok": True, "novedad": n}


async def _leer_imagen(archivo: UploadFile | None, que: str = "La foto") -> bytes:
    if archivo is None:
        raise HTTPException(status_code=400, detail=f"Falta {que[0].lower() + que[1:]}")
    data = await archivo.read()
    if not data:
        raise HTTPException(status_code=400, detail=f"Falta {que[0].lower() + que[1:]}")
    if len(data) > _MAX_FOTO_NOVEDAD_BYTES:
        raise HTTPException(status_code=413, detail=f"{que} supera los 15 MB")
    return data


@router.get("/contenido/novedades")
def listar_novedades_uruku(_pub: dict = Depends(auth.require_publicador), repo: Repo = Depends(get_repo)) -> dict:
    """Todas, también las dadas de baja: es la lista del panel."""
    return {"items": [_novedad_publica(n, repo) for n in repo.list_novedades_uruku()]}


@router.post("/contenido/novedades")
def crear_novedad_uruku(body: NovedadIn, pub: dict = Depends(auth.require_publicador), repo: Repo = Depends(get_repo)) -> dict:
    row = _validar_novedad(body, repo, nueva=True)
    row["created_by"] = pub.get("email") or pub.get("sub")
    creada = repo.add_novedad_uruku(row)
    logger.info("contenido.novedad_uruku_add", id=creada.get("id"))
    return _respuesta_novedad(creada, repo)


@router.patch("/contenido/novedades/{novedad_id}")
def editar_novedad_uruku(novedad_id: str, body: NovedadPatch, _pub: dict = Depends(auth.require_publicador),
                         repo: Repo = Depends(get_repo)) -> dict:
    _novedad_o_404(repo, novedad_id)
    patch = _validar_novedad(body, repo, nueva=False)
    if not patch:
        raise HTTPException(status_code=400, detail="No hay nada que cambiar")
    row = repo.update_novedad_uruku(novedad_id, patch)
    if not row:
        raise HTTPException(status_code=404, detail="Novedad no encontrada")
    logger.info("contenido.novedad_uruku_edit", id=novedad_id, campos=sorted(patch))
    return _respuesta_novedad(row, repo)


@router.delete("/contenido/novedades/{novedad_id}")
def dar_de_baja_novedad_uruku(novedad_id: str, _pub: dict = Depends(auth.require_publicador),
                              repo: Repo = Depends(get_repo)) -> dict:
    """Baja LÓGICA (`activo = false`): nunca se borra la fila ni sus archivos, así se
    puede volver a activar con un PATCH."""
    _novedad_o_404(repo, novedad_id)
    repo.update_novedad_uruku(novedad_id, {"activo": False})
    logger.info("contenido.novedad_uruku_baja", id=novedad_id)
    return {"ok": True}


async def _guardar_foto_novedad(novedad_id: str, data: bytes) -> tuple[str, str]:
    """Pasa la foto por `services/imagenes.py` (JPG + miniatura) y la guarda en la carpeta
    de la novedad. 400 si no es una imagen; 502 si el disco falla (sin dejar medio guardado)."""
    try:
        url, thumb = await run_in_threadpool(subir_foto_galeria, novedades_svc.carpeta(novedad_id), data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    if not url or not thumb:
        novedades_svc.borrar_archivos(novedad_id, url, thumb)
        raise HTTPException(status_code=502, detail="No se pudo subir la foto")
    return url, thumb


@router.post("/contenido/novedades/{novedad_id}/portada")
async def subir_portada_novedad_uruku(
    novedad_id: str,
    foto: UploadFile | None = File(None),
    _pub: dict = Depends(auth.require_publicador),
    repo: Repo = Depends(get_repo),
) -> dict:
    nov = _novedad_o_404(repo, novedad_id)
    data = await _leer_imagen(foto)
    url, thumb = await _guardar_foto_novedad(novedad_id, data)
    if not repo.update_novedad_uruku(novedad_id, {"portada_url": url, "portada_thumb_url": thumb}):
        novedades_svc.borrar_archivos(novedad_id, url, thumb)
        raise HTTPException(status_code=404, detail="Novedad no encontrada")
    # La portada de antes ya no la usa nadie: se saca del disco.
    novedades_svc.borrar_archivos(novedad_id, nov.get("portada_url"), nov.get("portada_thumb_url"))
    logger.info("contenido.novedad_uruku_portada", id=novedad_id)
    return {"ok": True, "portada_url": url, "portada_thumb_url": thumb}


@router.post("/contenido/novedades/{novedad_id}/fotos")
async def agregar_foto_novedad_uruku(
    novedad_id: str,
    foto: UploadFile | None = File(None),
    _pub: dict = Depends(auth.require_publicador),
    repo: Repo = Depends(get_repo),
) -> dict:
    nov = _novedad_o_404(repo, novedad_id)
    mensaje_tope = f"Una novedad puede tener hasta {novedades_svc.MAX_FOTOS} fotos."
    if len(nov.get("fotos") or []) >= novedades_svc.MAX_FOTOS:
        raise HTTPException(status_code=409, detail=mensaje_tope)      # antes de procesar nada
    data = await _leer_imagen(foto)
    url, thumb = await _guardar_foto_novedad(novedad_id, data)
    # El tope definitivo lo decide la base en una sola sentencia: varias subidas a la vez no lo pasan.
    fotos = repo.agregar_foto_novedad_uruku(novedad_id, {"url": url, "thumb_url": thumb}, novedades_svc.MAX_FOTOS)
    if fotos is None:
        novedades_svc.borrar_archivos(novedad_id, url, thumb)
        if repo.get_novedad_uruku(novedad_id):
            raise HTTPException(status_code=409, detail=mensaje_tope)
        raise HTTPException(status_code=404, detail="Novedad no encontrada")
    logger.info("contenido.novedad_uruku_foto_add", id=novedad_id, fotos=len(fotos))
    return {"ok": True, "foto": {"url": url, "thumb_url": thumb}, "fotos": fotos}


@router.delete("/contenido/novedades/{novedad_id}/fotos")
def sacar_foto_novedad_uruku(
    novedad_id: str,
    url: str = "",
    _pub: dict = Depends(auth.require_publicador),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Saca la foto de esa `url` de la lista y borra sus archivos (la grande y la miniatura)."""
    _novedad_o_404(repo, novedad_id)
    if not url.strip():
        raise HTTPException(status_code=400, detail="Falta la url de la foto")
    sacada = repo.quitar_foto_novedad_uruku(novedad_id, url.strip())
    if not sacada:
        raise HTTPException(status_code=404, detail="Esa foto no está en la novedad")
    novedades_svc.borrar_archivos(novedad_id, sacada.get("url"), sacada.get("thumb_url"))
    logger.info("contenido.novedad_uruku_foto_del", id=novedad_id)
    actual = repo.get_novedad_uruku(novedad_id) or {}
    return {"ok": True, "fotos": actual.get("fotos") or []}


@router.post("/contenido/novedades/{novedad_id}/video")
async def subir_video_novedad_uruku(
    novedad_id: str,
    video: UploadFile | None = File(None),
    poster: UploadFile | None = File(None),
    _pub: dict = Depends(auth.require_publicador),
    repo: Repo = Depends(get_repo),
) -> dict:
    """El video (mp4/webm/mov, hasta 100 MB) y, opcional, su póster (imagen). Con el
    video solo, el póster de antes se borra (era del video anterior). Con el póster
    solo, se cambia nada más el póster del video que ya tiene."""
    nov = _novedad_o_404(repo, novedad_id)
    if video is None and poster is None:
        raise HTTPException(status_code=400, detail="Falta el video")
    video_data = None
    if video is not None:
        tipo = (video.content_type or "").split(";")[0].strip().lower()
        if tipo not in _VIDEOS_NOVEDAD:
            raise HTTPException(status_code=400, detail="El video tiene que ser mp4, webm o mov")
        video_data = await video.read()
        if not video_data:
            raise HTTPException(status_code=400, detail="Falta el video")
        if len(video_data) > _MAX_VIDEO_BYTES:
            raise HTTPException(status_code=413, detail="El video supera los 100 MB")
    elif not nov.get("video_url"):
        raise HTTPException(status_code=400, detail="Primero subí el video")
    poster_jpg = None
    if poster is not None:
        poster_data = await _leer_imagen(poster, "El póster")
        try:
            poster_jpg = await run_in_threadpool(procesar_imagen, poster_data, 1280, 80)
        except Exception:  # noqa: BLE001
            raise HTTPException(status_code=400, detail="El póster no es una imagen válida") from None

    patch: dict = {}
    nuevos: list[str] = []
    if video_data is not None:
        url_video = subir_video_comercio(novedades_svc.carpeta(novedad_id), video_data, video.content_type)
        if not url_video:
            raise HTTPException(status_code=502, detail="No se pudo subir el video")
        nuevos.append(url_video)
        patch["video_url"] = url_video
        patch["video_poster_url"] = None
    if poster_jpg is not None:
        url_poster = guardar_foto_local(
            f"{novedades_svc.carpeta(novedad_id)}/poster-{secrets.token_hex(8)}.jpg", poster_jpg)
        if not url_poster:
            novedades_svc.borrar_archivos(novedad_id, *nuevos)
            raise HTTPException(status_code=502, detail="No se pudo subir el póster")
        nuevos.append(url_poster)
        patch["video_poster_url"] = url_poster

    row = repo.update_novedad_uruku(novedad_id, patch)
    if not row:
        novedades_svc.borrar_archivos(novedad_id, *nuevos)
        raise HTTPException(status_code=404, detail="Novedad no encontrada")
    if "video_url" in patch:
        novedades_svc.borrar_archivos(novedad_id, nov.get("video_url"))
    if "video_poster_url" in patch:
        novedades_svc.borrar_archivos(novedad_id, nov.get("video_poster_url"))
    logger.info("contenido.novedad_uruku_video", id=novedad_id)
    return {"ok": True, "video_url": row.get("video_url"), "video_poster_url": row.get("video_poster_url")}


# ---- Redes sociales ----
class RedUpdate(BaseModel):
    url: str | None = None


@router.put("/contenido/redes/{clave}")
def editar_red(clave: str, body: RedUpdate, _pub: dict = Depends(auth.require_publicador), repo: Repo = Depends(get_repo)) -> dict:
    row = repo.update_red(clave, (body.url or "").strip() or None)
    if not row:
        raise HTTPException(status_code=404, detail="Red no encontrada")
    return {"ok": True, "red": row}
