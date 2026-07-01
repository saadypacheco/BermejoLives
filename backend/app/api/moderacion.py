"""Panel de moderación: listar pendientes y aprobar/rechazar/pedir cambios.

Escrituras con service_role (backend). Requiere JWT de admin.
"""
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.auth import require_admin
from app.db.repository import Repo, get_repo
from app.models.schemas import ModerarBody
from app.services.reservalo_sync import ReservaloSyncClient, get_reservalo_sync_client

router = APIRouter()
logger = structlog.get_logger()

_ESTADOS = {"aprobado", "rechazado", "cambios"}


@router.get("/moderacion/publicaciones")
def listar(
    estado: str | None = Query(default="pendiente"),
    _admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    items = repo.list_publicaciones(estado)
    return {"items": items, "total": len(items)}


@router.post("/moderacion/publicaciones/{pub_id}")
def moderar(
    pub_id: str,
    body: ModerarBody,
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    if body.estado not in _ESTADOS:
        raise HTTPException(status_code=400, detail=f"estado inválido: {body.estado}")
    updated = repo.set_estado_publicacion(pub_id, body.estado, body.motivo, admin["email"])
    if not updated:
        raise HTTPException(status_code=404, detail="publicación no encontrada")
    logger.info("moderacion.accion", pub=pub_id, estado=body.estado, by=admin["email"])
    return {"ok": True, "publicacion": updated}


# ---- Moderación de comercios (alta del agente de campo) ----
@router.get("/moderacion/comercios")
def listar_comercios(
    verificado: bool | None = Query(default=False),
    todos: bool = Query(default=False),
    _admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    if todos:
        items = repo.list_todos_comercios(verificado=None)
    else:
        items = repo.list_comercios_admin(verificado)
    return {"items": items, "total": len(items)}


@router.post("/moderacion/comercios/{comercio_id}/verificar")
def verificar_comercio(
    comercio_id: str,
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    updated = repo.set_comercio_verificado(comercio_id, True)
    if not updated:
        raise HTTPException(status_code=404, detail="comercio no encontrado")
    logger.info("moderacion.comercio_verificado", comercio=comercio_id, by=admin["email"])
    return {"ok": True, "comercio": updated}


@router.post("/moderacion/comercios/{comercio_id}/rechazar")
def rechazar_comercio(
    comercio_id: str,
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    updated = repo.desactivar_comercio(comercio_id)
    if not updated:
        raise HTTPException(status_code=404, detail="comercio no encontrado")
    logger.info("moderacion.comercio_rechazado", comercio=comercio_id, by=admin["email"])
    return {"ok": True, "comercio": updated}


# ── Suscripciones ─────────────────────────────────────────────────────────────

class EditarComercioBody(BaseModel):
    nombre: str | None = None
    whatsapp: str | None = None
    descripcion: str | None = None
    modalidad: str | None = None
    direccion: str | None = None
    email: str | None = None
    facebook_url: str | None = None
    instagram_url: str | None = None
    tiktok_url: str | None = None
    sitio_web: str | None = None
    horario: str | None = None
    pedido_minimo: str | None = None
    tiene_factura: bool | None = None
    envios_internacionales: bool | None = None
    tiene_stock: bool | None = None
    rubro_slugs: list[str] | None = None


@router.put("/admin/comercio/{comercio_id}")
def editar_comercio(
    comercio_id: str,
    body: EditarComercioBody,
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Edita campos de un comercio desde el panel admin."""
    patch = {k: v for k, v in body.model_dump(exclude={"rubro_slugs"}).items() if v is not None}
    if not patch and not body.rubro_slugs:
        raise HTTPException(status_code=400, detail="Nada para actualizar")
    updated = repo.update_comercio(comercio_id, patch, body.rubro_slugs)
    logger.info("moderacion.comercio_editado", comercio=comercio_id, campos=list(patch.keys()), by=admin["email"])
    return {"ok": True, "comercio": updated}


class PagoBody(BaseModel):
    monto: float
    moneda: str = "BOB"
    metodo: str = "qr-bolivia"
    referencia: str | None = None
    meses: int = 1           # cuántos meses cubre este pago
    notas: str | None = None


@router.get("/admin/suscripciones")
def listar_suscripciones(
    _admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Lista todos los comercios con su estado de suscripción."""
    items = repo.list_suscripciones()
    return {"items": items, "total": len(items)}


@router.get("/admin/estadisticas")
def estadisticas(
    _admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Monitoreo: usuarios nuevos, alertas de baja, ofertas y contactos."""
    return repo.estadisticas_admin()


class ResponderReclamoBody(BaseModel):
    respuesta: str


@router.get("/admin/reclamos")
def listar_reclamos(
    estado: str | None = Query(default=None),
    _admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    items = repo.list_reclamos(estado)
    return {"items": items, "total": len(items)}


@router.post("/admin/reclamos/{reclamo_id}/responder")
def responder_reclamo(
    reclamo_id: str,
    body: ResponderReclamoBody,
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    updated = repo.responder_reclamo(reclamo_id, body.respuesta, admin["email"])
    if not updated:
        raise HTTPException(status_code=404, detail="reclamo no encontrado")
    logger.info("reclamo.respondido", reclamo=reclamo_id, by=admin["email"])
    return {"ok": True, "reclamo": updated}


# ---- Datos de Reservalo (proxy vía /api/admin-sync/*, dashboard unificado) ----

@router.get("/admin/reservalo/resumen")
def reservalo_resumen(
    _admin: dict = Depends(require_admin),
    cliente: ReservaloSyncClient = Depends(get_reservalo_sync_client),
) -> dict:
    return cliente.resumen() or {}


@router.get("/admin/reservalo/consultas")
def reservalo_consultas(
    estado: str | None = Query(default=None),
    _admin: dict = Depends(require_admin),
    cliente: ReservaloSyncClient = Depends(get_reservalo_sync_client),
) -> dict:
    items = cliente.list_consultas(estado)
    return {"items": items, "total": len(items)}


class ResponderConsultaReservaloBody(BaseModel):
    respuesta: str


@router.post("/admin/reservalo/consultas/{consulta_id}/responder")
def reservalo_responder_consulta(
    consulta_id: int,
    body: ResponderConsultaReservaloBody,
    admin: dict = Depends(require_admin),
    cliente: ReservaloSyncClient = Depends(get_reservalo_sync_client),
) -> dict:
    try:
        updated = cliente.responder_consulta(consulta_id, body.respuesta, admin["email"])
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"No se pudo responder en Reservalo: {exc}")
    if not updated:
        raise HTTPException(status_code=502, detail="Reservalo no está configurado (admin_sync_secret / tienda_api_url)")
    return {"ok": True, "consulta": updated}


@router.post("/admin/comercio/{comercio_id}/pago")
def registrar_pago(
    comercio_id: str,
    body: PagoBody,
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Registra un pago y extiende paga_hasta. Reactiva si estaba suspendido."""
    result = repo.registrar_pago(comercio_id, {
        "monto": body.monto,
        "moneda": body.moneda,
        "metodo": body.metodo,
        "referencia": body.referencia,
        "meses": body.meses,
        "notas": body.notas,
        "registrado_por": admin["email"],
    })
    logger.info("suscripcion.pago", comercio=comercio_id, meses=body.meses, by=admin["email"])
    return {"ok": True, **result}


@router.post("/admin/comercio/{comercio_id}/suspender")
def suspender_comercio(
    comercio_id: str,
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Suspende un comercio (oculta de búsquedas)."""
    repo.suspender_comercio(comercio_id)
    logger.info("suscripcion.suspendido", comercio=comercio_id, by=admin["email"])
    return {"ok": True}


@router.post("/admin/comercio/{comercio_id}/activar")
def activar_comercio(
    comercio_id: str,
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Reactiva un comercio suspendido."""
    repo.activar_comercio(comercio_id)
    logger.info("suscripcion.activado", comercio=comercio_id, by=admin["email"])
    return {"ok": True}


# ---- Pagos self-service pendientes de confirmación ----
class ConfirmarPagoBody(BaseModel):
    meses: int = 1


@router.get("/admin/pagos/pendientes")
def listar_pagos_pendientes(
    _admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Pagos QR que los comercios subieron y esperan confirmación."""
    items = repo.list_pagos_pendientes()
    return {"items": items, "total": len(items)}


@router.post("/admin/pagos/{pago_id}/confirmar")
def confirmar_pago(
    pago_id: str,
    body: ConfirmarPagoBody,
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Confirma un pago pendiente: lo marca confirmado y extiende paga_hasta."""
    result = repo.confirmar_pago(pago_id, body.meses, admin["email"])
    logger.info("suscripcion.pago_confirmado", pago=pago_id, meses=body.meses, by=admin["email"])
    return result


# ---- Mensaje del admin a un comercio (notificación) ----
class MensajeAdminBody(BaseModel):
    cuerpo: str


@router.post("/admin/comercio/{comercio_id}/mensaje")
def enviar_mensaje_comercio(
    comercio_id: str,
    body: MensajeAdminBody,
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    """El admin le envía un mensaje/notificación al comercio (aparece en su bandeja)."""
    if not body.cuerpo.strip():
        raise HTTPException(status_code=400, detail="Mensaje vacío")
    repo.crear_mensaje({
        "comercio_id": comercio_id, "autor": "admin",
        "nombre": "Encontralo", "cuerpo": body.cuerpo.strip(),
    })
    logger.info("admin.mensaje", comercio=comercio_id, by=admin["email"])
    return {"ok": True}


# ---- Solicitudes de cambio de número (cuenta sin email/pass, perdió el celu) ----

@router.get("/admin/solicitudes-cambio-numero")
def listar_solicitudes_cambio_numero(
    estado: str | None = Query(default="pendiente"),
    _admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    items = repo.list_solicitudes_cambio_numero(estado)
    return {"items": items, "total": len(items)}


@router.post("/admin/solicitudes-cambio-numero/{solicitud_id}/aprobar")
def aprobar_solicitud_cambio_numero(
    solicitud_id: str,
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Actualiza el WhatsApp del comercio al número nuevo. Siempre manual."""
    updated = repo.aprobar_solicitud_cambio_numero(solicitud_id, admin["email"])
    if not updated:
        raise HTTPException(status_code=404, detail="solicitud no encontrada")
    logger.info("solicitud_cambio_numero.aprobada", solicitud=solicitud_id, by=admin["email"])
    return {"ok": True, "solicitud": updated}


@router.post("/admin/solicitudes-cambio-numero/{solicitud_id}/rechazar")
def rechazar_solicitud_cambio_numero(
    solicitud_id: str,
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    updated = repo.rechazar_solicitud_cambio_numero(solicitud_id, admin["email"])
    if not updated:
        raise HTTPException(status_code=404, detail="solicitud no encontrada")
    logger.info("solicitud_cambio_numero.rechazada", solicitud=solicitud_id, by=admin["email"])
    return {"ok": True, "solicitud": updated}
