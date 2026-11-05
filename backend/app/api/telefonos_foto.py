"""Panel «Teléfonos en fotos» (docs/telefonos-en-fotos.md): las propuestas que dejó el worker y qué hacer con ellas.

QUIÉN PUEDE
===========
El permiso `moderar`, el mismo de «Negocios» en el panel. Aplicar un número ESCRIBE en el comercio, así que
además se exige `comercios.editar` (el de «Editar negocio»): sin eso, `moderar` solo serviría para saltear ese
permiso. Quien está limitado a una ciudad (el claim `ciudad` sin alcance global) ve y toca sólo los comercios
de la suya, con el mismo criterio del contenido para redes (`content._alcance`): lo que no es de su ciudad se
contesta como «no existe» (404; en el lote, con el motivo `otra_ciudad`).

APLICAR UN NÚMERO NO TIENE CAMINO PROPIO
========================================
Escribir en `comercios` va por `moderacion.editar_comercio`, la función del endpoint «Editar negocio»: ahí está
la validación del WhatsApp (formato, que no sea de otro comercio, que cambiarlo anule la clave de la cuenta),
el permiso extra `comercios.cuenta` para tocar el WhatsApp y el registro `moderacion.comercio_editado`. Acá no
se repite nada de eso: se arma el mismo cuerpo y se la llama. Por eso, para APLICAR COMO WHATSAPP hace falta
también `comercios.cuenta` (como al editar el WhatsApp a mano); como teléfono alcanza `comercios.editar`.

Nada de esto es público: el front del sitio nunca lee estas tablas.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.content import _alcance
from app.api.moderacion import EditarComercioBody, editar_comercio
from app.core.auth import require_permiso
from app.core.config import settings
from app.core.permisos import tiene as tiene_permiso
from app.core.telefono import validar_whatsapp
from app.core.telefonos_foto import mismo_numero, numero_visible, whatsapp_de
from app.db.content_repository import ContentRepo, get_content_repo
from app.db.repository import Repo, get_repo
from app.db.telefonos_repository import TelefonosRepo, get_telefonos_repo
from app.services import telefonos_foto

router = APIRouter()
logger = structlog.get_logger()

_permiso = require_permiso("moderar")

ESTADOS = ("pendiente", "coincide", "aplicado_whatsapp", "aplicado_telefono", "descartado")
_RESUELTOS = ("aplicado_whatsapp", "aplicado_telefono", "descartado")
MAX_LOTE = 100

#: Los motivos con que el lote saltea un número (`saltados[].motivo`): claves cortas en snake_case para que el
#: panel las traduzca.
MOTIVOS_LOTE = ("no_existe", "otra_ciudad", "no_pendiente", "no_celular", "compartido", "tiene_whatsapp",
                "sin_permiso", "numero_en_uso", "whatsapp_invalido", "error")


class AplicarBody(BaseModel):
    como: Literal["whatsapp", "telefono"]
    #: true si el comercio ya tiene otro valor en ese campo y se lo quiere pisar.
    reemplazar: bool = False


class LoteBody(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=MAX_LOTE)


def _actor(claims: dict) -> str:
    return claims.get("email") or claims.get("sub") or "desconocido"


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ciudad_id_del_filtro(trepo: TelefonosRepo, claims: dict, slug: str | None) -> tuple[str | None, bool]:
    """`(ciudad_id a filtrar, la ciudad de quien pregunta no existe)`. Quien está limitado a una ciudad ve SÓLO la
    suya (el `?ciudad=` del cliente no cuenta); si su ciudad no existe en la base no ve nada. Un slug desconocido
    es 404."""
    al = _alcance(trepo, claims)
    if al:
        return al.id, al.id is None
    slug = (slug or "").strip()
    if not slug:
        return None, False
    fila = next((c for c in trepo.list_ciudades() if c["slug"] == slug), None)
    if not fila:
        raise HTTPException(status_code=404, detail=f"Ciudad no encontrada: {slug}")
    return fila["id"], False


def _item(d: dict, otros: int) -> dict:
    c = d.get("comercios") or {}
    ciudad = c.get("ciudades") or {}
    return {
        "id": d["id"],
        "comercio": {"id": c.get("id") or d.get("comercio_id"), "nombre": c.get("nombre"), "slug": c.get("slug"),
                     "whatsapp": c.get("whatsapp"), "telefono": c.get("telefono"),
                     "ciudad": ciudad.get("nombre"), "ciudad_slug": ciudad.get("slug")},
        "numero": d["numero"],
        "numero_visible": numero_visible(d["numero"]),
        "tipo": d["tipo"],
        "texto_leido": d["texto_leido"],
        "foto_url": d["foto_url"],
        # La miniatura sólo si la foto leída sigue siendo la portada actual del comercio.
        "foto_thumb_url": c.get("portada_thumb_url") if c.get("portada_url") == d["foto_url"] else None,
        "motor": d["motor"],
        "estado": d["estado"],
        "compartido": bool(d.get("compartido")),
        "otros_comercios": max(0, otros - 1),
    }


@router.get("/admin/telefonos-detectados")
def listar(
    ciudad: str | None = Query(default=None, max_length=60, description="slug de la ciudad (opcional)"),
    estado: str | None = Query(default=None, description="pendiente, coincide, aplicado_whatsapp, aplicado_telefono o descartado; sin él, todos"),
    sin_whatsapp: bool = Query(default=False, description="sólo comercios que no tienen WhatsApp"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    claims: dict = Depends(_permiso),
    trepo: TelefonosRepo = Depends(get_telefonos_repo),
) -> dict:
    """`{items: [{id, comercio: {id, nombre, slug, whatsapp, telefono, ciudad, ciudad_slug}, numero, numero_visible,
    tipo, texto_leido, foto_url, foto_thumb_url, motor, estado, compartido, otros_comercios}], total}`.
    Sin `estado` devuelve todos los estados."""
    if estado and estado not in ESTADOS:
        raise HTTPException(status_code=400, detail=f"Estado desconocido: {estado}")
    ciudad_id, sin_ciudad = _ciudad_id_del_filtro(trepo, claims, ciudad)
    if sin_ciudad:
        return {"items": [], "total": 0}
    filas, total = trepo.list_detectados(estado or None, ciudad_id, sin_whatsapp, limit, offset)
    cuentas = trepo.contar_comercios_por_numero(sorted({f["numero"] for f in filas})) if filas else {}
    return {"items": [_item(f, cuentas.get(f["numero"], 1)) for f in filas], "total": total}


@router.get("/admin/telefonos-detectados/resumen")
def resumen(
    ciudad: str | None = Query(default=None, max_length=60),
    claims: dict = Depends(_permiso),
    trepo: TelefonosRepo = Depends(get_telefonos_repo),
    crepo: ContentRepo = Depends(get_content_repo),
) -> dict:
    """`{escaneadas, pendientes_de_escanear, numeros, sin_whatsapp_con_numero, motor_activo, worker,
    tesseract_instalado}`.

    `motor_activo`: `tesseract` (lector gratis) o `gemini` (tiene costo: lo decide el interruptor
    `gemini_phone_scan`). `worker`: true si `TELEFONOS_FOTO_WORKER` está prendido. `tesseract_instalado`: si el
    servidor tiene el lector gratis (sin él y con el motor `tesseract`, el worker no lee nada)."""
    ciudad_id, sin_ciudad = _ciudad_id_del_filtro(trepo, claims, ciudad)
    motor = telefonos_foto.motor_activo(crepo)
    datos = {} if sin_ciudad else (trepo.resumen(motor, ciudad_id) or {})
    return {
        "escaneadas": int(datos.get("escaneadas") or 0),
        "pendientes_de_escanear": int(datos.get("pendientes_de_escanear") or 0),
        "numeros": int(datos.get("numeros") or 0),
        "sin_whatsapp_con_numero": int(datos.get("sin_whatsapp_con_numero") or 0),
        "motor_activo": motor,
        "worker": bool(settings.telefonos_foto_worker),
        "tesseract_instalado": telefonos_foto.tesseract_disponible(),
    }


# ───────────────────────────────────────────────────────────── acciones

def _exigir_edicion(claims: dict) -> None:
    """Aplicar un número escribe en el comercio: hace falta el permiso de «Editar negocio» además de `moderar`."""
    if not tiene_permiso(claims, "comercios.editar"):
        raise HTTPException(status_code=403, detail="Tu cuenta no tiene permiso para editar comercios")


def _cargar(trepo: TelefonosRepo, claims: dict, detectado_id: str) -> tuple[dict | None, dict | None, str | None]:
    """`(propuesta, comercio, motivo)`: el motivo es `no_existe` (no hay propuesta, está dada de baja o el comercio
    ya no está activo) u `otra_ciudad` (es de una ciudad que quien pregunta no puede ver)."""
    d = trepo.get_detectado(detectado_id)
    if not d or d.get("activo") is False:
        return None, None, "no_existe"
    c = trepo.get_comercio_min(d["comercio_id"])
    if not c or c.get("activo") is False:
        return None, None, "no_existe"
    al = _alcance(trepo, claims)
    if al and not al.comercio_ok(c):
        return None, None, "otra_ciudad"
    return d, c, None


def _detectado_y_comercio(trepo: TelefonosRepo, claims: dict, detectado_id: str) -> tuple[dict, dict]:
    """La propuesta y su comercio, o 404 (no existe, está dada de baja o es de otra ciudad)."""
    d, c, motivo = _cargar(trepo, claims, detectado_id)
    if motivo:
        raise HTTPException(status_code=404, detail="Teléfono no encontrado")
    return d, c


def _aplicar(trepo: TelefonosRepo, repo: Repo, claims: dict, d: dict, c: dict, como: str, reemplazar: bool) -> dict:
    """Escribe el número en el comercio por el camino de «Editar negocio» y marca la propuesta."""
    if d["estado"] in _RESUELTOS:
        raise HTTPException(status_code=409, detail="Este número ya estaba resuelto")
    numero = d["numero"]
    campo = "whatsapp" if como == "whatsapp" else "telefono"
    if como == "whatsapp":
        if d["tipo"] != "celular":
            raise HTTPException(status_code=422,
                                detail="Un teléfono fijo no sirve como WhatsApp: usalo como teléfono")
        valor = whatsapp_de(numero)
        error = validar_whatsapp(valor)       # el mismo validador del alta
        if error:
            raise HTTPException(status_code=400, detail=error)
    else:
        valor = numero
    actual = (c.get(campo) or "").strip()
    if actual and mismo_numero(actual, numero):
        # Ya es el dato del comercio: no hay nada que escribir, sólo queda anotado.
        trepo.update_detectado(d["id"], {"estado": "coincide"})
        return {"ok": True, "cambio": False, "estado": "coincide",
                "comercio": {"id": c["id"], "whatsapp": c.get("whatsapp"), "telefono": c.get("telefono")}}
    if actual and not reemplazar:
        raise HTTPException(
            status_code=409,
            detail=f"El comercio ya tiene otro {campo} cargado: {actual}. Para pisarlo mandá reemplazar=true.")
    # Mismo camino que «Editar negocio»: validación, permisos de cuenta, clave anulada y registro.
    editado = editar_comercio(c["id"], EditarComercioBody(**{campo: valor}), claims, repo)
    estado = f"aplicado_{como}"
    trepo.update_detectado(d["id"], {"estado": estado, "revisado_por": _actor(claims), "revisado_at": _ahora()})
    nuevo = editado.get("comercio") or {}
    logger.info("telefonos_foto.aplicado", comercio=c["id"], campo=campo, numero_terminado_en=numero[-4:],
                reemplazo=bool(actual), by=_actor(claims))
    return {"ok": True, "cambio": True, "estado": estado,
            "comercio": {"id": c["id"], "whatsapp": nuevo.get("whatsapp", c.get("whatsapp")),
                         "telefono": nuevo.get("telefono", c.get("telefono"))}}


def _motivo_de_error(exc: HTTPException) -> str:
    """El motivo del lote para un error que salió de `editar_comercio` o de la validación."""
    return {403: "sin_permiso", 409: "numero_en_uso", 400: "whatsapp_invalido", 422: "no_celular"}.get(
        exc.status_code, "error")


@router.post("/admin/telefonos-detectados/aplicar-lote")
def aplicar_lote(
    body: LoteBody,
    claims: dict = Depends(_permiso),
    trepo: TelefonosRepo = Depends(get_telefonos_repo),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Aplica como WhatsApp los números marcados que cumplen la regla del lote: propuesta sin resolver, número
    `celular`, no `compartido` y comercio SIN WhatsApp. Los demás se saltean con su motivo.

    `{aplicados: n, ids_aplicados: [...], saltados: [{id, motivo, detalle?}]}`. `motivo` es una de
    `MOTIVOS_LOTE` (clave corta); `detalle` es el texto en español del error, sólo cuando lo hay."""
    _exigir_edicion(claims)
    aplicados: list[str] = []
    saltados: list[dict] = []
    for did in dict.fromkeys(body.ids):
        d, c, motivo = _cargar(trepo, claims, did)
        detalle = None
        if not motivo:
            if d["estado"] in _RESUELTOS:
                motivo = "no_pendiente"
            elif d["tipo"] != "celular":
                motivo = "no_celular"
            elif d.get("compartido"):
                motivo = "compartido"
            elif (c.get("whatsapp") or "").strip():
                motivo = "tiene_whatsapp"
        if not motivo:
            try:
                _aplicar(trepo, repo, claims, d, c, "whatsapp", False)
                aplicados.append(did)
                continue
            except HTTPException as exc:
                motivo, detalle = _motivo_de_error(exc), str(exc.detail)
        saltados.append({"id": did, "motivo": motivo, **({"detalle": detalle} if detalle else {})})
    logger.info("telefonos_foto.lote", aplicados=len(aplicados), saltados=len(saltados), by=_actor(claims))
    return {"aplicados": len(aplicados), "ids_aplicados": aplicados, "saltados": saltados}


@router.post("/admin/telefonos-detectados/{detectado_id}/aplicar")
def aplicar(
    detectado_id: str,
    body: AplicarBody,
    claims: dict = Depends(_permiso),
    trepo: TelefonosRepo = Depends(get_telefonos_repo),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Usa el número como WhatsApp o como teléfono del comercio. Un `fijo` sólo sirve como teléfono (como
    `whatsapp` es 422). Si el comercio ya tenía otro valor en ese campo contesta 409 —con cuál es en el
    `detail`— salvo `reemplazar: true`. Devuelve `{ok, cambio, estado, comercio: {id, whatsapp, telefono}}`."""
    _exigir_edicion(claims)
    d, c = _detectado_y_comercio(trepo, claims, detectado_id)
    return _aplicar(trepo, repo, claims, d, c, body.como, body.reemplazar)


@router.post("/admin/telefonos-detectados/{detectado_id}/descartar")
def descartar(
    detectado_id: str,
    claims: dict = Depends(_permiso),
    trepo: TelefonosRepo = Depends(get_telefonos_repo),
) -> dict:
    """Descarta la propuesta (queda en la base con estado `descartado`: no vuelve a proponerse). Un número ya
    aplicado no se descarta (409)."""
    d, _c = _detectado_y_comercio(trepo, claims, detectado_id)
    if d["estado"] in ("aplicado_whatsapp", "aplicado_telefono"):
        raise HTTPException(status_code=409, detail="Este número ya se aplicó al comercio")
    if d["estado"] != "descartado":
        trepo.update_detectado(d["id"], {"estado": "descartado", "revisado_por": _actor(claims),
                                         "revisado_at": _ahora()})
        logger.info("telefonos_foto.descartado", comercio=d["comercio_id"], by=_actor(claims))
    return {"ok": True, "estado": "descartado"}
