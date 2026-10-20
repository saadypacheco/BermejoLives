"""Fotos que llegan de quien todavía no sabemos de qué comercio es.

EL PROBLEMA
===========
Una foto de un número desconocido (o de un grupo sin atar) no se copiaba a
ningún lado: WAHA la borra de su volumen y, cuando alguien después decía «ese
número es de la Ferretería Sol», la foto ya no estaba. La oferta se perdía.

LA SOLUCIÓN
===========
Se baja apenas llega, se procesa igual que cualquier foto del sitio y se guarda
en `WA_RECEIVED_DIR`, un disco PRIVADO:

  - NUNCA bajo `FOTOS_DIR` (ése lo sirve /fotos, público y cacheado un año): es
    la foto de un desconocido que nadie moderó.
  - Se mira sólo por el endpoint autenticado del admin (`api/reception.py`).
  - Se borra a los `WA_RECEIVED_RETENTION_DAYS` (30): la fila queda, el archivo no.

`media_path` guarda la ruta RELATIVA (`2026-10/<id>.jpg`): si el directorio se
mueve de volumen, las filas siguen sirviendo.

Nada de acá lanza: una foto que no se pudo guardar no puede tumbar la ingesta
del mensaje (el crudo igual queda en `wa_inbox`).
"""
import hashlib
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import structlog

from app.core.config import settings

logger = structlog.get_logger()

#: Filas por lote de la retención y tope de lotes por corrida (no girar para siempre).
_TAMANO_LOTE = 500
_MAX_LOTES = 200


def _raiz() -> Path:
    return Path(settings.wa_received_dir)


def _nombre_seguro(wa_message_id: str) -> str:
    """El id de WAHA trae `@`, `.` y `_`; se deja un nombre de archivo inofensivo.
    El hash corto evita que dos ids distintos que se limpian igual se pisen."""
    limpio = re.sub(r"[^A-Za-z0-9_-]", "_", wa_message_id)[:100]
    corto = hashlib.sha256(wa_message_id.encode()).hexdigest()[:8]
    return f"{limpio}-{corto}"


def safe_path(media_path: str | None) -> Path | None:
    """La ruta absoluta de un `media_path`, sólo si queda DENTRO de `WA_RECEIVED_DIR`.
    Un valor adulterado en la base (`../../etc/passwd`) devuelve None."""
    if not media_path:
        return None
    try:
        raiz = _raiz().resolve()
        destino = (raiz / media_path).resolve()
        if destino == raiz or raiz not in destino.parents:
            logger.warning("wa_received.ruta_fuera_del_directorio", media_path=media_path)
            return None
        return destino
    except Exception:  # noqa: BLE001
        return None


def read(media_path: str | None) -> bytes | None:
    """Los bytes de la foto guardada, o None si no está."""
    ruta = safe_path(media_path)
    if ruta is None:
        return None
    try:
        return ruta.read_bytes() if ruta.is_file() else None
    except OSError:
        logger.warning("wa_received.lectura_fallo", media_path=media_path, exc_info=True)
        return None


def save(payload) -> str | None:
    """Baja la media del mensaje y la deja en el disco privado.

    Devuelve la ruta relativa, o None si no se pudo (sin media, no es una imagen,
    WAHA ya no la tiene, el disco falló). Nunca lanza."""
    if not payload.id or not (payload.type == "image" or payload.has_media):
        return None
    try:
        from app.services.imagenes import procesar_imagen
        from app.services.wa_media import descargar_media

        data = descargar_media(payload.media_url)
        if not data:
            logger.info("wa_received.sin_media", wa_message_id=payload.id)
            return None
        try:
            procesada = procesar_imagen(data, 1280, 80)
        except Exception as exc:  # noqa: BLE001 — un sticker o un archivo no es una foto
            logger.info("wa_received.no_es_imagen", error=str(exc))
            return None
        relativa = f"{datetime.now(timezone.utc):%Y-%m}/{_nombre_seguro(payload.id)}.jpg"
        destino = safe_path(relativa)
        if destino is None:
            return None
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(procesada)
        logger.info("wa_received.guardada", wa_message_id=payload.id, bytes=len(procesada))
        return relativa
    except Exception:  # noqa: BLE001
        logger.warning("wa_received.save_fallo", wa_message_id=getattr(payload, "id", None), exc_info=True)
        return None


def delete(media_path: str | None) -> bool:
    """Borra el archivo. True si ya no está (existía o no)."""
    ruta = safe_path(media_path)
    if ruta is None:
        return False
    try:
        ruta.unlink(missing_ok=True)
        return True
    except OSError:
        logger.warning("wa_received.borrado_fallo", media_path=media_path, exc_info=True)
        return False


def purge_expired(repo, dias: int | None = None) -> int:
    """Retención: borra el ARCHIVO de las filas más viejas que `dias` y les pone
    `media_purged_at`. La fila queda (es la bitácora). Devuelve cuántas purgó."""
    dias = settings.wa_received_retention_days if dias is None else dias
    corte = (datetime.now(timezone.utc) - timedelta(days=max(0, dias))).isoformat()
    n = 0
    # POR LOTES, HASTA VACIAR lo vencido: con un solo lote de 500 por día, un atraso
    # (o una ráfaga de fotos) tardaba semanas en ponerse al día.
    for _ in range(_MAX_LOTES):
        lote = repo.list_wa_inbox_media_vigente(corte, _TAMANO_LOTE)
        if not lote:
            break
        avance = 0
        for fila in lote:
            ruta = fila.get("media_path")
            if safe_path(ruta) is None:
                # Un `media_path` inválido (vacío, adulterado, fuera del directorio) no
                # tiene archivo que borrar: se marca purgada igual, o la fila volvería
                # en cada lote para siempre.
                logger.warning("wa_received.media_path_invalido_purgado", wa_message_id=fila.get("wa_message_id"))
                repo.marcar_wa_inbox_media_purgada(fila["wa_message_id"])
                avance += 1
            elif delete(ruta):
                repo.marcar_wa_inbox_media_purgada(fila["wa_message_id"])
                n += 1
                avance += 1
        if avance == 0:
            break                     # todo el lote falló al borrar (disco): se reintenta mañana
    if n:
        logger.info("wa_received.purgadas", n=n, dias=dias)
    return n


def purge_events(repo, dias: int | None = None) -> dict:
    """Retención de los datos personales de WAHA que no son fotos: vacía `raw` y
    `participants` de `wa_group_events` y el número de los pares LID dados de baja que
    no se ven hace `WA_EVENTS_RETENTION_DAYS`. Las filas quedan (no hay borrado físico).
    Por lotes, hasta vaciar lo vencido. Devuelve cuántas vació de cada tabla."""
    dias = settings.wa_events_retention_days if dias is None else dias
    corte = (datetime.now(timezone.utc) - timedelta(days=max(0, dias))).isoformat()
    cuenta = {"events": 0, "lids": 0}
    for clave, purgar in (("events", repo.purgar_wa_group_events), ("lids", repo.purgar_wa_lid_inactivos)):
        for _ in range(_MAX_LOTES):
            hechas = purgar(corte, _TAMANO_LOTE)
            cuenta[clave] += hechas
            if hechas < _TAMANO_LOTE:
                break
    if cuenta["events"] or cuenta["lids"]:
        logger.info("wa_received.eventos_purgados", dias=dias, **cuenta)
    return cuenta


def reprocess(repo, filas: list[dict], by: str) -> dict:
    """«Es de…»: vuelve a pasar por la ingesta lo que quedó `sin_comercio`.

    Reconstruye el evento desde `wa_inbox.raw`, pone la fila sin resultado (si no,
    la ingesta la rechaza como duplicada) y le pasa la foto del disco privado: la
    de WAHA ya no existe. Las más viejas primero, para que la foto y el precio que
    llegaron en dos mensajes se vuelvan a juntar (sólo entre ellos: lo que ya estaba
    publicado no se toca nunca).

    IDEMPOTENTE: `liberar_wa_inbox` sólo libera filas que siguen en `sin_comercio` y
    avisa si lo logró. Una fila que otro «Es de…» ya tomó, o que ya se resolvió, se
    saltea: dos pedidos a la vez no duplican ni vuelven a fusionar nada.

    Todo lo reprocesado entra `pendiente`, sin cuota ni cobro (ver
    `ingest.handle_message(reproceso=…)`). Los mensajes del explorador no se
    reprocesan: sus fotos se publican sólo por código.

    Devuelve `{"reprocessed", "published", "ignored"}`: `published` es lo que
    terminó en `publicada`; el resto (charla, ubicación, sin permiso…) es `ignored`.
    """
    from app.core.config import settings
    from app.services import ingest, wa_identity

    cuenta = {"reprocessed": 0, "published": 0, "ignored": 0}
    tanda: dict = {"ultima": {}}           # lo que esta tanda va creando, para juntar foto + texto
    for fila in sorted(filas, key=lambda f: str(f.get("created_at") or "")):
        crudo = fila.get("raw") or {}
        wamid = fila.get("wa_message_id")
        if not crudo or not wamid:
            continue
        numero = wa_identity.number_of_inbox_row(repo, fila)
        if numero and settings.es_numero_explorador(numero):
            continue
        try:
            if not repo.liberar_wa_inbox(wamid, by):
                logger.info("wa_received.reproceso_ya_tomada", wa_message_id=wamid)
                continue
        except Exception:  # noqa: BLE001
            logger.warning("wa_received.liberar_fallo", wa_message_id=wamid, exc_info=True)
            continue
        cuenta["reprocessed"] += 1
        try:
            evento = {"event": "message",
                      "session": "cloud" if fila.get("via") == "cloud" else "default",
                      "payload": crudo}
            vigente = None if fila.get("media_purged_at") else fila.get("media_path")
            ingest.handle_message(evento, repo, media_path=vigente, reproceso=tanda)
            resultado = (repo.get_wa_inbox(wamid) or {}).get("resultado")
        except Exception:  # noqa: BLE001 — una fila rota no corta las demás
            logger.warning("wa_received.reproceso_fallo", wa_message_id=wamid, exc_info=True)
            resultado = None
        if resultado is None:
            # La ingesta se cortó con la fila liberada: se la devuelve a «Sin dueño»
            # para que no quede sin resultado (ni visible ni reprocesable).
            repo.marcar_wa_inbox(wamid, "sin_comercio", "falló el reproceso: probá de nuevo")
        cuenta["published" if resultado == "publicada" else "ignored"] += 1
    return cuenta
