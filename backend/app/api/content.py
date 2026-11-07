"""Contenido para redes: banco de fotos, autorización, piezas, publicación manual y descargas
(docs/contenido-redes-tecnico.md §8).

QUIÉN HACE QUÉ
==============
- Panel (`/admin/content/*`): el permiso `difusion` («Publicar en las redes de URUKU»); la
  autorización también la registra quien tiene `pagos`.
- App de campo (`/campo/mis-comercios/{id}/...`): el agente, sólo en SU ciudad.
- Mi comercio (`/comercio/social-consent`): el comerciante lee y cambia su autorización.
- Público (`/public/pieces/{token}`, `/content/files/...`): sin login; el token tiene 128 bits y
  las descargas del panel llevan una firma HMAC que vence a los 15 minutos.

Los archivos viven en un disco PRIVADO (`CONTENT_DIR`), nunca bajo `/fotos`. WAHA no manda nada:
acá no se publica en ninguna red; una persona lo hace a mano y pega el link.
"""
from __future__ import annotations

import re
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Literal

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator, model_validator
from starlette.concurrency import run_in_threadpool

from app.api.campo import _propio_o_404
from app.api.comercio import _comercio_dueno
from app.core import auth
from app.core.auth import require_alguno, require_permiso
from app.core.config import settings
from app.core.permisos import permisos_de
from app.core.sesion_comercio import require_comercio_vigente
from app.db.content_repository import ContentConflict, ContentRepo, get_content_repo
from app.db.repository import Repo, get_repo
from app.services import (cargas, content_captions, content_consent, content_posts, content_present,
                          content_public, content_render, content_requests, content_selector, content_storage,
                          content_video_texts, fotos_galeria)
from app.services.imagenes import subir_foto_galeria

router = APIRouter()
logger = structlog.get_logger()

_MAX_FOTO_BYTES = 15 * 1024 * 1024
_RE_SHA = re.compile(r"^[0-9a-f]{64}$")
_STATUS = ("queued", "rendering", "ready_for_review", "approved", "published", "skipped", "failed")
_ESTADOS_DE_REVISION = "ready_for_review,failed,queued,rendering"

MSG_NO_CONFIGURADO = "El banco de contenido no está configurado"
MSG_TOPE_DISCO = "El banco de contenido llegó a su tope de espacio. Avisale al admin."

_permiso_difusion = require_permiso("difusion")
_permiso_consent = require_alguno("difusion", "pagos")


def _actor(claims: dict) -> str:
    return claims.get("email") or claims.get("sub") or "desconocido"


def _error(status: int, codigo: str, mensaje: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"codigo": codigo, "mensaje": mensaje})


#: Roles con alcance sobre todas las ciudades: aunque su cuenta tenga una ciudad asignada, el panel no los limita.
_ROLES_CON_ALCANCE_GLOBAL = ("admin", "publicador")


def _ciudad_limitada(claims: dict) -> str | None:
    """El slug de la ciudad a la que está LIMITADO quien pregunta, o None si ve todas. Se limita a quien lleva el
    claim `ciudad` y no tiene alcance global: ni el permiso `*` (admin) ni un rol admin/publicador. Un agente de
    campo, o un rol del equipo creado para una sola ciudad, ve sólo la suya; el `?ciudad=` del cliente no cuenta."""
    slug = (claims.get("ciudad") or "").strip()
    if not slug or "*" in permisos_de(claims):
        return None
    roles = set(claims.get("roles") or [])
    if claims.get("rol"):
        roles.add(claims["rol"])
    return None if roles & set(_ROLES_CON_ALCANCE_GLOBAL) else slug


class _Alcance:
    """La ciudad de quien está limitado a una. Todo lo que no sea de ella se contesta como «no existe» (404)."""

    def __init__(self, crepo: ContentRepo, slug: str):
        self.slug = slug
        fila = next((c for c in crepo.list_ciudades() if c["slug"] == slug), None)
        self.id = fila["id"] if fila else None

    def comercio_ok(self, comercio: dict | None) -> bool:
        if not comercio:
            return False
        return (comercio.get("ciudades") or {}).get("slug") == self.slug or (
            self.id is not None and comercio.get("ciudad_id") == self.id)

    def pieza_ok(self, crepo: ContentRepo, pieza: dict) -> bool:
        if pieza.get("ciudad_id"):
            return self.id is not None and pieza["ciudad_id"] == self.id
        return bool(pieza.get("comercio_id")) and self.comercio_ok(crepo.get_comercio_ficha(pieza["comercio_id"]))

    def piezas(self, crepo: ContentRepo, piezas: list[dict]) -> list[dict]:
        return [p for p in piezas if self.pieza_ok(crepo, p)]


def _alcance(crepo: ContentRepo, claims: dict | None) -> _Alcance | None:
    slug = _ciudad_limitada(claims or {})
    return _Alcance(crepo, slug) if slug else None


def _comercio_o_404(crepo: ContentRepo, comercio_id: str, claims: dict | None = None) -> dict:
    c = crepo.get_comercio_ficha(comercio_id)
    if not c or c.get("activo") is False:
        raise HTTPException(status_code=404, detail="Comercio no encontrado")
    al = _alcance(crepo, claims)
    if al and not al.comercio_ok(c):
        raise HTTPException(status_code=404, detail="Comercio no encontrado")
    return c


def _fecha_o_400(texto: str | None, campo: str = "fecha") -> date:
    try:
        return cargas.parse_fecha(texto or "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"La {campo} no es válida (usá AAAA-MM-DD)") from exc


# ══════════════════════════════════════════════════════ autorización para redes

class SocialConsentUpdate(BaseModel):
    granted: bool
    via: str
    note: str | None = None


class SocialConsentAgentUpdate(BaseModel):
    granted: bool
    note: str | None = None


class SocialConsentMerchantUpdate(BaseModel):
    granted: bool


@router.put("/admin/content/merchants/{comercio_id}/social-consent")
def admin_social_consent(comercio_id: str, body: SocialConsentUpdate,
                         claims: dict = Depends(_permiso_consent),
                         crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    """Registra que el comercio autorizó (o retiró) aparecer en las redes y la página de URUKU. Al retirar, las
    piezas que no salieron se saltean y se devuelve lo que ya está publicado."""
    _comercio_o_404(crepo, comercio_id, claims)
    if body.via not in content_consent.VIAS_PANEL:
        raise HTTPException(status_code=400, detail="Vía no válida")
    return content_consent.aplicar(crepo, comercio_id, body.granted, body.via, _actor(claims), body.note)


@router.get("/admin/content/merchants/{comercio_id}/social-consent/history")
def admin_social_consent_history(comercio_id: str, claims: dict = Depends(_permiso_consent),
                                 crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    _comercio_o_404(crepo, comercio_id, claims)
    return {"items": [content_consent.respuesta(f) for f in crepo.list_consents(comercio_id)]}


@router.put("/campo/mis-comercios/{comercio_id}/social-consent")
def campo_social_consent(comercio_id: str, body: SocialConsentAgentUpdate,
                         agente: dict = Depends(auth.require_agente),
                         repo: Repo = Depends(get_repo),
                         crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    """El agente registra, parado en el local, que el dueño aceptó (o que dejó de aceptar)."""
    _propio_o_404(repo, comercio_id, agente)
    r = content_consent.aplicar(crepo, comercio_id, body.granted, content_consent.VIA_AGENTE_VISITA,
                                _actor(agente), body.note)
    return r["consent"] if "consent" in r else r


@router.get("/comercio/social-consent")
def comercio_get_social_consent(claims: dict = Depends(require_comercio_vigente),
                                crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    """Al comerciante sólo se le devuelve si autorizó, por qué vía y cuándo: la nota y quién la registró
    son del equipo de URUKU."""
    r = content_consent.respuesta(content_consent.vigente(crepo, claims["comercio_id"]))
    return {"granted": r["granted"], "via": r["via"], "recorded_at": r["recorded_at"]}


@router.put("/comercio/social-consent")
def comercio_put_social_consent(body: SocialConsentMerchantUpdate, claims: dict = Depends(_comercio_dueno),
                                crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    """El comerciante prende o apaga su autorización desde Mi comercio. No se puede si lo dio de baja el admin (403)."""
    quien = f"comercio:{claims.get('cuenta_id') or claims.get('email') or claims['comercio_id']}"
    r = content_consent.aplicar(crepo, claims["comercio_id"], body.granted, content_consent.VIA_COMERCIO, quien)
    return r["consent"] if "consent" in r else r


# ══════════════════════════════════════════════════════════ banco de fotos

def _merchants(crepo: ContentRepo, fichas: list[dict], hoy: date) -> list[dict]:
    """`ContentMerchantResponse` de cada comercio."""
    if not fichas:
        return []
    ids = [c["id"] for c in fichas]
    consentimientos = crepo.current_consents(ids)
    assets = crepo.list_assets(ids)
    galeria = crepo.gallery_photos(ids)
    planes = {p["slug"]: p for p in crepo.list_planes()}
    propias = crepo.list_own_pieces_since((hoy - timedelta(days=400)).isoformat())
    out = []
    for c in fichas:
        cid = c["id"]
        suyas = [a for a in assets if a["comercio_id"] == cid]
        ultima = max((p["scheduled_for"] for p in propias if p["comercio_id"] == cid), default=None)
        out.append({
            "id": cid, "nombre": c.get("nombre"), "slug": c.get("slug"),
            "rubro": (c.get("rubros") or {}).get("nombre"), "calle": c.get("calle"),
            "ciudad_slug": (c.get("ciudades") or {}).get("slug"), "ciudad_nombre": (c.get("ciudades") or {}).get("nombre"),
            "is_subscriber": content_selector.es_suscriptor(c, content_selector.plan_del(c, planes), hoy),
            "social_consent": content_consent.respuesta(consentimientos.get(cid)),
            "bank_photos": len(suyas), "bank_photos_usable": sum(1 for a in suyas if content_present.sirve_para_video(a)),
            "gallery_photos": sum(1 for g in galeria if g["comercio_id"] == cid),
            "last_piece_on": ultima,
        })
    return out


@router.get("/admin/content/merchants")
def admin_merchants(q: str | None = Query(default=None, max_length=80), ciudad: str | None = Query(default=None, max_length=60),
                    limit: int = Query(default=20, ge=1, le=50), claims: dict = Depends(_permiso_difusion),
                    crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    """Busca el comercio al que se le suben fotos. `recent`: los 5 últimos donde subió quien pregunta. Quien está
    limitado a una ciudad sólo ve la suya: el `?ciudad=` que mande se ignora."""
    ciudad_id = None
    al = _alcance(crepo, claims)
    if al:
        if al.id is None:
            return {"items": [], "recent": []}
        ciudad_id = al.id
    elif ciudad:
        fila = next((c for c in crepo.list_ciudades() if c["slug"] == ciudad), None)
        if not fila:
            raise HTTPException(status_code=400, detail="Ciudad desconocida")
        ciudad_id = fila["id"]
    hoy = cargas.hoy_bolivia()
    items = _merchants(crepo, crepo.search_comercios(q, ciudad_id, limit), hoy)
    ids = crepo.recent_uploaded_comercios(_actor(claims), 5)
    por_id = {c["id"]: c for c in crepo.list_comercios_activos(ids=ids)} if ids else {}
    recientes = _merchants(crepo, [por_id[i] for i in ids if i in por_id and (not al or al.comercio_ok(por_id[i]))], hoy)
    return {"items": items, "recent": recientes}


def _parse_toma(texto: str | None) -> datetime | None:
    """Cuándo sacó la foto el teléfono: ISO 8601, o el `lastModified` del archivo (epoch en ms o en s).
    Sólo se guarda si es creíble (entre 2000 y mañana)."""
    t = (texto or "").strip()
    if not t:
        return None
    if re.fullmatch(r"\d{9,14}", t):
        n = int(t)
        try:
            dt = datetime.fromtimestamp(n / 1000 if n > 10**11 else n, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    else:
        dt = cargas.parse_ts(t)
    if dt is None or not (datetime(2000, 1, 1, tzinfo=timezone.utc) <= dt <= datetime.now(timezone.utc) + timedelta(days=1)):
        return None
    return dt


def _lista_de_fotos(crepo: ContentRepo, comercio_id: str) -> dict:
    """El banco del comercio, con su autorización vigente (`social_consent`, el mismo shape que en el
    panel): la app de campo no tiene otro modo de leerla."""
    r = content_present.asset_list_response(crepo.list_assets([comercio_id]))
    r["social_consent"] = content_consent.respuesta(content_consent.vigente(crepo, comercio_id))
    return r


@router.get("/admin/content/merchants/{comercio_id}/assets")
def admin_list_assets(comercio_id: str, claims: dict = Depends(_permiso_difusion),
                      crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    _comercio_o_404(crepo, comercio_id, claims)
    return _lista_de_fotos(crepo, comercio_id)


@router.get("/campo/mis-comercios/{comercio_id}/content-assets")
def campo_list_assets(comercio_id: str, agente: dict = Depends(auth.require_agente),
                      repo: Repo = Depends(get_repo), crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    _propio_o_404(repo, comercio_id, agente)
    return _lista_de_fotos(crepo, comercio_id)


async def _subir_foto_banco(repo: Repo, crepo: ContentRepo, comercio_id: str, slug: str | None, foto: UploadFile,
                            source: str, actor: str, source_sha256: str | None, taken_at: str | None,
                            show_in_ficha: bool, has_people: bool, people_ok: bool | None) -> dict:
    """La subida de una foto al banco (admin y agente). Idempotente: lo repetido devuelve `duplicate=true`
    sin escribir nada, así la cola del teléfono puede reintentar sin miedo."""
    if not content_storage.dir_seguro() or not content_storage.asegurar_dir():
        raise HTTPException(status_code=503, detail=MSG_NO_CONFIGURADO)
    if has_people and people_ok is not True:
        raise _error(409, "people_not_confirmed", "Confirmá que las personas de la foto aceptaron aparecer")
    sha_origen = (source_sha256 or "").strip().lower() or None
    if sha_origen and not _RE_SHA.match(sha_origen):
        raise HTTPException(status_code=400, detail="source_sha256 no es válido")
    data = await foto.read()
    if not data:
        raise HTTPException(status_code=400, detail="Falta la foto")
    if len(data) > _MAX_FOTO_BYTES:
        raise HTTPException(status_code=413, detail="La foto supera los 15 MB")

    def respuesta(asset: dict, duplicado: bool, ficha: dict | None = None, avisos: list[str] | None = None) -> dict:
        return {"ok": True, "duplicate": duplicado, "asset": content_present.asset_response(asset),
                "ficha": ficha or {"requested": bool(show_in_ficha), "added": False, "reason": None},
                "warnings": avisos or []}

    previo = await run_in_threadpool(crepo.find_asset, comercio_id, None, sha_origen) if sha_origen else None
    if previo:
        return respuesta(previo, True)
    if not content_storage.hay_lugar(len(data)):
        raise HTTPException(status_code=507, detail=MSG_TOPE_DISCO)
    try:
        proc = await run_in_threadpool(content_storage.procesar_foto, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="El archivo no es una imagen válida") from exc
    previo = await run_in_threadpool(crepo.find_asset, comercio_id, proc["sha256"], None)
    if previo:
        return respuesta(previo, True)

    asset_id = content_storage.nuevo_id()
    try:
        rel_foto, rel_thumb = await run_in_threadpool(content_storage.guardar_foto, comercio_id, asset_id, proc)
    except OSError as exc:
        logger.warning("content.banco_guardado_fallo", comercio=comercio_id, exc_info=True)
        raise HTTPException(status_code=502, detail="No se pudo guardar la foto, probá de nuevo") from exc
    captura = _parse_toma(taken_at)
    fila = {"id": asset_id, "comercio_id": comercio_id, "kind": "photo", "source": source, "file_path": rel_foto,
            "thumb_path": rel_thumb, "sha256": proc["sha256"], "source_sha256": sha_origen, "width": proc["width"],
            "height": proc["height"], "bytes": proc["bytes"], "taken_at": captura.isoformat() if captura else None,
            "usable_for_social": True, "has_people": bool(has_people), "people_ok": people_ok if has_people else None,
            "uploaded_by": actor}
    try:
        asset = await run_in_threadpool(crepo.insert_asset, fila)
    except ContentConflict:
        # Dos subidas iguales a la vez: el índice único dejó pasar a una. Gana la que ya estaba.
        content_storage.borrar(rel_foto)
        content_storage.borrar(rel_thumb)
        previo = await run_in_threadpool(crepo.find_asset, comercio_id, proc["sha256"], sha_origen)
        if previo:
            return respuesta(previo, True)
        raise HTTPException(status_code=409, detail="Esa foto ya está en el banco") from None
    except Exception:
        content_storage.borrar(rel_foto)
        content_storage.borrar(rel_thumb)
        raise

    ficha = {"requested": bool(show_in_ficha), "added": False, "reason": None}
    if show_in_ficha:
        ficha = await _copiar_a_la_ficha(repo, crepo, comercio_id, slug, data, asset, ficha)
    avisos: list[str] = []
    if min(proc["width"], proc["height"]) < content_storage.LADO_MENOR_MINIMO:
        avisos.append("La foto es chica: se guarda, pero no entra en los videos")
    if not content_consent.esta_autorizado(crepo, comercio_id):
        avisos.append("Se guarda igual, pero no sale en las redes ni en la página hasta registrar la autorización")
    logger.info("content.banco_foto_subida", comercio=comercio_id, asset=asset_id, source=source, por=actor,
                bytes=proc["bytes"])
    return respuesta(asset, False, ficha, avisos)


async def _copiar_a_la_ficha(repo: Repo, crepo: ContentRepo, comercio_id: str, slug: str | None, data: bytes,
                             asset: dict, ficha: dict) -> dict:
    """«Mostrar también en la ficha»: una copia en la galería, con el tope del plan. Un 409 de tope NO
    frena la subida al banco (`ficha.reason = "tope"`)."""
    comercio = await run_in_threadpool(repo.get_comercio, comercio_id)
    if not comercio:
        return {**ficha, "reason": "error"}
    try:
        subida = await run_in_threadpool(fotos_galeria.preparar, repo, comercio, reemplazar=None, extra=None,
                                         puede_pagar=False)
    except HTTPException as exc:
        return {**ficha, "reason": "tope" if exc.status_code == 409 else "error"}
    try:
        url, thumb = await run_in_threadpool(subir_foto_galeria, slug or comercio.get("slug") or comercio_id, data)
        if not url:
            return {**ficha, "reason": "error"}
        fila = await run_in_threadpool(fotos_galeria.registrar, repo, comercio, subida, url, thumb)
        if fila and fila.get("id"):
            await run_in_threadpool(crepo.update_asset, asset["id"], {"gallery_photo_id": fila["id"]})
        return {**ficha, "added": True}
    except Exception:  # noqa: BLE001
        logger.warning("content.banco_ficha_fallo", comercio=comercio_id, exc_info=True)
        return {**ficha, "reason": "error"}


@router.post("/admin/content/merchants/{comercio_id}/assets")
async def admin_upload_asset(
    comercio_id: str, foto: UploadFile = File(...), source_sha256: str | None = Form(None),
    taken_at: str | None = Form(None), show_in_ficha: bool = Form(False), has_people: bool = Form(False),
    people_ok: bool | None = Form(None), claims: dict = Depends(_permiso_difusion),
    repo: Repo = Depends(get_repo), crepo: ContentRepo = Depends(get_content_repo),
) -> dict:
    c = await run_in_threadpool(_comercio_o_404, crepo, comercio_id, claims)
    return await _subir_foto_banco(repo, crepo, comercio_id, c.get("slug"), foto, "admin_upload", _actor(claims),
                                   source_sha256, taken_at, show_in_ficha, has_people, people_ok)


@router.post("/campo/mis-comercios/{comercio_id}/content-assets")
async def campo_upload_asset(
    comercio_id: str, foto: UploadFile = File(...), source_sha256: str | None = Form(None),
    taken_at: str | None = Form(None), show_in_ficha: bool = Form(False), has_people: bool = Form(False),
    people_ok: bool | None = Form(None), agente: dict = Depends(auth.require_agente),
    repo: Repo = Depends(get_repo), crepo: ContentRepo = Depends(get_content_repo),
) -> dict:
    """El agente sube al banco del comercio de SU ciudad. Con `show_in_ficha` respeta el tope de la galería y no reemplaza."""
    comercio = await run_in_threadpool(_propio_o_404, repo, comercio_id, agente)
    return await _subir_foto_banco(repo, crepo, comercio_id, comercio.get("slug"), foto, "agent_upload",
                                   _actor(agente), source_sha256, taken_at, show_in_ficha, has_people, people_ok)


class ContentAssetUpdate(BaseModel):
    usable_for_social: bool | None = None
    has_people: bool | None = None
    people_ok: bool | None = None


def _asset_o_404(crepo: ContentRepo, asset_id: str, claims: dict | None = None) -> dict:
    a = crepo.get_asset(asset_id)
    if not a or not a.get("activo"):
        raise HTTPException(status_code=404, detail="Foto no encontrada")
    al = _alcance(crepo, claims)
    if al and not al.comercio_ok(crepo.get_comercio_ficha(a.get("comercio_id"))):
        raise HTTPException(status_code=404, detail="Foto no encontrada")
    return a


@router.patch("/admin/content/assets/{asset_id}")
def admin_update_asset(asset_id: str, body: ContentAssetUpdate, claims: dict = Depends(_permiso_difusion),
                       crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    _asset_o_404(crepo, asset_id, claims)
    pedidos = body.model_fields_set
    patch = {k: getattr(body, k) for k in ("usable_for_social", "has_people") if k in pedidos and getattr(body, k) is not None}
    if "people_ok" in pedidos:
        patch["people_ok"] = body.people_ok
    if not patch:
        raise HTTPException(status_code=400, detail="No hay nada que cambiar")
    nueva = crepo.update_asset(asset_id, patch)
    if not nueva:
        raise HTTPException(status_code=404, detail="Foto no encontrada")
    if not content_storage.asset_sirve(nueva):
        # «No usar en redes» (o personas sin confirmar): las piezas vivas que la usan buscan reemplazo o se saltean.
        content_selector.retirar_asset_de_piezas(crepo, asset_id, _actor(claims))
    return content_present.asset_response(nueva)


@router.delete("/admin/content/assets/{asset_id}")
def admin_delete_asset(asset_id: str, claims: dict = Depends(_permiso_difusion),
                       crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    """Baja lógica: la fila queda y el archivo se borra a los `CONTENT_ASSET_PURGE_DAYS` días."""
    _asset_o_404(crepo, asset_id, claims)
    crepo.update_asset(asset_id, {"activo": False, "deactivated_by": _actor(claims),
                                  "deactivated_at": datetime.now(timezone.utc).isoformat()})
    content_selector.retirar_asset_de_piezas(crepo, asset_id, _actor(claims))
    return {"ok": True}


# ════════════════════════════════════════════════════ semana, piezas y revisión

def _pieza_o_404(crepo: ContentRepo, piece_id: str, claims: dict | None = None) -> dict:
    p = crepo.get_piece(piece_id)
    if not p:
        raise HTTPException(status_code=404, detail="Pieza no encontrada")
    al = _alcance(crepo, claims)
    if al and not al.pieza_ok(crepo, p):
        raise HTTPException(status_code=404, detail="Pieza no encontrada")
    return p


def _devolver(crepo: ContentRepo, piece_id: str) -> dict:
    return content_present.cargar_pieza(crepo, _pieza_o_404(crepo, piece_id))


def _de_su_ciudad(crepo: ContentRepo, claims: dict, piezas: list[dict]) -> list[dict]:
    """Las piezas de la lista que quien pregunta puede ver (todas, salvo que esté limitado a una ciudad)."""
    al = _alcance(crepo, claims)
    return al.piezas(crepo, piezas) if al else piezas


@router.get("/admin/content/week")
def admin_week(start: str | None = Query(default=None, max_length=10), claims: dict = Depends(_permiso_difusion),
               crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    hoy = cargas.hoy_bolivia()
    lunes = content_selector.lunes_de(hoy) if not start else _fecha_o_400(start, "fecha")
    if lunes.weekday() != 0:
        raise HTTPException(status_code=400, detail="La fecha tiene que ser un lunes")
    piezas = _de_su_ciudad(crepo, claims, crepo.list_pieces(date_from=lunes.isoformat(),
                                                             date_to=(lunes + timedelta(days=6)).isoformat()))
    dias = []
    for i in range(7):
        d = lunes + timedelta(days=i)
        dias.append({"date": d.isoformat(), "weekday_label": content_present.WEEKDAY_LABEL[i],
                     "pieces": [content_present.piece_summary(p) for p in piezas if str(p["scheduled_for"])[:10] == d.isoformat()]})
    return {"week_start": lunes.isoformat(), "days": dias, "queue": _cola(crepo, claims)}


def _cola(crepo: ContentRepo, claims: dict) -> dict:
    """Cuántas piezas hay en cada estado. Para quien está limitado a una ciudad, sólo las de ella."""
    if not _alcance(crepo, claims):
        return crepo.count_pieces_by_status()
    cola: dict[str, int] = {}
    for p in _de_su_ciudad(crepo, claims, crepo.list_pieces(limit=1000)):
        cola[p["status"]] = cola.get(p["status"], 0) + 1
    return cola


class ContentWeekPlanCreate(BaseModel):
    week_start: date | None = None


@router.post("/admin/content/week/plan")
def admin_plan_week(body: ContentWeekPlanCreate | None = None, claims: dict = Depends(_permiso_difusion),
                    repo: Repo = Depends(get_repo), crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    """Corre el selector a mano (para arrancar sin esperar al domingo). Idempotente. Planifica TODAS las ciudades:
    quien está limitado a una no lo corre (403)."""
    if _ciudad_limitada(claims):
        raise HTTPException(status_code=403, detail="Sólo podés ver tu ciudad")
    hoy = cargas.hoy_bolivia()
    pedida = body.week_start if body else None
    if pedida is None:
        pedida = content_selector.lunes_de(hoy) + (
            timedelta(days=7) if hoy.weekday() == settings.content_planning_weekday else timedelta(0))
    if pedida.weekday() != 0:
        raise HTTPException(status_code=400, detail="La fecha tiene que ser un lunes")
    if pedida + timedelta(days=6) < hoy:
        raise HTTPException(status_code=400, detail="Esa semana ya pasó")
    return content_selector.plan_week(repo, crepo, pedida, _actor(claims))


@router.get("/admin/content/pieces")
def admin_list_pieces(status: str = Query(default=_ESTADOS_DE_REVISION, max_length=200),
                      claims: dict = Depends(_permiso_difusion),
                      crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    estados = [s.strip() for s in status.split(",") if s.strip()]
    if not estados or any(s not in _STATUS for s in estados):
        raise HTTPException(status_code=400, detail="Estado desconocido")
    piezas = crepo.list_pieces(statuses=estados, limit=200)
    return {"items": content_present.cargar_piezas(crepo, _de_su_ciudad(crepo, claims, piezas))}


@router.get("/admin/content/pieces/{piece_id}")
def admin_get_piece(piece_id: str, claims: dict = Depends(_permiso_difusion),
                    crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    _pieza_o_404(crepo, piece_id, claims)
    return _devolver(crepo, piece_id)


class ContentPieceUpdate(BaseModel):
    caption_tiktok: str | None = None
    caption_ig: str | None = None
    caption_channel: str | None = None
    hashtags: list[str] | None = None


_CAMPO_DE_RED = (("caption_tiktok", "tiktok", "TikTok"), ("caption_ig", "instagram", "Instagram"),
                 ("caption_channel", "channel", "el canal"))


@router.patch("/admin/content/pieces/{piece_id}")
def admin_edit_piece(piece_id: str, body: ContentPieceUpdate, claims: dict = Depends(_permiso_difusion),
                     crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    """Edita los textos. Pasan por el mismo validador (menos «números ajenos»: la persona puede querer uno)."""
    pieza = _pieza_o_404(crepo, piece_id, claims)
    if pieza["status"] in ("approved", "published"):
        raise HTTPException(status_code=409, detail="La pieza ya está aprobada")
    if pieza["status"] == "skipped":
        raise HTTPException(status_code=409, detail="La pieza fue salteada")
    facts = pieza.get("facts") or {}
    patch: dict = {}
    objeciones: list[str] = []
    for campo, red, etiqueta in _CAMPO_DE_RED:
        if campo not in body.model_fields_set or getattr(body, campo) is None:
            continue
        texto = content_captions.normalizar_texto(getattr(body, campo)).strip()      # lo guardado es lo validado
        if not texto:
            raise HTTPException(status_code=400, detail=f"El texto de {etiqueta} no puede quedar vacío")
        objeciones += [f"{etiqueta}: {o}" for o in content_captions.validate_caption(texto, facts, red)
                       if not o.startswith("El número ")]
        patch[campo] = texto
    if "hashtags" in body.model_fields_set and body.hashtags is not None:
        limpios = [content_captions.normalizar_texto(t).strip() for t in body.hashtags]
        etiquetas = [t if t.startswith("#") else f"#{t}" for t in limpios if t]
        objeciones += content_captions.validate_hashtags(etiquetas, facts)
        patch["hashtags"] = etiquetas
    if not patch:
        raise HTTPException(status_code=400, detail="No hay nada que cambiar")
    if objeciones:
        raise HTTPException(status_code=400, detail="; ".join(objeciones))
    final = {**pieza, **patch}
    patch["caption_edited"] = True
    patch["caption_checks"] = content_captions.validate_piece(
        facts, final.get("caption_tiktok"), final.get("caption_ig"), final.get("caption_channel"),
        final.get("hashtags"), ignorar_numeros=True)
    nueva = crepo.update_piece(piece_id, patch, if_status=["queued", "rendering", "ready_for_review", "failed"])
    if not nueva:
        raise HTTPException(status_code=409, detail="La pieza ya está aprobada")
    return _devolver(crepo, piece_id)


# ── pedir un video a mano (§17.3) ──

_RE_SLUG = r"^[a-z0-9][a-z0-9-]{0,79}$"


class ContentPieceRequest(BaseModel):
    """`{"kind": "comercio", "comercio_id"}` o `{"kind": "rubro", "rubro_slug", "ciudad_slug"}`."""
    kind: Literal["comercio", "rubro"]
    comercio_id: str | None = Field(default=None, max_length=64)
    rubro_slug: str | None = Field(default=None, pattern=_RE_SLUG)
    ciudad_slug: str | None = Field(default=None, pattern=_RE_SLUG)

    @field_validator("comercio_id")
    @classmethod
    def _es_uuid(cls, v: str | None) -> str | None:
        """El id de un comercio es un UUID: algo distinto llegaba a la base y volvía como 500."""
        return None if v is None else _uuid_de_comercio(v)

    @model_validator(mode="after")
    def _completo(self):
        if self.kind == "comercio" and not self.comercio_id:
            raise ValueError("Falta comercio_id")
        if self.kind == "rubro" and not (self.rubro_slug and self.ciudad_slug):
            raise ValueError("Faltan rubro_slug y ciudad_slug")
        return self


def _uuid_de_comercio(valor: str) -> str:
    """El UUID en su forma canónica (minúsculas, con guiones); ValueError (-> 422) si no lo es."""
    try:
        return str(uuid.UUID(valor.strip()))
    except (ValueError, AttributeError) as exc:
        raise ValueError("comercio_id tiene que ser un UUID") from exc


@router.post("/admin/content/pieces/request", status_code=201)
def admin_request_piece(body: ContentPieceRequest, claims: dict = Depends(_permiso_difusion),
                        crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    """«Pedir un video»: de un negocio o de un rubro en una ciudad. Crea una pieza `queued` (origen `pedido`: sin
    cuota ni tareas). 422 con el motivo si el comercio o el rubro no alcanzan; 429 con 5 pedidos armándose."""
    limite = _ciudad_limitada(claims)
    if body.kind == "comercio":
        pieza = content_requests.pedir_comercio(crepo, body.comercio_id, _actor(claims), limite)
    else:
        pieza = content_requests.pedir_rubro(crepo, body.rubro_slug, body.ciudad_slug, _actor(claims), limite)
    return content_present.cargar_pieza(crepo, pieza)


@router.get("/admin/content/request-options")
def admin_request_options(ciudad_slug: str = Query(min_length=1, max_length=80, pattern=_RE_SLUG),
                          claims: dict = Depends(_permiso_difusion),
                          crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    """Los rubros que se pueden pedir en una ciudad, con cuántos comercios cumplen las condiciones (`eligible`).
    Sólo para el panel interno: ese número no se muestra al público."""
    limite = _ciudad_limitada(claims)
    if limite and ciudad_slug != limite:
        raise HTTPException(status_code=403, detail="Sólo podés ver tu ciudad")
    return {"rubros": content_requests.opciones_de_ciudad(crepo, ciudad_slug)}


@router.get("/admin/content/merchants/{comercio_id}/request-check")
def admin_request_check(comercio_id: str, claims: dict = Depends(_permiso_difusion),
                        crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    """Antes de pedir el video de un negocio: ¿tiene autorización?, ¿cuántas fotos sirven hoy? y, si no se puede,
    el motivo (el mismo texto que daría el 422)."""
    comercio = crepo.get_comercio_ficha(comercio_id)
    limite = _ciudad_limitada(claims)
    if not comercio or (limite and (comercio.get("ciudades") or {}).get("slug") != limite):
        raise HTTPException(status_code=404, detail="Comercio no encontrado")
    d = content_requests.diagnostico_comercio(crepo, comercio, cargas.hoy_bolivia())
    return {"consent": d["consent"], "usable_photos": d["usable_photos"], "ok": d["ok"], "reason": d["reason"]}


# ── textos del video v2 (§16.9) ──

#: Estados en los que se pueden cambiar los textos del video (y re-armarlo).
_ESTADOS_DE_TEXTOS = ["queued", "ready_for_review", "failed"]
_MSG_NO_EDITABLE = {
    "rendering": "La pieza se está armando: esperá a que termine para cambiar los textos del video",
    "approved": "La pieza ya está aprobada",
    "published": "La pieza ya está publicada",
    "skipped": "La pieza fue salteada",
}


class VideoTextsChip(BaseModel):
    """La frase de UNA foto. `source_id` es el `id` de la fuente (`sources[].id` de la pieza)."""
    source_id: str = Field(max_length=64)
    text: str | None = Field(default=None, max_length=200)


class VideoTextsUpdate(BaseModel):
    kick: str | None = Field(default=None, max_length=200)
    title1: str = Field(max_length=200)
    title2: str = Field(max_length=200)
    subtitle: str | None = Field(default=None, max_length=200)
    search_term: str = Field(max_length=200)
    chips: list[VideoTextsChip] = Field(default_factory=list, max_length=12)
    photo_flags_ok: bool | None = None


def _exigir_pieza_editable(pieza: dict) -> None:
    """409 si la pieza no admite cambiar los textos del video."""
    if pieza["status"] not in _ESTADOS_DE_TEXTOS:
        raise HTTPException(status_code=409, detail=_MSG_NO_EDITABLE.get(pieza["status"], "La pieza no se puede cambiar ahora"))


def _volver_a_armar(pieza: dict) -> dict:
    """El UPDATE que re-encola el video: sólo si estaba lista o con problemas (en `queued` ya está en la cola).
    El video viejo queda hasta que el nuevo termine bien (§4.4)."""
    if pieza["status"] in ("ready_for_review", "failed"):
        return {"status": "queued", "render_attempts": 0, "render_error": None, "render_started_at": None,
                "render_next_at": datetime.now(timezone.utc).isoformat()}
    return {}


@router.patch("/admin/content/pieces/{piece_id}/video-texts")
def admin_edit_video_texts(piece_id: str, body: VideoTextsUpdate, claims: dict = Depends(_permiso_difusion),
                           crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    """Guarda los textos del video que corrigió una persona. Pasan por el mismo validador (400 con la objeción)
    y la pieza vuelve a la cola para armarse de nuevo (en `queued` sólo se guardan). En `ofertas` y `rubro` el chip es
    el nombre del comercio y no se edita: las frases que lleguen se ignoran."""
    pieza = _pieza_o_404(crepo, piece_id, claims)
    _exigir_pieza_editable(pieza)
    fuentes = crepo.list_sources(piece_id)
    por_id = {f["id"]: f for f in fuentes}
    if any(c.source_id not in por_id for c in body.chips):
        raise HTTPException(status_code=400, detail="Una de las frases no es de una foto de esta pieza")
    pilar = pieza["pillar"]
    textos = content_video_texts.normalizar_textos(body.model_dump())
    nuevos = ({} if pilar in content_video_texts.PILARES_CON_NOMBRE
              else {c.source_id: content_video_texts.limpiar(c.text) for c in body.chips})
    chips = [nuevos[f["id"]] if f["id"] in nuevos else f.get("chip_text") for f in fuentes]
    objeciones = content_video_texts.validate_video_texts(textos, chips, pilar, pieza.get("facts"))
    if objeciones:
        raise HTTPException(status_code=400, detail="; ".join(objeciones))
    # Si los textos y las frases quedan IGUAL a lo guardado y sólo cambia «revisé las fotos marcadas», se guarda
    # eso solo: no hay nada que volver a armar, así que no se re-encola ni se toca el estado.
    guardados = pieza.get("video_texts") or {}
    iguales = bool(guardados) and all(guardados.get(c) == textos[c] for c in content_video_texts.CAMPOS) and all(
        texto == por_id[fuente_id].get("chip_text") for fuente_id, texto in nuevos.items())
    if iguales:
        solo: dict = {}
        if body.photo_flags_ok is not None and body.photo_flags_ok != bool(pieza.get("photo_flags_ok")):
            solo["photo_flags_ok"] = body.photo_flags_ok
        if pieza.get("video_texts_checks"):
            # Pasaron el validador tal como están: las objeciones viejas ya no valen (y una persona los confirmó).
            solo["video_texts_checks"] = []
            solo["video_texts_engine"] = "human"
        if solo and not crepo.update_piece(piece_id, solo, if_status=_ESTADOS_DE_TEXTOS):
            raise HTTPException(status_code=409, detail="La pieza cambió mientras tanto, abrila de nuevo")
        return _devolver(crepo, piece_id)
    patch = {"video_texts": content_video_texts.armar_textos(textos, pilar, pieza.get("facts") or {}),
             "video_texts_engine": "human", "video_texts_checks": [], "template_version": 2,
             **_volver_a_armar(pieza)}
    if body.photo_flags_ok is not None:
        patch["photo_flags_ok"] = body.photo_flags_ok
    # Primero el UPDATE condicional de la pieza (si cambió de estado mientras tanto, 409 y NO se toca nada más) y
    # recién después las frases de las fotos.
    if not crepo.update_piece(piece_id, patch, if_status=_ESTADOS_DE_TEXTOS):
        raise HTTPException(status_code=409, detail="La pieza cambió mientras tanto, abrila de nuevo")
    for fuente_id, texto in nuevos.items():
        crepo.update_source(fuente_id, {"chip_text": texto})
    return _devolver(crepo, piece_id)


#: Cada «pedir otra propuesta» puede llamar a Gemini (con fotos): una por pieza cada `ENFRIAMIENTO_PROPUESTA_SEG`.
ENFRIAMIENTO_PROPUESTA_SEG = 60
_ultima_propuesta: dict[str, float] = {}


def reiniciar_enfriamiento_de_propuestas() -> None:
    _ultima_propuesta.clear()


def _enfriar_propuesta(piece_id: str) -> None:
    """429 si ya se pidió otra propuesta de esta pieza hace menos de un minuto (en memoria de este proceso)."""
    ahora = time.monotonic()
    espera = ENFRIAMIENTO_PROPUESTA_SEG - (ahora - _ultima_propuesta.get(piece_id, -1e9))
    if espera > 0:
        raise HTTPException(status_code=429, detail=f"Esperá {int(espera) + 1} segundos para pedir otra propuesta")
    if len(_ultima_propuesta) > 2000:
        for k in [k for k, t in _ultima_propuesta.items() if ahora - t >= ENFRIAMIENTO_PROPUESTA_SEG]:
            del _ultima_propuesta[k]
    _ultima_propuesta[piece_id] = ahora


@router.post("/admin/content/pieces/{piece_id}/video-texts/propose")
def admin_propose_video_texts(piece_id: str, claims: dict = Depends(_permiso_difusion),
                              crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    """«Pedir otra propuesta»: vuelve a pedirle a Gemini las frases mirando las fotos y re-encola el video (mismos
    409 que el PATCH; 429 si se pidió otra hace menos de 60 s). Sin Gemini, o si falla, salen los textos fijos.
    Pisa lo que se haya escrito a mano."""
    pieza = _pieza_o_404(crepo, piece_id, claims)
    _exigir_pieza_editable(pieza)
    _enfriar_propuesta(piece_id)
    nueva = content_video_texts.proponer_y_guardar(crepo, pieza, {**_volver_a_armar(pieza), "template_version": 2},
                                                   if_status=_ESTADOS_DE_TEXTOS)
    if not nueva:
        raise HTTPException(status_code=409, detail="La pieza cambió mientras tanto, abrila de nuevo")
    return _devolver(crepo, piece_id)


class ContentPieceSourcesUpdate(BaseModel):
    remove_positions: list[int] = Field(min_length=1, max_length=6)


@router.put("/admin/content/pieces/{piece_id}/sources")
def admin_change_sources(piece_id: str, body: ContentPieceSourcesUpdate, claims: dict = Depends(_permiso_difusion),
                         crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    """«Cambiar fotos»: quita las marcadas, busca reemplazos y vuelve a armar el video."""
    pieza = _pieza_o_404(crepo, piece_id, claims)
    if pieza["status"] not in ("ready_for_review", "failed"):
        raise HTTPException(status_code=409, detail="Sólo se cambian las fotos de una pieza lista para revisar o con problemas")
    content_selector.cambiar_fotos(crepo, pieza, body.remove_positions)
    nueva = crepo.update_piece(piece_id, {
        "status": "queued", "render_attempts": 0, "render_error": None, "render_started_at": None,
        "render_next_at": datetime.now(timezone.utc).isoformat()}, if_status=["ready_for_review", "failed"])
    if not nueva:
        raise HTTPException(status_code=409, detail="La pieza cambió mientras tanto, abrila de nuevo")
    return _devolver(crepo, piece_id)


@router.post("/admin/content/pieces/{piece_id}/approve")
def admin_approve_piece(piece_id: str, claims: dict = Depends(_permiso_difusion),
                        crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    _pieza_o_404(crepo, piece_id, claims)
    content_posts.approve(crepo, piece_id, _actor(claims))
    return _devolver(crepo, piece_id)


class ContentPieceBatchApprove(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=20)


@router.post("/admin/content/pieces/approve-batch")
def admin_approve_batch(body: ContentPieceBatchApprove, claims: dict = Depends(_permiso_difusion),
                        crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    """Aprueba de una vez las que están en verde (sin objeciones y sin editar)."""
    if _alcance(crepo, claims):
        for piece_id in body.ids:                       # una de otra ciudad: 404, y no se aprueba ninguna
            _pieza_o_404(crepo, piece_id, claims)
    return content_posts.approve_batch(crepo, body.ids, _actor(claims))


class ContentPieceSkip(BaseModel):
    reason: str
    note: str | None = None


@router.post("/admin/content/pieces/{piece_id}/skip")
def admin_skip_piece(piece_id: str, body: ContentPieceSkip, claims: dict = Depends(_permiso_difusion),
                     crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    if body.reason not in ("bad_photos", "merchant_asked", "other"):
        raise HTTPException(status_code=400, detail="Motivo no válido")
    nota = (body.note or "").strip() or None
    if nota and len(nota) > 300:
        raise HTTPException(status_code=400, detail="La nota admite hasta 300 caracteres")
    pieza = _pieza_o_404(crepo, piece_id, claims)
    if pieza["status"] == "published":
        raise HTTPException(status_code=409, detail="Ya está publicada")
    if pieza["status"] == "skipped":
        raise HTTPException(status_code=409, detail="Ya está salteada")
    ahora = datetime.now(timezone.utc).isoformat()
    nueva = crepo.update_piece(piece_id, {"status": "skipped", "skip_reason": body.reason, "skip_note": nota,
                                          "skipped_by": _actor(claims), "skipped_at": ahora},
                               if_status=["queued", "rendering", "ready_for_review", "approved", "failed"])
    if not nueva:
        raise HTTPException(status_code=409, detail="Ya está publicada")
    for post in crepo.list_posts([piece_id]):
        if post["status"] in ("pending", "claimed"):
            crepo.update_post(post["id"], {"status": "skipped", "skip_reason": "pieza salteada", "claimed_by": None,
                                           "claimed_at": None}, if_status=["pending", "claimed"])
    return _devolver(crepo, piece_id)


@router.post("/admin/content/pieces/{piece_id}/retry")
def admin_retry_piece(piece_id: str, claims: dict = Depends(_permiso_difusion),
                      crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    pieza = _pieza_o_404(crepo, piece_id, claims)
    if pieza["status"] != "failed":
        raise HTTPException(status_code=409, detail="Sólo se reintenta una pieza con problemas")
    nueva = crepo.update_piece(piece_id, {"status": "queued", "render_attempts": 0, "render_error": None,
                                          "render_started_at": None,
                                          "render_next_at": datetime.now(timezone.utc).isoformat()}, if_status="failed")
    if not nueva:
        raise HTTPException(status_code=409, detail="Sólo se reintenta una pieza con problemas")
    return _devolver(crepo, piece_id)


@router.get("/admin/content/pieces/{piece_id}/download-links")
def admin_download_links(piece_id: str, claims: dict = Depends(_permiso_difusion),
                         crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    """Los links para bajar el video y la portada: firmados, vencen a los 15 minutos."""
    pieza = _pieza_o_404(crepo, piece_id, claims)
    if pieza["status"] not in content_present.CON_VIDEO or not pieza.get("video_path"):
        raise HTTPException(status_code=404, detail="La pieza todavía no tiene video")
    if pieza.get("files_purged_at"):
        raise HTTPException(status_code=410, detail="El video ya se borró por antigüedad")
    video = content_storage.ruta_firmada("piece", piece_id, "video")
    return {"video_url": video, "video_download_url": f"{video}&download=1",
            "cover_url": content_storage.ruta_firmada("piece", piece_id, "cover"),
            "expires_at": content_storage.vence_en().isoformat()}


# ═══════════════════════════════════════════════════════ paquete del día y redes

def _entrega(crepo: ContentRepo, pieza: dict, posts: list[dict], firmante: str | None) -> dict | None:
    """La tarea de entregar el video a mano (`piece_delivery`): sin WhatsApp (§15), con el link para bajarlo."""
    if not pieza.get("comercio_id") or pieza["status"] != "published":
        return None
    tareas = [t for t in crepo.list_tasks(status="open", comercio_id=pieza["comercio_id"], kinds=["piece_delivery"])
              if t.get("piece_id") == pieza["id"]]
    if not tareas:
        return None
    return {"task_id": tareas[0]["id"], "whatsapp": None, "message_text": None,
            "download_url": content_present.url_de_descarga(pieza)}


@router.get("/admin/content/today")
def admin_today(date_: str | None = Query(default=None, alias="date", max_length=10),
                claims: dict = Depends(_permiso_difusion), crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    """El «Paquete del día»: lo aprobado para hoy con una fila por red, lo atrasado y lo que falta aprobar."""
    hoy = _fecha_o_400(date_) if date_ else cargas.hoy_bolivia()
    firmante = claims.get("nombre")
    ahora = datetime.now(timezone.utc)

    def item(p: dict, posts: list[dict]) -> dict:
        return {"piece": content_present.piece_summary(p),
                "posts": [content_present.post_response(p, x, ahora) for x in posts],
                "delivery": _entrega(crepo, p, posts, firmante)}

    del_dia = _de_su_ciudad(crepo, claims, crepo.list_pieces(date_from=hoy.isoformat(), date_to=hoy.isoformat()))
    aprobadas = [p for p in del_dia if p["status"] in ("approved", "published")]
    atrasadas = _de_su_ciudad(crepo, claims, crepo.list_pieces(
        statuses=["approved"], date_to=(hoy - timedelta(days=1)).isoformat()))
    posts = crepo.list_posts([p["id"] for p in aprobadas + atrasadas]) if (aprobadas or atrasadas) else []
    por_pieza: dict[str, list[dict]] = {}
    for x in posts:
        por_pieza.setdefault(x["piece_id"], []).append(x)
    abiertos = ("pending", "claimed")
    siguiente = _de_su_ciudad(crepo, claims, crepo.list_pieces(
        statuses=["queued", "rendering", "ready_for_review", "approved"],
        date_from=(hoy + timedelta(days=1)).isoformat(), limit=1 if not _alcance(crepo, claims) else 100))
    return {
        "date": hoy.isoformat(),
        "items": [item(p, por_pieza.get(p["id"], [])) for p in aprobadas],
        "overdue": [item(p, por_pieza.get(p["id"], [])) for p in atrasadas
                    if any(x["status"] in abiertos for x in por_pieza.get(p["id"], []))],
        "pending_review": [content_present.piece_summary(p) for p in del_dia
                           if p["status"] in ("queued", "rendering", "ready_for_review")],
        "next": ({"date": siguiente[0]["scheduled_for"],
                  "pillar_label": content_present.PILLAR_LABEL.get(siguiente[0]["pillar"], siguiente[0]["pillar"])}
                 if siguiente else None),
    }


def _post_devuelto(crepo: ContentRepo, post: dict) -> dict:
    pieza = _pieza_o_404(crepo, post["piece_id"])
    return content_present.post_response(pieza, post)


def _exigir_post_visible(crepo: ContentRepo, post_id: str, claims: dict) -> None:
    """404 si el posteo es de una pieza de otra ciudad (para quien está limitado a una)."""
    if not _alcance(crepo, claims):
        return
    post = crepo.get_post(post_id)
    if post:
        _pieza_o_404(crepo, post["piece_id"], claims)


@router.post("/admin/content/posts/{post_id}/claim")
def admin_claim_post(post_id: str, claims: dict = Depends(_permiso_difusion),
                     crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    _exigir_post_visible(crepo, post_id, claims)
    return _post_devuelto(crepo, content_posts.claim(crepo, post_id, _actor(claims)))


@router.post("/admin/content/posts/{post_id}/release")
def admin_release_post(post_id: str, claims: dict = Depends(_permiso_difusion),
                       crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    _exigir_post_visible(crepo, post_id, claims)
    return _post_devuelto(crepo, content_posts.release(crepo, post_id, _actor(claims)))


class ContentPostPublish(BaseModel):
    post_url: str | None = None
    without_link: bool = False


@router.post("/admin/content/posts/{post_id}/posted")
def admin_posted(post_id: str, body: ContentPostPublish, claims: dict = Depends(_permiso_difusion),
                 crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    """«Salió»: con el link de la publicación, o «salió sin link». Si era la última red, la pieza queda publicada."""
    _exigir_post_visible(crepo, post_id, claims)
    return _post_devuelto(crepo, content_posts.mark_posted(crepo, post_id, _actor(claims), body.post_url, body.without_link))


class ContentPostSkip(BaseModel):
    reason: str


@router.post("/admin/content/posts/{post_id}/skip")
def admin_skip_post(post_id: str, body: ContentPostSkip, claims: dict = Depends(_permiso_difusion),
                    crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    _exigir_post_visible(crepo, post_id, claims)
    return _post_devuelto(crepo, content_posts.skip_post(crepo, post_id, _actor(claims), body.reason))


@router.get("/admin/content/status")
def admin_content_status(_claims: dict = Depends(_permiso_difusion),
                         crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    """Para debug remoto: ¿el render está vivo? la cola, el disco y si Gemini está configurado."""
    return {"render_worker": content_render.estado_del_worker(), "current_piece_id": content_render.pieza_en_curso(),
            "queue": crepo.count_pieces_by_status(), "last_render": content_render.ultimo_render(),
            "disk": content_storage.estado_disco(), "gemini_configured": bool(settings.gemini_api_key)}


# ═══════════════════════════════════════════════════ archivos y página pública

_CABECERAS = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff", "X-Robots-Tag": "noindex"}


def _servir(rel: str | None, media_type: str, descarga: bool, nombre: str) -> FileResponse:
    """El archivo, con las cabeceras de algo privado. FileResponse atiende los pedidos por rango
    (el `<video>` de Safari de iPhone los exige)."""
    ruta = content_storage.safe_path(rel)
    if ruta is None or not ruta.is_file():
        raise HTTPException(status_code=404, detail="El archivo no está")
    if descarga:
        return FileResponse(ruta, media_type=media_type, headers=_CABECERAS, filename=nombre,
                            content_disposition_type="attachment")
    return FileResponse(ruta, media_type=media_type, headers=_CABECERAS)


def _nombre_pieza(pieza: dict, ext: str) -> str:
    f = pieza.get("facts") or {}
    if pieza.get("pillar") == "rubro" and f.get("rubro_slug"):
        centro = "-".join(x for x in (f["rubro_slug"], f.get("ciudad_slug")) if x)
    else:
        centro = f.get("slug") or "ofertas"
    return content_storage.nombre_de_descarga(centro, str(pieza.get("scheduled_for") or ""), ext)


def _archivo_de_pieza(pieza: dict, kind: str, descarga: bool) -> FileResponse:
    if pieza.get("status") not in content_present.CON_VIDEO:
        raise HTTPException(status_code=404, detail="El archivo no está")
    ruta = pieza.get("video_path") if kind == "video" else pieza.get("cover_path")
    if pieza.get("files_purged_at") or not ruta:
        raise HTTPException(status_code=410, detail="El video ya se borró por antigüedad")
    if kind == "video":
        return _servir(ruta, "video/mp4", descarga, _nombre_pieza(pieza, "mp4"))
    return _servir(ruta, "image/jpeg", descarga, _nombre_pieza(pieza, "jpg"))


@router.get("/content/files/{scope}/{item_id}/{kind}")
def content_file(scope: str, item_id: str, kind: str, exp: str = Query(default="", max_length=20),
                 sig: str = Query(default="", max_length=100), download: int = Query(default=0),
                 crepo: ContentRepo = Depends(get_content_repo)):
    """Un archivo del disco privado con su URL firmada (15 min). `download=1` va FUERA de la firma."""
    try:
        vence = int(exp)
    except ValueError:
        raise HTTPException(status_code=403, detail="El enlace no es válido") from None
    veredicto = content_storage.verificar(scope, item_id, kind, vence, sig)
    if veredicto == "invalida":
        raise HTTPException(status_code=403, detail="El enlace no es válido")
    if veredicto == "vencida":
        raise HTTPException(status_code=403, detail="El enlace venció. Volvé a abrir la pantalla.")
    if scope == "piece":
        pieza = crepo.get_piece(item_id)
        if not pieza:
            raise HTTPException(status_code=404, detail="Pieza no encontrada")
        return _archivo_de_pieza(pieza, kind, bool(download))
    asset = crepo.get_asset(item_id)
    if not asset or not asset.get("activo"):
        raise HTTPException(status_code=404, detail="Foto no encontrada")
    if asset.get("file_purged_at"):
        raise HTTPException(status_code=410, detail="La foto ya se borró")
    rel = asset["file_path"] if kind == "file" else asset["thumb_path"]
    return _servir(rel, "image/jpeg", bool(download), f"uruku-foto-{item_id[:8]}.jpg")


def _pieza_publica(crepo: ContentRepo, token: str) -> dict:
    """La pieza de un token, o 404 / 410. El token son 22+ caracteres de `secrets.token_urlsafe`."""
    if not content_posts.token_valido(token):
        raise HTTPException(status_code=404, detail="Esta pieza no existe")
    pieza = crepo.get_piece_by_token(token)
    if not pieza or pieza.get("status") != "published":
        raise HTTPException(status_code=404, detail="Esta pieza no existe")
    vence = content_posts._parse(pieza.get("share_expires_at"))
    if (vence and vence < datetime.now(timezone.utc)) or pieza.get("files_purged_at"):
        raise HTTPException(status_code=410, detail="Este enlace venció. Pedile uno nuevo a URUKU.")
    # Aunque el link no haya vencido: si alguien que aparece en el video retiró la autorización o se dio de
    # baja, deja de abrir.
    if not content_consent.vigente_para_compartir(crepo, pieza):
        raise HTTPException(status_code=410, detail="Este enlace venció. Pedile uno nuevo a URUKU.")
    return pieza


@router.get("/public/pieces/{token}")
def public_piece(token: str, crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    """La página del comerciante: su video, para bajar y subir a su estado. Sin login, sin indexar."""
    pieza = _pieza_publica(crepo, token)
    f = pieza.get("facts") or {}
    posts = [p for p in crepo.list_posts([pieza["id"]]) if p["status"] == "posted"]
    base = f"/public/pieces/{token}"
    if pieza.get("comercio_id"):
        texto = content_captions.status_text(f)
    elif pieza.get("pillar") == "rubro":
        texto = content_captions.status_text_rubro(f)
    else:
        texto = (f"Ofertas de la semana en {f.get('ciudad') or 'su ciudad'} en URUKU: "
                 f"{settings.sitio_url.rstrip('/')}/ofertas?ref=st-ofertas")
    return {"comercio_nombre": f.get("nombre"), "comercio_slug": f.get("slug"), "pillar": pieza["pillar"],
            "published_at": pieza.get("published_at"), "expires_at": pieza.get("share_expires_at"),
            "video_url": f"{base}/video", "video_download_url": f"{base}/video?download=1", "cover_url": f"{base}/cover",
            "posts": [{"network": p["network"], "network_label": content_captions.NETWORK_LABEL[p["network"]],
                       "post_url": p.get("post_url")} for p in posts],
            "status_text": texto}


@router.get("/public/pieces/{token}/video")
def public_piece_video(token: str, download: int = Query(default=0), crepo: ContentRepo = Depends(get_content_repo)):
    return _archivo_de_pieza(_pieza_publica(crepo, token), "video", bool(download))


@router.get("/public/pieces/{token}/cover")
def public_piece_cover(token: str, download: int = Query(default=0), crepo: ContentRepo = Depends(get_content_repo)):
    return _archivo_de_pieza(_pieza_publica(crepo, token), "cover", bool(download))


# ═══════════════════════════════════════════════════ videos de URUKU en la home (§15.1)

_CABECERAS_VIDEO_PUBLICO = {"Cache-Control": "public, max-age=3600", "X-Content-Type-Options": "nosniff"}


@router.get("/public/videos")
def public_videos(city: str | None = Query(default=None, max_length=60, pattern=r"^[a-z0-9-]*$"),
                  limit: int = Query(default=12), crepo: ContentRepo = Depends(get_content_repo)) -> dict:
    """Los videos de URUKU para la franja de la home: los ya publicados, con archivos en el disco y todos
    sus comercios activos y autorizados. Sin login. `limit` entre 1 y 24."""
    items = content_public.listar(crepo, city or None, min(max(limit, 1), 24))
    return {"items": items}


def _video_publico_o_404(crepo: ContentRepo, video_id: str) -> dict:
    try:
        if str(uuid.UUID(video_id)) != video_id.lower():
            raise ValueError
    except ValueError:
        raise HTTPException(status_code=404, detail="El video no está") from None
    pieza = crepo.get_piece(video_id.lower())
    if not pieza or not content_public.es_publica(crepo, pieza):
        raise HTTPException(status_code=404, detail="El video no está")
    return pieza


def _servir_video_publico(pieza: dict, kind: str) -> FileResponse:
    rel, media = (pieza["video_path"], "video/mp4") if kind == "video" else (pieza["cover_path"], "image/jpeg")
    ruta = content_storage.safe_path(rel)
    if ruta is None or not ruta.is_file():
        raise HTTPException(status_code=404, detail="El video no está")
    return FileResponse(ruta, media_type=media, headers=_CABECERAS_VIDEO_PUBLICO)


@router.get("/public/videos/{video_id}/video")
def public_video_file(video_id: str, crepo: ContentRepo = Depends(get_content_repo)):
    return _servir_video_publico(_video_publico_o_404(crepo, video_id), "video")


@router.get("/public/videos/{video_id}/cover")
def public_video_cover(video_id: str, crepo: ContentRepo = Depends(get_content_repo)):
    return _servir_video_publico(_video_publico_o_404(crepo, video_id), "cover")
