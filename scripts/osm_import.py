#!/usr/bin/env python3
"""
Importa negocios desde OpenStreetMap/Overpass a la base de datos de buscadonde.

Uso:
    python scripts/osm_import.py --ciudad bermejo
    python scripts/osm_import.py --pais bolivia
    python scripts/osm_import.py --pais argentina
    python scripts/osm_import.py --pais bolivia --dry-run
    python scripts/osm_import.py --ciudad bermejo --limit 200

Requiere en el entorno:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY

Correr dentro del contenedor backend (ya tiene las deps):
    docker cp scripts/osm_import.py buscadonde-backend:/tmp/osm_import.py
    docker exec buscadonde-backend python /tmp/osm_import.py --pais bolivia
"""

import argparse
import json
import os
import re
import sys
import time
import unicodedata
from typing import Optional

import urllib.parse
import urllib.request
from dotenv import load_dotenv
from supabase import create_client

# ── Config ────────────────────────────────────────────────────────────────────

load_dotenv("backend/.env")
load_dotenv(".env")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# ── Áreas geográficas ─────────────────────────────────────────────────────────
# Formato: (sur, oeste, norte, este)

CIUDADES_BBOX: dict[str, tuple[float, float, float, float]] = {
    "bermejo":         (-22.82, -64.46, -22.65, -64.25),
    "yacuiba":         (-22.12, -63.78, -21.90, -63.55),
    "villazon":        (-22.15, -65.67, -21.97, -65.47),
    "tarija":          (-21.62, -64.85, -21.43, -64.64),
    "santa-cruz":      (-17.88, -63.28, -17.67, -63.08),
    "la-paz":          (-16.58, -68.23, -16.42, -68.04),
    "cochabamba":      (-17.46, -66.22, -17.32, -66.08),
    "sucre":           (-19.07, -65.30, -18.96, -65.18),
    "oruro":           (-17.99, -67.20, -17.94, -67.09),
    "potosi":          (-19.62, -65.79, -19.52, -65.72),
    "trinidad":        (-14.87, -65.00, -14.78, -64.88),
    "cobija":          (-11.05, -68.82, -10.99, -68.73),
    "puerto-quijarro": (-17.81, -57.82, -17.76, -57.72),
    "desaguadero":     (-16.59, -69.07, -16.54, -68.99),
    "la-quiaca":       (-22.12, -65.64, -22.07, -65.58),
    "jujuy":           (-24.22, -65.34, -24.14, -65.26),
    "salta":           (-24.82, -65.47, -24.74, -65.38),
}

# Bolivia: 9 departamentos (chunks para no hacer timeout en Overpass)
BOLIVIA_CHUNKS: list[tuple[str, tuple[float, float, float, float]]] = [
    ("La Paz",        (-18.30, -70.00, -10.00, -60.50)),
    ("Cochabamba",    (-18.90, -66.70, -14.50, -63.00)),
    ("Santa Cruz",    (-22.00, -63.70, -13.50, -57.50)),
    ("Oruro",         (-21.00, -68.70, -15.50, -65.50)),
    ("Potosí",        (-23.00, -68.20, -17.50, -64.00)),
    ("Chuquisaca",    (-21.50, -65.70, -17.50, -62.70)),
    ("Tarija",        (-22.90, -65.50, -20.50, -62.00)),
    ("Beni",          (-16.50, -68.50,  -9.50, -60.50)),
    ("Pando",         (-14.00, -70.50,  -9.50, -65.50)),
]

# Argentina: provincias clave (frontera + grandes centros)
ARGENTINA_CHUNKS: list[tuple[str, tuple[float, float, float, float]]] = [
    ("Jujuy",          (-24.50, -67.50, -21.70, -64.50)),
    ("Salta",          (-26.50, -68.50, -21.70, -63.00)),
    ("Tucumán",        (-28.00, -66.50, -25.50, -64.50)),
    ("Catamarca",      (-29.50, -69.50, -25.00, -65.00)),
    ("La Rioja",       (-31.00, -69.50, -27.00, -65.50)),
    ("Santiago Estero",(-29.50, -65.50, -25.00, -61.00)),
    ("Chaco",          (-27.50, -63.00, -24.00, -59.00)),
    ("Formosa",        (-26.50, -62.50, -22.00, -57.50)),
    ("Misiones",       (-28.00, -56.50, -25.50, -53.50)),
    ("Corrientes",     (-30.50, -60.00, -27.00, -55.50)),
    ("Entre Ríos",     (-34.50, -60.00, -29.50, -57.50)),
    ("Córdoba",        (-35.50, -66.50, -28.50, -62.50)),
    ("Santa Fe",       (-34.50, -62.50, -28.00, -58.50)),
    ("Buenos Aires",   (-41.00, -63.50, -33.50, -56.50)),
    ("Mendoza",        (-37.50, -70.50, -31.50, -67.50)),
    ("San Juan",       (-32.50, -70.00, -28.00, -67.00)),
    ("San Luis",       (-35.50, -67.50, -31.50, -64.00)),
    ("La Pampa",       (-40.00, -68.00, -34.00, -63.00)),
    ("Neuquén",        (-40.50, -71.00, -35.50, -68.50)),
    ("Río Negro",      (-42.00, -71.00, -37.00, -62.50)),
    ("Chubut",         (-46.50, -72.00, -40.50, -63.50)),
    ("Santa Cruz AR",  (-52.00, -73.00, -46.00, -65.00)),
    ("Tierra del F.",  (-55.50, -68.50, -52.00, -63.00)),
]

PAISES: dict[str, list[tuple[str, tuple[float, float, float, float]]]] = {
    "bolivia":   BOLIVIA_CHUNKS,
    "argentina": ARGENTINA_CHUNKS,
}

# ── Mapeo OSM → rubro ─────────────────────────────────────────────────────────

OSM_TAG_TO_RUBRO: dict[str, str] = {
    # shop
    "clothes":            "ropa",
    "shoes":              "calzado",
    "supermarket":        "supermercado",
    "convenience":        "supermercado",
    "electronics":        "electronica",
    "mobile_phones":      "electronica",
    "computer":           "electronica",
    "hardware":           "ferreteria",
    "car_parts":          "repuestos",
    "tyres":              "repuestos",
    "toys":               "jugueteria",
    "jewelry":            "joyeria",
    "optician":           "optica",
    "pharmacy":           "farmacia",
    "bakery":             "panaderia",
    "butcher":            "carniceria",
    "greengrocer":        "verduleria",
    "alcohol":            "licoreria",
    "beverages":          "licoreria",
    "books":              "libreria",
    "stationery":         "libreria",
    "sports":             "deportes",
    "beauty":             "peluqueria",
    "hairdresser":        "peluqueria",
    "furniture":          "muebleria",
    "florist":            "floristeria",
    "pet":                "veterinaria",
    "travel_agency":      "agencia-viajes",
    "department_store":   "supermercado",
    "mall":               "supermercado",
    "variety_store":      "otros",
    "general":            "otros",
    # amenity
    "restaurant":         "restaurante",
    "fast_food":          "restaurante",
    "cafe":               "restaurante",
    "bar":                "bar",
    "pub":                "bar",
    "hotel":              "hotel",
    "hostel":             "hotel",
    "guest_house":        "hotel",
    "motel":              "hotel",
    "bank":               "casa-de-cambio",
    "bureau_de_change":   "casa-de-cambio",
    "pharmacy":           "farmacia",
    "hospital":           "salud",
    "clinic":             "salud",
    "dentist":            "salud",
    "doctors":            "salud",
    "fuel":               "combustible",
    "car_wash":           "taller",
    "car_repair":         "taller",
    "taxi":               "transporte",
    "bus_station":        "transporte",
    "veterinary":         "veterinaria",
    "gym":                "deportes",
    "school":             "educacion",
    "college":            "educacion",
    "university":         "educacion",
    # tourism
    "attraction":         "turismo",
    "museum":             "turismo",
    # craft
    "tailor":             "ropa",
    "shoemaker":          "calzado",
    "electronics_repair": "electronica",
    "car_repair":         "taller",
}

# Overpass query base
_AMENITIES = (
    "restaurant|fast_food|cafe|bar|hotel|hostel|guest_house|motel|"
    "bank|bureau_de_change|pharmacy|hospital|clinic|dentist|doctors|"
    "fuel|car_wash|car_repair|taxi|bus_station|veterinary|gym|school|"
    "college|university"
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return re.sub(r"^-+|-+$", "", text) or "negocio"


def unique_slug(base: str, existing: set[str]) -> str:
    slug = slugify(base)[:60]
    candidate = slug
    i = 2
    while candidate in existing:
        candidate = f"{slug}-{i}"
        i += 1
    existing.add(candidate)
    return candidate


def osm_ref(osm_id: int | str) -> str:
    return f"osm:{osm_id}"


def ciudad_mas_cercana(lat: float, lng: float, ciudades: list[dict]) -> str | None:
    """Devuelve el id de la ciudad más cercana (distancia euclídea en grados)."""
    mejor_id, mejor_dist = None, float("inf")
    for c in ciudades:
        if c.get("lat") is None or c.get("lng") is None:
            continue
        dist = (c["lat"] - lat) ** 2 + (c["lng"] - lng) ** 2
        if dist < mejor_dist:
            mejor_dist = dist
            mejor_id = c["id"]
    return mejor_id


def extract_rubro(tags: dict) -> str:
    for key in ("shop", "amenity", "tourism", "craft", "office"):
        val = tags.get(key)
        if val and val in OSM_TAG_TO_RUBRO:
            return OSM_TAG_TO_RUBRO[val]
    return "otros"


def extract_phone(tags: dict) -> Optional[str]:
    for key in ("contact:phone", "phone", "contact:mobile"):
        val = tags.get(key, "").replace(" ", "").replace("-", "").replace("+", "")
        if val and val.isdigit() and len(val) >= 7:
            return val
    return None


def extract_optional(tags: dict) -> dict:
    out: dict = {}

    # Dirección
    street = tags.get("addr:street", "")
    number = tags.get("addr:housenumber", "")
    if street:
        out["direccion"] = f"{street} {number}".strip()[:200]

    # Contacto
    if tags.get("opening_hours") or tags.get("contact:opening_hours"):
        out["horario"] = (tags.get("opening_hours") or tags.get("contact:opening_hours"))[:200]
    for src in ("website", "contact:website", "url"):
        if tags.get(src) and "sitio_web" not in out:
            out["sitio_web"] = tags[src][:300]
    for src in ("email", "contact:email"):
        if tags.get(src) and "email" not in out:
            out["email"] = tags[src][:200]
    for src in ("contact:instagram", "instagram"):
        if tags.get(src) and "instagram_url" not in out:
            v = tags[src]
            out["instagram_url"] = v if v.startswith("http") else f"https://instagram.com/{v.lstrip('@')}"
    for src in ("contact:facebook", "facebook"):
        if tags.get(src) and "facebook_url" not in out:
            v = tags[src]
            out["facebook_url"] = v if v.startswith("http") else f"https://facebook.com/{v}"

    # Marca y operador
    if tags.get("brand") and tags.get("brand") != tags.get("name"):
        out["marca"] = tags["brand"][:120]
    if tags.get("branch"):
        out["sucursal"] = tags["branch"][:120]
    if tags.get("operator"):
        out["operador"] = tags["operator"][:120]

    # Cocina (restaurantes)
    if tags.get("cuisine"):
        out["tipo_cocina"] = tags["cuisine"][:120]

    # Estrellas (hoteles)
    stars = tags.get("stars") or tags.get("tourism:stars")
    if stars:
        try:
            out["estrellas"] = int(float(stars))
        except (ValueError, TypeError):
            pass

    # ATM
    if tags.get("atm") == "yes":
        out["tiene_atm"] = True

    # Combustibles
    combustibles = [c.replace("fuel:", "") for c in
                    ("fuel:diesel", "fuel:gasoline", "fuel:cng", "fuel:lpg", "fuel:oil",
                     "fuel:electricity", "fuel:octane_91", "fuel:octane_95")
                    if tags.get(c) == "yes"]
    if combustibles:
        out["combustibles"] = combustibles

    # Internet
    if tags.get("internet_access") and tags["internet_access"] != "no":
        out["internet_access"] = True

    # Especialidad médica
    if tags.get("healthcare:speciality"):
        out["especialidad"] = tags["healthcare:speciality"][:120]

    # Descripción (solo descripción libre de OSM)
    if tags.get("description"):
        out["descripcion"] = tags["description"][:500]

    return out


# ── Overpass ──────────────────────────────────────────────────────────────────

def query_overpass(label: str, bbox: tuple[float, float, float, float], retries: int = 3) -> list[dict]:
    s, w, n, e = bbox
    query = f"""
[out:json][timeout:90];
(
  node["shop"]({s},{w},{n},{e});
  node["amenity"~"{_AMENITIES}"]({s},{w},{n},{e});
  node["tourism"~"hotel|hostel|guest_house|attraction|museum"]({s},{w},{n},{e});
  node["craft"]({s},{w},{n},{e});
  way["shop"]({s},{w},{n},{e});
  way["amenity"~"restaurant|fast_food|cafe|bar|hotel|hostel|bank|pharmacy|fuel"]({s},{w},{n},{e});
);
out center tags;
""".strip()

    for attempt in range(1, retries + 1):
        try:
            print(f"  [{label}] Consultando Overpass (intento {attempt})...")
            payload = urllib.parse.urlencode({"data": query}).encode()
            req = urllib.request.Request(
                OVERPASS_URL, data=payload, method="POST",
                headers={"Content-Type": "application/x-www-form-urlencoded",
                         "User-Agent": "buscadonde-osm-import/1.0"},
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                elements = json.loads(resp.read()).get("elements", [])
            print(f"  [{label}] → {len(elements)} elementos OSM")
            return elements
        except Exception as exc:
            print(f"  [{label}] ERROR: {exc}")
            if attempt < retries:
                time.sleep(10 * attempt)
    return []


# ── Transform ─────────────────────────────────────────────────────────────────

def element_to_row(
    el: dict,
    ciudad_id: str,
    rubro_map: dict[str, str],
    existing_slugs: set[str],
    existing_refs: set[str],
    ciudades_db: list[dict] | None = None,
) -> Optional[dict]:
    tags = el.get("tags", {})
    nombre = tags.get("name") or tags.get("name:es") or tags.get("brand")
    if not nombre:
        return None

    ref = osm_ref(el["id"])
    if ref in existing_refs:
        return None

    if el["type"] == "node":
        lat, lng = el.get("lat"), el.get("lon")
    else:
        center = el.get("center", {})
        lat, lng = center.get("lat"), center.get("lon")
    if lat is None or lng is None:
        return None

    rubro_slug = extract_rubro(tags)
    rubro_id = rubro_map.get(rubro_slug) or rubro_map.get("otros")
    slug = unique_slug(nombre, existing_slugs)
    phone = extract_phone(tags)

    # Asignar ciudad más cercana si hay lista de ciudades disponible
    cid = ciudad_mas_cercana(lat, lng, ciudades_db) if ciudades_db else ciudad_id

    row: dict = {
        "slug":        slug,
        "nombre":      nombre[:120],
        "ciudad_id":   cid,
        "lat":         lat,
        "lng":         lng,
        "rubro_id":    rubro_id,
        "verificado":  False,
        "activo":      True,
        "fuente":      "osm",
        "cargado_por": ref,
        "modalidad":   "minorista",
        "plan":        "gratis",
        "whatsapp":    phone or "",   # NOT NULL en DB; vacío = sin dato
    }
    row.update(extract_optional(tags))
    return row


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Importa negocios OSM a buscadonde")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--ciudad", help="Slug de ciudad (ej: bermejo)")
    group.add_argument("--pais",   help="País completo: bolivia | argentina")
    parser.add_argument("--dry-run", action="store_true", help="Solo muestra, no inserta")
    parser.add_argument("--limit",   type=int, default=0,  help="Limitar inserciones (0=sin límite)")
    parser.add_argument("--batch",   type=int, default=50, help="Tamaño del batch")
    parser.add_argument("--ciudad-default", default="bermejo",
                        help="Ciudad que se asigna a negocios sin ciudad DB (default: bermejo)")
    args = parser.parse_args()

    db = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Rubros
    res = db.table("rubros").select("id, slug").execute()
    rubro_map = {r["slug"]: r["id"] for r in (res.data or [])}
    print(f"Rubros cargados: {len(rubro_map)}")

    # Ciudades con coordenadas para asignación automática
    res = db.table("ciudades").select("id, slug, nombre, lat, lng").execute()
    ciudades_db = [c for c in (res.data or []) if c.get("lat") is not None]
    print(f"Ciudades con coords: {len(ciudades_db)}")

    # Slugs y refs OSM ya existentes
    res = db.table("comercios").select("slug, cargado_por").eq("activo", True).limit(200000).execute()
    existing_slugs: set[str] = {r["slug"] for r in (res.data or [])}
    existing_refs:  set[str] = {r["cargado_por"] for r in (res.data or []) if (r.get("cargado_por") or "").startswith("osm:")}
    print(f"Existentes: {len(existing_slugs)} slugs, {len(existing_refs)} refs OSM ya importadas")

    # Armar lista de chunks a procesar
    if args.ciudad:
        if args.ciudad not in CIUDADES_BBOX:
            print(f"ERROR: ciudad '{args.ciudad}' no tiene bbox. Disponibles: {', '.join(CIUDADES_BBOX)}")
            sys.exit(1)
        # Buscar ciudad_id en DB
        res = db.table("ciudades").select("id").eq("slug", args.ciudad).limit(1).execute()
        ciudad_id = res.data[0]["id"] if res.data else None
        if not ciudad_id:
            print(f"ERROR: '{args.ciudad}' no encontrada en DB")
            sys.exit(1)
        chunks = [(args.ciudad, CIUDADES_BBOX[args.ciudad], ciudad_id)]

    else:
        if args.pais not in PAISES:
            print(f"ERROR: pais debe ser 'bolivia' o 'argentina'")
            sys.exit(1)
        # Para país completo usamos ciudad_default para asignar ciudad_id
        res = db.table("ciudades").select("id, slug, nombre, lat, lng").execute()
        ciudades_db = res.data or []
        ciudad_default_id = next((c["id"] for c in ciudades_db if c["slug"] == args.ciudad_default), None)
        if not ciudad_default_id:
            print(f"ERROR: ciudad default '{args.ciudad_default}' no encontrada en DB")
            sys.exit(1)

        chunks = [
            (nombre, bbox, ciudad_default_id)
            for nombre, bbox in PAISES[args.pais]
        ]

    # Procesar chunks
    total_rows: list[dict] = []
    for label, bbox, ciudad_id in chunks:
        elements = query_overpass(label, bbox)
        for el in elements:
            row = element_to_row(el, ciudad_id, rubro_map, existing_slugs, existing_refs, ciudades_db)
            if row:
                total_rows.append(row)
                if args.limit and len(total_rows) >= args.limit:
                    break
        if args.limit and len(total_rows) >= args.limit:
            print(f"  Límite de {args.limit} alcanzado")
            break
        time.sleep(2)  # respetar rate limit de Overpass entre chunks

    print(f"\n{'='*50}")
    print(f"Total para insertar: {len(total_rows)}")

    if args.dry_run:
        from collections import Counter
        rubros_c = Counter(r.get("rubro_id") for r in total_rows)
        id_to_slug = {v: k for k, v in rubro_map.items()}
        print("\nDistribución por rubro:")
        for rid, n in rubros_c.most_common(20):
            print(f"  {n:5d}  {id_to_slug.get(rid, '?')}")
        print("\nMuestra de 10 registros:")
        for r in total_rows[:10]:
            print(f"  · {r['nombre'][:40]:40s} | {r.get('direccion','')[:30]:30s} | wa={r.get('whatsapp','')}")
        return

    if not total_rows:
        print("Nada para insertar.")
        return

    # Insertar en batches
    inserted, errors = 0, 0
    for i in range(0, len(total_rows), args.batch):
        batch = total_rows[i:i + args.batch]
        try:
            db.table("comercios").insert(batch).execute()
            inserted += len(batch)
            pct = inserted * 100 // len(total_rows)
            print(f"  Batch {i//args.batch+1:3d}: {len(batch)} insertados — {inserted}/{len(total_rows)} ({pct}%)")
        except Exception as exc:
            errors += len(batch)
            print(f"  ERROR batch {i//args.batch+1}: {exc}")
        time.sleep(0.3)

    print(f"\n✓ Completado: {inserted} insertados, {errors} errores")
    print(f"  Todos quedan con verificado=false — revisarlos en /admin")


if __name__ == "__main__":
    main()
