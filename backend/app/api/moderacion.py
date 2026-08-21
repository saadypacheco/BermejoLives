"""Panel de moderación: listar pendientes y aprobar/rechazar/pedir cambios.

Escrituras con service_role (backend). Requiere JWT de admin.
"""
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.auth import require_admin, require_moderador
from app.core.config import settings
from app.core.telefono import validar_whatsapp
from app.services.rubros import SLUG_DESCARTE, aplicar_rubros, resolver_rubros
from app.db.repository import Repo, get_repo
from app.models.schemas import ModerarBody
from app.services.clasificador import moderar_publicacion
from app.services.reservalo_sync import ReservaloSyncClient, get_reservalo_sync_client

router = APIRouter()
logger = structlog.get_logger()

_ESTADOS = {"aprobado", "rechazado", "cambios"}


@router.get("/moderacion/publicaciones")
def listar(
    estado: str | None = Query(default="pendiente"),
    _mod: dict = Depends(require_moderador),
    repo: Repo = Depends(get_repo),
) -> dict:
    items = repo.list_publicaciones(estado)
    return {"items": items, "total": len(items)}


def _validar_codigo_al_aprobar(repo: Repo, pub_id: str) -> None:
    """Antes de publicar algo que se atribuyó por código, se revalida el código.

    La atribución se hizo cuando entró el mensaje; entre eso y la aprobación pudo
    pasar cualquier cosa (el comercio cambió de código, se dio de baja, alguien
    reasignó la publicación). Aprobar es el acto que la hace pública, así que la
    verificación se rehace acá contra el código del alta.
    """
    from app.core.codigo import formatear, normalizar

    pub = repo.get_publicacion(pub_id)
    if not pub:
        raise HTTPException(status_code=404, detail="publicación no encontrada")
    if pub.get("identidad_origen") != "codigo":
        return  # se identificó por número: no hay código que validar

    recibido = normalizar(pub.get("codigo_recibido"))
    comercio = repo.get_comercio(pub["comercio_id"])
    esperado = normalizar((comercio or {}).get("codigo"))

    if not recibido or not esperado or recibido != esperado:
        raise HTTPException(
            status_code=409,
            detail=(
                "El código de esta publicación ya no coincide con el del comercio "
                f"(recibido: {formatear(recibido) if recibido else 'ninguno'}, "
                f"actual: {formatear(esperado) if esperado else 'ninguno'}). "
                "Revisá a qué comercio corresponde antes de aprobarla."
            ),
        )


@router.post("/moderacion/publicaciones/{pub_id}")
def moderar(
    pub_id: str,
    body: ModerarBody,
    mod: dict = Depends(require_moderador),
    repo: Repo = Depends(get_repo),
) -> dict:
    if body.estado not in _ESTADOS:
        raise HTTPException(status_code=400, detail=f"estado inválido: {body.estado}")
    if body.estado == "aprobado":
        _validar_codigo_al_aprobar(repo, pub_id)
    updated = repo.set_estado_publicacion(pub_id, body.estado, body.motivo, mod["email"])
    if not updated:
        raise HTTPException(status_code=404, detail="publicación no encontrada")
    logger.info("moderacion.accion", pub=pub_id, estado=body.estado, by=mod["email"])
    return {"ok": True, "publicacion": updated}


class RevisarIABody(BaseModel):
    titulo: str
    descripcion: str | None = None


@router.post("/moderacion/publicaciones/{pub_id}/revisar-ia")
def revisar_con_ia(
    pub_id: str,
    body: RevisarIABody,
    mod: dict = Depends(require_moderador),
) -> dict:
    """Asistente de moderación: la IA sugiere aprobar/rechazar/dudoso. NO decide sola —
    el moderador confirma la acción con el POST normal. Si no hay IA configurada,
    devuelve 'dudoso' (cae a revisión humana)."""
    resultado = moderar_publicacion(body.titulo, body.descripcion)
    logger.info("moderacion.revisar_ia", pub=pub_id, veredicto=resultado["veredicto"], by=mod["email"])
    return resultado


# ---- Moderación de comercios (alta del agente de campo) ----
@router.get("/moderacion/comercios")
def listar_comercios(
    verificado: bool | None = Query(default=False),
    todos: bool = Query(default=False),
    _mod: dict = Depends(require_moderador),
    repo: Repo = Depends(get_repo),
) -> dict:
    if todos:
        # El panel filtra/busca/pagina del lado del cliente: traemos hasta 5000
        # (suficiente para el admin; si algún día se superan, pasar a filtro server-side).
        items = repo.list_todos_comercios(verificado=None, limit=5000)
    else:
        items = repo.list_comercios_admin(verificado)
    return {"items": items, "total": len(items)}


@router.post("/moderacion/comercios/{comercio_id}/verificar")
def verificar_comercio(
    comercio_id: str,
    mod: dict = Depends(require_moderador),
    repo: Repo = Depends(get_repo),
) -> dict:
    updated = repo.set_comercio_verificado(comercio_id, True)
    if not updated:
        raise HTTPException(status_code=404, detail="comercio no encontrado")
    logger.info("moderacion.comercio_verificado", comercio=comercio_id, by=mod["email"])
    return {"ok": True, "comercio": updated}


@router.post("/moderacion/comercios/{comercio_id}/rechazar")
def rechazar_comercio(
    comercio_id: str,
    mod: dict = Depends(require_moderador),
    repo: Repo = Depends(get_repo),
) -> dict:
    updated = repo.desactivar_comercio(comercio_id)
    if not updated:
        raise HTTPException(status_code=404, detail="comercio no encontrado")
    logger.info("moderacion.comercio_rechazado", comercio=comercio_id, by=mod["email"])
    return {"ok": True, "comercio": updated}


# ── Suscripciones ─────────────────────────────────────────────────────────────

class EditarComercioBody(BaseModel):
    nombre: str | None = None
    whatsapp: str | None = None
    telefono: str | None = None
    descripcion: str | None = None
    productos: str | None = None
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
    # Si cambió de qué vende, se recalculan los rubros. Sólo suma: los que se
    # eligieron a mano en este mismo formulario no se pierden.
    if {"productos", "descripcion", "nombre"} & patch.keys():
        aplicar_rubros(repo, updated, body.rubro_slugs or repo.get_comercio_rubros(comercio_id))
    logger.info("moderacion.comercio_editado", comercio=comercio_id, campos=list(patch.keys()), by=admin["email"])
    return {"ok": True, "comercio": updated}


# ── Lugares (mercados / galerías / referencias): ABM desde el admin ─────────────
class LugarAdminBody(BaseModel):
    nombre: str | None = None
    tipo: str | None = None
    ciudad_slug: str | None = None
    lat: float | None = None
    lng: float | None = None
    poligono: list | None = None


@router.get("/admin/lugares")
def admin_list_lugares(
    ciudad_slug: str = Query(default="bermejo"),
    _mod: dict = Depends(require_moderador),
    repo: Repo = Depends(get_repo),
) -> dict:
    ciudad_id = repo.get_ciudad_id(ciudad_slug) or repo.get_ciudad_id("bermejo")
    return {"items": repo.list_lugares(ciudad_id)}


@router.post("/admin/lugares")
def admin_crear_lugar(
    body: LugarAdminBody,
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    nombre = (body.nombre or "").strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="Falta el nombre")
    ciudad_id = repo.get_ciudad_id(body.ciudad_slug or "bermejo") or repo.get_ciudad_id("bermejo")
    lugar = repo.crear_lugar({"nombre": nombre, "tipo": body.tipo or "mercado", "ciudad_id": ciudad_id, "lat": body.lat, "lng": body.lng})
    logger.info("admin.lugar_creado", lugar=lugar["id"], by=admin["email"])
    return {"ok": True, "lugar": lugar}


@router.put("/admin/lugares/{lugar_id}")
def admin_update_lugar(
    lugar_id: str,
    body: LugarAdminBody,
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    patch: dict = {}
    if body.nombre is not None and body.nombre.strip():
        patch["nombre"] = body.nombre.strip()
    if body.tipo is not None and body.tipo.strip():
        patch["tipo"] = body.tipo.strip()
    if body.lat is not None:
        patch["lat"] = body.lat
    if body.lng is not None:
        patch["lng"] = body.lng
    if body.poligono is not None:
        patch["poligono"] = body.poligono   # [] borra el polígono
    if not patch:
        raise HTTPException(status_code=400, detail="Nada para actualizar")
    return {"ok": True, "lugar": repo.update_lugar(lugar_id, patch)}


@router.delete("/admin/lugares/{lugar_id}")
def admin_delete_lugar(
    lugar_id: str,
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    repo.update_lugar(lugar_id, {"activo": False})
    logger.info("admin.lugar_borrado", lugar=lugar_id, by=admin["email"])
    return {"ok": True}


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


@router.get("/admin/kpis")
def kpis(_admin: dict = Depends(require_admin), repo: Repo = Depends(get_repo)) -> dict:
    """KPIs del sitio: búsquedas top, búsquedas sin resultado, locales más
    visitados/contactados y resumen de monetización."""
    return repo.kpis_admin()


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


def _advertencias_whatsapp(repo: Repo, comercio_id: str | None) -> list[str]:
    """Chequea el WhatsApp del comercio al momento de cobrarle.

    El alta es mínima a propósito (se carga rápido, a veces sin número), así que
    esta es la primera instancia donde el número importa de verdad: a partir del
    pago el comercio está en el mapa y las reservas de Reservalo le llegan por
    ahí. No bloquea el pago —la plata ya entró— pero deja el problema a la vista
    del admin, que está con el comercio en ese momento y puede corregirlo.
    """
    if not comercio_id:
        return []
    comercio = repo.get_comercio(comercio_id)
    if not comercio:
        return []
    error = validar_whatsapp(comercio.get("whatsapp"))
    if not error:
        return []
    logger.warning("suscripcion.whatsapp_invalido", comercio=comercio_id, detalle=error)
    return [error]


def _asegurar_login(repo: Repo, comercio_id: str | None) -> bool:
    """Le garantiza cuenta al comercio en el momento en que empieza a pagar.

    El alta por agente de campo nunca creaba la fila en `comercio_usuarios`, así
    que el comercio cargado en la calle no tenía forma de entrar al panel — ni
    siquiera por la recuperación de WhatsApp, que busca justamente esa fila. El
    pago es el punto exacto del ciclo donde deja de ser un comercio del mapa y
    pasa a ser uno que publica, así que la cuenta se crea acá.

    Devuelve True si el comercio quedó con cuenta utilizable.
    """
    if not comercio_id:
        return False
    try:
        repo.asegurar_comercio_usuario(comercio_id)
        return True
    except Exception:  # noqa: BLE001 — nunca romper el registro de un pago
        logger.warning("suscripcion.login_no_creado", comercio=comercio_id, exc_info=True)
        return False


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
    return {
        "ok": True, **result,
        "advertencias": _advertencias_whatsapp(repo, comercio_id),
        "login": _asegurar_login(repo, comercio_id),
    }


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
    comercio_id = result.get("comercio_id")
    return {
        **result,
        "advertencias": _advertencias_whatsapp(repo, comercio_id),
        "login": _asegurar_login(repo, comercio_id),
    }


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


# ---- Confiable: publica sin pasar por la cola de moderación ----
class ConfiableBody(BaseModel):
    confiable: bool = True


@router.post("/admin/comercio/{comercio_id}/confiable")
def set_confiable(
    comercio_id: str,
    body: ConfiableBody,
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Marca (o desmarca) un comercio como confiable.

    `confiable` decide si lo que publica sale directo o cae en la cola de
    moderación, pero no había NINGUNA forma de escribirlo: los únicos valores
    true venían del seed inicial. En la práctica todo pasaba por moderación.
    """
    comercio = repo.set_comercio_confiable(comercio_id, body.confiable)
    logger.info("comercio.confiable", comercio=comercio_id, valor=body.confiable, by=admin["email"])
    return {"ok": True, "comercio": comercio}


# ---- Números de WhatsApp autorizados a publicar por el comercio ----
class NumeroBody(BaseModel):
    numero: str
    etiqueta: str | None = None


@router.get("/admin/comercio/{comercio_id}/numeros")
def listar_numeros(
    comercio_id: str,
    _admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    items = repo.list_numeros_comercio(comercio_id)
    return {"items": items, "total": len(items)}


@router.post("/admin/comercio/{comercio_id}/numeros")
def agregar_numero(
    comercio_id: str,
    body: NumeroBody,
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Autoriza un número a publicar en nombre del comercio.

    El número público del local y el que manda los productos por WhatsApp no
    tienen por qué ser el mismo (el del empleado, el del dueño, un segundo
    local). Se dan de alta en la segunda pasada, con el dueño presente.
    """
    error = validar_whatsapp(body.numero)
    if error:
        raise HTTPException(status_code=400, detail=error)
    fila = repo.agregar_numero_comercio(comercio_id, body.numero, body.etiqueta, admin["email"])
    logger.info("comercio.numero_autorizado", comercio=comercio_id, by=admin["email"])
    return {"ok": True, "numero": fila}


# ---- Bajas del mapa: disparo manual ----
@router.post("/admin/bajas/ejecutar")
def ejecutar_bajas(
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Corre la baja de comercios vencidos ahora mismo.

    El job automático vive dentro del proceso del backend (loop con sleep de un
    día), así que se reinicia en cada deploy y puede pasar mucho sin correr.
    Esto permite dispararlo a mano sin esperar al ciclo.
    """
    ocultos = repo.ocultar_comercios_vencidos(
        dias=settings.dias_vencido_baja, dias_gracia=settings.dias_gracia_sin_pago
    )
    logger.info("suscripcion.bajas_manual", ocultos=ocultos, by=admin["email"])
    return {"ok": True, "ocultos": ocultos}


# ---- Reclasificar rubros a partir de lo cargado ----
@router.post("/admin/rubros/reclasificar")
def reclasificar_rubros(
    aplicar: bool = Query(False, description="false = previsualizar; true = escribir"),
    limite: int = Query(500, ge=1, le=2000),
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Deduce los rubros de los comercios ya cargados, desde nombre + productos +
    descripción.

    Nace de un problema concreto: en el primer recorrido se cargaron 84 locales en
    un día y los 92 quedaron en "Otros", porque elegir rubro de una lista de 42
    caminando es inviable. El dato para clasificarlos ya estaba escrito — sólo
    faltaba leerlo.

    Por defecto NO escribe: devuelve qué haría, para revisar antes. Sólo suma
    rubros, nunca borra los que se hayan curado a mano.
    """
    comercios = repo.list_todos_comercios(None, limite)
    cambios, sin_match = [], []

    for c in comercios:
        if not c.get("activo", True):
            continue
        actuales = set(repo.get_comercio_rubros(c["id"]))
        propuestos = set(resolver_rubros(repo, c, sorted(actuales)))
        if propuestos == {SLUG_DESCARTE}:
            sin_match.append({"slug": c.get("slug"), "nombre": c.get("nombre"),
                              "productos": c.get("productos"), "descripcion": c.get("descripcion")})
            continue
        if propuestos == actuales:
            continue
        cambios.append({
            "slug": c.get("slug"), "nombre": c.get("nombre"),
            "antes": sorted(actuales), "despues": sorted(propuestos),
            "suma": sorted(propuestos - actuales),
        })
        if aplicar:
            aplicar_rubros(repo, c, sorted(actuales))

    logger.info("rubros.reclasificar", aplicado=aplicar, cambios=len(cambios),
                sin_match=len(sin_match), by=admin["email"])
    return {
        "aplicado": aplicar,
        "analizados": len(comercios),
        "cambios": cambios,
        "sin_match": sin_match,
        "resumen": {"con_cambios": len(cambios), "sin_match": len(sin_match)},
    }
