"""Cuántas fotos de galería tiene un comercio, según su plan (docs/fotos-por-plan.md, A).

EL TOPE
=======
    tope = fotos_max del plan  (si está al día o es de cortesía)
           fotos_max del plan gratis  (si no)
         + comercios.fotos_extra  (las que compró a Bs 5)

«Al día» es la misma regla que la estrella (migración 0143):
    plan_cortesia  OR  (paga_hasta >= hoy de Bolivia  AND  NOT suspendido)
y suspendido NUNCA está al día, ni siquiera siendo de cortesía.

LO QUE YA TIENE NO SE BORRA
===========================
Con el pago vencido el tope baja al del plan gratis; las fotos que ya estaban
siguen ahí. Sólo no puede subir más hasta volver a estar al día.

AL LLEGAR AL TOPE
=================
La subida responde 409 con lo que la pantalla necesita para preguntar (ver
`detalle_tope`). Después el comercio elige una de dos salidas, que viajan como
campos del formulario de la misma subida:
  - `extra=pagar`      sólo el comerciante: cargo de Bs 5 + `fotos_extra` + 1.
  - `reemplazar=<id>`  cualquiera: entra la nueva y RECIÉN DESPUÉS se borra la vieja.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import structlog
from fastapi import HTTPException

from app.core.config import settings
from app.services import cargas, planes

logger = structlog.get_logger()

#: Si ni el plan ni el gratis tienen `fotos_max` (base sin migrar, o planes
#: editados a mano): el tope de siempre. Mejor que dejar a todos sin poder subir.
_TOPE_DE_RESPALDO = 10

#: Un uuid que no existe: `imagen_en_uso` pide un id a excluir y acá no hay ninguno.
_NINGUN_ID = "00000000-0000-0000-0000-000000000000"

MSG_SOLO_COMERCIO = "Sólo el comercio puede pagar una foto extra."


# ──────────────────────────────────────────────────────────── el tope

def al_dia(comercio: dict, hoy: date | None = None) -> bool:
    """¿El plan del comercio rige? Cortesía, o pago vigente y no suspendido."""
    if comercio.get("suspendido"):
        return False
    if comercio.get("plan_cortesia"):
        return True
    crudo = comercio.get("paga_hasta")
    if not crudo:
        return False
    try:
        hasta = date.fromisoformat(str(crudo)[:10])
    except ValueError:
        return False
    return hasta >= (hoy or cargas.hoy_bolivia())


def _fotos_max(plan: dict | None) -> int | None:
    v = (plan or {}).get("fotos_max")
    try:
        return None if v is None else max(0, int(v))
    except (TypeError, ValueError):
        return None


def tope_fotos(repo, comercio: dict, hoy: date | None = None) -> int:
    """El máximo de fotos de galería que puede tener ahora este comercio."""
    gratis = _fotos_max(repo.get_plan("gratis"))
    base = None
    if al_dia(comercio, hoy):
        base = _fotos_max(planes.plan_de(repo, comercio))
    if base is None:
        base = gratis
    if base is None:
        base = _TOPE_DE_RESPALDO
    try:
        extra = max(0, int(comercio.get("fotos_extra") or 0))
    except (TypeError, ValueError):
        extra = 0
    return base + extra


def precio_extra(repo, comercio: dict) -> tuple[float | int, str]:
    """Lo que cuesta una foto extra: el mismo extra de las publicaciones.

    Sale del plan del comercio (`precio_publicacion_extra`, el que se edita en
    Admin › Planes); si ese plan no lo tiene, del gratis. Nada escrito acá.
    """
    plan = planes.plan_de(repo, comercio)
    precio = plan.get("precio_publicacion_extra")
    if precio is None:
        precio = (repo.get_plan("gratis") or {}).get("precio_publicacion_extra")
    moneda = plan.get("moneda") or "BOB"
    try:
        f = float(precio or 0)
    except (TypeError, ValueError):
        f = 0.0
    return (int(f) if f == int(f) else f), moneda


def mas_vieja(fotos: list[dict]) -> dict | None:
    """La foto más antigua por fecha de alta (`created_at`); empata el orden en la lista."""
    if not fotos:
        return None
    return min(enumerate(fotos), key=lambda t: (str(t[1].get("created_at") or ""), t[0]))[1]


def detalle_tope(repo, comercio: dict, fotos: list[dict], limite: int) -> dict:
    """El cuerpo del 409 (`detail`). Lo lee la pantalla para preguntar qué hacer."""
    precio, moneda = precio_extra(repo, comercio)
    vieja = mas_vieja(fotos)
    return {
        "mensaje": f"Llegaste al tope de {limite} fotos de tu plan.",
        "codigo": "tope_fotos",
        "limite": limite,
        "precio_extra": precio,
        "moneda": moneda,
        "mas_vieja": {"id": vieja.get("id"), "url": vieja.get("url")} if vieja else None,
    }


def listado(repo, comercio: dict) -> dict:
    """Lo que devuelven los GET de la galería: las fotos y su tope actual."""
    return {"items": repo.list_fotos_comercio(comercio["id"]),
            "limite": tope_fotos(repo, comercio)}


# ──────────────────────────────────────────────── subir con reglas de tope

@dataclass
class Subida:
    """Qué hay que hacer con esta subida, ya validado."""
    fotos: list[dict]            # las que tenía antes de subir
    reemplaza: dict | None = None   # la foto que se borra DESPUÉS de guardar la nueva
    paga: bool = False              # hay que registrar el cargo de foto extra


def preparar(repo, comercio: dict, *, reemplazar: str | None, extra: str | None,
             puede_pagar: bool) -> Subida:
    """Valida los campos de la subida y decide qué corresponde. No escribe nada.

    - `extra` sólo acepta `pagar`; y sólo el comerciante (`puede_pagar`): el
      agente y el admin no pueden comprometer plata del comercio.
    - `reemplazar` tiene que ser una foto de ESTE comercio (404 si no).
    - Si NO está en el tope, `reemplazar` y `extra=pagar` no hacen nada de lo
      suyo: la foto simplemente entra. Ni se borra la vieja ni se cobra: sería
      cobrar (o borrar) algo que no hacía falta, por una pantalla desactualizada.
    - En el tope y sin ninguno de los dos: 409 con `detalle_tope`.
    """
    extra = (extra or "").strip().lower() or None
    reemplazar = (reemplazar or "").strip() or None
    if extra not in (None, "pagar"):
        raise HTTPException(status_code=400, detail="El valor de extra no es válido")
    if extra == "pagar" and not puede_pagar:
        raise HTTPException(status_code=403, detail=MSG_SOLO_COMERCIO)
    if extra and reemplazar:
        raise HTTPException(status_code=400, detail="Elegí una sola opción: pagar o reemplazar")

    fotos = repo.list_fotos_comercio(comercio["id"])
    vieja = None
    if reemplazar:
        vieja = next((f for f in fotos if str(f.get("id")) == reemplazar), None)
        if vieja is None:
            raise HTTPException(status_code=404, detail="Foto no encontrada")

    limite = tope_fotos(repo, comercio)
    if len(fotos) < limite:
        return Subida(fotos=fotos)
    if vieja is not None:
        return Subida(fotos=fotos, reemplaza=vieja)
    if extra == "pagar":
        return Subida(fotos=fotos, paga=True)
    raise HTTPException(status_code=409, detail=detalle_tope(repo, comercio, fotos, limite))


def registrar(repo, comercio: dict, subida: Subida, url: str, thumb: str | None) -> dict:
    """Deja la foto en la base y cierra lo que la subida pedía (cargo / borrado).

    EL ORDEN ES LA REGLA
    ====================
    1. La foto nueva ya está guardada (la guardó el endpoint; si eso falló, no
       se llega acá y la vieja sigue intacta).
    2. Se inserta su fila.
    3. Recién entonces: con `paga`, el cargo y `fotos_extra + 1`; con
       `reemplaza`, se borra la vieja (fila y archivos).
    Si el cargo no se puede registrar, se deshace la foto: no se le da gratis
    ni se le cobra sin foto.
    """
    cid = comercio["id"]
    orden = max((int(f.get("orden") or 0) for f in subida.fotos), default=-1) + 1
    try:
        row = repo.add_foto_comercio({"comercio_id": cid, "url": url, "thumb_url": thumb, "orden": orden})
    except Exception:
        borrar_archivos(comercio, {"url": url, "thumb_url": thumb}, repo)
        raise

    if subida.paga:
        precio, moneda = precio_extra(repo, comercio)
        try:
            repo.registrar_cargo_extra(cid, None, precio, moneda, concepto="foto_extra")
        except Exception as exc:  # noqa: BLE001
            logger.warning("comercio.foto_extra_cargo_fallo", comercio=cid, exc_info=True)
            if row.get("id"):
                repo.delete_foto_comercio(row["id"], cid)
            borrar_archivos(comercio, {"url": url, "thumb_url": thumb}, repo)
            raise HTTPException(status_code=502, detail="No se pudo registrar la foto extra, probá de nuevo") from exc
        actual = (repo.get_comercio(cid) or comercio).get("fotos_extra") or 0
        repo.update_comercio(cid, {"fotos_extra": int(actual) + 1}, None)
        logger.info("comercio.foto_extra_pagada", comercio=cid, monto=precio, moneda=moneda,
                    fotos_extra=int(actual) + 1)

    if subida.reemplaza is not None:
        borrar_foto(repo, comercio, subida.reemplaza)
        logger.info("comercio.foto_reemplazada", comercio=cid, foto_borrada=subida.reemplaza.get("id"))
    return row


# ───────────────────────────────────────────────────── borrar fila y archivos

def _ruta_en_disco(url: str | None) -> Path | None:
    """La ruta de una foto de galería (`<slug>/<archivo>.jpg`) bajo `fotos_dir`,
    o None si no hay que tocarla: URL ajena a nuestra base, no canónica
    (`?`, `#`, `%`, `\\`), con `.`/`..`, de otra forma que dos tramos, o que
    resuelta (siguiendo enlaces) caiga fuera de la carpeta de fotos."""
    if not url:
        return None
    base = settings.fotos_public_base_url.rstrip("/") + "/"
    if not url.startswith(base):
        return None
    relativa = url[len(base):]
    if any(c in relativa for c in "?#%\\\x00"):
        return None
    partes = relativa.split("/")
    if len(partes) != 2 or any(p in ("", ".", "..") for p in partes):
        return None
    if not partes[1].endswith(".jpg"):
        return None
    try:
        raiz = Path(settings.fotos_dir).resolve()
        ruta = (raiz / relativa).resolve()
    except (OSError, ValueError):
        return None
    if not ruta.is_relative_to(raiz) or ruta == raiz:
        return None
    return ruta


def borrar_archivos(comercio: dict, foto: dict, repo=None) -> None:
    """Borra del disco la foto grande y su miniatura. Nunca lanza.

    No toca un archivo que otro lugar siga mostrando: la portada del propio
    comercio o una publicación activa que apunte a la misma URL.
    """
    for campo in ("url", "thumb_url"):
        url = foto.get(campo)
        ruta = _ruta_en_disco(url)
        if ruta is None:
            if url:
                logger.info("comercio.foto_archivo_no_se_borra", url=url,
                            motivo="no es una foto de galería en forma canónica")
            continue
        if url in (comercio.get("portada_url"), comercio.get("portada_thumb_url")):
            logger.info("comercio.foto_archivo_en_uso", url=url, motivo="es la portada")
            continue
        try:
            if repo is not None and repo.imagen_en_uso(url, _NINGUN_ID):
                logger.info("comercio.foto_archivo_en_uso", url=url, motivo="la usa una publicación")
                continue
            ruta.unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            logger.warning("comercio.foto_archivo_borrar_fallo", url=url, exc_info=True)


def borrar_foto(repo, comercio: dict, foto: dict) -> bool:
    """Borra la fila (sólo si es de este comercio) y, si salió, los archivos."""
    if not repo.delete_foto_comercio(foto["id"], comercio["id"]):
        return False
    borrar_archivos(comercio, foto, repo)
    return True


def borrar_foto_por_id(repo, comercio_id: str, foto_id: str) -> bool:
    """Lo que usan los tres «borrar foto» (comerciante, agente, admin): la fila
    Y los archivos. Antes sólo borraban la fila, y el archivo quedaba en el
    disco para siempre; con topes de 50 a 300 fotos por plan, el disco crecía
    con fotos que ya nadie veía. False si la foto no es de ese comercio."""
    comercio = repo.get_comercio(comercio_id)
    if not comercio:
        return False
    foto = next((f for f in repo.list_fotos_comercio(comercio_id) if str(f.get("id")) == str(foto_id)), None)
    if foto is None:
        return False
    return borrar_foto(repo, comercio, foto)
