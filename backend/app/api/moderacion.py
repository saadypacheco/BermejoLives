"""Panel de moderación: listar pendientes y aprobar/rechazar/pedir cambios.

Escrituras con service_role (backend). Requiere JWT de admin.
"""
import re

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

from app.core.auth import require_admin, require_moderador
from app.core.config import settings
from starlette.concurrency import run_in_threadpool
from app.core.telefono import validar_whatsapp
from app.services import clasificador
from app.services.imagenes import subir_foto_galeria
from app.services.vision import VisionNoConfigurada, analizar_fotos
from app.services.normalizar import es_nombre_generico, normalizar_subcategoria
from app.services.sinonimos import desde_propuesta, sinonimos_para
from app.services.rubros import SLUG_DESCARTE, aplicar_rubros, resolver_rubros
from app.db.repository import Repo, get_repo
from app.models.schemas import ModerarBody
from app.services.clasificador import moderar_publicacion
from app.services.reservalo_sync import ReservaloSyncClient, get_reservalo_sync_client

router = APIRouter()


def _sinonimos(propuesta: dict, repo: Repo | None) -> str:
    """Los sinónimos del comercio: los que escribió la IA más los que ya están
    en el diccionario.

    Las dos fuentes se suman porque cubren huecos distintas. La IA aporta lo que
    ve en ESA vidriera; el diccionario aporta el vocabulario acumulado de todos
    los relevamientos anteriores y de las correcciones a mano. Un comercio nuevo
    hereda así todo lo aprendido sin gastar una llamada extra.
    """
    propios, aportes = desde_propuesta(propuesta.get("sinonimos"))
    partes = [propios]
    if repo is not None:
        # Lo que la IA descubrió en ESTA vidriera entra al diccionario compartido,
        # así que a partir de ahora encuentra también a los demás locales que
        # venden lo mismo. Sin este paso, cada hallazgo se quedaba en un solo
        # comercio y el diccionario sólo crecía corriendo el script a mano.
        # guardar_sinonimos no pisa lo cargado como 'manual'.
        try:
            if aportes:
                repo.guardar_sinonimos(aportes, origen="ia")
        except Exception:  # noqa: BLE001 — enriquecer no puede romper un análisis
            logger.warning("sinonimos.aporte_fallido", terminos=len(aportes))
        try:
            desde_dicc = sinonimos_para(
                {"prod_det_ia": propuesta.get("productos") or "",
                 "subcategoria": propuesta.get("subcategoria") or ""},
                repo.get_diccionario_sinonimos())
            partes.append(desde_dicc)
        except Exception:  # noqa: BLE001 — sin diccionario el análisis sigue
            pass

    vistos: list[str] = []
    for parte in partes:
        for s in parte.split(","):
            s = s.strip()
            if s and s.lower() not in [v.lower() for v in vistos]:
                vistos.append(s)
    return ", ".join(vistos)


def _patch_ia(propuesta: dict, repo: Repo | None = None,
              comercio: dict | None = None) -> dict:
    """Los campos que escribe el análisis por fotos, en un solo lugar.

    Estaba duplicado entre el análisis individual y el de tanda, y ya había
    empezado a divergir. Con los sinónimos y la subcategoría normalizada son
    cinco campos: si se agrega uno y se olvida una de las dos copias, la mitad
    de los comercios queda sin ese dato y no lo avisa nadie.
    """
    from datetime import datetime, timezone

    subcategoria = propuesta.get("subcategoria") or None
    patch = {
        "prod_det_ia": propuesta.get("productos") or None,
        "subcategoria": subcategoria,
        # Se recalcula siempre junto a la subcategoría: si quedara la anterior,
        # el agrupado mentiría y es peor que no tener nada.
        "subcategoria_norm": normalizar_subcategoria(subcategoria) or None,
        "sinonimos": _sinonimos(propuesta, repo) or None,
        "ia_analizado_at": datetime.now(timezone.utc).isoformat(),
    }
    # La descripción es de la IA: se regenera en cada análisis sin mirar lo que
    # había. Lo que escribe una persona vive en `prod_obs_human`, que no se toca.
    if propuesta.get("descripcion"):
        patch["descripcion"] = propuesta["descripcion"]

    # El nombre del cartel SÓLO se escribe si el comercio no tiene uno de
    # verdad. Es la diferencia con la descripción: el nombre lo pone una persona
    # que estuvo parada en la puerta, y ninguna lectura de foto puede pisar eso.
    #
    # Sin esto, un nombre que se lee "COMERCIAL MARIA" en una foto con reflejo
    # podría reemplazar al que el agente tipeó bien. Con esto, lo peor que pasa
    # es que un comercio sin nombre siga sin nombre.
    cartel = (propuesta.get("nombre_cartel") or "").strip()
    if cartel and comercio is not None:
        rubros = {r.get("nombre", "") for r in (repo.list_rubros() if repo else [])}
        if es_nombre_generico(comercio.get("nombre"), rubros) and not es_nombre_generico(cartel, rubros):
            # El slug se rearma solo al renombrar, si todavía era genérico.
            patch["nombre"] = cartel
    return patch

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
    prod_obs_human: str | None = None
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
    if {"prod_obs_human", "descripcion", "nombre"} & patch.keys():
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


# ---- Grupo de WhatsApp del comercio ----
#
# El canal por el que el comerciante manda sus ofertas: un grupo con su celular,
# uno de URUKU y el testigo. Vive en el perfil del comercio porque es parte de
# cómo se llega a ese local — igual que el código o los números autorizados.
class GrupoBody(BaseModel):
    grupo_jid: str
    nombre: str | None = None


@router.get("/admin/comercio/{comercio_id}/grupos")
def listar_grupos(
    comercio_id: str,
    _admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    items = repo.list_grupos_comercio(comercio_id)
    return {"items": items, "total": len(items)}


@router.post("/admin/comercio/{comercio_id}/grupos")
def atar_grupo(
    comercio_id: str,
    body: GrupoBody,
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Ata un grupo a mano, para cuando no se puede usar el código.

    El camino normal es mandar `URUKU-XXXX` adentro del grupo y que se ate solo.
    Esto es la salida para cuando el grupo se rehízo, o el comerciante no tiene
    el papel con el código a mano.
    """
    jid = (body.grupo_jid or "").strip()
    # Sin esta validación se puede atar un chat 1-a-1 por error, y ahí el
    # comercio empezaría a recibir como propio lo que le escriba cualquiera a
    # ese número.
    if not jid.endswith("@g.us"):
        raise HTTPException(
            status_code=400,
            detail="El ID de un grupo de WhatsApp termina en @g.us. Ese no es un grupo.")

    ya = repo.get_comercio_por_grupo(jid)
    if ya and ya.get("id") != comercio_id:
        raise HTTPException(
            status_code=409,
            detail=f"Ese grupo ya es de «{ya.get('nombre') or ya.get('slug')}». "
                   "Hay que soltarlo de ahí antes de atarlo acá.")

    repo.vincular_grupo_comercio(jid, comercio_id, body.nombre, "admin", admin["email"])
    logger.info("comercio.grupo_atado", comercio=comercio_id, grupo=jid, by=admin["email"])
    return {"ok": True, "grupos": repo.list_grupos_comercio(comercio_id)}


@router.delete("/admin/comercio/{comercio_id}/grupos/{grupo_jid}")
def soltar_grupo(
    comercio_id: str,
    grupo_jid: str,
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Suelta el grupo. Las publicaciones que ya entraron por ahí quedan: son
    ofertas que existieron, y borrarlas sería perder historia."""
    repo.desvincular_grupo(grupo_jid)
    logger.info("comercio.grupo_soltado", comercio=comercio_id, grupo=grupo_jid, by=admin["email"])
    return {"ok": True, "grupos": repo.list_grupos_comercio(comercio_id)}


# ---- Comercios importados de fuentes externas ----
#
# No son comercios de URUKU todavía: son una lista de qué existe y dónde. Pasan
# al mapa de a uno, cuando una persona los mira. Un registro de OpenStreetMap
# puede estar cerrado hace dos años y desde acá no hay forma de saberlo.
class PromoverBody(BaseModel):
    nombre: str | None = None          # se puede corregir al promover
    rubro_slug: str | None = None      # obligatorio si el importado no trae uno
    whatsapp: str | None = None


@router.get("/admin/importados")
def listar_importados(
    estado: str = "nuevo",
    ciudad_id: str | None = None,
    q: str | None = None,
    limite: int = 200,
    _admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    items = repo.list_importados(estado or None, ciudad_id, q, min(limite, 500))
    return {"items": items, "total": len(items), "resumen": repo.resumen_importados()}


@router.post("/admin/importados/{importado_id}/promover")
def promover_importado(
    importado_id: str,
    body: PromoverBody,
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Crea el comercio de URUKU a partir del importado.

    El comercio nace **sin verificar** y sin foto: lo que vino de la API es
    nombre, punto y a veces teléfono. La foto de la vidriera —que es lo que hace
    útil a la ficha— la saca alguien parado enfrente, y ninguna API la da: de
    19.861 negocios medidos, 91 tenían imagen.
    """
    imp = repo.get_importado(importado_id)
    if not imp:
        raise HTTPException(status_code=404, detail="No existe ese importado")
    if imp["estado"] == "promovido":
        raise HTTPException(status_code=409, detail="Ya está en el mapa")

    nombre = (body.nombre or imp.get("nombre") or "").strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="Sin nombre no se puede crear el comercio")
    if imp.get("lat") is None or imp.get("lng") is None:
        raise HTTPException(status_code=400, detail="Sin coordenadas no va al mapa")

    rubro_slug = body.rubro_slug or imp.get("rubro_slug") or "otros"
    from app.core.text import slugify

    comercio = repo.crear_comercio({
        "nombre": nombre,
        "slug": slugify(nombre),
        "ciudad_id": imp.get("ciudad_id"),
        "lat": imp["lat"], "lng": imp["lng"],
        "direccion": imp.get("direccion"),
        "whatsapp": body.whatsapp or imp.get("whatsapp") or imp.get("telefono"),
        "horario": imp.get("horario"),
        "sitio_web": imp.get("website"),
        "verificado": False,
        "activo": True,
        # De dónde salió, escrito en la ficha. Sin esto, en seis meses nadie
        # puede distinguir un local caminado de uno traído de un mapa abierto —
        # y la diferencia importa para la licencia y para la confianza.
        "cargado_por": f"import:{imp.get('fuente', 'osm')}",
    })
    rid = repo.get_rubro_id(rubro_slug)
    if rid:
        repo.set_comercio_rubros(comercio["id"], [rid])

    repo.marcar_importado(importado_id, {
        "estado": "promovido", "comercio_id": comercio["id"],
        "revisado_por": admin["email"], "revisado_at": _ahora(),
    })
    logger.info("importado.promovido", importado=importado_id,
                comercio=comercio["id"], by=admin["email"])
    return {"ok": True, "comercio": comercio}


@router.post("/admin/importados/{importado_id}/descartar")
def descartar_importado(
    importado_id: str,
    motivo: str = "",
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Descarta sin borrar: la fila queda para que la próxima importación no lo
    vuelva a proponer. Borrarlo lo haría reaparecer en cada corrida."""
    if not repo.get_importado(importado_id):
        raise HTTPException(status_code=404, detail="No existe ese importado")
    fila = repo.marcar_importado(importado_id, {
        "estado": "descartado", "motivo": motivo or None,
        "revisado_por": admin["email"], "revisado_at": _ahora(),
    })
    return {"ok": True, "importado": fila}


def _ahora() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


@router.post("/admin/comercio/{comercio_id}/grupo")
def crear_grupo_comercio(
    comercio_id: str,
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Arma el grupo de WhatsApp del comercio y lo deja atado.

    Reemplaza los cinco pasos manuales (crear, nombrar, agregar al comerciante,
    agregar los respaldos, mandar el código adentro). Y como el grupo lo crea el
    sistema, el identificador vuelve en la respuesta y se ata acá mismo: no hay
    ventana en la que el grupo exista sin saberse de quién es.
    """
    from app.services.wa_grupos import GrupoError, crear_grupo, id_del_grupo, numeros_de_grupo

    comercio = repo.get_comercio(comercio_id)
    if not comercio:
        raise HTTPException(status_code=404, detail="No existe ese comercio")

    ya = repo.list_grupos_comercio(comercio_id)
    if ya:
        raise HTTPException(
            status_code=409,
            detail="Este comercio ya tiene un grupo. Soltalo antes de crear otro.")

    whatsapp = (comercio.get("whatsapp") or "").strip()
    if not whatsapp:
        # Sin el número del comerciante el grupo sería URUKU hablando sola.
        raise HTTPException(
            status_code=400,
            detail="El comercio no tiene WhatsApp cargado: sin eso no hay a quién agregar.")

    nombre = f"URUKU · {comercio.get('nombre') or 'Comercio'}"[:60]
    try:
        respuesta = crear_grupo(nombre, [whatsapp, *numeros_de_grupo()])
    except GrupoError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    jid = id_del_grupo(respuesta)
    if not jid:
        # El grupo quedó creado en WhatsApp pero no sabemos su identificador.
        # Se avisa fuerte: hay que atarlo a mano desde el panel, o queda un
        # grupo huérfano en el que el comerciante va a mandar ofertas al vacío.
        logger.error("wa_grupo.sin_id", comercio=comercio_id, respuesta=str(respuesta)[:300])
        raise HTTPException(
            status_code=502,
            detail="El grupo se creó pero WhatsApp no devolvió su identificador. "
                   "Buscalo en el teléfono y atalo a mano desde el panel.")

    repo.vincular_grupo_comercio(jid, comercio_id, nombre, "auto", admin["email"])
    logger.info("comercio.grupo_creado", comercio=comercio_id, grupo=jid, by=admin["email"])
    return {"ok": True, "grupo_jid": jid, "nombre": nombre,
            "grupos": repo.list_grupos_comercio(comercio_id)}


@router.get("/admin/altas-por-dia")
def admin_altas_por_dia(
    dias: int = Query(default=60, ge=1, le=365),
    _mod: dict = Depends(require_moderador),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Cuántos comercios se cargaron cada día y en qué estado quedaron.

    Las columnas están elegidas para que se lean de a pares: `altas` contra
    `con_whatsapp` es la diferencia entre un punto en el mapa y un local al que
    se puede escribir; `altas` contra `analizados` dice qué falta pasar por la
    IA. Un total suelto no muestra ninguna de las dos cosas.
    """
    items = repo.altas_por_dia(dias)
    return {"items": items, "total": sum(d["altas"] for d in items)}


class RubrosBody(BaseModel):
    rubro_slugs: list[str]


@router.get("/admin/comercio/{comercio_id}/rubros")
def listar_rubros_comercio(
    comercio_id: str,
    _mod: dict = Depends(require_moderador),
    repo: Repo = Depends(get_repo),
) -> dict:
    return {"rubro_slugs": repo.get_comercio_rubros(comercio_id)}


@router.put("/admin/comercio/{comercio_id}/rubros")
def editar_rubros_comercio(
    comercio_id: str,
    body: RubrosBody,
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Deja el comercio con EXACTAMENTE estos rubros.

    Reemplaza en vez de sumar: hasta ahora sólo se podía agregar, y un rubro mal
    puesto no se podía sacar de ningún lado. Un rubro de más no es un dato
    extra — es un local apareciendo en una búsqueda que no le corresponde.

    El primero de la lista queda como principal.
    """
    if not repo.get_comercio(comercio_id):
        raise HTTPException(status_code=404, detail="No existe ese comercio")

    ids, desconocidos = [], []
    for slug in body.rubro_slugs:
        rid = repo.get_rubro_id(slug)
        (ids.append(rid) if rid else desconocidos.append(slug))
    if desconocidos:
        # Ignorarlos en silencio dejaría al comercio con menos rubros de los que
        # el panel muestra como guardados.
        raise HTTPException(status_code=400,
                            detail=f"Rubros que no existen: {', '.join(desconocidos)}")

    repo.reemplazar_comercio_rubros(comercio_id, ids)
    logger.info("comercio.rubros_editados", comercio=comercio_id,
                rubros=body.rubro_slugs, by=admin["email"])
    return {"ok": True, "rubro_slugs": repo.get_comercio_rubros(comercio_id)}


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
                              "prod_obs_human": c.get("prod_obs_human"),
                              "prod_det_ia": c.get("prod_det_ia"),
                              "descripcion": c.get("descripcion")})
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


# ---- Galería del comercio desde el panel ----
# Hasta ahora sólo podían tocarla el agente que lo cargó y el dueño del comercio.
# El admin no tenía forma de ver ni sumar fotos, y las fotos son justamente lo
# que hay que mirar para saber qué vende un local cuando el texto no alcanza.
_ADMIN_MAX_FOTOS = 10
_ADMIN_MAX_FOTO_BYTES = 15 * 1024 * 1024


def _comercio_o_404(repo: Repo, comercio_id: str) -> dict:
    comercio = repo.get_comercio(comercio_id)
    if not comercio:
        raise HTTPException(status_code=404, detail="Comercio no encontrado")
    return comercio


@router.get("/admin/comercio/{comercio_id}/fotos")
def admin_listar_fotos(
    comercio_id: str,
    _mod: dict = Depends(require_moderador),
    repo: Repo = Depends(get_repo),
) -> dict:
    _comercio_o_404(repo, comercio_id)
    return {"items": repo.list_fotos_comercio(comercio_id)}


@router.post("/admin/comercio/{comercio_id}/fotos")
async def admin_agregar_foto(
    comercio_id: str,
    foto: UploadFile = File(...),
    mod: dict = Depends(require_moderador),
    repo: Repo = Depends(get_repo),
) -> dict:
    comercio = _comercio_o_404(repo, comercio_id)
    if repo.count_fotos_comercio(comercio_id) >= _ADMIN_MAX_FOTOS:
        raise HTTPException(status_code=409, detail=f"Máximo {_ADMIN_MAX_FOTOS} fotos por comercio")
    data = await foto.read()
    if not data:
        raise HTTPException(status_code=400, detail="Falta la foto")
    if len(data) > _ADMIN_MAX_FOTO_BYTES:
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
    logger.info("admin.foto_add", comercio=comercio_id, by=mod["email"])
    return {"ok": True, "foto": row}


@router.delete("/admin/comercio/{comercio_id}/fotos/{foto_id}")
def admin_borrar_foto(
    comercio_id: str,
    foto_id: str,
    mod: dict = Depends(require_moderador),
    repo: Repo = Depends(get_repo),
) -> dict:
    _comercio_o_404(repo, comercio_id)
    if not repo.delete_foto_comercio(foto_id, comercio_id):
        raise HTTPException(status_code=404, detail="Foto no encontrada")
    logger.info("admin.foto_del", comercio=comercio_id, by=mod["email"])
    return {"ok": True}


# ---- Clasificar un comercio desde sus fotos ----
@router.post("/admin/comercio/{comercio_id}/analizar")
async def analizar_comercio(
    comercio_id: str,
    aplicar: bool = Query(False, description="false = sólo proponer; true = escribir"),
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Mira las fotos del local y propone productos, descripción, subcategoría y rubros.

    Por defecto NO escribe: devuelve la propuesta para poder revisarla. Aun con
    `aplicar=true`, `prod_obs_human` no se toca nunca — es el dato de la persona.
    """
    comercio = _comercio_o_404(repo, comercio_id)

    urls = [f["url"] for f in repo.list_fotos_comercio(comercio_id) if f.get("url")]
    if comercio.get("portada_url"):
        urls.insert(0, comercio["portada_url"])   # la portada primero: suele ser la vidriera
    if not urls:
        raise HTTPException(status_code=400, detail="El comercio no tiene fotos para analizar")

    try:
        propuesta = await run_in_threadpool(analizar_fotos, urls, repo.list_rubros())
    except VisionNoConfigurada as exc:
        raise HTTPException(status_code=503, detail=f"{exc}. Cargá GEMINI_API_KEY en backend/.env") from exc

    # Se registran aunque no se aplique la propuesta: que el modelo haya pedido
    # una categoría inexistente es información válida por sí sola.
    # Se registran los rubros que el modelo inventó Y la categoría que sugiere
    # cuando ninguno de los 42 le encaja. Sin lo segundo el reporte queda vacío
    # aunque falten categorías: el prompt obliga a elegir de la lista, así que un
    # modelo obediente nunca "descarta" nada.
    propuestos = list(propuesta.get("slugs_descartados") or [])
    if propuesta.get("categoria_sugerida"):
        propuestos.append(propuesta["categoria_sugerida"])
    if propuestos:
        try:
            repo.registrar_rubros_propuestos(propuestos, comercio_id)
        except Exception:  # noqa: BLE001 — nunca romper el análisis por el registro
            logger.warning("vision.registro_propuestos_fallo", comercio=comercio_id, exc_info=True)

    resultado = {
        "comercio": {"slug": comercio.get("slug"), "nombre": comercio.get("nombre"),
                     "prod_obs_human": comercio.get("prod_obs_human")},
        "fotos_disponibles": len(urls),
        "propuesta": propuesta,
        "aplicado": False,
    }

    if aplicar and propuesta.get("confianza", 0) > 0:
        actualizado = repo.update_comercio(comercio_id, _patch_ia(propuesta, repo, comercio), None)
        if propuesta["rubro_slugs"]:
            aplicar_rubros(repo, actualizado, propuesta["rubro_slugs"])
        resultado["aplicado"] = True
        logger.info("vision.aplicado", comercio=comercio_id, confianza=propuesta.get("confianza"),
                    rubros=propuesta.get("rubro_slugs"), by=admin["email"])

    return resultado


# La ruta /admin/rubros/propuestos estaba declarada DOS VECES.
#
# La primera devolvía {"items": [...], "total": n}; la segunda —la que el panel
# espera— devuelve {"propuestas": [...], "rubros": [...]}. FastAPI se queda con
# la primera que encuentra, así que la segunda nunca corrió y el panel recibía
# un 200 con un cuerpo que no tenía `propuestas`. Al leer `.length` de eso, la
# pantalla entera se caía con "Algo salió mal".
#
# No dio error en ningún lado: ni al arrancar (FastAPI permite duplicados sin
# chistar), ni en la red (200 OK), ni en los tests (ninguno pedía esta ruta).
# Un resultado plausible, que es la forma en que este proyecto falla.
#
# La guarda está en test_rutas_unicas.py: ninguna ruta puede repetir método y
# path. Una regla que se cumple sola no sirve; ésta ahora salta.

# ---- Análisis por fotos en tanda ----
@router.get("/admin/comercios/pendientes-analisis")
def pendientes_analisis(
    _admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    return {"pendientes": repo.contar_sin_analizar()}


@router.post("/admin/comercios/analizar-tanda")
async def analizar_tanda(
    limite: int = Query(5, ge=1, le=20),
    aplicar: bool = Query(True),
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Analiza un puñado de comercios pendientes y devuelve el avance.

    De a pocos y no todos de una: 161 comercios a varios segundos cada uno
    superan cualquier timeout de HTTP, y sobre todo chocan con el límite de
    frecuencia de Gemini. El panel llama a esto en bucle, así el progreso se ve
    y el proceso se puede cortar en cualquier momento sin perder lo hecho.
    """
    pendientes = repo.comercios_sin_analizar(limite)
    if not pendientes:
        return {"procesados": 0, "restantes": 0, "resultados": [], "sin_mas": True}

    rubros = repo.list_rubros()
    resultados = []

    for comercio in pendientes:
        urls = [f["url"] for f in repo.list_fotos_comercio(comercio["id"]) if f.get("url")]
        if comercio.get("portada_url"):
            urls.insert(0, comercio["portada_url"])

        try:
            propuesta = await run_in_threadpool(analizar_fotos, urls, rubros)
        except VisionNoConfigurada as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        fila = {"slug": comercio.get("slug"), "nombre": comercio.get("nombre"),
                "confianza": propuesta.get("confianza", 0),
                "productos": propuesta.get("productos", ""),
                "subcategoria": propuesta.get("subcategoria", ""),
                "rubros": propuesta.get("rubro_slugs", []),
                "tokens": propuesta.get("tokens", {}).get("total"),
                "error": propuesta.get("error")}

        propuestos = list(propuesta.get("slugs_descartados") or [])
        if propuesta.get("categoria_sugerida"):
            propuestos.append(propuesta["categoria_sugerida"])
        if propuestos:
            try:
                repo.registrar_rubros_propuestos(propuestos, comercio["id"])
            except Exception:  # noqa: BLE001
                logger.warning("vision.registro_propuestos_fallo", comercio=comercio["id"])

        if propuesta.get("error"):
            # No se marca como analizado: el fallo puede ser transitorio y
            # conviene reintentarlo en una tanda posterior. Se corta acá para no
            # gastar el resto de la tanda contra un problema que ya se repite.
            resultados.append(fila)
            logger.warning("vision.tanda_cortada", comercio=comercio.get("slug"),
                           error=propuesta.get("error"))
            break

        if aplicar and propuesta.get("confianza", 0) > 0:
            actualizado = repo.update_comercio(comercio["id"], _patch_ia(propuesta, repo, comercio), None)
            if propuesta["rubro_slugs"]:
                aplicar_rubros(repo, actualizado, propuesta["rubro_slugs"])
            fila["aplicado"] = True
        else:
            # Confianza 0 con respuesta válida: el modelo miró y no reconoció
            # nada. Se marca igual para que la tanda avance — si se dejara sin
            # marcar, cada corrida volvería a tropezar con los mismos.
            from datetime import datetime, timezone
            repo.update_comercio(comercio["id"],
                                 {"ia_analizado_at": datetime.now(timezone.utc).isoformat()}, None)
            fila["aplicado"] = False

        resultados.append(fila)

    logger.info("vision.tanda", procesados=len(resultados), by=admin["email"])
    return {
        "procesados": len(resultados),
        "restantes": repo.contar_sin_analizar(),
        "resultados": resultados,
        "sin_mas": False,
    }


class AdornoBody(BaseModel):
    tipo: str | None = None
    lat: float | None = None
    lng: float | None = None
    giro: float | None = None
    escala: float | None = None
    ciudad_slug: str | None = None
    # Sólo para tipo='bandera': cuál ('ar', 'bo', …). Los colores viven en el
    # frontend (lib/adornos.ts); acá viaja sólo la clave.
    variante: str | None = None


TIPOS_ADORNO = {"chalana", "lapacho", "bandera"}


@router.get("/admin/adornos")
def admin_list_adornos(
    ciudad_slug: str = Query(default="bermejo"),
    _mod: dict = Depends(require_moderador),
    repo: Repo = Depends(get_repo),
) -> dict:
    ciudad_id = repo.get_ciudad_id(ciudad_slug) or repo.get_ciudad_id("bermejo")
    return {"items": repo.list_adornos(ciudad_id)}


@router.post("/admin/adornos")
def admin_crear_adorno(
    body: AdornoBody,
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    tipo = (body.tipo or "").strip()
    if tipo not in TIPOS_ADORNO:
        raise HTTPException(status_code=400, detail=f"Tipo inválido: {tipo or '(vacío)'}")
    if body.lat is None or body.lng is None:
        raise HTTPException(status_code=400, detail="Falta la ubicación")

    ciudad_id = repo.get_ciudad_id(body.ciudad_slug or "bermejo") or repo.get_ciudad_id("bermejo")
    adorno = repo.crear_adorno({
        "tipo": tipo, "lat": body.lat, "lng": body.lng, "ciudad_id": ciudad_id,
        "giro": body.giro if body.giro is not None else 0,
        "escala": body.escala if body.escala is not None else 1,
        # Una bandera sin variante se dibujaría como la de Bolivia por defecto,
        # que sería adivinar cuál quiso poner. Mejor guardar lo que mandó.
        "variante": body.variante,
    })
    logger.info("admin.adorno_creado", tipo=tipo, by=admin["email"])
    return {"ok": True, "adorno": adorno}


@router.put("/admin/adornos/{adorno_id}")
def admin_update_adorno(
    adorno_id: str,
    body: AdornoBody,
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    patch: dict = {}
    if body.tipo is not None:
        if body.tipo not in TIPOS_ADORNO:
            raise HTTPException(status_code=400, detail=f"Tipo inválido: {body.tipo}")
        patch["tipo"] = body.tipo
    for campo in ("lat", "lng", "giro", "escala", "variante"):
        valor = getattr(body, campo)
        if valor is not None:
            patch[campo] = valor
    if not patch:
        raise HTTPException(status_code=400, detail="Nada para actualizar")
    return {"ok": True, "adorno": repo.update_adorno(adorno_id, patch)}


@router.delete("/admin/adornos/{adorno_id}")
def admin_delete_adorno(
    adorno_id: str,
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    # Baja lógica, igual que los lugares: un adorno borrado por error se
    # recupera con un update, y son datos puestos a mano que cuesta rehacer.
    repo.update_adorno(adorno_id, {"activo": False})
    logger.info("admin.adorno_borrado", adorno=adorno_id, by=admin["email"])
    return {"ok": True}


@router.get("/admin/catalogo")
def admin_catalogo(
    _mod: dict = Depends(require_moderador),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Rubros y productos con cuántos comercios tiene cada uno, y los huecos.

    Los huecos son de dos tipos distintos y el panel los muestra por separado
    porque se resuelven distinto: un rubro sin comercios puede ser una categoría
    que sobra o un relevamiento que falta —sólo lo sabe quien camina la ciudad—,
    mientras que un término buscado sin resultado es demanda medida y ya dice a
    qué salir a buscar.
    """
    from app.services.catalogo import informe

    return informe(repo)


# ── Peso de las fotos ─────────────────────────────────────────────────────────

@router.get("/admin/fotos/peso")
async def admin_fotos_peso(
    _mod: dict = Depends(require_moderador),
) -> dict:
    """Cuánto ocupan las fotos y los videos, y cuáles son los archivos más pesados.

    Va antes que cualquier botón de optimizar: todo lo que sube por el backend
    ya pasa por `procesar_imagen`, así que lo probable es que las fotos estén
    bien y el peso esté en los videos —que se guardan crudos— o en un puñado de
    archivos que entraron por otro camino. Apretar "reducir" sin mirar esto es
    trabajar sobre una suposición.
    """
    from app.services.peso_fotos import medir

    # Recorrer miles de archivos bloquea el event loop y con él todas las
    # demás peticiones del panel.
    return await run_in_threadpool(medir, settings.fotos_dir)


class OptimizarFotosBody(BaseModel):
    # Sin default a propósito: la operación pisa el archivo original y no se
    # puede deshacer. Que haya que escribir el umbral obliga a haber mirado la
    # medición antes.
    max_kb: int
    limite: int = 50


@router.post("/admin/fotos/optimizar")
async def admin_fotos_optimizar(
    body: OptimizarFotosBody,
    admin: dict = Depends(require_admin),
) -> dict:
    """Recomprime las imágenes que pasan `max_kb`. Irreversible.

    Pide admin y no moderador: pisa archivos sin vuelta atrás.
    """
    from app.services.peso_fotos import optimizar

    if body.max_kb < 50:
        # Por debajo de 50KB no hay nada que ganar y sí calidad que perder: la
        # portada de una ficha a 30KB se ve mal en un celular moderno.
        raise HTTPException(status_code=400, detail="El umbral mínimo es 50 KB")

    res = await run_in_threadpool(
        optimizar, settings.fotos_dir, body.max_kb, max(1, min(body.limite, 500)))
    logger.info("admin.fotos_optimizadas", by=admin["email"], **{
        k: v for k, v in res.items() if k != "detalle"})
    return res


# ── Vencimientos ──────────────────────────────────────────────────────────────

class VencimientoBody(BaseModel):
    nombre: str | None = None
    tipo: str | None = None
    vence_el: str | None = None
    aviso_dias: int | None = None
    proveedor: str | None = None
    url: str | None = None
    notas: str | None = None


_TIPOS_VENC = {"dominio", "hosting", "servicio", "sim", "plan", "otro"}


@router.get("/admin/vencimientos")
async def admin_vencimientos(
    _mod: dict = Depends(require_moderador),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Lo que se vence, y los certificados medidos en vivo.

    Van juntos en una sola respuesta porque el panel los muestra juntos: al que
    mira le da igual si la fecha la cargó una persona o la midió el sistema, lo
    que quiere saber es qué está por romperse.
    """
    from app.services.vencimientos import HOSTS_TLS, con_estado, vence_certificado

    items = con_estado(repo.list_vencimientos())

    # En hilo aparte y en paralelo: son cinco conexiones TLS con timeout, y
    # secuenciales podrían tardar media pantalla de espera si un host no responde.
    certs = await run_in_threadpool(
        lambda: [{**vence_certificado(h), "que_sirve": q} for h, q in HOSTS_TLS])

    return {
        "items": items,
        "certificados": certs,
        # El número que va en la pestaña. Las `sin_fecha` NO cuentan como alerta
        # —no son urgentes, son trabajo pendiente— pero sí se muestran aparte:
        # mezclarlas volvería el aviso ruido y el ruido se aprende a ignorar.
        "alertas": sum(1 for i in items if i["estado"] in {"vencido", "critico", "por_vencer"})
                   + sum(1 for c in certs if c.get("estado") in {"vencido", "critico", "por_vencer"}),
        "sin_fecha": sum(1 for i in items if i["estado"] == "sin_fecha"),
    }


@router.post("/admin/vencimientos")
def admin_crear_vencimiento(
    body: VencimientoBody,
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    if not (body.nombre or "").strip():
        raise HTTPException(status_code=400, detail="Falta el nombre")
    if body.tipo and body.tipo not in _TIPOS_VENC:
        raise HTTPException(status_code=400, detail=f"Tipo desconocido: {body.tipo}")
    row = {k: v for k, v in body.model_dump().items() if v is not None}
    creado = repo.crear_vencimiento(row)
    logger.info("admin.vencimiento_creado", nombre=body.nombre, by=admin["email"])
    return {"ok": True, "item": creado}


@router.put("/admin/vencimientos/{vid}")
def admin_editar_vencimiento(
    vid: str,
    body: VencimientoBody,
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    if body.tipo and body.tipo not in _TIPOS_VENC:
        raise HTTPException(status_code=400, detail=f"Tipo desconocido: {body.tipo}")
    # `exclude_unset` y no `if v is not None`: sin eso, borrar una fecha
    # mandando null sería imposible — se leería como "no lo toques".
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(status_code=400, detail="No hay nada que cambiar")
    logger.info("admin.vencimiento_editado", id=vid, campos=list(patch), by=admin["email"])
    return {"ok": True, "item": repo.update_vencimiento(vid, patch)}


@router.delete("/admin/vencimientos/{vid}")
def admin_borrar_vencimiento(
    vid: str,
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    repo.borrar_vencimiento(vid)
    logger.info("admin.vencimiento_borrado", id=vid, by=admin["email"])
    return {"ok": True}


# ── Rubros: crear, resolver propuestas y completar ────────────────────────────

@router.get("/admin/rubros/propuestos")
def admin_rubros_propuestos(
    _mod: dict = Depends(require_moderador),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Las categorías que la IA pidió y no existen, por frecuencia.

    Es la lista de qué falta MEDIDA y no supuesta: sale de vidrieras reales de
    Bermejo. Leerla bien es lo que evita repetir los 19 rubros vacíos que hubo
    que apagar en agosto — cada fila puede ser un rubro que falta o simplemente
    otra forma de decir uno que ya existe, y son cosas distintas.
    """
    return {
        "propuestas": repo.resumen_rubros_propuestos(60),
        "rubros": repo.list_rubros(),
    }


class RubroNuevoBody(BaseModel):
    slug: str
    nombre: str
    icono: str | None = None
    orden: int | None = None
    comercial: bool = True
    # Las palabras del diccionario, separadas por coma. Se arma un solo patrón:
    # el matcheo es una regex de Postgres y una alternancia es más barata que
    # veinte filas.
    palabras: str | None = None
    # De qué propuesta salió, para sacarla de la cola.
    resolver: str | None = None


_RE_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@router.post("/admin/rubros")
def admin_crear_rubro(
    body: RubroNuevoBody,
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    if not _RE_SLUG.match(body.slug):
        raise HTTPException(
            status_code=400,
            detail="El slug va en minúsculas, sin tildes ni espacios: 'taller-mecanico'")
    if not body.nombre.strip():
        raise HTTPException(status_code=400, detail="Falta el nombre")

    rubro = repo.crear_rubro({
        "slug": body.slug, "nombre": body.nombre.strip(),
        "icono": body.icono, "orden": body.orden or 99,
        "comercial": body.comercial,
    })
    if body.palabras and body.palabras.strip():
        repo.agregar_palabras_rubro(body.slug, _patron_de(body.palabras))
    if body.resolver:
        repo.borrar_propuestas(body.resolver)
    logger.info("admin.rubro_creado", slug=body.slug, by=admin["email"])
    return {"ok": True, "rubro": rubro}


class SinonimoBody(BaseModel):
    """Una propuesta que NO es un rubro nuevo, sino otra forma de decir uno que
    ya existe: 'lubricentro' es neumáticos, 'bijouterie' es joyería."""
    rubro_slug: str
    palabras: str
    resolver: str | None = None


@router.post("/admin/rubros/palabras")
def admin_agregar_palabras(
    body: SinonimoBody,
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    if not any(r["slug"] == body.rubro_slug for r in repo.list_rubros()):
        raise HTTPException(status_code=400, detail=f"No existe el rubro {body.rubro_slug}")
    if not body.palabras.strip():
        raise HTTPException(status_code=400, detail="Faltan las palabras")
    repo.agregar_palabras_rubro(body.rubro_slug, _patron_de(body.palabras))
    if body.resolver:
        repo.borrar_propuestas(body.resolver)
    logger.info("admin.palabras_agregadas", rubro=body.rubro_slug, by=admin["email"])
    return {"ok": True}


def _patron_de(palabras: str) -> str:
    r"""'lubricentro, engrase' -> '\m(lubricentro|engrase)'.

    `\m` es inicio de palabra en Postgres, y es lo que evita que "bar" matchee
    dentro de "barbería". Los caracteres especiales de regex se escapan: alguien
    va a escribir un paréntesis alguna vez, y sin escapar rompe el patrón entero
    —o peor, matchea de más— sin dar ningún error.
    """
    partes = []
    for p in palabras.split(","):
        t = " ".join(p.strip().lower().split())
        if not t:
            continue
        partes.append(re.escape(t))
    return r"\m(" + "|".join(dict.fromkeys(partes)) + ")"


@router.post("/admin/rubros/completar")
async def admin_completar_rubros(
    aplicar: bool = Query(default=False),
    rubros: str = Query(default=""),
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Simula —o aplica— los rubros que los productos de cada comercio sugieren.

    Lo mismo que corre `scripts/completar_rubros.py`: la lógica vive en un solo
    lugar, porque dos copias de una regla de clasificación se separan en semanas
    y después nadie sabe cuál informe creer.
    """
    from app.services.rubros_auto import LecturaIncompleta
    from app.services.rubros_auto import analizar as _analizar
    from app.services.rubros_auto import aplicar as _aplicar

    filtro = {s.strip() for s in rubros.split(",") if s.strip()} or None
    try:
        informe = await run_in_threadpool(_analizar, repo, filtro)
    except LecturaIncompleta as exc:
        # 409 y no 200-con-aviso: un aviso adentro de un informe se lee por
        # arriba y el número grande se cree igual.
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if not aplicar:
        return {**{k: v for k, v in informe.items() if k != "_todos"}, "aplicado": False}

    hechos = await run_in_threadpool(_aplicar, repo, informe)
    logger.info("admin.rubros_completados", rubros=hechos, by=admin["email"])
    return {**{k: v for k, v in informe.items() if k != "_todos"},
            "aplicado": True, "rubros_agregados": hechos}


class PreviewBody(BaseModel):
    palabras: str
    rubro_slug: str | None = None


@router.post("/admin/rubros/previsualizar")
async def admin_previsualizar_palabras(
    body: PreviewBody,
    _mod: dict = Depends(require_moderador),
    repo: Repo = Depends(get_repo),
) -> dict:
    """A qué comercios alcanzaría esta palabra, antes de guardarla.

    Es la respuesta a la pregunta que más caro salió del diccionario, y no es
    de criterio sino de alcance: una palabra correcta que además aparece en otro
    lado. "papa frita" describe bien la comida rápida y está en todos los
    kioscos; "bar" está dentro de "barbería".

    Eso es contable, no opinable — por eso lo cuenta una consulta y no un
    modelo. Un modelo puede advertirlo o no; esto acierta siempre.
    """
    if not body.palabras.strip():
        raise HTTPException(status_code=400, detail="Faltan las palabras")
    patron = _patron_de(body.palabras)
    filas = await run_in_threadpool(repo.previsualizar_patron, patron, body.rubro_slug)

    nuevos = [f for f in filas if not f.get("ya_lo_tiene")]
    # Con qué OTROS rubros conviven los que alcanzaría. Si los nuevos son todos
    # de un mismo rubro ajeno, la palabra está arrastrando y no clasificando —
    # que es exactamente lo que pasaba con "papa frita" y los kioscos.
    ajenos: dict[str, int] = {}
    for f in nuevos:
        for slug in (f.get("otros_rubros") or []):
            ajenos[slug] = ajenos.get(slug, 0) + 1

    return {
        "patron": patron,
        "alcanza": len(filas),
        "ya_lo_tienen": len(filas) - len(nuevos),
        "nuevos": len(nuevos),
        "conviven_con": sorted(({"slug": s, "comercios": n} for s, n in ajenos.items()),
                               key=lambda x: -x["comercios"])[:8],
        "ejemplos": [{"codigo": f.get("codigo"), "nombre": f.get("nombre"),
                      "vende": f.get("vende"), "otros_rubros": f.get("otros_rubros") or []}
                     for f in nuevos[:15]],
        # El tope de la función SQL. Sin decirlo, 200 se lee como "son 200".
        "recortado": len(filas) >= 200,
    }


# ── Análisis de las fotos de las ofertas ─────────────────────────────────────

@router.get("/admin/publicaciones/pendientes-analisis")
def admin_pubs_pendientes_analisis(
    _mod: dict = Depends(require_moderador),
    repo: Repo = Depends(get_repo),
) -> dict:
    return {"pendientes": len(repo.publicaciones_sin_analizar(500))}


@router.post("/admin/publicaciones/analizar-tanda")
async def admin_analizar_ofertas(
    limite: int = Query(default=3, ge=1, le=10),
    aplicar: bool = Query(default=True),
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Lee las fotos de las ofertas: qué son, con qué palabras se buscan y el
    precio si está escrito en la imagen.

    Existe por una razón concreta: el índice de búsqueda de `publicaciones` sale
    del título y la descripción, y cuando la oferta trae foto el título queda en
    NULL a propósito. Un comerciante apurado manda la foto sola — y esa oferta
    no aparecía en ninguna búsqueda.

    Va de a pocas y en bucle desde el navegador, igual que el análisis de
    comercios: cada llamada tarda segundos y el avance se ve.
    """
    from app.services.vision import VisionNoConfigurada, analizar_oferta

    pendientes = repo.publicaciones_sin_analizar(limite)
    if not pendientes:
        return {"procesados": 0, "sin_mas": True, "resultados": [], "restantes": 0}

    from datetime import datetime, timezone

    resultados = []
    for pub in pendientes:
        try:
            out = await run_in_threadpool(analizar_oferta, pub["imagen_url"])
        except VisionNoConfigurada as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        fila = {"id": pub["id"], "titulo": out.get("titulo"), "precio": out.get("precio"),
                "es_oferta": out.get("es_oferta"), "confianza": out.get("confianza"),
                "error": out.get("error")}

        if out.get("error"):
            # No se marca como analizada: el fallo puede ser transitorio. Y se
            # corta la tanda, para no gastarla contra un problema que se repite.
            resultados.append(fila)
            break

        patch: dict = {"ia_analizado_at": datetime.now(timezone.utc).isoformat()}
        if aplicar and out.get("confianza", 0) > 0 and out.get("es_oferta"):
            patch["terminos_ia"] = out["terminos"]
            # El título SÓLO si no hay uno: si el comerciante escribió algo, eso
            # gana. Lo que él dijo con sus palabras vale más que lo que dedujo
            # el modelo, y es la misma regla que separa `prod_obs_human` de
            # `prod_det_ia` en los comercios.
            if not (pub.get("titulo") or "").strip() and out.get("titulo"):
                patch["titulo"] = out["titulo"]
            # El precio también: sólo si falta Y si el modelo lo LEYÓ en la
            # foto. Un precio inventado manda a alguien a caminar veinte cuadras
            # para encontrar otro, y eso se paga con el comercio y el comprador.
            if pub.get("precio") is None and out.get("precio") is not None:
                patch["precio"] = out["precio"]
                patch["moneda"] = out["moneda"]
            fila["aplicado"] = True
        else:
            # Confianza 0 o "no es una oferta": se marca igual para que la cola
            # avance. Si no, cada corrida vuelve a tropezar con las mismas.
            fila["aplicado"] = False

        repo.update_publicacion(pub["id"], patch)
        resultados.append(fila)

    logger.info("vision.ofertas_tanda", procesados=len(resultados), by=admin["email"])
    restantes = len(repo.publicaciones_sin_analizar(500))
    return {"procesados": len(resultados), "resultados": resultados,
            "restantes": restantes, "sin_mas": restantes == 0}


class AplicarPatronBody(BaseModel):
    rubro_slug: str
    palabras: str


@router.post("/admin/rubros/recalcular-principal")
async def admin_recalcular_principal(
    aplicar: bool = Query(default=False),
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Arregla el rubro principal SÓLO donde no hay nada que decidir.

    De los que no cierran, algunos tienen **una sola** sugerencia: el texto
    dispara un único rubro y la ficha muestra otro. Ahí no falta criterio, falta
    que alguien lo escriba — y son 102 de 194.

    Los demás tienen dos o tres, y ésos NO se tocan. La razón es concreta y no
    es prudencia: `rubros_sugeridos` devuelve un `array_agg(distinct ...)`, o
    sea orden alfabético. Con varias sugerencias, "la primera" no significa
    nada — Bazar gana porque empieza con B. Elegir entre tres es criterio
    humano, y para eso está la cola.

    No marca los comercios como revisados por una persona: la marca tiene que
    seguir queriendo decir eso. Salen de la cola solos, porque la cola es "el
    principal no está entre las sugerencias" y después de esto sí lo está.

    Sin `aplicar=true` no escribe nada: devuelve la lista de qué cambiaría.
    """
    from app.services.rubros_auto import MAX_RUBROS

    filas = await run_in_threadpool(repo.rubros_a_revisar, "dudosos", 1000)
    unicos = [f for f in filas if len(f.get("sugeridos") or []) == 1]

    detalle, salteados, hechos = [], [], 0
    for f in unicos:
        destino = f["sugeridos"][0]
        otros = [s for s in (f.get("ya_tiene") or []) if s != destino]
        # El mismo tope que el completado masivo: un comercio en siete
        # categorías no filtra en ninguna, y sumarle una más lo empeora.
        if len(otros) + 1 > MAX_RUBROS:
            salteados.append({"codigo": f.get("codigo"), "nombre": f.get("nombre")})
            continue

        detalle.append({
            "comercio_id": f["comercio_id"], "codigo": f.get("codigo"),
            "nombre": f.get("nombre"), "de": f.get("principal_nombre") or f.get("principal"),
            "a": destino, "texto": (f.get("texto") or "")[:110],
        })
        if not aplicar:
            continue

        repo.update_comercio(f["comercio_id"], {}, [destino] + otros)
        repo.registrar_correccion_rubro({
            "comercio_id": f["comercio_id"],
            "veredicto": "corregido",
            "rubro_antes": f.get("principal"),
            "rubro_nuevo": destino,
            "texto": (f.get("texto") or "")[:2000],
            # Queda dicho que esto no lo decidió una persona: el día que haya que
            # auditar una clasificación rara, la diferencia importa.
            "revisado_por": f"recalculo-automatico ({admin['email']})",
        })
        hechos += 1

    if aplicar:
        logger.info("admin.recalculo_principal", comercios=hechos, by=admin["email"])
    return {
        "aplicado": aplicar, "cambiados": hechos if aplicar else 0,
        "candidatos": len(detalle),
        # Cuántos quedan para revisar a mano, dicho acá para que el botón no se
        # lea como "esto arregla todo".
        "ambiguos": len(filas) - len(unicos),
        "salteados": salteados,
        "detalle": detalle[:200],
        "detalle_recortado": max(0, len(detalle) - 200),
    }


@router.post("/admin/comercio/{comercio_id}/rubro/sugerencias")
async def admin_sugerencias_de_rubro(
    comercio_id: str,
    _mod: dict = Depends(require_moderador),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Recalcular el rubro de UN comercio, ahora, sin cambiar nada.

    Devuelve las dos opiniones por separado y no una mezclada, porque no valen
    lo mismo:

    - **El diccionario** es lo que clasifica de verdad. Si acá dice "hospedaje",
      cualquier comercio nuevo con ese texto va a caer en hospedaje solo. Es la
      respuesta que importa.
    - **La IA** es una segunda opinión, y sirve sobre todo cuando el diccionario
      no dice nada: son 56 rubros, y buscar a mano en esa lista es justo lo que
      hace que revisar 200 comercios se abandone a la mitad.

    Mezcladas en un solo número, la de la IA taparía que el diccionario no sabe
    — y ese hueco es exactamente lo que hay que ver para saber qué palabra
    agregar.

    No escribe: el que aplica es el veredicto humano, en el endpoint de al lado.
    """
    comercio = repo.get_comercio(comercio_id)
    if not comercio:
        raise HTTPException(status_code=404, detail="No existe el comercio")

    # El MISMO texto que arma la clasificación real (`rubros_auto._texto_de`).
    # Mostrar otro sería tranquilizar sobre algo que no se probó.
    texto = " ".join(filter(None, [comercio.get("nombre"), comercio.get("subcategoria"),
                                   comercio.get("prod_det_ia")]))
    rubros = repo.list_rubros()
    nombres = {r["slug"]: r.get("nombre", r["slug"]) for r in rubros}

    diccionario = await run_in_threadpool(repo.sugerir_rubros_por_texto, texto)
    ia = await run_in_threadpool(
        clasificador.sugerir_rubros_explicado, comercio.get("nombre") or "", texto, rubros)

    def _con_nombre(slugs):
        return [{"slug": s, "nombre": nombres.get(s, s)} for s in slugs if s in nombres]

    return {
        "texto": texto,
        "ya_tiene": _con_nombre(repo.get_comercio_rubros(comercio_id)),
        "diccionario": _con_nombre([s for s in diccionario if s != "otros"]),
        "ia": ({"rubros": _con_nombre(ia["rubros"]), "motivo": ia["motivo"]} if ia else None),
    }


class RevisionRubroBody(BaseModel):
    """El veredicto de una persona sobre cómo quedó clasificado un comercio."""
    veredicto: str                      # "ok" | "corregido"
    # Los rubros correctos, EN ORDEN: el primero es el principal —el que sale en
    # la ficha, en el color del pin y en el filtro— y los demás quedan para que
    # el buscador lo encuentre. Un comercio casi nunca es una sola cosa: el
    # puesto de coca machucada también vende bebidas y golosinas, y obligarlo a
    # elegir uno lo saca de las otras dos búsquedas.
    rubro_slugs: list[str] | None = None
    # Forma vieja, de un solo rubro. Se mantiene porque la cola de revisión la
    # usa para el atajo de un toque.
    rubro_slug: str | None = None
    # El rubro que la persona TENÍA A LA VISTA cuando decidió. Viaja desde el
    # panel en vez de releerse acá: si entre que se dibujó la cola y se apretó
    # el botón alguien más lo cambió, lo que queda anotado es sobre qué se
    # opinó de verdad.
    rubro_antes: str | None = None
    # Palabra que lo hubiera clasificado bien. Opcional a propósito: se manda
    # sólo si el que revisa ya vio la vista previa de a cuántos alcanza.
    palabras: str | None = None


@router.get("/admin/rubros/revision")
async def admin_rubros_revision(
    estado: str = Query(default="dudosos"),
    limite: int = Query(default=100, le=300),
    _mod: dict = Depends(require_moderador),
    repo: Repo = Depends(get_repo),
) -> dict:
    """La cola de clasificaciones que no cierran, para mirarlas de a una.

    Es la respuesta al tamaño real del problema: de 1080 comercios activos, 851
    tienen el principal coherente con lo que el diccionario diría hoy. Revisar
    "todo" son 229 fichas, no 1080 — y esa diferencia es la que decide si esto se
    hace o se abandona a la semana.

    No propone nada automático. Muestra el texto que se clasificó, el rubro que
    está puesto y los que el diccionario deduce, y deja que una persona diga
    cuál es. Lo que aprende el sistema es lo que esa persona escribe.
    """
    items = await run_in_threadpool(repo.rubros_a_revisar, estado, limite)
    resumen = await run_in_threadpool(repo.rubros_revision_resumen)
    return {"items": items, "resumen": resumen, "rubros": repo.list_rubros()}


@router.post("/admin/rubros/revision/{comercio_id}")
async def admin_revisar_rubro(
    comercio_id: str,
    body: RevisionRubroBody,
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Guarda el veredicto y, si hubo corrección, la aplica.

    Marca el comercio como revisado por una persona SIEMPRE, incluso cuando el
    veredicto es "está bien". Ese es el punto: un comercio revisado sale de la
    cola y ninguna corrida masiva lo vuelve a tocar. Sin la marca, el próximo
    recálculo pisa las correcciones a mano y nadie se entera.
    """
    if body.veredicto not in {"ok", "corregido"}:
        raise HTTPException(status_code=400, detail="Veredicto inválido")

    comercio = repo.get_comercio(comercio_id)
    if not comercio:
        raise HTTPException(status_code=404, detail="No existe el comercio")

    texto = " ".join(filter(None, [comercio.get("nombre"), comercio.get("subcategoria"),
                                   comercio.get("prod_det_ia")]))

    elegidos = [s for s in (body.rubro_slugs or ([body.rubro_slug] if body.rubro_slug else []))
                if s]
    elegidos = list(dict.fromkeys(elegidos))  # sin repetidos, conservando el orden

    if body.veredicto == "corregido":
        if not elegidos:
            raise HTTPException(status_code=400, detail="Falta el rubro correcto")
        existentes = {r["slug"] for r in repo.list_rubros()}
        faltan = [s for s in elegidos if s not in existentes]
        if faltan:
            raise HTTPException(status_code=400, detail=f"No existe el rubro {faltan[0]}")

        if body.rubro_slugs is not None:
            # Lista explícita: es EXACTAMENTE lo que la persona dejó marcado, en
            # su orden. Sumarle los que ya tenía haría imposible sacar uno mal
            # puesto, que es la mitad de para qué se abre esta pantalla.
            repo.update_comercio(comercio_id, {}, elegidos)
        else:
            # Atajo de un toque desde la cola: el elegido pasa al frente y los
            # que ya tenía quedan detrás. Mandar sólo el nuevo borraría los
            # demás y el buscador dejaría de encontrarlo por ellos.
            otros = [s for s in repo.get_comercio_rubros(comercio_id) if s not in elegidos]
            repo.update_comercio(comercio_id, {}, elegidos + otros)

        if body.palabras and body.palabras.strip():
            repo.agregar_palabras_rubro(elegidos[0], _patron_de(body.palabras))

    repo.marcar_rubro_revisado(comercio_id, admin["email"])
    repo.registrar_correccion_rubro({
        "comercio_id": comercio_id,
        "veredicto": body.veredicto,
        "rubro_antes": body.rubro_antes,
        "rubro_nuevo": (", ".join(elegidos) if body.veredicto == "corregido" else None),
        "texto": texto[:2000],
        "palabras": body.palabras,
        "revisado_por": admin["email"],
    })
    logger.info("admin.rubro_revisado", comercio=comercio_id, veredicto=body.veredicto,
                rubros=elegidos, by=admin["email"])
    return {"ok": True}


@router.post("/admin/rubros/aplicar-patron")
async def admin_aplicar_patron(
    body: AplicarPatronBody,
    admin: dict = Depends(require_admin),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Le agrega el rubro a los comercios que esta palabra alcanza, ahora.

    Cierra el hueco entre crear un rubro y que los comercios lo tengan. Antes
    había que acordarse de correr "Completar rubros" después; si nadie lo hacía,
    el rubro quedaba con cero comercios y parecía roto — el rubro existía, el
    diccionario existía, y en la fila de chips prometía algo que no había.

    Se aplica SOBRE LA MISMA LISTA que se acaba de ver en la vista previa, no
    sobre un recálculo: lo que se escribe es exactamente lo que se miró.
    """
    if not any(r["slug"] == body.rubro_slug for r in repo.list_rubros()):
        raise HTTPException(status_code=400, detail=f"No existe el rubro {body.rubro_slug}")

    from app.services.rubros_auto import MAX_RUBROS

    patron = _patron_de(body.palabras)
    filas = await run_in_threadpool(repo.previsualizar_patron, patron, body.rubro_slug)
    rubro_id = repo.get_rubro_id(body.rubro_slug)
    if not rubro_id:
        raise HTTPException(status_code=400, detail="El rubro no tiene id")

    agregados, salteados = 0, []
    for f in filas:
        if f.get("ya_lo_tiene"):
            continue
        otros = list(f.get("otros_rubros") or [])
        # El mismo tope que el completado masivo: un comercio en siete
        # categorías no filtra en ninguna, y agregarle una más lo empeora.
        if len(otros) + 1 > MAX_RUBROS:
            salteados.append({"codigo": f.get("codigo"), "nombre": f.get("nombre"),
                              "rubros": len(otros)})
            continue
        previos = [rid for rid in (repo.get_rubro_id(s) for s in otros) if rid]
        repo.set_comercio_rubros(f["comercio_id"], list(dict.fromkeys(previos + [rubro_id])))
        agregados += 1

    logger.info("admin.patron_aplicado", rubro=body.rubro_slug, comercios=agregados,
                by=admin["email"])
    return {"ok": True, "agregados": agregados, "salteados": salteados}
