"""API de integración para el sistema de marketing: `/v1/integration/*` (E1–E10).

Contrato y decisión: docs/integracion-marketing.md. Autenticación con API key (`Authorization: Bearer
uki_<key_id>.<secreto>`), alcance por comercio (404, no 403, para lo que está fuera), `Idempotency-Key` en toda
escritura y `If-Match`/ETag sobre cada publicación. Errores: `{"error": {"code", "message", "details"}}`.

Sólo se lee y se toca lo de los comercios que el admin de Uruku puso en el alcance del cliente. Nunca sale un
teléfono, el crudo de WAHA, el código URUKU-XXXX, `verificado` ni cuántos comercios hay fuera del alcance.
WAHA sólo lee: nada de esto manda por WhatsApp (la difusión es sólo Facebook e Instagram, por la Graph API).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.core.auth import require_integracion
from app.core.errores_integracion import IntegracionError
from app.db.repository import Repo, get_repo
from app.services import difusion, integracion, planes
from app.services.integracion import Cliente

logger = structlog.get_logger()

router = APIRouter(prefix="/v1/integration", tags=["integracion"])

_ESTADOS = ("pendiente", "aprobado", "rechazado", "cambios")
LIMITE_MAXIMO = 100
LIMITE_POR_DEFECTO = 50


# ═══════════════════════════════════════════════════════════════════════════ helpers

def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _no_encontrada(que: str = "la publicación") -> IntegracionError:
    # 404 también para lo que existe pero está fuera del alcance: no se filtra la existencia.
    return IntegracionError(404, "not_found", f"No encontramos {que}.")


def _uuid_o_404(valor: str, que: str = "la publicación") -> str:
    try:
        return str(uuid.UUID(str(valor)))
    except ValueError:
        raise _no_encontrada(que) from None


def _alcance(repo: Repo, cliente: Cliente) -> list[str]:
    return [f["comercio_id"] for f in repo.integracion_comercios_de(cliente.grupo_id)]


def _publicacion_en_alcance(repo: Repo, cliente: Cliente, pub_id: str) -> tuple[dict, dict]:
    """(publicación, info del comercio) o 404. Una publicación fuera del alcance es un 404 igual que una inexistente."""
    pub_id = _uuid_o_404(pub_id)
    pub = repo.integracion_get_publicacion(pub_id)
    if not pub:
        raise _no_encontrada()
    en_alcance = {f["comercio_id"] for f in repo.integracion_comercios_de(cliente.grupo_id)}
    if pub.get("comercio_id") not in en_alcance:
        raise _no_encontrada()
    info = next(iter(repo.integracion_info_comercios([pub["comercio_id"]])), None) or {}
    return pub, info


def _json(estado: int, cuerpo: dict, extra: dict[str, str] | None = None) -> JSONResponse:
    headers = dict(extra or {})
    if isinstance(cuerpo, dict) and cuerpo.get("etag"):
        headers["ETag"] = cuerpo["etag"]
    return JSONResponse(cuerpo, status_code=estado, headers=headers)


def _cuerpo_json(crudo: bytes) -> dict:
    try:
        cuerpo = json.loads(crudo or b"{}")
    except ValueError:
        raise IntegracionError(422, "validation", "El cuerpo no es un JSON válido.") from None
    if not isinstance(cuerpo, dict):
        raise IntegracionError(422, "validation", "El cuerpo tiene que ser un objeto JSON.")
    return cuerpo


def _fila(f: dict) -> dict:
    return {"fila_id": f["id"], "destino": f["destino"], "estado": f["estado"], "intentos": f.get("intentos") or 0,
            "motivo": f.get("motivo"), "external_post_id": f.get("external_post_id"), "permalink": f.get("permalink"),
            "enviado_at": f.get("enviado_at"), "verificado_at": f.get("verificado_at")}


def _filas_de(repo: Repo, pub_id: str) -> list[dict]:
    return [f for f in repo.difusion_de_publicacion(pub_id) if f["destino"] in integracion.DESTINOS_INTEGRACION]


async def _escritura(request: Request, repo: Repo, cliente: Cliente, hash_extra: bytes | None, ejecutar) -> JSONResponse:
    """El esqueleto de toda escritura: Idempotency-Key obligatoria → búsqueda de idempotencia (ANTES de lo demás)
    → `ejecutar()` en un hilo. `hash_extra` reemplaza al cuerpo en el hash del pedido (E6: el archivo)."""
    key = integracion.exigir_idempotency_key(request.headers.get("idempotency-key"))
    crudo = hash_extra if hash_extra is not None else await request.body()
    h = integracion.hash_de_pedido(request.method, request.url.path, crudo)
    estado, cuerpo = await run_in_threadpool(integracion.con_idempotencia, repo, cliente, key, h, ejecutar)
    return _json(estado, cuerpo)


# ═══════════════════════════════════════════════════════════════════════════ E1 / E2

@router.get("/me")
def me(cliente: Cliente = Depends(require_integracion()), repo: Repo = Depends(get_repo)):
    """E1: la clave es válida; sus scopes y los comercios en su alcance."""
    return {"key_id": cliente.key_id, "nombre": cliente.nombre, "scopes": sorted(cliente.scopes),
            "comercios": _alcance(repo, cliente), "version": integracion.VERSION_API}


@router.get("/merchants")
def merchants(cliente: Cliente = Depends(require_integracion("publications:read")), repo: Repo = Depends(get_repo)):
    """E2: los comercios del alcance. Sin `verificado`, sin código, sin teléfonos."""
    items = []
    for info in repo.integracion_info_comercios(_alcance(repo, cliente)):
        plan = planes.plan_de(repo, info)
        ciudad = {"nombre": info.get("ciudad")} if info.get("ciudad") else None
        items.append({
            "id": info["id"], "slug": info.get("slug"), "nombre": info.get("nombre"), "ciudad": info.get("ciudad"),
            "plan": info.get("plan"), "plan_tiene_redes": planes.funcion(plan, "redes"),
            "grupo_atado": bool(info.get("grupo_atado")), "activo": bool(info.get("activo", True)),
            "public_url": integracion.url_publica(info.get("slug")),
            "broadcast_footer": {d: difusion.pie_de(info, d, ciudad) for d in integracion.DESTINOS_INTEGRACION},
        })
    return {"items": items}


# ═══════════════════════════════════════════════════════════════════════════ E3 / E4

@router.get("/publications")
def publications(request: Request, cliente: Cliente = Depends(require_integracion("publications:read")),
                 repo: Repo = Depends(get_repo)):
    """E3: cambios desde el cursor `(updated_at, id)`, sólo de los comercios del alcance."""
    q = request.query_params
    crudo_limite = q.get("limit", str(LIMITE_POR_DEFECTO))
    if not crudo_limite.isdigit() or not 1 <= int(crudo_limite) <= LIMITE_MAXIMO:
        raise IntegracionError(422, "validation", f"limit tiene que ser un entero entre 1 y {LIMITE_MAXIMO}.")
    estado = q.get("estado") or None
    if estado is not None and estado not in _ESTADOS:
        raise IntegracionError(422, "validation", f"estado tiene que ser uno de: {', '.join(_ESTADOS)}.")
    cursor = q.get("cursor") or None
    desde = integracion.decodificar_cursor(cursor)
    ids = _alcance(repo, cliente)
    filas = repo.integracion_listar_publicaciones(ids, desde, int(crudo_limite), estado)
    comercios = {i["id"]: i for i in repo.integracion_info_comercios(sorted({f["comercio_id"] for f in filas}))}
    items = [integracion.vista_publicacion(f, comercios.get(f["comercio_id"])) for f in filas]
    return {"items": items, "next_cursor": integracion.codificar_cursor(filas[-1]) if filas else cursor}


@router.get("/publications/{pub_id}")
def publication(pub_id: str, cliente: Cliente = Depends(require_integracion("publications:read")),
                repo: Repo = Depends(get_repo)):
    """E4: el detalle con su media y su ETag (también en el header)."""
    pub, info = _publicacion_en_alcance(repo, cliente, pub_id)
    return _json(200, integracion.vista_publicacion(pub, info))


# ═══════════════════════════════════════════════════════════════════════════ E5

@router.patch("/publications/{pub_id}")
async def enrich(pub_id: str, request: Request,
                 cliente: Cliente = Depends(require_integracion("publications:write")),
                 repo: Repo = Depends(get_repo)):
    """E5: enriquecer el contenido de una publicación PENDIENTE. No cambia el estado."""
    crudo = await request.body()
    if_match = request.headers.get("if-match")

    def ejecutar() -> tuple[int, dict]:
        pub, info = _publicacion_en_alcance(repo, cliente, pub_id)
        integracion.exigir_if_match(if_match, pub)
        if pub.get("estado") != "pendiente" or not pub.get("activo", True):
            raise IntegracionError(409, "not_pending", "La publicación ya no está pendiente.")
        parche = integracion.validar_enriquecimiento(_cuerpo_json(crudo))
        # Control optimista: sólo aplica si NADIE la tocó entre la lectura y el UPDATE (el comercio, un moderador).
        nueva = repo.integracion_actualizar_publicacion_si(
            pub["id"], parche, {"estado": "pendiente", "updated_at": pub.get("updated_at")})
        if not nueva:
            raise IntegracionError(412, "etag_mismatch", "La publicación cambió mientras la actualizábamos.")
        logger.info("integracion.enriquecida", pub=pub["id"], por=cliente.key_id, campos=sorted(parche))
        return 200, integracion.vista_publicacion({**pub, **nueva}, info)

    return await _escritura(request, repo, cliente, crudo, ejecutar)


# ═══════════════════════════════════════════════════════════════════════════ E6

@router.post("/media")
async def upload_media(request: Request, cliente: Cliente = Depends(require_integracion("media:write")),
                       repo: Repo = Depends(get_repo)):
    """E6: sube el JPEG cuadrado (multipart, campo `file`). Idempotente por sha256 del contenido."""
    integracion.exigir_idempotency_key(request.headers.get("idempotency-key"))
    try:
        form = await request.form()
    except Exception:  # noqa: BLE001
        raise IntegracionError(422, "validation", "El cuerpo tiene que ser multipart con el campo `file`.") from None
    archivo = form.get("file")
    if archivo is None or not hasattr(archivo, "read"):
        raise IntegracionError(422, "validation", "Falta el archivo (campo `file`).")
    contenido = await archivo.read()
    return await _escritura(request, repo, cliente, b"MEDIA" + contenido,
                            lambda: (200, integracion.guardar_media(contenido)))


# ═══════════════════════════════════════════════════════════════════════════ E7

def _validar_moderacion(cuerpo: dict) -> dict:
    decision = cuerpo.get("decision")
    if decision not in ("approve", "reject"):
        raise IntegracionError(422, "validation", "decision tiene que ser approve o reject.")
    actor = cuerpo.get("actor")
    if not isinstance(actor, dict) or not str(actor.get("usuario") or "").strip():
        raise IntegracionError(422, "validation", "Falta actor.usuario (quién autorizó).")
    motivo = cuerpo.get("motivo")
    if motivo is not None and (not isinstance(motivo, str) or len(motivo) > 500):
        raise IntegracionError(422, "validation", "El motivo tiene que ser texto de hasta 500 caracteres.")
    dif = cuerpo.get("difusion")
    if dif is not None:
        if not isinstance(dif, dict):
            raise IntegracionError(422, "validation", "difusion tiene que ser un objeto.")
        destinos = dif.get("destinos") or []
        if (not isinstance(destinos, list) or len(set(destinos)) != len(destinos)
                or any(d not in integracion.DESTINOS_INTEGRACION for d in destinos)):
            raise IntegracionError(422, "validation", "Destino de difusión desconocido (facebook o instagram).")
        texto = dif.get("texto")
        if destinos and (not isinstance(texto, str) or not texto.strip() or len(texto) > 2000):
            raise IntegracionError(422, "validation", "La difusión necesita `texto` (hasta 2000 caracteres).")
        if dif.get("media_id") is not None and not isinstance(dif.get("media_id"), str):
            raise IntegracionError(422, "validation", "media_id tiene que ser texto.")
    return cuerpo


def _aprobar(repo: Repo, cliente: Cliente, pub: dict, info: dict, cuerpo: dict) -> tuple[int, dict]:
    from app.api.moderacion import _validar_codigo_al_aprobar

    if not info.get("activo", True):
        raise IntegracionError(409, "comercio_de_baja", "El comercio está dado de baja: la publicación no se vería.")
    try:
        _validar_codigo_al_aprobar(repo, pub["id"])
    except HTTPException as exc:
        if exc.status_code == 409:
            # El mensaje del panel trae los códigos URUKU-XXXX: a la integración no se le muestran.
            raise IntegracionError(409, "codigo_no_coincide",
                                   "El código con el que entró la publicación ya no coincide con el del comercio.") from None
        raise
    actor = integracion.actor_de(cuerpo.get("actor"))
    dif = cuerpo.get("difusion") or {}
    destinos = list(dif.get("destinos") or [])

    imagen = None
    if destinos:
        comercio = repo.get_comercio(pub["comercio_id"]) or {}
        if not planes.funcion(planes.plan_de(repo, comercio), "redes"):
            raise IntegracionError(422, "destino_no_habilitado_por_plan", "El plan del comercio no incluye redes.")
        for d in destinos:
            if not difusion.configurado(d):
                raise IntegracionError(422, "destino_no_configurado", f"{difusion.NOMBRE[d]} no está configurado en Uruku.")
        if dif.get("media_id"):
            imagen = integracion.resolver_media(dif["media_id"])
            if not imagen:
                raise IntegracionError(422, "media_not_found", "No existe ese media_id (subilo antes con POST /media).")
        if "instagram" in destinos and not (imagen or pub.get("imagen_url")):
            raise IntegracionError(422, "validation", "Instagram no publica sin imagen.")
        # Las filas se anotan ANTES de aprobar: si la aprobación falla (412), no hay una oferta aprobada sin
        # difusión; y como sólo las envía E9, las filas de una publicación pendiente no salen.
        extra = {"texto_override": dif["texto"].strip(), "imagen_url_override": imagen, "solicitado_por": actor}
        difusion.encolar(repo, pub["id"], destinos, extra)
        for f in _filas_de(repo, pub["id"]):
            if f["destino"] in destinos and f["estado"] in ("pendiente", "omitido"):
                repo.actualizar_difusion(f["id"], {"estado": "pendiente", "motivo": None, **extra})

    ahora = _ahora()
    nueva = repo.integracion_actualizar_publicacion_si(
        pub["id"],
        {"estado": "aprobado", "motivo_moderacion": None, "moderado_por": actor, "moderado_at": ahora, "approved_at": ahora},
        {"estado": "pendiente", "updated_at": pub.get("updated_at")})
    if not nueva:
        raise IntegracionError(412, "etag_mismatch", "La publicación cambió mientras la aprobábamos.")
    final = {**pub, **nueva}
    comercio = repo.get_comercio(pub["comercio_id"]) or {}
    filas = []
    for f in _filas_de(repo, pub["id"]):
        if f["destino"] in destinos:
            texto, _img = difusion.contenido_de(repo, f, final, comercio)
            filas.append({"fila_id": f["id"], "destino": f["destino"], "estado": f["estado"], "texto_final": texto})
    logger.info("integracion.aprobada", pub=pub["id"], por=actor, destinos=destinos, key=cliente.key_id)
    return 200, {"estado": "aprobado", "approved_at": final.get("approved_at") or ahora, "etag": integracion.etag_de(final),
                 "public_url": integracion.url_publica(info.get("slug")), "difusion": filas}


def _rechazar(repo: Repo, cliente: Cliente, pub: dict, info: dict, cuerpo: dict) -> tuple[int, dict]:
    actor = integracion.actor_de(cuerpo.get("actor"))
    ahora = _ahora()
    nueva = repo.integracion_actualizar_publicacion_si(
        pub["id"], {"estado": "rechazado", "motivo_moderacion": (cuerpo.get("motivo") or None),
                    "moderado_por": actor, "moderado_at": ahora},
        {"estado": "pendiente", "updated_at": pub.get("updated_at")})
    if not nueva:
        raise IntegracionError(412, "etag_mismatch", "La publicación cambió mientras la rechazábamos.")
    try:
        repo.descartar_difusion_de(pub["id"], "la publicación se bajó de la moderación")
    except Exception:  # noqa: BLE001 - el rechazo ya está hecho; la cola no lo frena
        logger.warning("integracion.descartar_difusion_fallo", pub=pub["id"], exc_info=True)
    logger.info("integracion.rechazada", pub=pub["id"], por=actor, key=cliente.key_id)
    return 200, {**integracion.vista_publicacion({**pub, **nueva}, info), "difusion": []}


@router.post("/publications/{pub_id}/moderation")
async def moderation(pub_id: str, request: Request,
                     cliente: Cliente = Depends(require_integracion("publications:write")),
                     repo: Repo = Depends(get_repo)):
    """E7: aprobar o rechazar una publicación pendiente (una sola aprobación: la de la integración)."""
    crudo = await request.body()
    if_match = request.headers.get("if-match")

    def ejecutar() -> tuple[int, dict]:
        pub, info = _publicacion_en_alcance(repo, cliente, pub_id)
        integracion.exigir_if_match(if_match, pub)
        cuerpo = _validar_moderacion(_cuerpo_json(crudo))
        if pub.get("estado") != "pendiente" or not pub.get("activo", True):
            raise IntegracionError(409, "not_pending", "La publicación ya no está pendiente.")
        if cuerpo["decision"] == "approve":
            return _aprobar(repo, cliente, pub, info, cuerpo)
        return _rechazar(repo, cliente, pub, info, cuerpo)

    return await _escritura(request, repo, cliente, crudo, ejecutar)


# ═══════════════════════════════════════════════════════════════════════════ E8 / E9 / E10

@router.get("/publications/{pub_id}/broadcasts")
def list_broadcasts(pub_id: str, cliente: Cliente = Depends(require_integracion("publications:read")),
                    repo: Repo = Depends(get_repo)):
    """E8: las filas de difusión de la publicación (Facebook e Instagram)."""
    pub, _info = _publicacion_en_alcance(repo, cliente, pub_id)
    return {"items": [_fila(f) for f in _filas_de(repo, pub["id"])]}


@router.post("/publications/{pub_id}/broadcasts/send")
async def send_broadcasts(pub_id: str, request: Request,
                          cliente: Cliente = Depends(require_integracion("broadcast:send")),
                          repo: Repo = Depends(get_repo)):
    """E9: envía las filas PENDIENTES de esa publicación (Facebook/Instagram). Nunca reenvía una `enviada`; una
    `incierta` primero se resuelve consultando a Meta."""
    if_match = request.headers.get("if-match")

    def ejecutar() -> tuple[int, dict]:
        pub, _info = _publicacion_en_alcance(repo, cliente, pub_id)
        integracion.exigir_if_match(if_match, pub)
        if pub.get("estado") != "aprobado" or not pub.get("activo", True):
            raise IntegracionError(409, "not_approved", "La publicación no está aprobada.")
        for f in _filas_de(repo, pub["id"]):
            if f["estado"] == "incierto":
                difusion.resolver_incierto(repo, f)
                f = repo.get_difusion_fila(f["id"]) or f
            if f["estado"] == "pendiente":
                difusion.procesar(repo, f, reclamar=True)
        return 200, {"items": [_fila(f) for f in _filas_de(repo, pub["id"])], "etag": integracion.etag_de(pub)}

    return await _escritura(request, repo, cliente, b"", ejecutar)


@router.post("/broadcasts/{fila_id}/verify")
async def verify_broadcast(fila_id: str, request: Request,
                           cliente: Cliente = Depends(require_integracion("publications:read")),
                           repo: Repo = Depends(get_repo)):
    """E10: Uruku relee el posteo en la Graph API con su token y guarda `verificado_at` + `permalink`."""
    def ejecutar() -> tuple[int, dict]:
        fid = _uuid_o_404(fila_id, "la fila de difusión")
        fila = repo.get_difusion_fila(fid)
        if not fila:
            raise _no_encontrada("la fila de difusión")
        _publicacion_en_alcance(repo, cliente, fila["publicacion_id"])      # fuera del alcance ⇒ 404
        if fila["destino"] not in integracion.DESTINOS_INTEGRACION:
            raise IntegracionError(409, "not_verifiable", "Ese destino no se puede verificar.")
        if fila["estado"] != "enviado":
            raise IntegracionError(409, "not_sent", "La fila todavía no se envió.")
        try:
            difusion.verificar(repo, fila)
        except difusion.DifusionIncierta as exc:
            raise IntegracionError(502, "graph_unavailable", f"Meta no contestó: {exc}") from exc
        except difusion.DifusionError as exc:
            raise IntegracionError(409, "verification_failed", str(exc)) from exc
        return 200, _fila(repo.get_difusion_fila(fid) or fila)

    return await _escritura(request, repo, cliente, b"", ejecutar)
