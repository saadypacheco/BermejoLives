"""De dónde sale `comercios.calle`.

En Bermejo casi ningún comercio tiene dirección: 1.247 de 1.248 vacía. Pero
todos tienen GPS. Este script le pone a cada uno la calle sobre la que está,
sacándola de OpenStreetMap —el mismo mapa que usan los tiles— y eligiendo el
tramo de calle más cercano al punto.

No escribe en la base: imprime el SQL. Así el cambio se revisa antes de
aplicarse, queda en una migración con el resto y se puede volver atrás.

    python backend/scripts/calles-desde-osm.py bermejo > selfhost/postgres-init/0128_calles_de_bermejo.sql

Las calles bajadas quedan en `.osm-<ciudad>.json` para no volver a pedirle a
Overpass lo mismo (contesta 504 si insistís). Otra ruta: `OSM_CACHE=...`.

Para otra ciudad (Santa Cruz), agregar su caja en CIUDADES y correrlo igual.
Lo único que hay que revisar a ojo es el resumen que sale por stderr: si una
calle se lleva el 40% de los comercios, probablemente el corte de 70 m está
pegando dos calles paralelas en una.
"""
from __future__ import annotations

import json
import math
import os
import sys
import urllib.parse
import urllib.request

# Cajas (sur, oeste, norte, este) con margen sobre la extensión real de los
# comercios cargados. Más grande de la cuenta no molesta; más chica deja
# comercios del borde sin calle.
CIUDADES = {
    "bermejo": (-22.7500, -64.3610, -22.7200, -64.3180),
}

#: Más lejos que esto, el punto no está "sobre" esa calle y se deja en NULL.
#: 70 m es una cuadra corta: alcanza para un puesto en la vereda de enfrente
#: o un GPS que erró, y no tanto como para agarrar la calle paralela.
CORTE_M = 70.0

OVERPASS = "https://overpass-api.de/api/interpreter"
UA = "URUKU/1.0 (directorio de comercios; https://uruku.bo)"


def tramos_de_osm(caja: tuple[float, float, float, float], cache: str | None = None) -> list[dict]:
    """Los tramos de calle CON NOMBRE de la caja. Sin nombre no sirven: lo que
    buscamos es una etiqueta que una persona reconozca.

    Overpass es gratis y compartido: pide una consulta cada tanto y contesta
    504 si insistís. Las calles de una ciudad no cambian de una corrida a la
    otra, así que se guardan en `cache` y la segunda vuelta no sale a la red.
    Para forzar una descarga nueva, borrar el archivo."""
    if cache and os.path.exists(cache):
        return json.load(open(cache, encoding="utf-8"))
    q = f'[out:json][timeout:90];way["highway"]["name"]{caja};out geom;'
    req = urllib.request.Request(
        OVERPASS, data=urllib.parse.urlencode({"data": q}).encode(), headers={"User-Agent": UA}
    )
    datos = json.load(urllib.request.urlopen(req, timeout=180))
    tramos = [w for w in datos.get("elements", []) if w.get("type") == "way" and w.get("geometry")]
    if cache:
        os.makedirs(os.path.dirname(cache) or ".", exist_ok=True)
        json.dump(tramos, open(cache, "w", encoding="utf-8"), ensure_ascii=False)
    return tramos


def _proyector(lat_ref: float):
    """Metros planos. A escala de una ciudad la curvatura no cambia nada y
    evita hacer trigonometría por cada una de las 2.333 comparaciones."""
    kx = 111_320 * math.cos(math.radians(lat_ref))
    return lambda lat, lng: (lng * kx, lat * 110_540)


def _dist_a_segmento(px, py, x1, y1, x2, y2) -> float:
    dx, dy = x2 - x1, y2 - y1
    largo = dx * dx + dy * dy
    t = 0.0 if largo == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / largo))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def asignar(comercios: list[dict], tramos: list[dict], lat_ref: float) -> dict[str, str | None]:
    xy = _proyector(lat_ref)
    segs = []
    for w in tramos:
        nombre = w["tags"]["name"]
        puntos = [xy(p["lat"], p["lon"]) for p in w["geometry"]]
        for (x1, y1), (x2, y2) in zip(puntos, puntos[1:]):
            segs.append((x1, y1, x2, y2, nombre))

    salida: dict[str, str | None] = {}
    for c in comercios:
        if c.get("lat") is None or c.get("lng") is None:
            salida[c["id"]] = None
            continue
        px, py = xy(c["lat"], c["lng"])
        mejor, mejor_d = None, float("inf")
        for x1, y1, x2, y2, nombre in segs:
            # Caja rápida: sin esto son 2,9 millones de raíces cuadradas.
            if px < min(x1, x2) - CORTE_M or px > max(x1, x2) + CORTE_M:
                continue
            if py < min(y1, y2) - CORTE_M or py > max(y1, y2) + CORTE_M:
                continue
            d = _dist_a_segmento(px, py, x1, y1, x2, y2)
            if d < mejor_d:
                mejor, mejor_d = nombre, d
        salida[c["id"]] = mejor if mejor_d <= CORTE_M else None
    return salida


def _comercios_de(ciudad: str) -> list[dict]:
    """Los comercios activos de la ciudad, por PostgREST. Sólo lectura."""
    base = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_ANON_KEY"]
    cab = {"apikey": key, "Authorization": f"Bearer {key}"}
    filas: list[dict] = []
    while True:
        url = (f"{base}/rest/v1/comercios?select=id,lat,lng,ciudades!inner(slug)"
               f"&activo=eq.true&ciudades.slug=eq.{ciudad}&order=id&offset={len(filas)}&limit=1000")
        lote = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=cab), timeout=90))
        filas += lote
        if len(lote) < 1000:
            return filas


def main() -> None:
    # El SQL sale por stdout y va a un archivo. En Windows, stdout redirigido
    # es cp1252 y "Ortuño" sale "Ortu?o": nombres de calle rotos en la base,
    # en silencio. El SQL es UTF-8 siempre, se corra donde se corra.
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    ciudad = sys.argv[1] if len(sys.argv) > 1 else "bermejo"
    caja = CIUDADES[ciudad]
    comercios = _comercios_de(ciudad)
    tramos = tramos_de_osm(caja, cache=os.environ.get("OSM_CACHE") or f".osm-{ciudad}.json")
    lat_ref = sum(c["lat"] for c in comercios if c.get("lat") is not None) / max(1, len(comercios))
    calles = asignar(comercios, tramos, lat_ref)

    con = {k: v for k, v in calles.items() if v}
    import collections
    cuenta = collections.Counter(con.values())
    print(f"{len(comercios)} comercios · {len(tramos)} tramos · "
          f"{len(con)} con calle · {len(comercios) - len(con)} sin calle", file=sys.stderr)
    for nombre, n in cuenta.most_common(15):
        print(f"  {n:5}  {nombre}", file=sys.stderr)

    esc = lambda s: s.replace("'", "''")
    print(f"-- Calle de cada comercio de {ciudad}, deducida del GPS contra OpenStreetMap.")
    print(f"-- Generado por backend/scripts/calles-desde-osm.py · {len(con)} de {len(comercios)} comercios.")
    print("-- No pisa una calle ya puesta a mano: sólo completa las vacías.")
    print("update comercios c set calle = v.calle")
    print("from (values")
    filas_sql = [f"  ('{cid}'::uuid, '{esc(nom)}')" for cid, nom in sorted(con.items())]
    print(",\n".join(filas_sql))
    print(") as v(id, calle)")
    print("where c.id = v.id and c.calle is null;")


if __name__ == "__main__":
    main()
