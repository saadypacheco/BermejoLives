"""La portada de un comercio: cambiarla sin perder fotos ni dejar archivos huérfanos.

(docs/portada-y-permisos.md)

La portada es una columna aparte (`comercios.portada_url` / `portada_thumb_url`),
no una fila de `comercio_fotos`. Hay dos formas de cambiarla y las usan los
tres perfiles (admin, agente, comerciante) igual:

    usar_de_galeria   elegir una foto que ya está en la galería. Es un
                      INTERCAMBIO: la elegida pasa a ser la portada y la
                      portada anterior ocupa su lugar en la galería. La
                      cantidad de fotos no cambia, así que no choca con el
                      tope del plan, y no se borra ningún archivo.

    poner_nueva       subir una foto nueva como portada. Pisa la anterior y
                      borra del disco sus archivos, salvo que la galería (o
                      una publicación) los siga usando. El AGENTE no borra
                      archivos (docs/portada-y-permisos.md, ronda 2): para él la
                      portada anterior pasa a la galería, aunque eso supere el tope.

En las dos, `portada_pos` vuelve a null: el recorte que alguien eligió para la
foto anterior no corresponde a la nueva.
"""
from __future__ import annotations

import structlog
from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.services import fotos_galeria

logger = structlog.get_logger()


class UsarPortadaBody(BaseModel):
    """Cuerpo de `PUT <base>/portada`: qué foto de la galería pasa a ser la portada."""
    foto_id: str = Field(min_length=1, max_length=64)


def _url(valor) -> str | None:
    return str(valor).strip() or None if valor else None


def usar_de_galeria(repo, comercio: dict, foto_id: str) -> dict:
    """Intercambia la portada con una foto de la galería. Devuelve el comercio actualizado.

    - 404 si la foto no es de ESTE comercio.
    - Si la foto elegida ya es la portada, no hay nada que mover.
    - Sin portada anterior, la foto elegida sale de la galería (queda una menos).
    - Si la portada anterior ya figura en otra fila de la galería, no se la
      vuelve a meter (quedaría repetida): sólo sale la elegida.
    - Nunca borra archivos: todo lo que se veía antes se sigue viendo.
    """
    cid = comercio["id"]
    fotos = repo.list_fotos_comercio(cid)
    foto = next((f for f in fotos if str(f.get("id")) == str(foto_id)), None)
    if foto is None:
        raise HTTPException(status_code=404, detail="Foto no encontrada")

    original = {"url": foto.get("url"), "thumb_url": foto.get("thumb_url")}   # por si hay que deshacer
    nueva_url = _url(foto.get("url"))
    if not nueva_url:
        raise HTTPException(status_code=404, detail="Foto no encontrada")
    nueva_thumb = _url(foto.get("thumb_url")) or nueva_url
    vieja_url = _url(comercio.get("portada_url"))
    vieja_thumb = _url(comercio.get("portada_thumb_url"))

    if vieja_url == nueva_url:
        return comercio     # ya es la portada

    patch = {"portada_url": nueva_url, "portada_thumb_url": nueva_thumb, "portada_pos": None}

    # ¿La portada anterior ya está en la galería, en otra fila? Entonces no se repite.
    otras = [f for f in fotos if str(f.get("id")) != str(foto_id)]
    vieja_ya_esta = bool(vieja_url) and any(
        vieja_url in (_url(f.get("url")), _url(f.get("thumb_url"))) for f in otras)

    if vieja_url and not vieja_ya_esta:
        # Intercambio. Primero la fila de la galería (la portada anterior queda
        # a salvo en las dos partes), después la portada; si ésta falla se
        # deshace la fila y no se pierde nada.
        repo.update_foto_comercio(
            foto["id"], cid, {"url": vieja_url, "thumb_url": vieja_thumb})
        try:
            actualizado = repo.update_comercio(cid, patch, None)
        except Exception:
            repo.update_foto_comercio(foto["id"], cid, original)
            raise
    else:
        # Sin portada anterior (o ya repetida en la galería): la elegida sale de
        # la galería. Primero la portada, después la fila: si falla la baja de
        # la fila, la foto queda repetida un rato, nunca perdida.
        actualizado = repo.update_comercio(cid, patch, None)
        # DELETE físico a propósito, y seguro: `comercio_fotos` no es un registro
        # sino un PUNTERO a una URL (no tiene `activo` ni historia propia). La foto
        # no se pierde: acaba de pasar a `portada_url`/`portada_thumb_url` en la
        # línea de arriba, con la misma URL, y ningún archivo se toca. Si el
        # puntero se dejara "inactivo" la foto saldría repetida (portada + galería).
        repo.delete_foto_comercio(foto["id"], cid)

    logger.info("comercio.portada_de_galeria", comercio=cid, foto=foto["id"],
                intercambio=bool(vieja_url and not vieja_ya_esta))
    return actualizado or {**comercio, **patch}


def poner_nueva(repo, comercio: dict, portada_url: str, portada_thumb: str | None,
                *, conservar_anterior: bool = False) -> dict:
    """Pisa la portada con una foto recién subida. Devuelve el comercio actualizado.

    El recorte vuelve a null. Qué pasa con la portada anterior:

    - Por defecto (admin, publicador, comerciante) sus archivos se borran del
      disco, salvo que la galería, otro comercio o una publicación activa los usen.
    - `conservar_anterior=True` (el AGENTE, que sólo sube y no borra): la portada
      anterior pasa a la galería —aunque eso supere el tope del plan: ya existía—
      y no se borra ningún archivo.

    Si no se puede guardar la portada nueva, los archivos recién subidos se borran
    (no quedan huérfanos en el disco) y el error sigue su camino.
    """
    cid = comercio["id"]
    vieja_url = _url(comercio.get("portada_url"))
    vieja_thumb = _url(comercio.get("portada_thumb_url"))

    patch = {"portada_url": portada_url, "portada_thumb_url": portada_thumb, "portada_pos": None}

    fila_nueva = None
    if conservar_anterior and vieja_url:
        fila_nueva = _guardar_en_galeria(repo, cid, vieja_url, vieja_thumb)
    try:
        actualizado = repo.update_comercio(cid, patch, None) or {**comercio, **patch}
    except Exception:
        # Ya se subieron los archivos de la portada nueva y la base no la aceptó:
        # sin esto quedan en el disco para siempre, sin que nada los apunte.
        if fila_nueva and fila_nueva.get("id"):
            try:
                repo.delete_foto_comercio(fila_nueva["id"], cid)   # puntero propio, recién creado
            except Exception:  # noqa: BLE001
                logger.warning("comercio.portada_deshacer_galeria_fallo", comercio=cid, exc_info=True)
        fotos_galeria.borrar_archivos(comercio, {"url": portada_url, "thumb_url": portada_thumb}, repo)
        logger.warning("comercio.portada_nueva_fallo", comercio=cid, exc_info=True)
        raise

    if not conservar_anterior:
        try:
            _soltar_archivos_viejos(repo, actualizado, vieja_url, vieja_thumb)
        except Exception:  # noqa: BLE001 — limpiar el disco no puede romper el cambio de portada
            logger.warning("comercio.portada_limpieza_fallo", comercio=cid, exc_info=True)
    logger.info("comercio.portada_nueva", comercio=cid, anterior_a_galeria=bool(fila_nueva))
    return actualizado


def _guardar_en_galeria(repo, cid: str, url: str, thumb: str | None) -> dict | None:
    """Agrega la portada anterior a la galería, sin tope. None si ya estaba en ella."""
    fotos = repo.list_fotos_comercio(cid)
    for f in fotos:
        if url in (_url(f.get("url")), _url(f.get("thumb_url"))):
            return None
    orden = max((int(f.get("orden") or 0) for f in fotos), default=-1) + 1
    return repo.add_foto_comercio({"comercio_id": cid, "url": url, "thumb_url": thumb, "orden": orden})


def _soltar_archivos_viejos(repo, comercio: dict, vieja_url: str | None,
                            vieja_thumb: str | None) -> None:
    """Borra los archivos de la portada anterior que nadie más usa."""
    en_galeria: set[str] = set()
    for f in repo.list_fotos_comercio(comercio["id"]):
        en_galeria.update(u for u in (_url(f.get("url")), _url(f.get("thumb_url"))) if u)
    vigentes = {_url(comercio.get("portada_url")), _url(comercio.get("portada_thumb_url"))}

    def sobra(u: str | None) -> str | None:
        return u if u and u not in en_galeria and u not in vigentes else None

    foto = {"url": sobra(vieja_url), "thumb_url": sobra(vieja_thumb)}
    if foto["url"] or foto["thumb_url"]:
        # `borrar_archivos` además respeta lo que una publicación activa siga mostrando.
        fotos_galeria.borrar_archivos(comercio, foto, repo)


def respuesta(repo, comercio: dict) -> dict:
    """Lo que devuelve `PUT <base>/portada`: la portada nueva y la galería al día."""
    galeria = fotos_galeria.listado(repo, comercio)
    return {
        "ok": True,
        "portada_url": comercio.get("portada_url"),
        "portada_thumb_url": comercio.get("portada_thumb_url"),
        "fotos": galeria["items"],
        "limite": galeria["limite"],
    }
