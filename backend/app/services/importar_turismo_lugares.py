"""Importar los LUGARES PARA VISITAR de la página de turismo de una ciudad a Importados (docs/lugares-turismo.md).

QUÉ HACE
========
Segunda parte de `importar_turismo` (que trae los negocios con teléfono): acá van los lugares que NO son comercios.
Plazas, parques y miradores; museos y bibliotecas; iglesias y patrimonio dentro de la ciudad; centros culturales;
excursiones fuera de la ciudad y del municipio; y las áreas protegidas. Cada uno queda como una fila de
`comercios_importados` con `fuente = 'turismo'` y `rubro_slug = 'para-visitar'` (rubro NO comercial, migración
0196). Nada llega al sitio hasta que una persona la revisa y toca «Promover» en Admin › Importados.

SÓLO DATOS Y EL ENLACE: se toman nombre, dirección, teléfono y horario (los bloques con rótulo de la ficha) y el
enlace a la ficha (`fuente_url`). La reseña, la presentación, la información, el precio de entrada y las fotos tienen
autor y NO se traen: el lector descarta todo bloque cuyo rótulo no sea uno de los tres, y ninguna imagen se
descarga. `website` queda vacío (la página de turismo no es la web del lugar).

CÓMO SE USA (una vez, a mano, dentro del contenedor del backend)
================================================================
    docker exec buscadonde-backend python -m app.services.importar_turismo_lugares --ciudad tarija --dry-run
    docker exec buscadonde-backend python -m app.services.importar_turismo_lugares --ciudad tarija
    ... --limite 20        # sólo los primeros 20 lugares (para probar)

`--dry-run` lee el sitio y lista lo que cargaría; no escribe nada ni consulta Nominatim. La corrida real hace como
máximo ~130 consultas a Nominatim (1 por segundo, con caché).

CÓMO LEE EL SITIO (plan A y plan B)
===================================
  A. La API REST pública de WordPress (`/wp-json/wp/v2/...`): 1 pedido para las categorías y 6 para los posts
     (`per_page=100`). Los rótulos son los mismos que en la ficha.
  B. Si la API no sirve (la cierran, cambia de forma): se lee el listado «Qué hacer» y cada una de las 62 fichas en
     HTML. Mismo lector de bloques.
  Las 3 áreas protegidas no tienen ficha: sus nombres van fijos en este módulo, con la URL de su página.
BUENA EDUCACIÓN: robots.txt lo permite; un pedido por segundo y User-Agent propio (`URUKU/1.0 (+https://uruku.bo)`).

UBICACIÓN: no hay coordenadas en la página. El único par de números que trae el HTML (-21.534641, -64.734265) es el
enlace del pie a la oficina de turismo y se repite en TODAS las páginas: nunca se usa (ni se acepta como resultado).
Se busca en Nominatim primero por NOMBRE y después por dirección, en una caja de 15 km para los lugares de la ciudad y
de 120 km para los de afuera. Siempre queda `aproximada`; si no aparece, `no_encontrada` y el punto se pone a mano.
Nunca se usa Google (0066).

IDEMPOTENTE: `fuente_id = 'turismo:<host>:post:<id de WordPress>'` (áreas: `…:area:<slug>`). Con `(fuente, fuente_id)`
ya existente la fila no se toca: ni el estado ni lo que una persona corrigió.
"""
from __future__ import annotations

import argparse
import html
import json
import math
import re
import sys
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import urlparse

import structlog

from app.core.telefonos_foto import numero_visible
from app.services import importar_turismo, tarjetas

logger = structlog.get_logger()

FUENTE = importar_turismo.FUENTE            # 'turismo': la misma sala de espera que los negocios
RUBRO = "para-visitar"
USER_AGENT = tarjetas.USER_AGENT
INTERVALO_PEDIDOS = importar_turismo.INTERVALO_PEDIDOS
FALLAS_NOMINATIM_SEGUIDAS = importar_turismo.FALLAS_NOMINATIM_SEGUIDAS
RADIO_CIUDAD_KM = tarjetas.RADIO_CIUDAD_KM  # 15
RADIO_LEJOS_KM = 120
DISTANCIA_REPETIDO_M = 200

#: La lista fija del tipo de lugar (`subcategoria`). La usa también el PATCH de Importados.
SUBCATEGORIAS = ("Plaza", "Parque", "Mirador", "Museo", "Biblioteca o archivo", "Iglesia", "Patrimonio",
                 "Centro cultural", "Excursión", "Área protegida")

#: Categoría del sitio (slug de WordPress) → radio de la caja de búsqueda en km.
CATEGORIAS: dict[str, int] = {
    "plazas-parques-y-miradores": RADIO_CIUDAD_KM,
    "museos-y-bibliotecas": RADIO_CIUDAD_KM,
    "dentro-de-la-ciudad": RADIO_CIUDAD_KM,
    "centros-culturales": RADIO_CIUDAD_KM,
    "fuera-de-la-ciudad": RADIO_LEJOS_KM,
    "fuera-del-municipio": RADIO_LEJOS_KM,
}
CATEGORIA_AREAS = "areas-protegidas"
CATEGORIA_PADRE = "que-hacer"                # todos los posts de lugar también la llevan

#: Un sitio por ciudad (cada uno arma su HTML distinto). Las áreas protegidas no tienen ficha propia: nombre fijo y
#: la URL de la página donde las muestra el sitio (medido el 12/11/2026; El Cardón figura sólo como «potencial»).
SITIOS: dict[str, dict] = {
    "tarija": {
        "base": "https://tarijaturismo.com",
        "listado": "/que-hacer/",
        "pagina_areas": "/areas-protegidas/",
        "areas": (
            ("sama", "Reserva Biológica de la Cordillera de Sama"),
            ("tariquia", "Reserva Nacional de Flora y Fauna Tariquía"),
            ("aguarague", "Parque Nacional Aguaragüe"),
        ),
    },
}

#: El par de números del enlace del pie (oficina de turismo): jamás es el punto de un lugar. Tolerancia ~2 m.
PUNTO_DEL_PIE = (-21.534641, -64.734265)
_TOLERANCIA_PIE = 0.00002

MAX_HORARIO = 300
MAX_URL = 300
TIMEOUT_JSON = 20
_CAMPOS_API = "id,slug,link,title,categories,content"


# ───────────────────────────────────────────────────────────── el modelo

@dataclass
class Lugar:
    """Un lugar tal como lo muestra el sitio: sólo los datos que se toman. Nada de reseñas ni fotos."""
    nombre: str
    categoria: str                       # slug de la categoría del sitio (o `areas-protegidas`)
    subcategoria: str                    # de la lista fija (`SUBCATEGORIAS`)
    direccion: str | None
    telefonos: list[str]                 # el texto crudo de cada bloque «Teléfono»
    horario: str | None
    url: str | None                      # el enlace a la ficha (o a la página de áreas)
    radio_km: int
    wp_id: int | None = None             # el id del post en WordPress (None en las áreas)
    area: str | None = None              # el slug fijo de un área protegida
    categorias: list[str] = field(default_factory=list)   # todas las categorías del post (slugs)


_ESPACIOS = re.compile(r"[\s​﻿]+")


def _limpio(texto: str | None) -> str:
    return _ESPACIOS.sub(" ", texto or "").strip()


def _plano(texto: str | None) -> str:
    """Minúsculas y sin tildes (para comparar rótulos y primeras palabras)."""
    return "".join(c for c in unicodedata.normalize("NFD", (texto or "").lower()) if unicodedata.category(c) != "Mn")


def subcategoria_de(categoria: str, nombre: str) -> str:
    """El tipo de lugar según la categoría del sitio y la primera palabra del nombre."""
    primera = (_plano(nombre).split() or [""])[0]
    if categoria == "plazas-parques-y-miradores":
        if primera in ("plaza", "plazuela"):
            return "Plaza"
        if primera == "parque":
            return "Parque"
        if primera == "mirador":
            return "Mirador"
        return "Plaza"                    # lo que no dice qué es, en esta categoría, es un espacio público
    if categoria == "museos-y-bibliotecas":
        return "Museo" if primera == "museo" else "Biblioteca o archivo"
    if categoria == "dentro-de-la-ciudad":
        return "Iglesia" if primera in ("iglesia", "capilla", "catedral") else "Patrimonio"
    if categoria == "centros-culturales":
        return "Centro cultural"
    if categoria in ("fuera-de-la-ciudad", "fuera-del-municipio"):
        return "Excursión"
    return "Área protegida"


# ───────────────────────────────────────────────────────────── el lector de bloques (puro, sin red)

_RE_RESTOS_HTML = re.compile(r"<[^>]+>")


class _LectorBloques(HTMLParser):
    """Junta los bloques con rótulo de una ficha: `<div class="box-body"><h3 class="elementskit-info-box-title">
    Dirección</h3><p>…</p></div>`. Devuelve `(rótulo, valor)` sólo de los rótulos que se toman (Dirección,
    Teléfono, Horario): el valor de cualquier otro bloque (Reseña, Presentación, Información, Entrada…) se descarta
    sin guardarlo."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.bloques: list[tuple[str, str]] = []
        self._prof = 0                       # profundidad de divs dentro de `box-body` (0 = afuera)
        self._modo: str | None = None        # 'rotulo' | 'valor'
        self._rotulo: str | None = None
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        clases = (dict(attrs).get("class") or "").split()
        if not self._prof:
            if tag == "div" and "box-body" in clases:
                self._prof, self._modo, self._rotulo, self._buf = 1, None, None, []
            return
        if tag == "div":
            self._prof += 1
        elif tag == "h3" and "elementskit-info-box-title" in clases:
            self._modo, self._buf = "rotulo", []
        elif tag in ("br", "p", "li") and self._modo == "valor":
            self._buf.append(" ")

    def handle_endtag(self, tag):
        if not self._prof:
            return
        if tag == "h3" and self._modo == "rotulo":
            self._rotulo = _limpio("".join(self._buf))
            self._modo, self._buf = "valor", []
        elif tag == "div":
            self._prof -= 1
            if self._prof == 0:
                if self._rotulo and _tipo_de_rotulo(self._rotulo):
                    self.bloques.append((self._rotulo, _limpio("".join(self._buf))))
                self._modo, self._rotulo, self._buf = None, None, []

    def handle_data(self, data):
        if self._modo in ("rotulo", "valor"):
            self._buf.append(data)


def _tipo_de_rotulo(rotulo: str) -> str | None:
    """`direccion` | `telefono` | `horario` | None. Se acepta la errata «Horaios» que trae el sitio."""
    r = _plano(rotulo)
    if r.startswith("direccion"):
        return "direccion"
    if r.startswith("telefono"):
        return "telefono"
    if r.startswith("hora"):
        return "horario"
    return None


def leer_bloques(contenido_html: str) -> dict:
    """`{direccion, telefonos, horario}` de un contenido HTML (el `content.rendered` de la API o la ficha). Puro."""
    lector = _LectorBloques()
    lector.feed(contenido_html or "")
    lector.close()
    datos: dict = {"direccion": None, "telefonos": [], "horario": None}
    for rotulo, valor in lector.bloques:
        if not valor:
            continue
        tipo = _tipo_de_rotulo(rotulo)
        if tipo == "telefono":
            datos["telefonos"].append(valor)
        elif tipo == "direccion" and datos["direccion"] is None:
            datos["direccion"] = valor[: tarjetas.MAX_DIRECCION]
        elif tipo == "horario" and datos["horario"] is None:
            datos["horario"] = valor[:MAX_HORARIO]
    return datos


def _titulo_limpio(titulo: str | None) -> str:
    return _limpio(html.unescape(_RE_RESTOS_HTML.sub(" ", titulo or "")))[: tarjetas.MAX_NOMBRE]


def _url_del_sitio(url: str | None, base: str) -> str | None:
    """El enlace si es https y del mismo sitio; si no, None (un dato del sitio es una entrada externa)."""
    valor = (url or "").strip()[:MAX_URL]
    p = urlparse(valor)
    if p.scheme == "https" and p.hostname and p.hostname.lower() == (urlparse(base).hostname or "").lower():
        return valor
    return None


# ───────────────────────────────────────────────────────────── plan A: la API de WordPress

def _json(texto: str, que: str):
    try:
        return json.loads(texto)
    except ValueError:
        raise RuntimeError(f"La API de WordPress no contestó un JSON válido ({que})") from None


def lugares_de_posts(posts: list, categoria: str, sitio: dict, slug_de_id: dict[int, str]) -> list[Lugar]:
    """Los lugares de la respuesta de `/wp/v2/posts?categories=<id>` (puro). Un post sin id entero o sin título se
    saltea. Sólo se leen los bloques con rótulo del contenido: el resto no se guarda."""
    out: list[Lugar] = []
    radio = CATEGORIAS[categoria]
    for p in posts:
        if not isinstance(p, dict) or not isinstance(p.get("id"), int) or isinstance(p.get("id"), bool):
            continue
        titulo = p.get("title")
        nombre = _titulo_limpio(titulo.get("rendered") if isinstance(titulo, dict) else None)
        if not nombre:
            continue
        contenido = p.get("content")
        datos = leer_bloques(contenido.get("rendered") if isinstance(contenido, dict) else "")
        cats = [slug_de_id[c] for c in (p.get("categories") or []) if isinstance(c, int) and c in slug_de_id]
        out.append(Lugar(nombre=nombre, categoria=categoria, subcategoria=subcategoria_de(categoria, nombre),
                         direccion=datos["direccion"], telefonos=datos["telefonos"], horario=datos["horario"],
                         url=_url_del_sitio(p.get("link"), sitio["base"]), radio_km=radio, wp_id=p["id"],
                         categorias=cats))
    return out


def leer_por_api(sitio: dict, pedir: Callable[[str], str]) -> list[Lugar]:
    """Plan A: 1 pedido de categorías y 1 por categoría de lugar. `pedir(url)` devuelve el texto (y espera el
    intervalo entre pedidos). Lanza `RuntimeError` si la API no sirve."""
    base = sitio["base"].rstrip("/")
    slugs = [*CATEGORIAS, CATEGORIA_PADRE]
    cats = _json(pedir(f"{base}/wp-json/wp/v2/categories?per_page=100&slug={','.join(slugs)}&_fields=id,slug"),
                 "categorías")
    if not isinstance(cats, list):
        raise RuntimeError("La API de WordPress no devolvió la lista de categorías")
    id_de = {c["slug"]: c["id"] for c in cats if isinstance(c, dict) and c.get("slug") in slugs
             and isinstance(c.get("id"), int)}
    faltan = [s for s in CATEGORIAS if s not in id_de]
    if faltan:
        raise RuntimeError(f"La API no tiene las categorías: {', '.join(faltan)}")
    slug_de_id = {v: k for k, v in id_de.items()}
    lugares: list[Lugar] = []
    for slug in CATEGORIAS:
        posts = _json(pedir(f"{base}/wp-json/wp/v2/posts?categories={id_de[slug]}&per_page=100"
                            f"&_fields={_CAMPOS_API}"), slug)
        if not isinstance(posts, list):
            raise RuntimeError(f"La API no devolvió la lista de posts de {slug}")
        if len(posts) >= 100:
            logger.warning("importar_turismo_lugares.pagina_llena", categoria=slug)
        lugares += lugares_de_posts(posts, slug, sitio, slug_de_id)
        logger.info("importar_turismo_lugares.categoria_leida", categoria=slug, lugares=len(posts))
    return lugares


# ───────────────────────────────────────────────────────────── plan B: el listado y las fichas en HTML

_RE_POST_ID = re.compile(r'data-elementor-type="wp-post"\s+data-elementor-id="(\d+)"')


def _recorte_de_ficha(pagina: str) -> str:
    """Sólo el contenido del post: desde `data-elementor-type="wp-post"` hasta el pie. El encabezado y el pie del
    sitio traen sus propios bloques (la oficina de turismo) y no son del lugar."""
    i = pagina.find('data-elementor-type="wp-post"')
    if i < 0:
        return ""
    j = pagina.find('data-elementor-type="footer"', i)
    return pagina[i:j] if j > i else pagina[i:]


def leer_por_html(sitio: dict, pedir: Callable[[str], str]) -> list[Lugar]:
    """Plan B: el listado «Qué hacer» da el nombre, la categoría y el enlace de cada ficha; cada ficha se lee con el
    mismo lector de bloques. Una ficha sin id de post (cambió el HTML) se saltea con un aviso."""
    base = sitio["base"].rstrip("/")
    url_listado = base + sitio["listado"]
    entradas = importar_turismo.leer_pagina(pedir(url_listado), url_listado)
    lugares: list[Lugar] = []
    for e in entradas:
        categoria = next((c for c in e.categorias if c in CATEGORIAS), None)
        enlace = _url_del_sitio(e.detalle, base)
        if not categoria or not enlace:
            continue
        pagina = pedir(enlace)
        m = _RE_POST_ID.search(pagina)
        if not m:
            logger.warning("importar_turismo_lugares.ficha_sin_id", categoria=categoria)
            continue
        datos = leer_bloques(_recorte_de_ficha(pagina))
        nombre = _titulo_limpio(e.nombre)
        lugares.append(Lugar(nombre=nombre, categoria=categoria, subcategoria=subcategoria_de(categoria, nombre),
                             direccion=datos["direccion"], telefonos=datos["telefonos"], horario=datos["horario"],
                             url=enlace, radio_km=CATEGORIAS[categoria], wp_id=int(m.group(1)),
                             categorias=list(e.categorias)))
    return lugares


def lugares_de_areas(sitio: dict) -> list[Lugar]:
    """Las áreas protegidas: nombres fijos (la página no las estructura) y la URL de su página."""
    url = sitio["base"].rstrip("/") + sitio["pagina_areas"]
    return [Lugar(nombre=nombre, categoria=CATEGORIA_AREAS, subcategoria="Área protegida", direccion=None,
                  telefonos=[], horario=None, url=url, radio_km=RADIO_LEJOS_KM, area=slug,
                  categorias=[CATEGORIA_AREAS])
            for slug, nombre in sitio["areas"]]


def sin_repetir(lugares: list[Lugar]) -> list[Lugar]:
    """Un post que está en dos categorías de lugar cuenta una sola vez (la primera que lo trajo)."""
    vistos: set[str] = set()
    out = []
    for l in lugares:
        fid = _clave(l)
        if fid not in vistos:
            vistos.add(fid)
            out.append(l)
    return out


# ───────────────────────────────────────────────────────────── red

def descargar(url: str) -> str:
    """El texto de una URL del sitio (la misma descarga educada que `importar_turismo`: User-Agent propio, sólo
    https, tope de tamaño). `RuntimeError` en español si no se pudo."""
    return importar_turismo.descargar_pagina(url)


def _con_ritmo(descargar_: Callable[[str], str], dormir: Callable[[float], None]) -> Callable[[str], str]:
    """Un pedido por segundo: espera antes de cada pedido salvo el primero."""
    estado = {"n": 0}

    def pedir(url: str) -> str:
        if estado["n"]:
            dormir(INTERVALO_PEDIDOS)
        estado["n"] += 1
        return descargar_(url)

    return pedir


def leer_sitio(sitio: dict, *, descargar_: Callable[[str], str] | None = None,
               dormir: Callable[[float], None] = time.sleep) -> list[Lugar]:
    """Plan A (API) y, si no sirve, plan B (HTML). Siempre suma las áreas protegidas. Sin repetir."""
    pedir = _con_ritmo(descargar_ or descargar, dormir)
    try:
        lugares = leer_por_api(sitio, pedir)
        if not lugares:
            raise RuntimeError("La API no devolvió ningún lugar")
    except RuntimeError as exc:
        logger.warning("importar_turismo_lugares.api_no_sirve_va_el_plan_b", motivo=str(exc)[:200])
        lugares = leer_por_html(sitio, pedir)
    return sin_repetir(lugares + lugares_de_areas(sitio))


# ───────────────────────────────────────────────────────────── los datos de una fila

def _clave(l: Lugar) -> str:
    return f"area:{l.area}" if l.area else f"post:{l.wp_id}"


def fuente_id_de(l: Lugar, base: str) -> str:
    """`turismo:<host>:post:<id>` (áreas: `…:area:<slug>`): el mismo lugar es siempre la misma clave."""
    host = (urlparse(base).hostname or "sitio").lower()
    return f"{FUENTE}:{host}:{_clave(l)}"


def telefono_de(l: Lugar) -> str | None:
    """Los teléfonos normalizados como en tarjetas, sin repetir, TODOS a `telefono` (nunca a `whatsapp`: es el número
    que la Alcaldía publica para llamar; pasarlo a WhatsApp lo decide una persona)."""
    e = importar_turismo.Entrada(nombre=l.nombre, direccion=None, telefonos=l.telefonos, enlace=None,
                                 subcategoria=None, seccion="", url="")
    return " / ".join(numero_visible(t.numero) for t in importar_turismo.telefonos_de(e))[:80] or None


def es_punto_del_pie(lat: float | None, lng: float | None) -> bool:
    return (lat is not None and lng is not None
            and abs(lat - PUNTO_DEL_PIE[0]) <= _TOLERANCIA_PIE and abs(lng - PUNTO_DEL_PIE[1]) <= _TOLERANCIA_PIE)


def _texto_para_el_revisor(l: Lugar) -> str:
    lineas = [f"Lugar para visitar · {l.subcategoria}", f"Origen: {l.url or '-'}", "--"]
    if l.direccion:
        lineas.append(f"Dirección: {l.direccion}")
    lineas += [f"Teléfono: {t}" for t in l.telefonos]
    if l.horario:
        lineas.append(f"Horario: {l.horario}")
    return "\n".join(lineas)[: tarjetas.MAX_TEXTO_LEIDO]


def armar_fila(l: Lugar, *, base: str, ciudad_id: str, punto: dict | None, repetido: dict | None) -> dict:
    """La fila de `comercios_importados` de un lugar (nuevo, sin revisar). Sin reseña, foto ni contenido del post
    en `tags`; `website` vacío; `whatsapp` vacío. Un punto que sea el del pie del sitio se descarta."""
    if punto and es_punto_del_pie(punto.get("lat"), punto.get("lng")):
        punto = None
    return {
        "fuente": FUENTE, "fuente_id": fuente_id_de(l, base), "ciudad_id": ciudad_id,
        "nombre": l.nombre, "categoria": l.categoria, "rubro_slug": RUBRO, "subcategoria": l.subcategoria,
        "lat": punto["lat"] if punto else None, "lng": punto["lng"] if punto else None,
        "telefono": telefono_de(l), "whatsapp": None, "website": None, "email": None,
        "direccion": l.direccion, "horario": l.horario, "fuente_url": l.url,
        "tags": {"wp_id": l.wp_id, "categorias": l.categorias},
        "estado": "nuevo", "ubicacion": "aproximada" if punto else "no_encontrada",
        "foto_ref": None, "texto_leido": _texto_para_el_revisor(l), "lector": None,
        "duplicado_de": repetido["id"] if repetido else None,
    }


# ───────────────────────────────────────────────────────────── ubicación y repetidos

def ubicar(l: Lugar, ciudad: dict, *, pedir: Callable[[dict], list] | None = None) -> dict | None:
    """El punto aproximado del lugar: primero por NOMBRE y, si no aparece, por dirección. Caja de `l.radio_km`
    alrededor del centro de la ciudad. Como mucho 2 consultas. `UbicacionNoDisponible` si el mapa no contesta."""
    for consulta in (l.nombre, l.direccion):
        if not consulta or len(consulta.strip()) < 4:
            continue
        punto = tarjetas.buscar_direccion(consulta, ciudad, pedir=pedir, radio_km=l.radio_km)
        if punto and not es_punto_del_pie(punto["lat"], punto["lng"]):
            return punto
    return None


def distancia_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Metros entre dos puntos (haversine)."""
    f1, f2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((f2 - f1) / 2) ** 2
         + math.cos(f1) * math.cos(f2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2)
    return 2 * 6371000 * math.asin(math.sqrt(a))


def _numero(v) -> float | None:
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def indice_comercios(repo, ciudad_id: str) -> list[dict]:
    """`[{id, nombre, lat, lng}]` de los comercios ACTIVOS de la ciudad (una vez por corrida)."""
    return [{"id": c["id"], "nombre": c.get("nombre"), "lat": _numero(c.get("lat")), "lng": _numero(c.get("lng"))}
            for c in repo.list_comercios_de_ciudad(ciudad_id) if c.get("nombre")]


def buscar_repetido(nombre: str, punto: dict | None, comercios: list[dict]) -> dict | None:
    """Un comercio activo de la ciudad con nombre parecido y, si el lugar tiene punto (y el comercio también), a
    200 m o menos. Es una MARCA para el revisor, no una decisión."""
    for c in comercios:
        if not importar_turismo.mismo_nombre(nombre, c["nombre"]):
            continue
        if punto and c["lat"] is not None and c["lng"] is not None \
                and distancia_m(punto["lat"], punto["lng"], c["lat"], c["lng"]) > DISTANCIA_REPETIDO_M:
            continue
        return {"id": c["id"], "nombre": c["nombre"]}
    return None


# ───────────────────────────────────────────────────────────── cargar

@dataclass
class Resumen:
    leidos: int = 0
    nuevos: int = 0
    ya_existentes: int = 0
    aproximadas: int = 0
    no_encontradas: int = 0
    repetidos: int = 0
    por_categoria: Counter = field(default_factory=Counter)
    por_subcategoria: Counter = field(default_factory=Counter)


def cargar(repo, lugares: list[Lugar], ciudad: dict, base: str, *, dry_run: bool = False,
           limite: int | None = None, pedir: Callable[[dict], list] | None = None,
           mostrar: Callable[[str], None] = print) -> Resumen:
    """Deja los lugares en `comercios_importados`. Con `dry_run` NO escribe ni consulta Nominatim: sólo lee la base
    (existentes y repetidos) y muestra lo que cargaría."""
    r = Resumen(leidos=len(lugares))
    for l in lugares:
        r.por_categoria[l.categoria] += 1
        r.por_subcategoria[l.subcategoria] += 1
    elegidos = lugares if limite is None else lugares[: max(0, limite)]
    comercios = indice_comercios(repo, ciudad["id"])
    ubicando = not dry_run
    fallas = 0
    for l in elegidos:
        fid = fuente_id_de(l, base)
        if repo.get_importado_por_fuente(FUENTE, fid):        # idempotente: no se toca (ni estado ni correcciones)
            r.ya_existentes += 1
            continue
        punto = None
        if ubicando:
            try:
                punto = ubicar(l, ciudad, pedir=pedir)
                fallas = 0
            except tarjetas.UbicacionNoDisponible:
                fallas += 1
                if fallas >= FALLAS_NOMINATIM_SEGUIDAS:
                    ubicando = False
                    logger.warning("importar_turismo_lugares.sin_mapas_se_deja_de_ubicar", fallas=fallas)
        repetido = buscar_repetido(l.nombre, punto, comercios)
        fila = armar_fila(l, base=base, ciudad_id=ciudad["id"], punto=punto, repetido=repetido)
        if dry_run:
            r.nuevos += 1
            r.repetidos += 1 if repetido else 0
            mostrar(_linea_dry_run(l, fila, repetido))
            continue
        if repo.crear_importado(fila) is None:                 # otra corrida simultánea ganó
            r.ya_existentes += 1
            continue
        r.nuevos += 1
        r.aproximadas += 1 if punto else 0
        r.no_encontradas += 0 if punto else 1
        r.repetidos += 1 if repetido else 0
        logger.info("importar_turismo_lugares.cargado", categoria=l.categoria, subcategoria=l.subcategoria,
                    con_punto=bool(punto), repetido=bool(repetido))
    return r


def _linea_dry_run(l: Lugar, fila: dict, repetido: dict | None) -> str:
    marca = f"  [repetido de «{repetido['nombre']}»]" if repetido else ""
    return (f"  {l.categoria[:26]:26} {l.subcategoria[:20]:20} {l.nombre[:38]:38} | "
            f"{(l.direccion or '-')[:40]:40} | {fila['telefono'] or '-'}{marca}")


# ───────────────────────────────────────────────────────────── línea de comandos

def _imprimir_resumen(r: Resumen, dry_run: bool) -> None:
    print("\nPor categoría del sitio:")
    for cat, n in r.por_categoria.items():
        print(f"  {cat:28} {n:4}")
    print("\nPor tipo de lugar (subcategoría):")
    for sub in SUBCATEGORIAS:
        if r.por_subcategoria[sub]:
            print(f"  {sub:28} {r.por_subcategoria[sub]:4}")
    print(f"\nLeídos:                 {r.leidos}")
    if dry_run:
        print(f"Cargaría (nuevos):      {r.nuevos}")
        print(f"Ya existentes:          {r.ya_existentes}")
        print(f"Marcados como repetidos: {r.repetidos}")
        print("\nSimulación: no se escribió nada ni se consultó el mapa. Repetir sin --dry-run para cargarlos.")
        return
    print(f"Nuevos:                 {r.nuevos}")
    print(f"Ya existentes:          {r.ya_existentes}")
    print(f"Aproximadas (con punto): {r.aproximadas}")
    print(f"No encontradas (sin punto, se marcan a mano): {r.no_encontradas}")
    print(f"Marcados como repetidos: {r.repetidos}")


def main(argv: list[str] | None = None, repo=None, *, descargar_: Callable[[str], str] | None = None,
         pedir: Callable[[dict], list] | None = None, dormir: Callable[[float], None] = time.sleep) -> int:
    ap = argparse.ArgumentParser(prog="importar_turismo_lugares", description="Importa los lugares para visitar de "
                                 "la página de turismo de una ciudad a Importados (rubro para-visitar).")
    ap.add_argument("--ciudad", required=True, help=f"slug de la ciudad ({', '.join(SITIOS)})")
    ap.add_argument("--dry-run", action="store_true", help="muestra lo que cargaría, sin escribir ni consultar el mapa")
    ap.add_argument("--limite", type=int, default=None, help="cargar sólo los primeros N lugares")
    args = ap.parse_args(argv)

    sitio = SITIOS.get(args.ciudad)
    if not sitio:
        print(f"No hay un lector de lugares para «{args.ciudad}». Hay: {', '.join(SITIOS)}.", file=sys.stderr)
        return 2
    if args.limite is not None and args.limite < 1:
        print("--limite tiene que ser 1 o más.", file=sys.stderr)
        return 2
    if repo is None:
        from app.db.repository import get_repo
        repo = get_repo()
    ciudad = repo.get_ciudad(args.ciudad)
    if not ciudad:
        print(f"No existe la ciudad «{args.ciudad}».", file=sys.stderr)
        return 2
    if not args.dry_run:
        if not repo.get_rubro_id(RUBRO):
            print(f"Falta el rubro «{RUBRO}»: aplicá la migración 0196 antes de cargar.", file=sys.stderr)
            return 2
        if _numero(ciudad.get("lat")) is None or _numero(ciudad.get("lng")) is None:
            print("La ciudad no tiene centro (lat/lng): sin él la búsqueda en el mapa no queda acotada a la caja "
                  "de 15 o 120 km.", file=sys.stderr)
            return 2

    print(f"Ciudad: {ciudad['nombre']} · sitio: {sitio['base']} · un pedido por segundo"
          f"{' · SIMULACIÓN' if args.dry_run else ''}")
    try:
        lugares = leer_sitio(sitio, descargar_=descargar_, dormir=dormir)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    resumen = cargar(repo, lugares, ciudad, sitio["base"], dry_run=args.dry_run, limite=args.limite, pedir=pedir)
    _imprimir_resumen(resumen, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
