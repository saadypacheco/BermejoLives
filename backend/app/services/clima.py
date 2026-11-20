"""Clima desde open-meteo (gratis, sin API key). El de Bermejo se guarda en la tabla `clima` y el de las demás
ciudades en `clima_ciudades`; el frontend lee de ahí (no pega a open-meteo)."""
import httpx
import structlog
from starlette.concurrency import run_in_threadpool

logger = structlog.get_logger()

_LAT, _LON = -22.7361, -64.3433  # Bermejo


def _desc(code: int) -> tuple[str, str]:
    """Código WMO → (descripción, emoji)."""
    if code == 0:
        return "Despejado", "☀️"
    if code in (1, 2):
        return "Parcialmente nublado", "⛅"
    if code == 3:
        return "Nublado", "☁️"
    if code in (45, 48):
        return "Niebla", "🌫️"
    if 51 <= code <= 67 or 80 <= code <= 82:
        return "Lluvia", "🌧️"
    if 71 <= code <= 77 or 85 <= code <= 86:
        return "Nieve", "❄️"
    if 95 <= code <= 99:
        return "Tormenta", "⛈️"
    return "—", "🌡️"


async def fetch_clima_bermejo() -> dict | None:
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={_LAT}&longitude={_LON}"
        "&current=temperature_2m,weather_code&timezone=auto"
    )
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
        if r.status_code != 200:
            return None
        cur = r.json().get("current", {})
        desc, icono = _desc(int(cur.get("weather_code", -1)))
        return {"temp_c": cur.get("temperature_2m"), "descripcion": desc, "icono": icono, "fuente": "open-meteo"}
    except Exception:  # noqa: BLE001
        return None


def _numero(v) -> float | None:
    """Un valor de open-meteo como número, o None si falta o no es número (un bool no cuenta)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v)


def parsear_clima_ciudades(ciudades: list[dict], payload) -> dict[str, dict]:
    """Arma `{ciudad_id: {"temp_c", "descripcion"}}` con la respuesta de open-meteo para varias coordenadas.

    Con una sola coordenada open-meteo contesta un objeto; con varias, una lista en el MISMO orden que las
    coordenadas pedidas: se aceptan las dos formas. Una ciudad sin temperatura (o una respuesta rara) se saltea:
    queda sin entrada y el que llama conserva el dato anterior. La descripción es la misma de Bermejo, sin emoji."""
    if isinstance(payload, dict):
        # Un error de open-meteo viene como {"error": true, "reason": ...}: sin "current" no hay nada que tomar.
        items = [payload]
    elif isinstance(payload, list):
        items = payload
    else:
        return {}
    if len(items) != len(ciudades):
        # Si no coincide la cantidad no se puede saber cuál es de quién: mejor nada que el clima de otra ciudad.
        logger.warning("clima_ciudades.respuesta_desalineada", pedidas=len(ciudades), recibidas=len(items))
        return {}
    out: dict[str, dict] = {}
    for ciudad, item in zip(ciudades, items):
        cur = item.get("current") if isinstance(item, dict) else None
        if not isinstance(cur, dict):
            continue
        temp = _numero(cur.get("temperature_2m"))
        if temp is None:
            continue
        code = cur.get("weather_code")
        desc, _icono = _desc(int(code) if _numero(code) is not None else -1)
        out[str(ciudad["id"])] = {"temp_c": temp, "descripcion": desc}
    return out


async def fetch_clima_ciudades(ciudades: list[dict]) -> dict[str, dict]:
    """El clima actual de varias ciudades en UNA sola llamada a open-meteo (`latitude=a,b,…&longitude=…`).
    `ciudades`: filas con `id`, `lat` y `lng`. Nunca levanta: ante un error o un timeout devuelve `{}`."""
    validas = [c for c in ciudades if _numero(c.get("lat")) is not None and _numero(c.get("lng")) is not None]
    if not validas:
        return {}
    lats = ",".join(f"{float(c['lat']):.4f}" for c in validas)
    lons = ",".join(f"{float(c['lng']):.4f}" for c in validas)
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lats}&longitude={lons}"
        "&current=temperature_2m,weather_code&timezone=auto"
    )
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url)
        if r.status_code != 200:
            logger.warning("clima_ciudades.http_error", status=r.status_code)
            return {}
        return parsear_clima_ciudades(validas, r.json())
    except Exception as exc:  # noqa: BLE001
        logger.warning("clima_ciudades.fetch_error", error=str(exc))
        return {}


async def actualizar_clima_ciudades(repo) -> int:
    """Una vuelta del clima por ciudad: lee las ciudades activas con coordenadas, pide el clima de todas juntas y
    guarda cada una en `clima_ciudades`. Una ciudad que falló (sin dato, o que no se pudo guardar) se saltea y
    conserva su fila anterior. Devuelve cuántas guardó. Nunca levanta: el loop no se puede caer por esto."""
    try:
        ciudades = await run_in_threadpool(repo.list_ciudades_con_coordenadas) or []
        if not ciudades:
            return 0
        datos = await fetch_clima_ciudades(ciudades)
    except Exception as exc:  # noqa: BLE001
        logger.warning("clima_ciudades.error", error=str(exc))
        return 0
    guardadas = 0
    for c in ciudades:
        d = datos.get(str(c["id"]))
        if not d:
            logger.info("clima_ciudades.sin_dato", ciudad=c.get("slug"))
            continue
        try:
            await run_in_threadpool(repo.upsert_clima_ciudad, str(c["id"]), d["temp_c"], d["descripcion"])
            guardadas += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("clima_ciudades.guardar_error", ciudad=c.get("slug"), error=str(exc))
    logger.info("clima_ciudades.actualizado", guardadas=guardadas, pedidas=len(ciudades))
    return guardadas
