"""Detección automática del lugar (mercado/galería) por GPS.

En el autoregistro el dueño manda su ubicación; si cae DENTRO del polígono de una
manzana → ese lugar (confiable); si no, el lugar-punto más cercano dentro de un
radio chico. Así el comercio queda asignado al mercado/galería sin que nadie elija.
"""
from math import asin, cos, radians, sin, sqrt


def _dist_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000.0
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * r * asin(sqrt(a))


def _en_poligono(lat: float, lng: float, poly: list) -> bool:
    """Ray casting. poly = [[lat, lng], ...] (lat = y, lng = x)."""
    dentro = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        yi, xi = poly[i][0], poly[i][1]
        yj, xj = poly[j][0], poly[j][1]
        if ((yi > lat) != (yj > lat)) and (lng < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi):
            dentro = not dentro
        j = i
    return dentro


def elegir_lugar(lugares: list[dict], lat: float | None, lng: float | None, radio_m: float = 35.0) -> str | None:
    """Id del lugar al que corresponde el punto, o None. `radio_m=0` = solo polígono."""
    if lat is None or lng is None:
        return None
    # 1) polígono de la manzana que CONTIENE el punto (lo más confiable)
    for l in lugares:
        poly = l.get("poligono")
        if poly and len(poly) >= 3:
            try:
                if _en_poligono(lat, lng, poly):
                    return l["id"]
            except (TypeError, IndexError, KeyError):
                continue
    # 2) el lugar-punto más cercano dentro del radio
    mejor, mejor_d = None, radio_m
    for l in lugares:
        if l.get("lat") is None or l.get("lng") is None:
            continue
        d = _dist_m(lat, lng, l["lat"], l["lng"])
        if d <= mejor_d:
            mejor_d = d
            mejor = l["id"]
    return mejor
