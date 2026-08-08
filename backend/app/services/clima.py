"""Clima de Bermejo desde open-meteo (gratis, sin API key). El resultado se
guarda en la tabla `clima`; el frontend lo lee de ahí (no pega a open-meteo)."""
import httpx

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
