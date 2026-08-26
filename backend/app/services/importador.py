"""Traer comercios de OpenStreetMap (Overpass API) a la tabla de importados.

QUÉ ESPERAR DE ESTA FUENTE
==========================

Medido el 2026-08-26 sobre las cinco ciudades (19.861 negocios):

    ciudad        total   con nombre   teléfono   whatsapp   foto
    Bermejo          20           18          2          0      0
    Tarija          808          535         35          0      0
    Cochabamba    5.892        3.389        724        207      2
    La Paz        8.103        6.581        646          1     87
    Santa Cruz    5.038        4.697        387          4      2

O sea: **nombre, ubicación y categoría**. La foto es el 0,5% y el WhatsApp el
1%. No es una fuente de fichas completas, es una lista de qué existe y dónde —
que para salir a la calle vale, y para llenar el mapa no.

Bermejo es el caso que lo demuestra al revés: OSM tiene 20 registros (bancos y
gasolineras) contra los 270 que el equipo relevó a pie. Ahí no hay nada que
importar.

LICENCIA
========

OSM es ODbL: se puede usar y redistribuir **con atribución**. Google Places,
HERE y Mapbox prohíben almacenar sus datos y mostrarlos fuera de su mapa, en
cualquier plan — por eso este módulo habla sólo con Overpass.
"""
from __future__ import annotations

import structlog

logger = structlog.get_logger()

# Espejos: el principal devuelve "server too busy" seguido, y una importación
# que falla por eso parece un error de código.
_ESPEJOS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
_TIMEOUT = 300.0

# Amenities que son comercio de cara al comprador. El resto de `amenity`
# (escuelas, iglesias, cajeros) no va: llenaría el mapa de cosas que nadie
# busca para comprar.
_AMENITIES = "restaurant|cafe|pharmacy|bar|fast_food|marketplace|fuel|bank|ice_cream"

# OSM → taxonomía de URUKU. Lo que no está acá queda con rubro_slug NULL y se
# resuelve a mano en el panel: es preferible a inventarle un rubro, que es el
# error que ya costó limpiar `alimentos` y `hogar`.
_RUBRO: dict[str, str] = {
    # comida y bebida
    "bakery": "panaderia", "butcher": "alimentos", "greengrocer": "alimentos",
    "supermarket": "alimentos", "convenience": "alimentos", "grocery": "alimentos",
    "alcohol": "bebidas", "beverages": "bebidas", "wine": "bebidas",
    "confectionery": "kiosco", "kiosk": "kiosco", "pastry": "panaderia",
    "amenity:restaurant": "restaurantes", "amenity:fast_food": "comida-rapida",
    "amenity:cafe": "cafeteria", "amenity:ice_cream": "cafeteria",
    "amenity:bar": "restaurantes", "amenity:marketplace": "alimentos",
    "amenity:pharmacy": "farmacia", "amenity:bank": "cambio",
    # indumentaria
    "clothes": "ropa", "boutique": "ropa", "fashion": "ropa",
    "shoes": "calzado", "bag": "marroquineria", "leather": "marroquineria",
    "fabric": "blanqueria", "curtain": "blanqueria", "underwear": "lenceria",
    "second_hand": "ropa-americana", "charity": "ropa-americana",
    # casa
    "furniture": "muebles", "bed": "muebles", "houseware": "bazar",
    "kitchen": "bazar", "interior_decoration": "hogar", "florist": "floreria",
    "hardware": "ferreteria", "doityourself": "ferreteria", "paint": "ferreteria",
    "electrical": "ferreteria", "trade": "ferreteria",
    # tecnología
    "mobile_phone": "celulares", "computer": "computacion",
    "electronics": "electronica", "appliance": "electrodomesticos",
    # vehículos
    "car_parts": "repuestos-autos", "car_repair": "gomeria-servicio",
    "tyres": "neumaticos", "motorcycle": "motos", "bicycle": "bicicletas",
    "amenity:fuel": "repuestos-autos",
    # servicios y varios
    "hairdresser": "peluqueria", "beauty": "belleza", "cosmetics": "belleza",
    "perfumery": "belleza", "optician": "optica", "jewelry": "joyeria",
    "watches": "joyeria", "toys": "jugueteria", "stationery": "jugueteria",
    "books": "jugueteria", "sports": "deportes", "gift": "regaleria",
    "party": "regaleria", "baby_goods": "bebes", "pet": "mascotas",
    "laundry": "lavadero", "locksmith": "cerrajeria", "travel_agency": "envios",
}


def _consulta(lat: float, lng: float, radio_m: int) -> str:
    return (
        f"[out:json][timeout:240];("
        f'node(around:{radio_m},{lat},{lng})[shop];'
        f'way(around:{radio_m},{lat},{lng})[shop];'
        f'node(around:{radio_m},{lat},{lng})[amenity~"^({_AMENITIES})$"];'
        f");out tags center;"
    )


def traer_de_overpass(lat: float, lng: float, radio_m: int = 10000) -> list[dict]:
    """Los elementos crudos de Overpass. Lanza si ningún espejo responde."""
    import httpx

    q = _consulta(lat, lng, radio_m)
    ultimo = ""
    for url in _ESPEJOS:
        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                r = client.post(url, content=q.encode("utf-8"))
            if r.status_code == 200 and r.text.lstrip().startswith("{"):
                return r.json().get("elements", [])
            # Overpass contesta 200 con una página HTML cuando está saturado:
            # sin este chequeo, "servidor ocupado" se lee como "no hay datos".
            ultimo = f"{url}: HTTP {r.status_code}, respuesta no JSON"
        except Exception as exc:  # noqa: BLE001
            ultimo = f"{url}: {exc}"
        logger.warning("importador.espejo_fallo", detalle=ultimo)
    raise RuntimeError(f"Ningún espejo de Overpass respondió. Último: {ultimo}")


def _telefono(tags: dict) -> str | None:
    for k in ("contact:phone", "phone", "contact:mobile", "mobile"):
        if tags.get(k):
            return str(tags[k]).split(";")[0].strip()
    return None


def _whatsapp(tags: dict) -> str | None:
    for k in ("contact:whatsapp", "whatsapp"):
        if tags.get(k):
            return str(tags[k]).split(";")[0].strip()
    return None


def normalizar(el: dict) -> dict | None:
    """Un elemento de Overpass → una fila de comercios_importados.

    Devuelve None si no sirve: sin nombre no hay nada que mostrarle a nadie ni
    forma de reconocerlo en la calle, y sin coordenadas no va al mapa.
    """
    tags = el.get("tags") or {}
    nombre = (tags.get("name") or "").strip()
    if not nombre:
        return None

    lat = el.get("lat") or (el.get("center") or {}).get("lat")
    lng = el.get("lon") or (el.get("center") or {}).get("lon")
    if lat is None or lng is None:
        return None

    if tags.get("shop"):
        categoria = tags["shop"]
        clave = categoria
    else:
        categoria = f"amenity:{tags.get('amenity', '')}"
        clave = categoria

    calle = tags.get("addr:street")
    numero = tags.get("addr:housenumber")
    direccion = " ".join(x for x in (calle, numero) if x) or None

    return {
        "fuente": "osm",
        "fuente_id": f"{el.get('type')}/{el.get('id')}",
        "nombre": nombre,
        "categoria": categoria,
        "rubro_slug": _RUBRO.get(clave),
        "lat": float(lat),
        "lng": float(lng),
        "telefono": _telefono(tags),
        "whatsapp": _whatsapp(tags),
        "website": tags.get("website") or tags.get("contact:website"),
        "horario": tags.get("opening_hours"),
        "direccion": direccion,
        "tags": tags,
    }
