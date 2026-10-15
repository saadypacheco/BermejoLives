"""Mapa de calles recorridas (docs/mapa-calles.md).

Tres cosas, todas en el servidor:

  1. IMPORTAR las calles de una ciudad desde OpenStreetMap (Overpass) y guardarlas como tramos.
  2. CALCULAR qué tan cubierto está cada tramo por los comercios cargados (`cobertura`) y en qué
     estado queda (`estado_de`), con la marca manual por encima.
  3. Guardar el resultado en una CACHÉ por ciudad, que una marca, un alta o una importación invalidan.

La regla de estado, en una sola función (`estado_de`), para que el frontend no la reescriba:

    · Se muestrea la línea cada 15 m (`PASO_M`).
    · Un punto está CUBIERTO si hay un comercio activo de la ciudad, con lat/lng, a 35 m o menos
      (`RADIO_M`). `cobertura` = % de puntos cubiertos (0 a 100).
    · Automático:  cobertura >= 60  -> recorrida
                   15 <= cobertura < 60 -> parcial
                   cobertura < 15   -> pendiente
    · La ÚLTIMA marca manual gana sobre el automático: recorrida, sin_comercios (calle de casas o
      baldío) o pendiente (volver a abrirla).

Para no comparar cada punto contra cada comercio (miles × miles) los comercios se meten en una
grilla de celdas de `RADIO_M`: un punto sólo mira su celda y las 8 vecinas.
"""
from __future__ import annotations

import math
import re
import threading
import time
from datetime import datetime, timezone
from typing import Callable, Iterable

import httpx
import structlog
from fastapi import HTTPException

logger = structlog.get_logger()

# ── la regla ─────────────────────────────────────────────────────────────────
PASO_M = 15.0              # cada cuántos metros se muestrea la línea
RADIO_M = 35.0             # un comercio a esta distancia o menos cubre el punto
UMBRAL_RECORRIDA = 60.0    # % de cobertura desde el que un tramo cuenta como recorrido
UMBRAL_PARCIAL = 15.0      # % de cobertura desde el que es parcial (debajo, pendiente)
ESTADOS_MARCA = ("recorrida", "sin_comercios", "pendiente")

# ── la caché ─────────────────────────────────────────────────────────────────
TTL_S = 300                # unos minutos: el borde de lo que tarda en notarse un cambio de GPS

# ── Overpass ─────────────────────────────────────────────────────────────────
OVERPASS_URLS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",   # el reintento prueba el espejo
)
UA = "URUKU/1.0 (directorio de comercios; https://uruku.bo)"
#: Las vías que entran al mapa: las que una persona camina a ofrecer algo. Con sus `_link`.
RE_TIPOS = r"^(primary|secondary|tertiary|residential|unclassified|living_street|pedestrian)(_link)?$"
_TIPOS = re.compile(RE_TIPOS)
MARGEN_M = 400             # la caja es la extensión de los comercios + este margen
CAJA_MAX_GRADOS = 0.3      # una caja más grande es un GPS roto, no una ciudad (~33 km)
TIMEOUT_QUERY_S = 40       # el timeout que se le pide al servidor de Overpass
TIMEOUT_HTTP_S = 50        # el del cliente: un poco más, para recibir el error en vez de cortar
PAUSA_REINTENTO_S = 1.5


class OverpassError(Exception):
    """Overpass no contestó o contestó mal."""


# ══════════════════════════════════════════════ geometría

def proyector(lat_ref: float) -> Callable[[float, float], tuple[float, float]]:
    """(lat, lng) -> (x, y) en metros planos. A escala de ciudad la curvatura no cambia nada."""
    kx = 111_320 * math.cos(math.radians(lat_ref))
    return lambda lat, lng: (lng * kx, lat * 110_540)


def largo_m(geom: list[list[float]]) -> float:
    """Largo de una línea [[lat,lng],...] en metros."""
    if len(geom) < 2:
        return 0.0
    xy = proyector(sum(p[0] for p in geom) / len(geom))
    pts = [xy(p[0], p[1]) for p in geom]
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))


def muestrear(puntos: list[tuple[float, float]], paso: float = PASO_M) -> list[tuple[float, float]]:
    """Puntos sobre la línea (en metros planos) separados por `paso` o menos.

    La línea se parte en `n = ceil(largo / paso)` partes iguales y se toma el medio de cada una:
    nunca hay más de `paso` entre dos muestras, y los extremos (las esquinas, donde el comercio de
    la calle de al lado también cae) no pesan de más. Una línea sin largo da un solo punto."""
    if not puntos:
        return []
    acumulado = [0.0]
    for a, b in zip(puntos, puntos[1:]):
        acumulado.append(acumulado[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    total = acumulado[-1]
    if total <= 0:
        return [puntos[0]]
    n = max(1, math.ceil(total / paso))
    salida = []
    seg = 0
    for i in range(n):
        d = (i + 0.5) * total / n
        while seg < len(puntos) - 2 and acumulado[seg + 1] < d:
            seg += 1
        a, b = puntos[seg], puntos[seg + 1]
        largo = acumulado[seg + 1] - acumulado[seg]
        t = 0.0 if largo <= 0 else (d - acumulado[seg]) / largo
        salida.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return salida


# ══════════════════════════════════════════════ cobertura y estado

def estado_de(cobertura: float, marca: dict | None) -> str:
    """El estado de un tramo: recorrida · parcial · pendiente · sin_comercios.

    La última marca manual gana. Sin marca, manda el % de puntos cubiertos (ver el docstring del
    módulo para los umbrales)."""
    if marca and marca.get("estado") in ESTADOS_MARCA:
        return marca["estado"]
    if cobertura >= UMBRAL_RECORRIDA:
        return "recorrida"
    if cobertura >= UMBRAL_PARCIAL:
        return "parcial"
    return "pendiente"


def _fecha(valor) -> datetime | None:
    """Un ISO de PostgREST ('2026-10-14T10:00:00+00:00', con 'Z' o sin zona) -> datetime con zona."""
    if not valor:
        return None
    try:
        dt = datetime.fromisoformat(str(valor).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _num(valor) -> float | None:
    try:
        n = float(valor)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


class _Grilla:
    """Los comercios en celdas de `RADIO_M`: preguntar «¿quién está a 35 m?» mira 9 celdas."""

    def __init__(self, comercios: Iterable[dict], xy: Callable[[float, float], tuple[float, float]]):
        self.celdas: dict[tuple[int, int], list[tuple[float, float, dict]]] = {}
        for c in comercios:
            lat, lng = _num(c.get("lat")), _num(c.get("lng"))
            if lat is None or lng is None:
                continue
            x, y = xy(lat, lng)
            self.celdas.setdefault((int(x // RADIO_M), int(y // RADIO_M)), []).append((x, y, c))

    def cerca(self, x: float, y: float) -> list[dict]:
        """Los comercios a `RADIO_M` o menos del punto (x, y)."""
        cx, cy = int(x // RADIO_M), int(y // RADIO_M)
        r2 = RADIO_M * RADIO_M
        out = []
        for i in (cx - 1, cx, cx + 1):
            for j in (cy - 1, cy, cy + 1):
                for px, py, c in self.celdas.get((i, j), ()):
                    if (px - x) ** 2 + (py - y) ** 2 <= r2:
                        out.append(c)
        return out


def cobertura_de_tramos(tramos: list[dict], comercios: list[dict]) -> list[dict]:
    """Por cada tramo: `cobertura` (% de puntos cubiertos), `comercios` (cuántos hay a lo largo) y
    `ultimo` ({fecha, quien} de la carga más reciente sobre el tramo, o None). Sin marcas."""
    puntos_geom = [p for t in tramos for p in (t.get("geom") or [])]
    if not puntos_geom:
        return [{"cobertura": 0.0, "comercios": 0, "ultimo": None} for _ in tramos]
    xy = proyector(sum(p[0] for p in puntos_geom) / len(puntos_geom))
    grilla = _Grilla(comercios, xy)

    salida = []
    for t in tramos:
        geom = t.get("geom") or []
        muestras = muestrear([xy(p[0], p[1]) for p in geom])
        cubiertos = 0
        vistos: dict[int, dict] = {}
        for x, y in muestras:
            cerca = grilla.cerca(x, y)
            if cerca:
                cubiertos += 1
                for c in cerca:
                    vistos[id(c)] = c
        cobertura = round(100.0 * cubiertos / len(muestras), 1) if muestras else 0.0
        salida.append({"cobertura": cobertura, "comercios": len(vistos), "ultimo": _ultimo(vistos.values()),
                       "_exacta": (100.0 * cubiertos / len(muestras)) if muestras else 0.0})
    return salida


def _ultimo(comercios: Iterable[dict]) -> dict | None:
    """La carga más reciente: `capturado_en` (la hora del celular) o, si no hay, `created_at`."""
    mejor, mejor_dt = None, None
    for c in comercios:
        crudo = c.get("capturado_en") or c.get("created_at")
        dt = _fecha(crudo)
        if dt is None:
            continue
        if mejor_dt is None or dt > mejor_dt:
            mejor, mejor_dt = {"fecha": crudo, "quien": c.get("cargado_por") or None}, dt
    return mejor


def armar_mapa(tramos: list[dict], comercios: list[dict], marcas: dict[str, dict]) -> dict:
    """`{tramos: [...], resumen: {...}}` con la forma exacta de la spec.

    `marcas`: tramo_id -> su última marca ({estado, nota, actor, created_at})."""
    calculo = cobertura_de_tramos(tramos, comercios)
    salida = []
    km = {"recorrida": 0.0, "sin_comercios": 0.0}
    total = 0.0
    for t, c in zip(tramos, calculo):
        geom = t.get("geom") or []
        metros = t.get("longitud_m")
        metros = float(metros) if metros is not None else largo_m(geom)
        marca = marcas.get(t["id"])
        # El estado se decide con el % sin redondear: 59,96 % no es «recorrida» aunque se vea 60,0.
        estado = estado_de(c["_exacta"], marca)
        total += metros
        if estado in km:
            km[estado] += metros
        salida.append({
            "id": t["id"], "nombre": t.get("nombre"), "tipo": t.get("tipo"), "geom": geom,
            "longitud_m": int(round(metros)),
            "cobertura": c["cobertura"], "estado": estado,
            "marca": ({"estado": marca["estado"], "nota": marca.get("nota"), "actor": marca.get("actor"),
                       "created_at": marca.get("created_at")} if marca else None),
            "comercios": c["comercios"], "ultimo": c["ultimo"],
        })
    # El % se mide sobre lo que HAY que recorrer: las calles «sin comercios» no cuentan en contra.
    a_recorrer = total - km["sin_comercios"]
    resumen = {
        "km_total": round(total / 1000, 2),
        "km_recorridos": round(km["recorrida"] / 1000, 2),
        "km_sin_comercios": round(km["sin_comercios"] / 1000, 2),
        "km_a_recorrer": round(a_recorrer / 1000, 2),
        "pct": round(100.0 * km["recorrida"] / a_recorrer, 1) if a_recorrer > 0 else 0.0,
    }
    return {"tramos": salida, "resumen": resumen}


def antes_de_arroba(valor: str | None) -> str | None:
    """'ana@uruku.bo' -> 'ana'. Lo que ve el agente de quien cargó o marcó."""
    return valor.split("@", 1)[0] if valor else valor


def vista_agente(mapa: dict) -> dict:
    """El mismo mapa para el agente: de `quien` y de `marca.actor` sólo la parte antes de la @."""
    tramos = []
    for t in mapa["tramos"]:
        t2 = dict(t)
        if t["ultimo"]:
            t2["ultimo"] = {**t["ultimo"], "quien": antes_de_arroba(t["ultimo"].get("quien"))}
        if t["marca"]:
            t2["marca"] = {**t["marca"], "actor": antes_de_arroba(t["marca"].get("actor"))}
        tramos.append(t2)
    return {"tramos": tramos, "resumen": mapa["resumen"]}


# ══════════════════════════════════════════════ caché por ciudad

_lock = threading.Lock()
_cache: dict[str, tuple[float, dict]] = {}
_version: dict[str, int] = {}


def _ahora() -> float:
    return time.monotonic()


def invalidar(ciudad_id: str | None) -> None:
    """Una marca, un alta o una importación en esa ciudad: lo guardado deja de valer."""
    if not ciudad_id:
        return
    with _lock:
        _cache.pop(ciudad_id, None)
        _version[ciudad_id] = _version.get(ciudad_id, 0) + 1


def limpiar_cache() -> None:
    with _lock:
        _cache.clear()
        _version.clear()


def mapa_de_ciudad(repo, ciudad_id: str) -> dict:
    """El mapa calculado de la ciudad, de la caché si está fresco (`TTL_S`).

    Si una invalidación llega MIENTRAS se calcula, el resultado viejo no se guarda: sin esto una
    marca hecha a mitad de cuenta quedaba tapada hasta que venciera el TTL."""
    with _lock:
        hit = _cache.get(ciudad_id)
        if hit and _ahora() - hit[0] < TTL_S:
            return hit[1]
        version = _version.get(ciudad_id, 0)
    tramos = repo.list_calles_tramos(ciudad_id)
    comercios = repo.list_comercios_para_calles(ciudad_id) if tramos else []
    marcas = {m["tramo_id"]: m for m in repo.list_calles_marcas_ultimas(ciudad_id)}
    mapa = armar_mapa(tramos, comercios, marcas)
    with _lock:
        if _version.get(ciudad_id, 0) == version:
            _cache[ciudad_id] = (_ahora(), mapa)
    return mapa


# ══════════════════════════════════════════════ marcas

def registrar_marca(repo, tramo: dict, estado: str, nota: str | None, actor: str | None) -> dict:
    """Anota la marca (nunca pisa una anterior) e invalida la caché de la ciudad del tramo."""
    nota = (nota or "").strip() or None
    fila = repo.crear_calle_marca({"tramo_id": tramo["id"], "estado": estado, "nota": nota, "actor": actor})
    invalidar(tramo.get("ciudad_id"))
    logger.info("calles.marca", tramo=tramo["id"], estado=estado, actor=actor)
    return {"estado": fila["estado"], "nota": fila.get("nota"), "actor": fila.get("actor"),
            "created_at": fila.get("created_at")}


# ══════════════════════════════════════════════ importar desde Overpass

def caja_de(comercios: list[dict]) -> tuple[float, float, float, float] | None:
    """(sur, oeste, norte, este): la extensión de los comercios con GPS + `MARGEN_M`.

    Un comercio con el GPS roto (en otra ciudad, o en el mar) estiraría la caja a cientos de
    kilómetros y Overpass no contestaría nunca. Si la caja se pasa de `CAJA_MAX_GRADOS`, se
    recorta al 1-99 % de los puntos; si aun así se pasa, se devuelve None."""
    pts = []
    for c in comercios:
        lat, lng = _num(c.get("lat")), _num(c.get("lng"))
        if lat is not None and lng is not None and -90 <= lat <= 90 and -180 <= lng <= 180 and (lat or lng):
            pts.append((lat, lng))
    if not pts:
        return None

    def extremos(ps):
        lats, lngs = [p[0] for p in ps], [p[1] for p in ps]
        return min(lats), max(lats), min(lngs), max(lngs)

    s, n, w, e = extremos(pts)
    if n - s > CAJA_MAX_GRADOS or e - w > CAJA_MAX_GRADOS:
        def corte(valores):
            v = sorted(valores)
            k = max(0, int(len(v) * 0.01))
            return v[k], v[len(v) - 1 - k]
        s, n = corte([p[0] for p in pts])
        w, e = corte([p[1] for p in pts])
        if n - s > CAJA_MAX_GRADOS or e - w > CAJA_MAX_GRADOS:
            return None
    dlat = MARGEN_M / 110_540
    dlng = MARGEN_M / (111_320 * math.cos(math.radians((s + n) / 2)))
    return (round(s - dlat, 5), round(w - dlng, 5), round(n + dlat, 5), round(e + dlng, 5))


def descargar_vias(caja: tuple[float, float, float, float]) -> list[dict]:
    """Las vías de la caja (sur, oeste, norte, este) según Overpass, con su geometría.

    Un intento y un reintento corto (otro servidor, tras una pausa) si el primero da timeout,
    error de red o 429/5xx. Si los dos fallan, `OverpassError`."""
    s, w, n, e = caja
    consulta = (f'[out:json][timeout:{TIMEOUT_QUERY_S}];'
                f'way["highway"~"{RE_TIPOS}"]({s},{w},{n},{e});out geom({s},{w},{n},{e});')
    ultimo = "sin respuesta"
    for intento, url in enumerate(OVERPASS_URLS):
        if intento:
            time.sleep(PAUSA_REINTENTO_S)
        try:
            r = httpx.post(url, data={"data": consulta}, headers={"User-Agent": UA},
                           timeout=httpx.Timeout(TIMEOUT_HTTP_S, connect=10))
        except httpx.HTTPError as exc:
            ultimo = f"{type(exc).__name__}"
            logger.warning("calles.overpass_red", url=url, error=str(exc)[:200])
            continue
        if r.status_code != 200:
            ultimo = f"HTTP {r.status_code}"
            logger.warning("calles.overpass_status", url=url, status=r.status_code)
            continue
        try:
            datos = r.json()
        except ValueError:
            ultimo = "respuesta ilegible"
            continue
        # Overpass a veces contesta 200 con un `remark` de timeout y la lista cortada.
        if "timed out" in str(datos.get("remark", "")).lower():
            ultimo = "timeout del servidor"
            continue
        return [el for el in datos.get("elements", []) if isinstance(el, dict)]
    raise OverpassError(ultimo)


def get_overpass() -> Callable[[tuple[float, float, float, float]], list[dict]]:
    """Dependencia de FastAPI: el cliente de Overpass. Los tests lo reemplazan por uno falso."""
    return descargar_vias


def _redondear(geom_osm: list) -> list[list[float]]:
    """Geometría de OSM [{lat, lon} | None, ...] -> [[lat,lng],...] con 5 decimales, sin repetidos
    seguidos. Si `out geom(bbox)` dejó huecos (nodos fuera de la caja), queda el tramo continuo
    más largo."""
    corridas: list[list[list[float]]] = [[]]
    for p in geom_osm or []:
        if not isinstance(p, dict) or _num(p.get("lat")) is None or _num(p.get("lon")) is None:
            corridas.append([])
            continue
        punto = [round(float(p["lat"]), 5), round(float(p["lon"]), 5)]
        if not corridas[-1] or corridas[-1][-1] != punto:
            corridas[-1].append(punto)
    return max(corridas, key=len)


def tramos_de_vias(vias: list[dict], ciudad_id: str) -> list[dict]:
    """Las filas de `calles_tramos` a partir de lo que devolvió Overpass.

    Sólo `highway` de `RE_TIPOS` (se vuelve a filtrar acá: no se confía en el servidor), con
    al menos 2 puntos distintos. Sin nombre -> `nombre` null."""
    filas = []
    vistos: set[int] = set()
    for v in vias:
        tags = v.get("tags") or {}
        tipo = tags.get("highway")
        way_id = v.get("id")
        if v.get("type") != "way" or not isinstance(tipo, str) or not _TIPOS.match(tipo):
            continue
        if not isinstance(way_id, int) or way_id in vistos:
            continue
        geom = _redondear(v.get("geometry"))
        if len(geom) < 2:
            continue
        vistos.add(way_id)
        nombre = (tags.get("name") or "").strip() or None
        filas.append({"ciudad_id": ciudad_id, "osm_way_id": way_id, "nombre": nombre, "tipo": tipo,
                      "geom": geom, "longitud_m": int(round(largo_m(geom))), "activo": True})
    return filas


def importar(repo, ciudad_id: str, ciudad: dict | None, overpass: Callable) -> dict:
    """Trae las calles de la ciudad y las guarda (upsert por `osm_way_id`). Responde `{tramos, km}`.

    HTTPException 400 si no hay de dónde sacar la caja, 502 si Overpass falla."""
    comercios = repo.list_comercios_para_calles(ciudad_id)
    caja = caja_de(comercios)
    if caja is None and ciudad and _num(ciudad.get("lat")) is not None and _num(ciudad.get("lng")) is not None:
        # Sin comercios con GPS: ~3 km alrededor del centro de la ciudad.
        lat, lng = float(ciudad["lat"]), float(ciudad["lng"])
        caja = (round(lat - 0.027, 5), round(lng - 0.03, 5), round(lat + 0.027, 5), round(lng + 0.03, 5))
    if caja is None:
        raise HTTPException(status_code=400, detail="La ciudad no tiene comercios con ubicación para armar el mapa")
    try:
        vias = overpass(caja)
    except OverpassError as exc:
        logger.error("calles.importar_overpass", ciudad=ciudad_id, error=str(exc))
        raise HTTPException(
            status_code=502,
            detail="No se pudieron traer las calles de OpenStreetMap (el servicio no respondió). "
                   "Probá de nuevo en unos minutos.") from exc
    filas = tramos_de_vias(vias, ciudad_id)
    if filas:
        repo.upsert_calles_tramos(filas)
    invalidar(ciudad_id)
    km = round(sum(f["longitud_m"] for f in filas) / 1000, 2)
    logger.info("calles.importadas", ciudad=ciudad_id, tramos=len(filas), km=km)
    return {"tramos": len(filas), "km": km}
