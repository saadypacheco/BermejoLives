"""Traer negocios de Overture Maps (Places) a `comercios_importados`, por ciudad (docs/vigia-fuentes.md, fase 2).

    docker exec buscadonde-backend python -m app.services.importar_overture --ciudad tarija --dry-run
    docker exec buscadonde-backend python -m app.services.importar_overture --ciudad tarija

QUÉ ES
======

Overture Maps Foundation (Meta, Microsoft, Amazon, TomTom) publica cada mes una base abierta de lugares en
GeoParquet, en un bucket público de S3. En Bolivia casi todo viene de las páginas de negocios de Meta. Medido el
16/11 (release 2026-10-21.0): ~290 lugares en Bermejo y ~3.800 en Tarija, contra 68 y ~800 de OpenStreetMap.
Trae nombre, categoría, punto, teléfono, web, redes, dirección y un `confidence`; NO trae horario.

LICENCIA
========

Cada fila declara la suya: CDLA-Permissive-2.0 (Meta, Microsoft), Apache-2.0 (Foursquare) o CC0. Las tres
permiten uso comercial y guardar los datos. Se guarda en `tags.overture.fuentes` de dónde vino cada una. Nada que
ver con Google ni con raspar páginas: es una descarga publicada para esto.

NADA SE PUBLICA SOLO
====================

Todo entra como `estado='nuevo'` a la cola de Importados y una persona lo promueve, de a uno. Un negocio de una
página de Facebook puede estar cerrado hace años (`operating_status` viene vacío en Bolivia). Solo entra lo de
`confidence` >= 0.5. Volver a correrlo no duplica ni pisa nada: lo que ya está (misma `fuente_id`) se saltea.

CÓMO LEE
========

Con DuckDB, que lee el GeoParquet de S3 filtrando por la caja de la ciudad (`bbox`) sin bajar el mundo entero.
La extensión `httpfs` se instala al construir la imagen en `DUCKDB_EXT_DIR` (el usuario del contenedor no
tiene carpeta personal).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable

import structlog

from app.core.telefonos_foto import normalizar as normalizar_telefono
from app.services import enlaces, tarjetas
from app.services.cargas import metros_entre
from app.services.importar_turismo import mismo_nombre

logger = structlog.get_logger()

FUENTE = "overture"
#: La release que se lee. Overture publica una por mes (https://docs.overturemaps.org/release/latest/); el vigía
#: diario va a buscar la nueva solo (fase 3). Mientras tanto se cambia acá o con --release.
RELEASE = "2026-10-21.0"
BUCKET = "s3://overturemaps-us-west-2/release/{release}/theme=places/type=place/*"
CONFIANZA_MINIMA = 0.5
#: Radio por ciudad (km desde `ciudades.lat/lng`): lo bastante para la mancha urbana sin comerse la ciudad vecina
#: (La Paz con 8 km no llega al centro de El Alto). Las que no están usan RADIO_KM.
RADIO_KM = 8.0
RADIOS: dict[str, float] = {"santa-cruz": 12.0, "cochabamba": 9.0, "la-paz": 8.0, "tarija": 7.0, "oruro": 6.0,
                            "bermejo": 4.0}
METROS_REPETIDO = 120          # como importar_osm: a menos de esto y con el nombre parecido, es el mismo local
MAX_TEXTO = tarjetas.MAX_TEXTO_LEIDO
_RE_RELEASE = re.compile(r"^\d{4}-\d{2}-\d{2}\.\d+$")

#: Categoría de Overture (`basic_category`) → rubro de URUKU. Lo que no está queda sin rubro y se elige en el
#: panel: mejor eso que inventarle uno (el error que costó limpiar `alimentos` y `hogar`).
RUBRO: dict[str, str] = {
    "restaurant": "restaurantes", "casual_eatery": "restaurantes", "food_service": "restaurantes",
    "food_and_drink": "restaurantes",
    "fast_food_restaurant": "comida-rapida",
    "cafe": "cafeteria", "coffee_shop": "cafeteria", "smoothie_juice_bar": "cafeteria",
    "non_alcoholic_beverage_venue": "cafeteria",
    "bar": "nocturna", "dance_club": "nocturna", "lounge": "nocturna", "music_venue": "nocturna",
    "brewery": "bebidas", "winery": "bebidas",
    "hotel": "hospedaje", "lodging": "hospedaje", "bed_and_breakfast": "hospedaje",
    "fashion_and_apparel_store": "ropa", "second_hand_store": "usados",
    "food_and_beverage_store": "alimentos", "convenience_store": "alimentos", "farmers_market": "alimentos",
    "warehouse_club_store": "alimentos",
    "hardware_home_and_garden_store": "ferreteria",
    "personal_or_beauty_service": "belleza", "personal_care_and_beauty_store": "belleza",
    "automotive_service": "taller-mecanico", "vehicle_service": "taller-mecanico",
    "vehicle_parts_store": "repuestos-autos",
    "pharmacy_and_drug_store": "farmacia",
    "gym": "gimnasios", "fitness_studio": "gimnasios", "sport_or_fitness_facility": "gimnasios",
    "sport_field": "gimnasios", "sport_court": "gimnasios",
    "travel_service": "turismo",
    "electronics_store": "electronica", "technical_service": "servicio-tecnico",
    "sporting_goods_store": "deportes",
    "animal_and_pet_store": "mascotas", "animal_or_pet_service": "mascotas",
    "flowers_and_gifts_store": "floreria", "toys_and_games_store": "jugueteria",
    "laundry_service": "lavadero", "event_or_party_service": "salones",
    "vision_or_eye_care_clinic": "optica", "shopping_mall": "galerias",
    "atm": "cajeros", "parking": "estacionamiento", "taxi_or_ride_share_service": "taxis",
}

#: Lo que no es un comercio: templos, escuelas, oficinas públicas, accidentes geográficos, plazas y monumentos
#: (los lugares para visitar van por docs/lugares-turismo.md, no por acá).
NO_COMERCIO = frozenset({
    "christian_place_of_worship", "religious_organization", "place_of_worship",
    "education", "place_of_learning", "college_university", "high_school", "elementary_school",
    "middle_school", "preschool", "campus_building", "research_institute", "library",
    "government_office", "community_and_government", "civic_organization", "police_station", "fire_station",
    "embassy", "courthouse", "public_utility", "electric_utility_provider", "social_or_community_service",
    "community_center", "youth_organization",
    "historic_site", "park", "public_plaza", "river", "mountain", "waterfall", "bridge", "nature_reserve",
    "geographic_entities", "museum", "cultural_center", "monument", "landmark_and_historical_building",
    "airport", "stadium_arena", "zoo", "aquarium", "animal_attraction", "skate_park",
    "adult_entertainment_venue",
})
CERRADOS = frozenset({"permanently_closed", "temporarily_closed", "closed"})


# ───────────────────────────────────────────────────────────── lectura (DuckDB → filas crudas)

def caja(lat: float, lng: float, radio_km: float) -> tuple[float, float, float, float]:
    """`(oeste, sur, este, norte)` de la ciudad."""
    oeste, norte, este, sur = tarjetas.caja_de_la_ciudad(lat, lng, radio_km)
    return oeste, sur, este, norte


def leer_overture(lat: float, lng: float, radio_km: float, *, release: str = RELEASE,
                  confianza: float = CONFIANZA_MINIMA) -> list[dict]:
    """Los lugares crudos de Overture dentro de la caja de la ciudad. Lanza si S3 no contesta."""
    import duckdb

    if not _RE_RELEASE.match(release):
        raise ValueError(f"Release inválida: {release!r}")
    oeste, sur, este, norte = caja(lat, lng, radio_km)
    con = duckdb.connect()
    ext = os.environ.get("DUCKDB_EXT_DIR")
    if ext:
        con.execute(f"SET extension_directory='{ext}'")
    tmp = tempfile.gettempdir().replace("\\", "/").replace("'", "")
    con.execute(f"SET home_directory='{tmp}'; SET temp_directory='{tmp}/duckdb';"
                " SET memory_limit='1GB'; SET threads=2; SET enable_progress_bar=false;")
    try:
        con.execute("LOAD httpfs")
    except Exception:  # noqa: BLE001 — sin la extensión preinstalada (PC de desarrollo): se baja
        con.execute("INSTALL httpfs; LOAD httpfs")
    con.execute("SET s3_region='us-west-2'")
    origen = BUCKET.format(release=release)
    consulta = f"""
        select id, names.primary as nombre, basic_category as categoria, taxonomy.primary as taxonomia,
               confidence as confianza, (bbox.xmin + bbox.xmax) / 2 as lng, (bbox.ymin + bbox.ymax) / 2 as lat,
               phones, websites, socials, emails, addresses, operating_status,
               list_distinct(list_transform(sources, lambda s: s.dataset)) as fuentes,
               list_distinct(list_transform(sources, lambda s: s.license)) as licencias
        from read_parquet('{origen}', hive_partitioning = 1)
        where bbox.xmin between {oeste:.6f} and {este:.6f}
          and bbox.ymin between {sur:.6f} and {norte:.6f}
          and confidence >= {float(confianza):.3f}
    """
    cur = con.execute(consulta)
    columnas = [d[0] for d in cur.description]
    return [dict(zip(columnas, fila)) for fila in cur.fetchall()]


# ───────────────────────────────────────────────────────────── normalizar (puro)

def _primero(lista) -> str | None:
    for v in lista or []:
        if v and str(v).strip():
            return str(v).strip()
    return None


def _email(lista) -> str | None:
    v = _primero(lista)
    return v[:120] if v and re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v) else None


_REDES = {"facebook.com": "facebook_url", "fb.com": "facebook_url", "fb.me": "facebook_url",
          "instagram.com": "instagram_url", "tiktok.com": "tiktok_url"}


def _host(url: str) -> str:
    resto = re.sub(r"^[a-z][a-z0-9+.-]*://", "", str(url).strip().lower())
    host = re.split(r"[/?#:]", resto, maxsplit=1)[0]
    return host[4:] if host.startswith("www.") else host


def red_de(url: str | None) -> str | None:
    """'facebook_url' | 'instagram_url' | 'tiktok_url' si el enlace es de esa red, o None."""
    if not url:
        return None
    host = _host(url)
    for dominio, campo in _REDES.items():
        if host == dominio or host.endswith("." + dominio):
            return campo
    return None


def web_propia(url: str | None) -> str | None:
    """Un sitio web de verdad: dominio con extensión de letras (`dario.ugarte.54` no), que no sea una red social
    ni un mapa de Google. Saneado como cualquier enlace importado."""
    if not url or red_de(url):
        return None
    host = _host(url)
    partes = host.split(".")
    if len(partes) < 2 or not re.fullmatch(r"[a-z]{2,24}", partes[-1]) or "google." in host:
        return None
    return enlaces.sanear_red(str(url).strip(), "El sitio web")


def direccion_de(texto: str | None) -> str | None:
    """La dirección escrita, sin enlaces: a veces viene un link de Google Maps en lugar de la calle."""
    t = " ".join(str(texto or "").split())[:200]
    if not t or re.search(r"https?://|www\.|google\.", t, re.IGNORECASE):
        return None
    return t


def motivo_descarte(cruda: dict) -> str | None:
    """Por qué una fila no entra ('sin_nombre', 'cerrado', 'no_comercio'), o None si entra."""
    nombre = str(cruda.get("nombre") or "").strip()
    if len(nombre) < 2:
        return "sin_nombre"
    if str(cruda.get("operating_status") or "").lower() in CERRADOS:
        return "cerrado"
    if cruda.get("categoria") in NO_COMERCIO:
        return "no_comercio"
    if cruda.get("lat") is None or cruda.get("lng") is None:
        return "sin_punto"
    return None


def armar_fila(cruda: dict, *, ciudad_id: str, release: str, rubros_validos: Callable[[str], bool]) -> dict:
    """Una fila cruda de Overture → una fila de `comercios_importados` (nuevo, sin revisar)."""
    tels = [t for t in (normalizar_telefono(p) for p in (cruda.get("phones") or [])[:4]) if t]
    whatsapp, telefono = tarjetas.repartir_telefonos(tels)
    redes = [str(s) for s in (cruda.get("socials") or []) if s][:5]
    website = None
    por_red: dict[str, str] = {}
    for url in [*(cruda.get("websites") or []), *redes]:
        campo = red_de(url)
        if campo:
            limpio = enlaces.sanear_red(str(url).strip(), "La red")
            if limpio:
                por_red.setdefault(campo, limpio)
        elif not website:
            website = web_propia(url)
    direccion = None
    localidad = None
    for a in cruda.get("addresses") or []:
        if isinstance(a, dict):
            direccion = direccion or direccion_de(a.get("freeform"))
            localidad = localidad or a.get("locality")
    categoria = cruda.get("categoria")
    rubro = RUBRO.get(categoria or "")
    if rubro and not rubros_validos(rubro):
        rubro = None
    confianza = round(float(cruda.get("confianza") or 0), 2)
    fuentes = [str(f) for f in (cruda.get("fuentes") or []) if f]
    texto = "\n".join([
        f"Overture Maps · release {release} · confianza {confianza:.2f}",
        f"Categoría: {categoria or '-'}" + (f" ({cruda.get('taxonomia')})" if cruda.get("taxonomia") else ""),
        f"Datos de: {', '.join(fuentes) or '-'}",
        *(f"Red: {r}" for r in redes),
    ])[:MAX_TEXTO]
    return {
        "fuente": FUENTE, "fuente_id": f"{FUENTE}:{cruda['id']}", "ciudad_id": ciudad_id,
        "nombre": str(cruda["nombre"]).strip()[:200], "categoria": categoria, "rubro_slug": rubro,
        "lat": round(float(cruda["lat"]), 6), "lng": round(float(cruda["lng"]), 6),
        "telefono": telefono, "whatsapp": whatsapp, "website": website, "email": _email(cruda.get("emails")),
        "horario": None, "direccion": direccion,
        "tags": {"overture": {"id": cruda["id"], "release": release, "confianza": confianza,
                              "categoria": categoria, "taxonomia": cruda.get("taxonomia"), "redes": redes,
                              "redes_por_red": por_red,
                              "fuentes": fuentes, "licencias": [str(x) for x in (cruda.get("licencias") or [])],
                              "localidad": localidad}},
        "estado": "nuevo", "ubicacion": "aproximada",
        "foto_ref": None, "texto_leido": texto, "lector": None, "duplicado_de": None,
    }


def buscar_repetido(fila: dict, comercios: list[dict], indice_tel: dict, repo) -> dict | None:
    """El comercio de URUKU que ya es este: mismo teléfono, o nombre parecido a menos de METROS_REPETIDO."""
    tels = [t for t in (normalizar_telefono(x) for x in (fila.get("whatsapp"), fila.get("telefono")) if x) if t]
    por_tel = tarjetas.buscar_repetido(repo, tels, indice_tel) if tels else None
    if por_tel:
        return por_tel
    for c in comercios:
        if c.get("lat") is None or c.get("lng") is None:
            continue
        d = metros_entre(fila["lat"], fila["lng"], c["lat"], c["lng"])
        if d is not None and d <= METROS_REPETIDO and mismo_nombre(fila["nombre"], c.get("nombre")):
            return c
    return None


# ───────────────────────────────────────────────────────────── cargar

@dataclass
class Resumen:
    leidas: int = 0
    descartadas: Counter = field(default_factory=Counter)
    nuevas: int = 0
    ya_estaban: int = 0
    repetidas: int = 0
    con_whatsapp: int = 0
    con_telefono: int = 0
    con_web: int = 0
    con_redes: int = 0
    sin_rubro: int = 0
    por_rubro: Counter = field(default_factory=Counter)


def cargar(repo, crudas: list[dict], ciudad: dict, *, release: str = RELEASE, dry_run: bool = False,
           limite: int | None = None, mostrar: Callable[[str], None] = print) -> Resumen:
    r = Resumen(leidas=len(crudas))
    rubros: dict[str, bool] = {}

    def valido(slug: str) -> bool:
        if slug not in rubros:
            rubros[slug] = bool(repo.get_rubro_id(slug))
        return rubros[slug]

    comercios = repo.comercios_con_coords(ciudad["id"])
    indice_tel = tarjetas.indice_telefonos(repo)
    utiles = []
    for c in crudas:
        motivo = motivo_descarte(c)
        if motivo:
            r.descartadas[motivo] += 1
        else:
            utiles.append(c)
    utiles.sort(key=lambda c: -(c.get("confianza") or 0))       # con --limite, primero lo más confiable
    if limite is not None:
        utiles = utiles[: max(0, limite)]
    for c in utiles:
        fila = armar_fila(c, ciudad_id=ciudad["id"], release=release, rubros_validos=valido)
        if dry_run and repo.get_importado_por_fuente(FUENTE, fila["fuente_id"]):    # al guardar lo dice el INSERT
            r.ya_estaban += 1
            continue
        repetido = buscar_repetido(fila, comercios, indice_tel, repo)
        if repetido:
            fila["duplicado_de"] = repetido["id"]
        if not dry_run and repo.crear_importado(fila) is None:          # ya estaba (misma fuente_id)
            r.ya_estaban += 1
            continue
        r.nuevas += 1
        r.repetidas += 1 if repetido else 0
        r.con_whatsapp += 1 if fila["whatsapp"] else 0
        r.con_telefono += 1 if fila["telefono"] else 0
        r.con_web += 1 if fila["website"] else 0
        r.con_redes += 1 if fila["tags"]["overture"]["redes_por_red"] else 0
        r.sin_rubro += 0 if fila["rubro_slug"] else 1
        r.por_rubro[fila["rubro_slug"] or "(sin rubro)"] += 1
        if dry_run and r.nuevas <= 15:
            mostrar(f"  {fila['nombre'][:34]:34} | {str(fila['categoria'] or '-')[:26]:26} | "
                    f"{fila['rubro_slug'] or '-':16} | {c.get('confianza') or 0:.2f}"
                    + ("  (ya está en URUKU)" if repetido else ""))
    logger.info("importar_overture.cargado", ciudad=ciudad.get("slug"), nuevas=r.nuevas, ya_estaban=r.ya_estaban,
                repetidas=r.repetidas, guardado=not dry_run)
    return r


def _imprimir(r: Resumen, dry_run: bool, mostrar: Callable[[str], None]) -> None:
    mostrar(f"\nLeídos de Overture:      {r.leidas}")
    mostrar(f"Descartados:             {sum(r.descartadas.values())}  "
            + ", ".join(f"{k}: {v}" for k, v in r.descartadas.most_common()))
    mostrar(f"{'Entrarían' if dry_run else 'Nuevos en Importados'}:    {r.nuevas}")
    mostrar(f"Ya estaban:              {r.ya_estaban}")
    mostrar(f"Ya están en URUKU:       {r.repetidas}  (marcados como repetidos para revisar)")
    mostrar(f"Con WhatsApp:            {r.con_whatsapp}")
    mostrar(f"Con otro teléfono:       {r.con_telefono}")
    mostrar(f"Con sitio web:           {r.con_web}")
    mostrar(f"Con Facebook/Instagram/TikTok: {r.con_redes}")
    mostrar(f"Sin rubro (se elige en el panel): {r.sin_rubro}")
    mostrar("Por rubro: " + ", ".join(f"{k} {v}" for k, v in r.por_rubro.most_common(12)))
    if dry_run:
        mostrar("\nSimulación: no se guardó nada. Repetir sin --dry-run para cargarlos (nada se publica solo).")


def main(argv: list[str] | None = None, repo=None, *, leer: Callable[..., list[dict]] | None = None,
         mostrar: Callable[[str], None] = print) -> int:
    ap = argparse.ArgumentParser(prog="importar_overture",
                                 description="Trae negocios de Overture Maps a Importados (nada se publica solo).")
    ap.add_argument("--ciudad", required=True, help="slug de la ciudad (p. ej. tarija)")
    ap.add_argument("--dry-run", action="store_true", help="muestra lo que cargaría, sin guardar nada")
    ap.add_argument("--radio-km", type=float, default=None, help="radio desde el centro de la ciudad")
    ap.add_argument("--confianza", type=float, default=CONFIANZA_MINIMA, help="confidence mínima (0 a 1)")
    ap.add_argument("--release", default=RELEASE, help="release de Overture (AAAA-MM-DD.N)")
    ap.add_argument("--limite", type=int, default=None, help="cargar sólo los N más confiables")
    args = ap.parse_args(argv)
    if not 0 <= args.confianza <= 1:
        print("--confianza va de 0 a 1.", file=sys.stderr)
        return 2
    if not _RE_RELEASE.match(args.release):
        print("--release tiene la forma AAAA-MM-DD.N (p. ej. 2026-10-21.0).", file=sys.stderr)
        return 2
    if repo is None:
        from app.db.repository import get_repo
        repo = get_repo()
    ciudad = repo.get_ciudad(args.ciudad)
    if not ciudad:
        print(f"No existe la ciudad «{args.ciudad}».", file=sys.stderr)
        return 2
    if ciudad.get("lat") is None or ciudad.get("lng") is None:
        print(f"La ciudad «{args.ciudad}» no tiene centro (lat/lng).", file=sys.stderr)
        return 2
    radio = args.radio_km or RADIOS.get(args.ciudad, RADIO_KM)
    mostrar(f"Ciudad: {ciudad['nombre']} · radio {radio:g} km · confianza >= {args.confianza:g} · "
            f"release {args.release}{' · SIMULACIÓN' if args.dry_run else ''}")
    mostrar("Leyendo Overture (S3)… puede tardar uno o dos minutos.")
    try:
        crudas = (leer or leer_overture)(float(ciudad["lat"]), float(ciudad["lng"]), radio,
                                         release=args.release, confianza=args.confianza)
    except Exception as exc:  # noqa: BLE001
        print(f"No se pudo leer Overture: {type(exc).__name__}: {str(exc)[:300]}", file=sys.stderr)
        return 1
    r = cargar(repo, crudas, ciudad, release=args.release, dry_run=args.dry_run, limite=args.limite,
               mostrar=mostrar)
    _imprimir(r, args.dry_run, mostrar)
    return 0


if __name__ == "__main__":
    sys.exit(main())
