"""Importados desde fotos de tarjetas de presentación (docs/carga-tarjetas.md).

QUIÉN PUEDE: todo exige el permiso `datos` VIGENTE (el de la sección Importados del panel), verificado contra la
base en cada pedido como el resto del panel. Nada de esto es público: la foto de la tarjeta puede traer datos
personales y vive en el disco privado.

El listado, «Promover» y «Descartar» siguen en `moderacion.py` (son los de siempre, con el filtro `fuente` y los
campos de la tarjeta). Acá: subir las fotos, ver la foto, corregir los campos y buscar la dirección en el mapa.
"""
from __future__ import annotations

import re
import uuid

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field

from app.core.auth import require_permiso
from app.core.telefono import normalizar_whatsapp, validar_whatsapp
from app.db.content_repository import ContentRepo, get_content_repo
from app.db.repository import Repo, get_repo
from app.services import archivos_privados, enlaces, tarjetas

router = APIRouter()
logger = structlog.get_logger()

_permiso = require_permiso("datos")
_RE_CORREO = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")


def _uuid_o_400(valor: str, etiqueta: str) -> str:
    try:
        return str(uuid.UUID(str(valor)))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=400, detail=f"{etiqueta} no es válida") from None


def _importado_o_404(repo: Repo, importado_id: str) -> dict:
    try:
        uuid.UUID(str(importado_id))
    except ValueError:
        raise HTTPException(status_code=404, detail="No existe ese importado") from None
    imp = repo.get_importado(importado_id)
    if not imp:
        raise HTTPException(status_code=404, detail="No existe ese importado")
    return imp


def _salida(repo: Repo, fila: dict) -> dict:
    nombres = repo.nombres_de_comercios([fila["duplicado_de"]]) if fila.get("duplicado_de") else {}
    return tarjetas.importado_salida(fila, nombres)


# ───────────────────────────────────────────────────────────── subir las fotos

@router.post("/admin/importados/tarjetas")
def cargar_tarjetas(
    ciudad_id: str = Form(...),
    fotos: list[UploadFile] = File(...),
    admin: dict = Depends(_permiso),
    repo: Repo = Depends(get_repo),
    crepo: ContentRepo = Depends(get_content_repo),
) -> dict:
    """Lee cada foto y deja una fila `nuevo` en Importados (`fuente = 'tarjeta'`).

    Devuelve `{items, errores}`: `items` son las filas creadas y `errores` las fotos que no se cargaron, cada una
    con su motivo (formato, tamaño, ya cargada, el lector no pudo). Una foto mala no frena a las demás. Es `def`
    (no `async`): el OCR y Nominatim bloquean, y FastAPI lo corre en un hilo aparte."""
    ciudad_id = _uuid_o_400(ciudad_id, "La ciudad")
    if not fotos:
        raise HTTPException(status_code=400, detail="Falta al menos una foto")
    if len(fotos) > tarjetas.MAX_ARCHIVOS:
        raise HTTPException(status_code=400, detail=f"Se pueden subir hasta {tarjetas.MAX_ARCHIVOS} fotos por vez")
    ciudad = repo.get_ciudad_por_id(ciudad_id)
    if not ciudad:
        raise HTTPException(status_code=404, detail="No existe esa ciudad")

    indice = tarjetas.indice_telefonos(repo)
    items: list[dict] = []
    errores: list[dict] = []
    nombres_repetidos: dict[str, str] = {}
    for foto in fotos:
        archivo = tarjetas.nombre_para_mostrar(foto.filename)
        # Se lee un byte de más que el tope: así se sabe que lo pasa sin cargar un archivo gigante entero.
        data = foto.file.read(tarjetas.MAX_BYTES + 1)
        try:
            r = tarjetas.procesar(repo, crepo, data, ciudad, indice)
        except Exception:  # noqa: BLE001 - una tarjeta rota no puede tumbar el lote
            logger.warning("tarjetas.foto_fallo", exc_info=True)
            errores.append({"archivo": archivo, "motivo": "No se pudo procesar la foto"})
            continue
        finally:
            del data
        if r.fila is None:
            errores.append({"archivo": archivo, "motivo": r.motivo or "No se pudo cargar"})
            continue
        if r.fila.get("duplicado_de") and r.fila["duplicado_de"] not in nombres_repetidos:
            nombres_repetidos.update(repo.nombres_de_comercios([r.fila["duplicado_de"]]))
        items.append(tarjetas.importado_salida(r.fila, nombres_repetidos))
    logger.info("tarjetas.lote", ciudad=ciudad_id, recibidas=len(fotos), cargadas=len(items),
                errores=len(errores), by=admin.get("email"))
    return {"items": items, "errores": errores}


# ───────────────────────────────────────────────────────────── ver la foto

@router.get("/admin/importados/{importado_id}/foto")
def foto_de_tarjeta(
    importado_id: str,
    _admin: dict = Depends(_permiso),
    repo: Repo = Depends(get_repo),
) -> Response:
    """La foto de la tarjeta (disco privado). 404 si el importado no es de tarjeta o no tiene foto. Sin caché."""
    imp = repo.get_importado(importado_id) if _es_uuid(importado_id) else None
    ref = (imp or {}).get("foto_ref")
    datos = archivos_privados.leer(ref) if imp and imp.get("fuente") == tarjetas.FUENTE and \
        archivos_privados.es_referencia(ref) else None
    if not datos:
        raise HTTPException(status_code=404, detail="Esa imagen no está")
    return Response(content=datos, media_type="image/jpeg", headers={
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    })


def _es_uuid(valor: str) -> bool:
    try:
        uuid.UUID(str(valor))
        return True
    except ValueError:
        return False


# ───────────────────────────────────────────────────────────── corregir los campos

class ImportadoPatch(BaseModel):
    """Los campos que la persona puede corregir al revisar. Lo que no viene no se toca; `null` o vacío lo borra."""
    nombre: str | None = Field(default=None, max_length=tarjetas.MAX_NOMBRE)
    direccion: str | None = Field(default=None, max_length=tarjetas.MAX_DIRECCION)
    telefono: str | None = Field(default=None, max_length=80)
    whatsapp: str | None = Field(default=None, max_length=40)
    website: str | None = Field(default=None, max_length=300)
    email: str | None = Field(default=None, max_length=120)
    rubro_slug: str | None = Field(default=None, max_length=80)
    lat: float | None = None
    lng: float | None = None


def _texto(valor: str | None) -> str | None:
    limpio = re.sub(r"[\x00-\x1f\x7f]", " ", str(valor or "")).strip()
    return re.sub(r"\s+", " ", limpio) or None


@router.patch("/admin/importados/{importado_id}")
def corregir_importado(
    importado_id: str,
    body: ImportadoPatch,
    admin: dict = Depends(_permiso),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Guarda lo que la persona corrigió. Sólo mientras el importado está `nuevo`. Guardar `lat` y `lng` (o mover
    el punto en el mapa) pasa la ubicación a `confirmada`; borrar el punto la deja `no_encontrada`."""
    imp = _importado_o_404(repo, importado_id)
    if imp.get("estado") != "nuevo":
        raise HTTPException(status_code=409, detail="Sólo se corrigen los importados sin revisar")
    enviados = body.model_fields_set
    patch: dict = {}

    for campo in ("nombre", "direccion", "telefono"):
        if campo in enviados:
            patch[campo] = _texto(getattr(body, campo))
    if "whatsapp" in enviados:
        crudo = _texto(body.whatsapp)
        if crudo:
            error = validar_whatsapp(crudo)
            if error:
                raise HTTPException(status_code=400, detail=error)
            patch["whatsapp"] = normalizar_whatsapp(crudo)
        else:
            patch["whatsapp"] = None
    if "website" in enviados:
        try:
            patch["website"] = enlaces.validar_red(_texto(body.website), "El sitio web") or None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if "email" in enviados:
        correo = _texto(body.email)
        if correo and not _RE_CORREO.match(correo):
            raise HTTPException(status_code=400, detail="El correo no es válido")
        patch["email"] = correo.lower() if correo else None
    if "rubro_slug" in enviados:
        slug = _texto(body.rubro_slug)
        if slug and not repo.get_rubro_id(slug):
            raise HTTPException(status_code=400, detail="Ese rubro no existe")
        patch["rubro_slug"] = slug
    if "lat" in enviados or "lng" in enviados:
        lat = body.lat if "lat" in enviados else imp.get("lat")
        lng = body.lng if "lng" in enviados else imp.get("lng")
        if (lat is None) != (lng is None):
            raise HTTPException(status_code=400, detail="Hace falta la latitud y la longitud juntas")
        if lat is not None and not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise HTTPException(status_code=400, detail="El punto no es válido")
        patch.update({"lat": lat, "lng": lng, "ubicacion": "confirmada" if lat is not None else "no_encontrada"})
    if not patch:
        return _salida(repo, imp)
    fila = repo.marcar_importado(importado_id, patch)
    logger.info("importado.corregido", importado=importado_id, campos=sorted(patch), by=admin.get("email"))
    return _salida(repo, fila or {**imp, **patch})


# ───────────────────────────────────────────────────────────── buscar la dirección

class UbicarBody(BaseModel):
    direccion: str = Field(min_length=1, max_length=tarjetas.MAX_DIRECCION)


@router.post("/admin/importados/{importado_id}/ubicar")
def ubicar_importado(
    importado_id: str,
    body: UbicarBody,
    admin: dict = Depends(_permiso),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Busca la dirección en OpenStreetMap (Nominatim), dentro de la ciudad del importado.

    Si la encuentra, el punto queda guardado como `aproximada` junto con la dirección buscada. Si no, NO cambia
    nada y contesta `encontrado: false`. Si el servicio de mapas no contesta, 503 (se puede reintentar)."""
    imp = _importado_o_404(repo, importado_id)
    if imp.get("estado") != "nuevo":
        raise HTTPException(status_code=409, detail="Sólo se ubican los importados sin revisar")
    direccion = _texto(body.direccion)
    if not direccion or len(direccion) < 4:
        raise HTTPException(status_code=400, detail="Escribí la dirección completa")
    ciudad = repo.get_ciudad_por_id(imp.get("ciudad_id")) if imp.get("ciudad_id") else None
    try:
        punto = tarjetas.buscar_direccion(direccion, ciudad)
    except tarjetas.UbicacionNoDisponible:
        raise HTTPException(status_code=503,
                            detail="El servicio de mapas no contestó, probá de nuevo en unos segundos") from None
    if not punto:
        return {"lat": None, "lng": None, "aproximada": False, "encontrado": False, "display_name": None}
    repo.marcar_importado(importado_id, {"lat": punto["lat"], "lng": punto["lng"], "direccion": direccion,
                                         "ubicacion": "aproximada"})
    logger.info("importado.ubicado", importado=importado_id, by=admin.get("email"))
    return {"lat": punto["lat"], "lng": punto["lng"], "aproximada": True, "encontrado": True,
            "display_name": punto["display_name"]}
