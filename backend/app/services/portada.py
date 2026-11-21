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
foto anterior no corresponde a la nueva. Lo mismo pasa con la portada de diseño
(`portada_diseno_url` y su propuesta, docs/portada-diseno.md): era de la foto anterior,
así que las dos columnas vuelven a null. Sus archivos (`<slug>/diseno-*.jpg`, nunca una foto) se sueltan del
disco, salvo cuando quien cambia la portada es el AGENTE (que no borra nada): ahí sólo se vacían las columnas.

La TARJETA de la portada (`portada_card_url` y `portada_calidad`, docs/home-ciudades.md §11) también era de la foto
anterior: las dos columnas vuelven a null en el mismo cambio, se suelta del disco el archivo `card-*.jpg` viejo (es un
derivado que se regenera: lo suelta también el agente) y se arma la tarjeta de la portada nueva. Si armarla falla, se
registra y el cambio de portada sigue: la tarjeta nunca lo rompe (`fotos_tarjeta.armar_seguro`).
"""
from __future__ import annotations

import structlog
from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.services import fotos_galeria, fotos_tarjeta, portada_diseno

logger = structlog.get_logger()


class UsarPortadaBody(BaseModel):
    """Cuerpo de `PUT <base>/portada`: qué foto de la galería pasa a ser la portada."""
    foto_id: str = Field(min_length=1, max_length=64)


def _url(valor) -> str | None:
    return str(valor).strip() or None if valor else None


def usar_de_galeria(repo, comercio: dict, foto_id: str, *, conservar_archivos: bool = False) -> dict:
    """Intercambia la portada con una foto de la galería. Devuelve el comercio actualizado.

    - 404 si la foto no es de ESTE comercio.
    - Si la foto elegida ya es la portada, no hay nada que mover.
    - Sin portada anterior, la foto elegida sale de la galería (queda una menos).
    - Si la portada anterior ya figura en otra fila de la galería, no se la
      vuelve a meter (quedaría repetida): sólo sale la elegida.
    - Nunca borra FOTOS: todo lo que se veía antes se sigue viendo. Lo único que se suelta del disco es el
      archivo de la portada de diseño que quedó vencida (el diseño era de la portada anterior) y los de diseño
      de la fila de galería intercambiada (0203: la foto de esa fila cambió), y no con
      `conservar_archivos=True` (el agente no borra nada: sólo se vacían las columnas).
    """
    cid = comercio["id"]
    diseno_viejo = portada_diseno.urls_de(comercio)
    tarjeta_vieja = comercio.get("portada_card_url")
    fotos = repo.list_fotos_comercio(cid)
    foto = next((f for f in fotos if str(f.get("id")) == str(foto_id)), None)
    if foto is None:
        raise HTTPException(status_code=404, detail="Foto no encontrada")

    original = {"url": foto.get("url"), "thumb_url": foto.get("thumb_url")}   # por si hay que deshacer
    diseno_de_la_foto = fotos_galeria.urls_de_diseno(foto)      # el diseño de la fila que sale de la galería (0203)
    nueva_url = _url(foto.get("url"))
    if not nueva_url:
        raise HTTPException(status_code=404, detail="Foto no encontrada")
    nueva_thumb = _url(foto.get("thumb_url")) or nueva_url
    vieja_url = _url(comercio.get("portada_url"))
    vieja_thumb = _url(comercio.get("portada_thumb_url"))

    if vieja_url == nueva_url:
        return comercio     # ya es la portada

    patch = {"portada_url": nueva_url, "portada_thumb_url": nueva_thumb, "portada_pos": None,
             **portada_diseno.COLUMNAS_VACIAS, **fotos_tarjeta.COLUMNAS_VACIAS}

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
            # Al deshacer también vuelve su diseño (cambiar el `url` lo había vaciado): no queda ningún archivo huérfano.
            repo.update_foto_comercio(foto["id"], cid, {**original, **dict(zip(fotos_galeria.COLUMNAS_DISENO, diseno_de_la_foto))})
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

    if not conservar_archivos:
        portada_diseno.soltar_huerfanos(repo, comercio, diseno_viejo)    # el diseño era de la portada anterior
        # La foto elegida ya no es la de esa fila (o la fila ya no existe): su diseño quedó vencido. La foto original
        # nunca se borra por un diseño. El agente (`conservar_archivos`) sólo vacía las columnas.
        fotos_galeria.soltar_disenos(comercio, diseno_de_la_foto)
    logger.info("comercio.portada_de_galeria", comercio=cid, foto=foto["id"],
                intercambio=bool(vieja_url and not vieja_ya_esta))
    return _rehacer_tarjeta(repo, actualizado or {**comercio, **patch}, tarjeta_vieja)


def poner_nueva(repo, comercio: dict, portada_url: str, portada_thumb: str | None,
                *, conservar_anterior: bool = False) -> dict:
    """Pisa la portada con una foto recién subida. Devuelve el comercio actualizado.

    El recorte vuelve a null. Qué pasa con la portada anterior:

    - Por defecto (admin, publicador, comerciante) sus archivos se borran del
      disco, salvo que la galería, otro comercio o una publicación activa los usen.
    - `conservar_anterior=True` (el AGENTE, que sólo sube y no borra): la portada
      anterior pasa a la galería —aunque eso supere el tope del plan: ya existía—
      y no se borra ningún archivo (tampoco los de la portada de diseño: sólo se vacían sus columnas).

    Si no se puede guardar la portada nueva, los archivos recién subidos se borran
    (no quedan huérfanos en el disco) y el error sigue su camino.
    """
    cid = comercio["id"]
    diseno_viejo = portada_diseno.urls_de(comercio)
    tarjeta_vieja = comercio.get("portada_card_url")
    vieja_url = _url(comercio.get("portada_url"))
    vieja_thumb = _url(comercio.get("portada_thumb_url"))

    patch = {"portada_url": portada_url, "portada_thumb_url": portada_thumb, "portada_pos": None,
             **portada_diseno.COLUMNAS_VACIAS, **fotos_tarjeta.COLUMNAS_VACIAS}

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
        portada_diseno.soltar_huerfanos(repo, comercio, diseno_viejo)    # el diseño era de la portada anterior
        try:
            _soltar_archivos_viejos(repo, actualizado, vieja_url, vieja_thumb)
        except Exception:  # noqa: BLE001 — limpiar el disco no puede romper el cambio de portada
            logger.warning("comercio.portada_limpieza_fallo", comercio=cid, exc_info=True)
    logger.info("comercio.portada_nueva", comercio=cid, anterior_a_galeria=bool(fila_nueva))
    return _rehacer_tarjeta(repo, actualizado, tarjeta_vieja)


def _rehacer_tarjeta(repo, comercio: dict, tarjeta_vieja: str | None) -> dict:
    """Después de cambiar la portada: suelta la tarjeta vieja (si nada más la apunta) y arma la de la portada nueva.
    Nunca lanza. Devuelve el comercio con `portada_card_url` y `portada_calidad` al día (o como quedó, si falló)."""
    try:
        fotos_tarjeta.soltar_huerfano(repo, comercio, tarjeta_vieja)
    except Exception:  # noqa: BLE001
        logger.warning("comercio.portada_tarjeta_soltar_fallo", comercio=comercio.get("id"), exc_info=True)
    nueva = fotos_tarjeta.armar_seguro(repo, comercio)
    return {**comercio, **nueva} if nueva else comercio


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


def respuesta(repo, comercio: dict, admin: bool = False) -> dict:
    """Lo que devuelve `PUT <base>/portada`: la portada nueva y la galería al día. Sin `admin`, sin las columnas
    privadas de la galería (la propuesta de diseño sin aprobar)."""
    galeria = fotos_galeria.listado(repo, comercio, admin=admin)
    return {
        "ok": True,
        "portada_url": comercio.get("portada_url"),
        "portada_thumb_url": comercio.get("portada_thumb_url"),
        "fotos": galeria["items"],
        "limite": galeria["limite"],
    }
