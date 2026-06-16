#!/usr/bin/env python3
"""
Importa negocios desde OpenStreetMap/Overpass a la base de datos de buscadonde.

Uso:
    python scripts/osm_import.py --ciudad bermejo
    python scripts/osm_import.py --ciudad yacuiba --dry-run
    python scripts/osm_import.py --ciudad bermejo --limit 500

Requiere en el entorno (o en .env):
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY

Se puede correr localmente contra Supabase Cloud o dentro del VPS.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from typing import Optional

import httpx
from dotenv import load_dotenv
from supabase import create_client

# ── Config ────────────────────────────────────────────────────────────────────

load_dotenv("backend/.env")
load_dotenv(".env")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Bounding boxes por ciudad_slug: (sur, oeste, norte, este)
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
    # Argentina
    "la-quiaca":       (-22.12, -65.64, -22.07, -65.58),
    "jujuy":           (-24.22, -65.34, -24.14, -65.26),
    "salta":           (-24.82, -65.47, -24.74, -65.38),
}

# Mapeo OSM tag → slug de rubro en nuestra DB
OSM_TAG_TO_RUBRO: dict[str, str] = {
    # shop
    "clothes":       "ropa",
    "shoes":         "calzado",
    "supermarket":   "supermercado",
    "convenience":   "supermercado",
    "electronics":   "electronica",
    "mobile_phones": "electronica",
    "computer":      "electronica",
    "hardware":      "ferreteria",
    "car_parts":     "repuestos",
    "tyres":         "repuestos",
    "toys":          "jugueteria",
    "jewelry":       "joyeria",
    "optician":      "optica",
    "pharmacy":      "farmacia",
    "bakery":        "panaderia",
    "butcher":       "carniceria",
    "greengrocer":   "verduleria",
    "alcohol":       "licoreria",
    "beverages":     "licoreria",
    "books":         "libreria",
    "stationery":    "libreria",
    "sports":        "deportes",
    "beauty":        "peluqueria",
    "hairdresser":   "peluqueria",
    "furniture":     "muebleria",
    "florist":       "floristeria",
    "pet":           "veterinaria",
    "travel_agency": "agencia-viajes",
    # amenity
    "restaurant":    "restaurante",
    "fast_food":     "restaurante",
    "cafe":          "restaurante",
    "bar":           "bar",
    "pub":           "bar",
    "hotel":         "hotel",
    "hostel":        "hotel",
    "guest_house":   "hotel",
    "motel":         "hotel",
    "bank":          "casa-de-cambio",
    "bureau_de_change": "casa-de-cambio",
    "pharmacy":      "farmacia",
    "hospital":      "salud",
    "clinic":        "salud",
    "dentist":       "salud",
    "doctors":       "salud",
    "fuel":          "combustible",
    "car_wash":      "taller",
    "car_repair":    "taller",
    "taxi":          "transporte",
    "bus_station":   "transporte",
    "veterinary":    "veterinaria",
    "gym":           "deportes",
    "school":        "educacion",
    "college":       "educacion",
    "university":    "educacion",
    # tourism
    "hotel":         "hotel",
    "hostel":        "hotel",
    "guest_house":   "hotel",
    "attraction":    "turismo",
    "museum":        "turismo",
    # craft
    "tailor":        "ropa",
    "shoemaker":     "calzado",
    "electronics_repair": "electronica",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = re.sub(r"^-+|-+$", "", text)
    return text or "negocio"


def unique_slug(base: str, existing: set[str]) -> str:
    slug = slugify(base)[:60]
    candidate = slug
    i = 2
    while candidate in existing:
        candidate = f"{slug}-{i}"
        i += 1
    existing.add(candidate)
    return candidate


def osm_id_to_source(osm_id: int | str) -> str:
    return f"osm:{osm_id}"


def extract_rubro(tags: dict) -> Optional[str]:
    for key in ("shop", "amenity", "tourism", "craft", "office"):
        val = tags.get(key)
        if val and val in OSM_TAG_TO_RUBRO:
            return OSM_TAG_TO_RUBRO[val]
    return "otros"


def extract_whatsapp(tags: dict) -> Optional[str]:
    """Intenta sacar número de WA de los tags OSM."""
    for key in ("contact:phone", "phone", "contact:mobile"):
        val = tags.get(key, "").replace(" ", "").replace("-", "").replace("+", "")
        if val and val.isdigit() and len(val) >= 7:
            return val
    return None


def extract_horario(tags: dict) -> Optional[str]:
    return tags.get("opening_hours") or tags.get("contact:opening_hours")


def extract_web(tags: dict) -> Optional[str]:
    return tags.get("website") or tags.get("contact:website") or tags.get("url")


def extract_instagram(tags: dict) -> Optional[str]:
    v = tags.get("contact:instagram") or tags.get("instagram")
    if v and not v.startswith("http"):
        v = f"https://instagram.com/{v.lstrip('@')}"
    return v


def extract_facebook(tags: dict) -> Optional[str]:
    v = tags.get("contact:facebook") or tags.get("facebook")
    if v and not v.startswith("http"):
        v = f"https://facebook.com/{v}"
    return v


# ── Overpass ──────────────────────────────────────────────────────────────────

def query_overpass(bbox: tuple[float, float, float, float], timeout: int = 60) -> list[dict]:
    s, w, n, e = bbox
    query = f"""
[out:json][timeout:{timeout}];
(
  node["shop"]({s},{w},{n},{e});
  node["amenity"~"restaurant|fast_food|cafe|bar|hotel|hostel|guest_house|motel|
    bank|bureau_de_change|pharmacy|hospital|clinic|dentist|doctors|fuel|
    car_repair|taxi|bus_station|veterinary|gym|school"]({s},{w},{n},{e});
  node["tourism"~"hotel|hostel|guest_house|attraction|museum"]({s},{w},{n},{e});
  node["craft"]({s},{w},{n},{e});
  way["shop"]({s},{w},{n},{e});
  way["amenity"~"restaurant|fast_food|cafe|bar|hotel|hostel|bank|pharmacy"]({s},{w},{n},{e});
);
out center tags;
""".strip()

    print(f"  Consultando Overpass API para bbox {bbox}...")
    resp = httpx.post(OVERPASS_URL, data={"data": query}, timeout=90)
    resp.raise_for_status()
    data = resp.json()
    elements = data.get("elements", [])
    print(f"  → {len(elements)} elementos OSM recibidos")
    return elements


# ── Transform ─────────────────────────────────────────────────────────────────

def element_to_row(
    el: dict,
    ciudad_id: str,
    rubro_map: dict[str, str],
    existing_slugs: set[str],
    existing_sources: set[str],
) -> Optional[dict]:
    tags = el.get("tags", {})
    nombre = tags.get("name") or tags.get("name:es") or tags.get("brand")
    if not nombre:
        return None  # sin nombre → skip

    source = osm_id_to_source(el["id"])  # "osm:123456"
    if source in existing_sources:
        return None  # ya importado

    # Coordenadas
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

    row = {
        "slug":        slug,
        "nombre":      nombre[:120],
        "ciudad_id":   ciudad_id,
        "lat":         lat,
        "lng":         lng,
        "rubro_id":    rubro_id,
        "verificado":  False,
        "activo":      True,
        "fuente":      "osm",
        "cargado_por": source,   # osm:<node_id> — permite reidentificar el elemento original
        "modalidad":   "local",
        "plan":        "gratis",
    }

    # Opcionales
    direccion = tags.get("addr:street", "")
    numero    = tags.get("addr:housenumber", "")
    if direccion:
        row["direccion"] = f"{direccion} {numero}".strip()

    wa = extract_whatsapp(tags)
    if wa:
        row["whatsapp"] = wa

    horario = extract_horario(tags)
    if horario:
        row["horario"] = horario[:200]

    web = extract_web(tags)
    if web:
        row["sitio_web"] = web[:300]

    ig = extract_instagram(tags)
    if ig:
        row["instagram_url"] = ig[:300]

    fb = extract_facebook(tags)
    if fb:
        row["facebook_url"] = fb[:300]

    desc_parts = []
    if tags.get("description"):
        desc_parts.append(tags["description"])
    if tags.get("cuisine"):
        desc_parts.append(f"Cocina: {tags['cuisine']}")
    if tags.get("brand"):
        desc_parts.append(f"Marca: {tags['brand']}")
    if desc_parts:
        row["descripcion"] = " · ".join(desc_parts)[:500]

    return row


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Importa negocios OSM a buscadonde")
    parser.add_argument("--ciudad", required=True, help="Slug de la ciudad (ej: bermejo)")
    parser.add_argument("--dry-run", action="store_true", help="No inserta, solo muestra cuántos encontraría")
    parser.add_argument("--limit", type=int, default=0, help="Limitar cantidad de inserciones (0 = sin límite)")
    parser.add_argument("--batch", type=int, default=50, help="Tamaño del batch de inserción")
    args = parser.parse_args()

    ciudad_slug = args.ciudad
    if ciudad_slug not in CIUDADES_BBOX:
        print(f"ERROR: ciudad '{ciudad_slug}' no tiene bbox definido.")
        print(f"Ciudades disponibles: {', '.join(CIUDADES_BBOX)}")
        sys.exit(1)

    db = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Cargar ciudad_id
    res = db.table("ciudades").select("id").eq("slug", ciudad_slug).limit(1).execute()
    if not res.data:
        print(f"ERROR: ciudad '{ciudad_slug}' no encontrada en la DB.")
        sys.exit(1)
    ciudad_id = res.data[0]["id"]
    print(f"Ciudad: {ciudad_slug} → {ciudad_id}")

    # Cargar rubros
    res = db.table("rubros").select("id, slug").execute()
    rubro_map = {r["slug"]: r["id"] for r in (res.data or [])}
    print(f"Rubros disponibles: {len(rubro_map)}")

    # Slugs y referencias OSM existentes para evitar duplicados
    res = db.table("comercios").select("slug, cargado_por").eq("activo", True).execute()
    existing_slugs: set[str] = {r["slug"] for r in (res.data or [])}
    existing_sources: set[str] = {r["cargado_por"] for r in (res.data or []) if r.get("cargado_por", "").startswith("osm:")}
    print(f"Comercios existentes: {len(existing_slugs)} (slugs), {len(existing_sources)} ya importados de OSM")

    # Query Overpass
    bbox = CIUDADES_BBOX[ciudad_slug]
    elements = query_overpass(bbox)

    # Transformar
    rows = []
    skipped = 0
    for el in elements:
        row = element_to_row(el, ciudad_id, rubro_map, existing_slugs, existing_sources)
        if row:
            rows.append(row)
            if args.limit and len(rows) >= args.limit:
                break
        else:
            skipped += 1

    print(f"\nResultado: {len(rows)} para insertar, {skipped} descartados (sin nombre / ya existentes / sin coords)")

    if args.dry_run:
        print("\n[DRY RUN] Primeros 5 registros:")
        for r in rows[:5]:
            print(f"  · {r['nombre']} ({r.get('direccion','sin dir')}) rubro={next((k for k,v in rubro_map.items() if v==r.get('rubro_id')),'?')}")
        return

    if not rows:
        print("Nada para insertar.")
        return

    # Insertar en batches
    inserted = 0
    errors = 0
    for i in range(0, len(rows), args.batch):
        batch = rows[i:i + args.batch]
        try:
            db.table("comercios").insert(batch).execute()
            inserted += len(batch)
            print(f"  Batch {i//args.batch + 1}: {len(batch)} insertados ({inserted}/{len(rows)})")
        except Exception as exc:
            errors += len(batch)
            print(f"  ERROR batch {i//args.batch + 1}: {exc}")
        time.sleep(0.3)  # respetar rate limit de Supabase

    print(f"\n✓ Importación completa: {inserted} insertados, {errors} errores")
    print(f"  Ciudad: {ciudad_slug} | Fuente: OSM")
    print(f"  Los negocios quedan con verificado=false — revisarlos en el admin.")


if __name__ == "__main__":
    main()
