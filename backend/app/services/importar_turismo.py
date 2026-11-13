"""Importar los negocios de la página de turismo de una ciudad a Importados (docs/importar-turismo.md).

QUÉ HACE
========
Lee las páginas de un sitio de turismo municipal (hoy: https://tarijaturismo.com, de la Alcaldía de Tarija) y deja
cada negocio como una fila de `comercios_importados` con `fuente = 'turismo'`. Nada llega al sitio hasta que una
persona la revisa y toca «Promover» (misma ficha de revisión que las tarjetas, `docs/carga-tarjetas.md`).

SÓLO DATOS, NUNCA FOTOS NI TEXTOS: se copian nombre, dirección, teléfonos y el enlace (web o Facebook). Las fotos y
las descripciones de la página tienen autor y no se traen; ninguna imagen se descarga.

CÓMO SE USA (una vez, a mano, dentro del contenedor del backend)
================================================================
    docker exec buscadonde-backend python -m app.services.importar_turismo --ciudad tarija --dry-run
    docker exec buscadonde-backend python -m app.services.importar_turismo --ciudad tarija
    ... --limite 20        # sólo los primeros 20 negocios útiles (para probar)

`--dry-run` lee las páginas y muestra lo que cargaría; no escribe nada ni consulta Nominatim.

BUENA EDUCACIÓN CON EL SITIO: robots.txt lo permite; un pedido por segundo, User-Agent propio (`URUKU/1.0
(+https://uruku.bo)`), 7 páginas en total. El sitio emite un `<link rel="next">` a `/page/2/`, pero esa página repite
el mismo listado (medido el 12/11/2026): NO se sigue.

CADA SITIO ES UN LECTOR APARTE: el HTML de cada municipio es distinto. Éste lee Elementor/WordPress de tarijaturismo
en tres formas: las fichas completas (Dónde dormir / comer, operadoras, agencias: nombre, dirección, `Telefono:`,
enlace), las tarjetas con extracto (Qué hacer: el extracto trae «Dirección … Teléfono …», cortado a ~12 palabras) y
las tablas (Cómo moverse: radio móviles y transporte hacia los alrededores; Guías de turismo autorizados).

IDEMPOTENTE: `fuente_id = 'turismo:<host>:<slug nombre>|<slug dirección>'`. Correrlo dos veces no duplica; una
sucursal (otra dirección del mismo negocio) es otra fila.
"""
from __future__ import annotations

import argparse
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

from app.core.telefonos_foto import Telefono, extraer
from app.core.text import slugify
from app.services import enlaces, tarjetas

logger = structlog.get_logger()

FUENTE = "turismo"
USER_AGENT = tarjetas.USER_AGENT
INTERVALO_PEDIDOS = 1.0            # un pedido por segundo al sitio
TIMEOUT_PAGINA = 20
MAX_BYTES_PAGINA = 5 * 1024 * 1024
FALLAS_NOMINATIM_SEGUIDAS = 5      # si el servicio de mapas falla tantas veces seguidas, no se insiste

#: Un sitio por ciudad (cada uno arma su HTML distinto). `base` + cada ruta = las páginas a leer.
SITIOS: dict[str, dict] = {
    "tarija": {
        "base": "https://tarijaturismo.com",
        "paginas": ["/donde-dormir/", "/donde-comer/", "/que-hacer/", "/operadoras-de-turismo/",
                    "/agencias-de-viajes/", "/como-moverse/", "/guias-de-turismo-autorizados/"],
    },
}

SECCIONES = {
    "donde-dormir": "Dónde dormir", "donde-comer": "Dónde comer", "que-hacer": "Qué hacer",
    "operadoras-de-turismo": "Operadoras de turismo", "agencias-de-viajes": "Agencias de viajes",
    "como-moverse": "Cómo moverse", "guias-de-turismo-autorizados": "Guías de turismo autorizados",
}

#: Subcategoría de la página (la clase `category-…` del artículo) → rubro de URUKU. Sólo rubros que EXISTEN y están
#: activos (0042 y siguientes; `hotel` y `gastronomia` están dados de baja: el vivo es `hospedaje` / `restaurantes`).
#: Lo que no está acá queda sin rubro y se resuelve en el panel.
RUBRO_POR_SUBCATEGORIA: dict[str, str] = {
    "hoteles": "hospedaje", "apart-hotel": "hospedaje", "hostales": "hospedaje", "hostels": "hospedaje",
    "alojamientos": "hospedaje", "residenciales": "hospedaje",
    "churrasquerias": "restaurantes", "boliviana-regional-criolla": "restaurantes", "resto-bar": "restaurantes",
    "saludable-vegetariana": "restaurantes", "pizzeria": "restaurantes", "pescados-y-mariscos": "restaurantes",
    "afuera-de-la-ciudad-campestre": "restaurantes", "cocina-italiana-pastas": "restaurantes",
    "saltenerias": "comida-rapida", "comida-rapida": "comida-rapida", "patio-de-comidas": "comida-rapida",
    "cafeteria": "cafeteria", "heladerias-dulces": "cafeteria",
    "bodegas-y-vinotecas": "bebidas", "diversion-nocturna": "nocturna",
    "complejos-deportivos-y-gimnasios": "gimnasios",
    # tablas de «Cómo moverse»: `taxis` es «Taxis y movilidad» (0083, activo). `transporte` (0011) quedó dado de baja
    # en la 0042: un comercio promovido ahí no aparecería en ninguna categoría.
    "radio-moviles": "taxis", "transporte-alrededores": "taxis",
}
#: Si ninguna subcategoría tiene rubro, el de la sección entera (sólo donde hay un único rubro posible).
RUBRO_POR_SECCION: dict[str, str] = {"donde-dormir": "hospedaje"}

#: Rubro `turismo` (agencias, operadoras, guías, complejos turísticos, balnearios): todavía NO existe en las
#: migraciones; el dueño lo crea desde el panel (Catálogo › Rubros) antes de correr el importador. Si no existe, la
#: fila queda sin rubro como cualquier otra (la validación de `cargar` lo deja en None).
RUBRO_TURISMO = "turismo"
SUBCATEGORIAS_TURISMO = frozenset({"complejos-turisticos", "balneareos-privados", "diversion-en-familia"})
SECCIONES_TURISMO = frozenset({"operadoras-de-turismo", "agencias-de-viajes", "guias-de-turismo-autorizados"})

#: Subcategorías de «Qué hacer» que NO son comercios sino lugares (plazas, miradores, museos, atractivos): van a
#: Lugares (docs/lugares-turismo.md), no a Importados. Una entrada se descarta sólo si TODAS sus categorías son de
#: éstas (una bodega etiquetada también «fuera de la ciudad» sigue siendo un comercio).
SUBCATEGORIAS_DE_LUGAR = frozenset({
    "plazas-parques-y-miradores", "museos-y-bibliotecas", "centros-culturales",
    "dentro-de-la-ciudad", "fuera-de-la-ciudad", "fuera-del-municipio",
})

MAX_TEXTO = tarjetas.MAX_TEXTO_LEIDO


# ───────────────────────────────────────────────────────────── el parser (puro, sin red)

@dataclass
class Entrada:
    """Un negocio (o una sucursal) tal como lo muestra la página. Todo crudo: nada se normaliza acá."""
    nombre: str
    direccion: str | None
    telefonos: list[str]                 # el texto de cada línea «Telefono: …» (sin el rótulo)
    enlace: str | None                   # web o Facebook del negocio
    subcategoria: str | None             # la categoría de la página (`hoteles`, `churrasquerias`…)
    seccion: str                         # `donde-dormir`…
    url: str                             # la página de donde salió
    categorias: tuple[str, ...] = ()
    lineas: list[str] = field(default_factory=list)   # las líneas crudas de esta entrada (para el revisor)
    sucursal: bool = False               # True si es otra dirección (otra fila) del mismo negocio
    email: str | None = None             # algunas fichas traen un correo suelto
    rubro: str | None = None             # lo fija el lector cuando la tabla ya dice qué es (taxis, transporte)
    notas: list[str] = field(default_factory=list)    # datos de la tabla que sirven al revisor (destinos, precio…)
    detalle: str | None = None           # el enlace a la ficha del sitio (sólo las tarjetas de «Qué hacer»)


_ESPACIOS = re.compile(r"[\s​﻿]+")


def _limpio(texto: str) -> str:
    return _ESPACIOS.sub(" ", texto or "").strip()


class _Lector(HTMLParser):
    """Recorre el HTML y junta, por cada `<article class="elementor-post …">`: sus categorías, el nombre
    (`elementor-heading-title`), las líneas de la lista (`elementor-icon-list-text`, con su enlace si lo tiene) y,
    en las tarjetas, el título y el extracto. Fuera de un artículo (menús, pie de página) no se mira nada."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.articulos: list[dict] = []
        self._art: dict | None = None
        self._cap: dict | None = None      # lo que se está leyendo: {tag, n, tipo, buf, href}
        self._href: str | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        clases = (a.get("class") or "").split()
        if tag == "article" and "elementor-post" in clases:
            self._art = {"cats": [c[9:] for c in clases if c.startswith("category-")], "nombres": [], "items": [],
                         "titulo": None, "extracto": None}
            self._cap = None
            return
        if self._art is None:
            return
        if tag == "a":
            self._href = a.get("href")
            if self._cap is not None and self._cap["tipo"] == "titulo" and self._cap["href"] is None:
                self._cap["href"] = self._href
        if self._cap is not None:
            if tag == self._cap["tag"]:
                self._cap["n"] += 1
            elif tag == "br":
                self._cap["buf"].append(" ")
            return
        tipo = None
        if "elementor-heading-title" in clases:
            tipo = "nombre"
        elif "elementor-icon-list-text" in clases:
            tipo = "item"
        elif "elementor-post__title" in clases:
            tipo = "titulo"
        elif "elementor-post__excerpt" in clases:
            tipo = "extracto"
        if tipo:
            self._cap = {"tag": tag, "n": 1, "tipo": tipo, "buf": [], "href": self._href if tipo == "item" else None}

    def handle_endtag(self, tag):
        if tag == "article":
            if self._art is not None:
                self.articulos.append(self._art)
            self._art = None
            self._cap = None
            return
        if tag == "a":
            self._href = None
        cap = self._cap
        if cap is not None and tag == cap["tag"]:
            cap["n"] -= 1
            if cap["n"] == 0:
                texto = _limpio("".join(cap["buf"]))
                art = self._art
                if art is not None and texto:
                    if cap["tipo"] == "nombre":
                        art["nombres"].append(texto)
                    elif cap["tipo"] == "item":
                        art["items"].append((texto, cap["href"]))
                    elif cap["tipo"] == "titulo":
                        art["titulo"] = (texto, cap["href"])
                    else:
                        art["extracto"] = texto
                self._cap = None

    def handle_data(self, data):
        if self._cap is not None:
            self._cap["buf"].append(data)


_RE_TELEFONO = re.compile(r"^(?:tel[eé]fonos?|tel\.?|cel(?:ular(?:es)?)?\.?|whats\s*app|wsp)\s*[:.\-]?\s*(.*)$", re.I)
_RE_HORARIO = re.compile(r"^horarios?\b", re.I)
_RE_SUCURSAL = re.compile(r"^sucursal\s*(?:#|n[º°o]\.?)?\s*\d*\s*[:\-–]?\s*(.*)$", re.I)
#: Los rótulos del extracto de las tarjetas de «Qué hacer». Sólo con mayúscula inicial, como los escribe el sitio.
_RE_ROTULO_EXTRACTO = re.compile(
    r"\b(Direcci[oó]n|Tel[eé]fonos?|Horarios?|Presentaci[oó]n|Rese[nñ]a|Informaci[oó]n|Entradas?|Nuestras Redes:?|Descripci[oó]n)\b")


def _direccion(texto: str | None) -> str | None:
    limpia = _limpio(texto or "").strip(" ,;.-–")
    return limpia[: tarjetas.MAX_DIRECCION] or None


def _enlace_absoluto(href: str | None) -> str | None:
    """El enlace del negocio si es una dirección web completa (los del menú son relativos: `/como-llegar/`)."""
    valor = (href or "").strip()
    if not re.match(r"^https?://", valor, re.I):
        return None
    return valor


def _entradas_de_ficha(art: dict, ctx: dict) -> list[Entrada]:
    """Una ficha completa: el nombre y la lista de líneas. Cada dirección es una entrada (la primera es el negocio;
    «Sucursal # N …» y las direcciones que siguen son sucursales); cada `Telefono:` va con la dirección anterior."""
    nombre = art["nombres"][0][: tarjetas.MAX_NOMBRE]
    ramas: list[dict] = []
    enlace = None
    email = None
    for texto, href in art["items"]:
        if _enlace_absoluto(href):
            enlace = enlace or _enlace_absoluto(href)
            continue
        correo = tarjetas._email(texto)
        if correo and len(texto) <= len(correo) + 20:      # «correo@x.com» o «Email: correo@x.com»: no es una dirección
            email = email or correo
            continue
        m_tel = _RE_TELEFONO.match(texto)
        if m_tel:
            if not ramas:
                ramas.append({"direccion": None, "telefonos": [], "lineas": []})
            ramas[-1]["telefonos"].append(m_tel.group(1))
            ramas[-1]["lineas"].append(texto)
            continue
        if _RE_HORARIO.match(texto):
            continue
        m_suc = _RE_SUCURSAL.match(texto)
        ramas.append({"direccion": _direccion(m_suc.group(1) if m_suc else texto), "telefonos": [],
                      "lineas": [texto]})
    if not ramas:
        ramas.append({"direccion": None, "telefonos": [], "lineas": []})
    return [Entrada(nombre=nombre, direccion=r["direccion"], telefonos=r["telefonos"], enlace=enlace,
                    sucursal=i > 0, email=email,
                    lineas=r["lineas"] + ([f"Enlace: {enlace}"] if enlace and i == 0 else [])
                    + ([f"Correo: {email}"] if email and i == 0 else []), **ctx)
            for i, r in enumerate(ramas)]


def _entrada_de_tarjeta(art: dict, ctx: dict) -> Entrada:
    """Una tarjeta de «Qué hacer»: título y extracto («Dirección … Teléfono … Horarios …», cortado por el sitio).
    La dirección es lo que va entre su rótulo y el rótulo que sigue; los teléfonos, lo que sigue a «Teléfono»."""
    nombre, href = art["titulo"]
    extracto = art["extracto"] or ""
    partes = _RE_ROTULO_EXTRACTO.split(extracto)         # [antes, rótulo, texto, rótulo, texto, …]
    direccion = None
    telefonos: list[str] = []
    for i in range(1, len(partes) - 1, 2):
        rotulo, texto = partes[i], partes[i + 1]
        if rotulo.startswith("Direcci") and direccion is None:
            direccion = _direccion(texto)
        elif rotulo.startswith("Tel"):
            telefonos.append(texto.strip())
    return Entrada(nombre=nombre[: tarjetas.MAX_NOMBRE], direccion=direccion, telefonos=telefonos, enlace=None,
                   lineas=[extracto] if extracto else [], detalle=_enlace_absoluto(href), **ctx)


def seccion_de(url: str) -> str:
    """El primer tramo de la ruta de la página: `https://…/donde-dormir/` → `donde-dormir`."""
    partes = [p for p in urlparse(url).path.split("/") if p]
    return partes[0] if partes else ""


def leer_pagina(html: str, url: str) -> list[Entrada]:
    """Todas las entradas de UNA página (puro: sin red). Incluye las que no sirven (sin teléfono ni dirección):
    `es_util` las filtra, así se pueden contar las dos cosas."""
    lector = _Lector()
    lector.feed(html or "")
    lector.close()
    seccion = seccion_de(url)
    entradas: list[Entrada] = []
    for art in lector.articulos:
        cats = [c for c in art["cats"] if c != seccion] or list(art["cats"])
        ctx = {"subcategoria": cats[0] if cats else None, "seccion": seccion, "url": url, "categorias": tuple(cats)}
        if art["nombres"]:
            entradas += _entradas_de_ficha(art, ctx)
        elif art["titulo"]:
            entradas.append(_entrada_de_tarjeta(art, ctx))
    if "<table" in (html or ""):
        tablas = _LectorTablas()
        tablas.feed(html)
        tablas.close()
        for tabla in tablas.tablas:
            tipo = _tipo_de_tabla(tabla["cabecera"])
            if tipo:
                entradas += _entradas_de_tabla(tabla, tipo, {"seccion": seccion, "url": url})
    return entradas


# ───────────────────────────────────────────────────────────── las tablas (Cómo moverse, Guías)

class _LectorTablas(HTMLParser):
    """Junta las tablas (`<table class="tablepress">`): la cabecera y, por fila, las celdas por número de columna
    (la clase `column-N` de cada `<td>`: así una celda con `rowspan` no corre las demás)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tablas: list[dict] = []
        self._tabla: dict | None = None
        self._fila: dict | None = None
        self._celda: dict | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            self._tabla = {"cabecera": [], "filas": []}
        elif self._tabla is None:
            return
        elif tag == "tr":
            self._fila = {"celdas": {}, "cabecera": [], "es_cabecera": False}
        elif tag in ("td", "th") and self._fila is not None:
            col = next((c[7:] for c in (a.get("class") or "").split() if c.startswith("column-")), None)
            self._celda = {"tag": tag, "col": col, "buf": []}
        elif tag == "br" and self._celda is not None:
            self._celda["buf"].append(" ")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._celda is not None and self._fila is not None:
            c, f = self._celda, self._fila
            texto = _limpio("".join(c["buf"]))
            if c["tag"] == "th":
                f["es_cabecera"] = True
                f["cabecera"].append(texto)
            else:
                f["celdas"][c["col"] or str(len(f["celdas"]) + 1)] = texto
            self._celda = None
        elif tag == "tr" and self._fila is not None and self._tabla is not None:
            if self._fila["es_cabecera"]:
                self._tabla["cabecera"] = self._fila["cabecera"]
            else:
                self._tabla["filas"].append(self._fila["celdas"])
            self._fila = None
        elif tag == "table" and self._tabla is not None:
            self.tablas.append(self._tabla)
            self._tabla = None

    def handle_data(self, data):
        if self._celda is not None:
            self._celda["buf"].append(data)


def _sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", (texto or "").lower()) if unicodedata.category(c) != "Mn")


def _tipo_de_tabla(cabecera: list[str]) -> str | None:
    """Qué tabla es, por los títulos de sus columnas (no por su id: el sitio los cambia al editar). Las demás
    tablas de la página (buses y minivans entre ciudades) no se leen."""
    c = [_sin_tildes(x).strip() for x in cabecera]
    if c[:2] == ["transporte", "telefono"]:
        return "radio-moviles"
    if len(c) >= 4 and c[0] == "asociacion" and c[1] == "destino" and "punto de salida" in c[3]:
        return "transporte-alrededores"
    if c[:3] == ["nombre", "contacto", "licencia"]:
        return "guias"
    return None


#: «VALLE Telf. 66 - 48064», «AS. SAN ANDRES Cel. 75145664»: el teléfono viene pegado al nombre de la asociación.
_RE_TEL_EN_NOMBRE = re.compile(r"\b(?:telf?s?|tel[eé]fonos?|cel(?:ular(?:es)?)?)(?:\.|:)?\s*(?=[\d+(])(.*)$", re.I)
_PALABRAS_CHICAS = frozenset({"de", "del", "la", "las", "los", "y", "e", "en"})
_RE_YA_DICE_TRANSPORTE = re.compile(r"^(?:asociaci|cooperativa|servicio|sindicato|transporte|trufi|micro|l[ií]nea|radio)",
                                    re.I)


def _nombre_de_asociacion(texto: str) -> str:
    """`VALLE` → «Transporte Valle»; `AS. VIRGEN DEL ROSARIO` → «Asociación Virgen del Rosario». La tabla escribe
    todo en mayúsculas y a veces sin decir que es un transporte."""
    nombre = _limpio(texto)
    if nombre.isupper():
        nombre = re.sub(r"^AS\.\s*", "ASOCIACION ", nombre)
        palabras = [p.capitalize() for p in nombre.split()]
        nombre = " ".join(p.lower() if i and p.lower() in _PALABRAS_CHICAS else p for i, p in enumerate(palabras))
        nombre = nombre.replace("Asociacion", "Asociación")
    if not _RE_YA_DICE_TRANSPORTE.match(nombre):
        nombre = f"Transporte {nombre}"
    return nombre[: tarjetas.MAX_NOMBRE]


def _entradas_de_tabla(tabla: dict, tipo: str, ctx: dict) -> list[Entrada]:
    ctx = {**ctx, "subcategoria": tipo, "categorias": (tipo,)}
    filas = tabla["filas"]
    if tipo == "radio-moviles":
        # Transporte | Teléfono: sin dirección (comercios de taxi; se cargan igual, sin punto)
        return [Entrada(nombre=_limpio(f["1"])[: tarjetas.MAX_NOMBRE], direccion=None, telefonos=[f.get("2", "")],
                        enlace=None, rubro="taxis", lineas=[f"{f['1']} | {f.get('2', '')}"], **ctx)
                for f in filas if f.get("1")]
    if tipo == "guias":
        # Nombre | Contacto | Licencia: sólo las vigentes. Sin dirección y sin rubro (no hay uno de guías).
        return [Entrada(nombre=f"{_limpio(f['1'])[: tarjetas.MAX_NOMBRE - 20]} · Guía de turismo", direccion=None,
                        telefonos=[f.get("2", "")], enlace=None, lineas=[f"{f['1']} | {f.get('2', '')} | Licencia: "
                                                                          f"{f.get('3', '')}"],
                        notas=["Guía autorizado (licencia vigente según la Secretaría de Turismo)"], **ctx)
                for f in filas if f.get("1") and _sin_tildes(f.get("3", "")).strip() == "vigente"]
    # transporte-alrededores: una entrada por asociación. Su celda `column-1` abre el grupo; las filas que siguen
    # sin esa celda son más destinos de la misma asociación (la celda de la asociación tiene `rowspan`).
    grupos: list[dict] = []
    for f in filas:
        if f.get("1"):
            grupos.append({"asociacion": f["1"], "destinos": [], "salidas": []})
        elif not grupos:
            continue
        g = grupos[-1]
        if f.get("2"):
            g["destinos"].append(f"{f['2']} {f.get('3', '')}".strip())
        if f.get("4") and f["4"] not in g["salidas"]:
            g["salidas"].append(f["4"])
    out = []
    for g in grupos:
        m = _RE_TEL_EN_NOMBRE.search(g["asociacion"])
        crudo_nombre = g["asociacion"][: m.start()] if m else g["asociacion"]
        notas = ["Destinos (precio ref.): " + "; ".join(g["destinos"])]
        if len(g["salidas"]) > 1:
            notas.append("Puntos de salida: " + "; ".join(g["salidas"]))
        out.append(Entrada(nombre=_nombre_de_asociacion(crudo_nombre),
                           direccion=_direccion(g["salidas"][0]) if g["salidas"] else None,
                           telefonos=[m.group(1)] if m else [], enlace=None, rubro="taxis",
                           lineas=[g["asociacion"]], notas=notas, **ctx))
    return out


# ───────────────────────────────────────────────────────────── los datos de una entrada

def _con_area_de_tarija(crudo: str) -> str:
    """Un fijo escrito sin el código de área (`66 - 48064`, `66-53691`: 7 dígitos que empiezan con 6) es de Tarija:
    se le pone el 4. Se mira cada pedazo separado por «/», «;» o «,» (los guiones forman parte del número). Los
    separadores quedan con espacios alrededor: `72063578/72063580` pegado lo leería el extractor como una fracción."""
    pedazos = []
    for pedazo in re.split(r"([/;,])", crudo or ""):
        digitos = re.sub(r"\D", "", pedazo)
        if len(digitos) == 7 and digitos[0] == "6" and re.fullmatch(r"[\d\s\-–‑.]+", pedazo.strip() or "x"):
            pedazo = "4" + digitos
        pedazos.append(" / " if pedazo in "/;," and pedazo else pedazo)       # «71/72» sin espacios se leería como fracción
    return "".join(pedazos)


def telefonos_de(entrada: Entrada) -> list[Telefono]:
    """Los teléfonos de la entrada, normalizados y sin repetir. Cada línea se lee por separado (los pedazos de una
    no se pegan con los de otra). Fijos de Tarija escritos `466-48444`, `466 75800` o `+591 466 54999` son el fijo
    `4 66 48444`; celulares de 8 dígitos que empiezan con 6 o 7; separadores `/` y `-` entre números."""
    vistos: set[str] = set()
    out: list[Telefono] = []
    for crudo in entrada.telefonos:
        for t in extraer(_con_area_de_tarija(crudo)):
            if t.numero not in vistos:
                vistos.add(t.numero)
                out.append(t)
    return out


def es_util(entrada: Entrada) -> bool:
    """¿Vale la pena traerla? Hace falta teléfono o dirección (las plazas y mercados sin ninguno de los dos quedan
    afuera)."""
    propias = [c for c in entrada.categorias if c != entrada.seccion]   # «que-hacer» como categoría no cuenta
    if propias and all(c in SUBCATEGORIAS_DE_LUGAR for c in propias):
        return False                              # es un lugar, no un comercio: va a Lugares
    return bool(telefonos_de(entrada) or entrada.direccion)


def rubro_sugerido(entrada: Entrada) -> str | None:
    if entrada.rubro:
        return entrada.rubro
    for c in entrada.categorias:
        if c in RUBRO_POR_SUBCATEGORIA:
            return RUBRO_POR_SUBCATEGORIA[c]
    if entrada.seccion in SECCIONES_TURISMO or any(c in SUBCATEGORIAS_TURISMO for c in entrada.categorias):
        return RUBRO_TURISMO
    return RUBRO_POR_SECCION.get(entrada.seccion)


def _slug(texto: str | None) -> str:
    return slugify(texto)[:100] if texto and texto.strip() else "-"


def fuente_id_de(entrada: Entrada) -> str:
    """`turismo:<host>:<slug nombre>|<slug dirección>`: el mismo negocio en la misma dirección es siempre la misma
    clave, lo lea la página que lo lea."""
    host = (urlparse(entrada.url).hostname or "sitio").lower()
    return f"{FUENTE}:{host}:{_slug(entrada.nombre)}|{_slug(entrada.direccion)}"


def _texto_para_el_revisor(e: Entrada) -> str:
    sub = e.subcategoria.replace("-", " ") if e.subcategoria else "-"
    cabeza = [f"Sección: {SECCIONES.get(e.seccion, e.seccion)} · {sub}" + (" · sucursal" if e.sucursal else ""),
              f"Origen: {e.url}"]
    if e.detalle:
        cabeza.append(f"Ficha: {e.detalle}")
    return "\n".join(cabeza + ["--"] + e.lineas + e.notas)[:MAX_TEXTO]


def armar_fila(e: Entrada, *, ciudad_id: str, rubro_slug: str | None, punto: dict | None,
               repetido: dict | None) -> dict:
    """La fila de `comercios_importados` de una entrada (nuevo, sin revisar). Sin foto ni lector."""
    whatsapp, telefono = tarjetas.repartir_telefonos(telefonos_de(e))
    website = enlaces.sanear_red(e.enlace, "El enlace") if e.enlace else None
    return {
        "fuente": FUENTE, "fuente_id": fuente_id_de(e), "ciudad_id": ciudad_id,
        "nombre": e.nombre, "categoria": e.subcategoria, "rubro_slug": rubro_slug,
        "lat": punto["lat"] if punto else None, "lng": punto["lng"] if punto else None,
        "telefono": telefono, "whatsapp": whatsapp, "website": website, "email": e.email,
        "direccion": e.direccion, "tags": {"turismo": {"seccion": e.seccion, "subcategoria": e.subcategoria,
                                                       "url": e.url, "sucursal": e.sucursal}},
        "estado": "nuevo", "ubicacion": "aproximada" if punto else "no_encontrada",
        "foto_ref": None, "texto_leido": _texto_para_el_revisor(e), "lector": None,
        "duplicado_de": repetido["id"] if repetido else None,
    }


# ───────────────────────────────────────────────────────────── repetidos por nombre

_VACIAS = frozenset({"de", "la", "el", "los", "las", "y", "e", "del", "en", "a"})
#: Palabras que no distinguen un negocio de otro (el tipo de local y la ciudad).
_GENERICAS = frozenset({
    "hotel", "hostal", "hostel", "residencial", "apart", "alojamiento", "restaurante", "restaurant", "resto", "bar",
    "cafe", "cafeteria", "pizzeria", "tarija", "tours", "tour", "viajes", "agencia", "turismo", "bodega", "bodegas",
    "complejo", "central", "centro", "plaza", "resort", "boutique",
})


def _palabras(nombre: str | None) -> set[str]:
    sin_tildes = "".join(c for c in unicodedata.normalize("NFD", (nombre or "").lower())
                         if unicodedata.category(c) != "Mn")
    todas = [p for p in re.split(r"[^a-z0-9]+", sin_tildes) if p and p not in _VACIAS]
    distintivas = {p for p in todas if p not in _GENERICAS}
    return distintivas or set(todas)


def mismo_nombre(a: str | None, b: str | None) -> bool:
    """¿Se parece lo bastante como para marcarlo como posible repetido? Mismas palabras distintivas (sin acentos,
    mayúsculas ni el tipo de local), o las de uno contenidas en las del otro si son al menos dos (o una de seis
    letras o más). Es una MARCA para el revisor, no una decisión."""
    pa, pb = _palabras(a), _palabras(b)
    if not pa or not pb:
        return False
    if pa == pb:
        return True
    chica, grande = (pa, pb) if len(pa) <= len(pb) else (pb, pa)
    if not chica <= grande:
        return False
    return len(chica) >= 2 or len(next(iter(chica))) >= 6


def indice_nombres(repo, ciudad_id: str) -> list[dict]:
    """`[{id, nombre}]` de los comercios ACTIVOS de la ciudad (se arma una vez por corrida)."""
    return [{"id": c["id"], "nombre": c.get("nombre")} for c in repo.list_comercios_de_ciudad(ciudad_id)
            if c.get("nombre")]


def buscar_repetido_por_nombre(nombre: str, comercios: list[dict]) -> dict | None:
    return next(({"id": c["id"], "nombre": c["nombre"]} for c in comercios if mismo_nombre(nombre, c["nombre"])),
                None)


# ───────────────────────────────────────────────────────────── cargar

@dataclass
class Resumen:
    leidas: int = 0            # todas las entradas de las páginas
    utiles: int = 0            # con teléfono o dirección (las que se intentan cargar)
    descartadas: int = 0       # sin nada para contactar
    nuevas: int = 0
    ya_existentes: int = 0
    con_punto: int = 0
    sin_punto: int = 0
    repetidas: int = 0
    por_seccion: Counter = field(default_factory=Counter)        # entradas leídas por sección
    utiles_por_seccion: Counter = field(default_factory=Counter)


def cargar(repo, entradas: list[Entrada], ciudad: dict, *, dry_run: bool = False, limite: int | None = None,
           pedir: Callable[[dict], list] | None = None, mostrar: Callable[[str], None] = print) -> Resumen:
    """Deja las entradas útiles en `comercios_importados`. Con `dry_run` NO escribe ni consulta Nominatim: sólo
    lee la base (ciudad, rubros, existentes, repetidos) y muestra lo que cargaría."""
    r = Resumen(leidas=len(entradas))
    for e in entradas:
        r.por_seccion[e.seccion] += 1
    utiles = []
    vistos: set[str] = set()
    for e in entradas:
        if not es_util(e):
            r.descartadas += 1
            continue
        fid = fuente_id_de(e)
        if fid in vistos:                         # el mismo negocio en dos secciones (operadora y agencia)
            continue
        vistos.add(fid)
        r.utiles_por_seccion[e.seccion] += 1
        utiles.append(e)
    r.utiles = len(utiles)
    if limite is not None:
        utiles = utiles[: max(0, limite)]

    indice_tel = tarjetas.indice_telefonos(repo)
    comercios = indice_nombres(repo, ciudad["id"])
    rubros: dict[str, bool] = {}
    ubicar = not dry_run
    fallas = 0
    for e in utiles:
        fid = fuente_id_de(e)
        if repo.get_importado_por_fuente(FUENTE, fid):
            r.ya_existentes += 1
            continue
        slug = rubro_sugerido(e)
        if slug and slug not in rubros:
            rubros[slug] = bool(repo.get_rubro_id(slug))
        if slug and not rubros[slug]:
            slug = None                           # un rubro que no existe se deja vacío
        tels = telefonos_de(e)
        repetido = tarjetas.buscar_repetido(repo, tels, indice_tel) or buscar_repetido_por_nombre(e.nombre, comercios)
        punto = None
        if ubicar and e.direccion:
            try:
                punto = tarjetas.buscar_direccion(e.direccion, ciudad, pedir=pedir)
                fallas = 0
            except tarjetas.UbicacionNoDisponible:
                fallas += 1
                if fallas >= FALLAS_NOMINATIM_SEGUIDAS:
                    ubicar = False
                    logger.warning("importar_turismo.sin_mapas_se_deja_de_ubicar", fallas=fallas)
        fila = armar_fila(e, ciudad_id=ciudad["id"], rubro_slug=slug, punto=punto, repetido=repetido)
        if dry_run:
            r.nuevas += 1
            r.repetidas += 1 if repetido else 0
            mostrar(_linea_dry_run(e, fila, repetido))
            continue
        if repo.crear_importado(fila) is None:    # otra corrida simultánea ganó
            r.ya_existentes += 1
            continue
        r.nuevas += 1
        r.con_punto += 1 if punto else 0
        r.sin_punto += 0 if punto else 1
        r.repetidas += 1 if repetido else 0
        logger.info("importar_turismo.cargada", seccion=e.seccion, subcategoria=e.subcategoria,
                    con_punto=bool(punto), repetida=bool(repetido), sucursal=e.sucursal)
    return r


def _linea_dry_run(e: Entrada, fila: dict, repetido: dict | None) -> str:
    tel = " / ".join(x for x in (fila["whatsapp"], fila["telefono"]) if x) or "-"
    marca = f"  [repetido de «{repetido['nombre']}»]" if repetido else ""
    return (f"  {e.seccion[:10]:10} {str(e.subcategoria)[:18]:18} {(fila['rubro_slug'] or '-')[:13]:13} "
            f"{e.nombre[:34]:34} | {(e.direccion or '-')[:44]:44} | {tel}{marca}")


# ───────────────────────────────────────────────────────────── red

def descargar_pagina(url: str) -> str:
    """El HTML de una página del sitio. Sólo http(s), con el User-Agent de URUKU y un tope de tamaño. Lanza
    `RuntimeError` (en español) si no se pudo."""
    import httpx

    try:
        r = httpx.get(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "es"}, timeout=TIMEOUT_PAGINA,
                      follow_redirects=True)
        r.raise_for_status()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"No se pudo leer {url}: {type(exc).__name__}") from None
    if len(r.content) > MAX_BYTES_PAGINA:
        raise RuntimeError(f"La página {url} pesa demasiado")
    return r.text


def leer_sitio(sitio: dict, *, descargar: Callable[[str], str] | None = None,
               dormir: Callable[[float], None] = time.sleep) -> list[Entrada]:
    """Baja las páginas del sitio (una por segundo) y junta sus entradas."""
    descargar = descargar or descargar_pagina
    entradas: list[Entrada] = []
    for i, ruta in enumerate(sitio["paginas"]):
        if i:
            dormir(INTERVALO_PEDIDOS)
        url = sitio["base"].rstrip("/") + ruta
        pagina = leer_pagina(descargar(url), url)
        logger.info("importar_turismo.pagina_leida", seccion=seccion_de(url), entradas=len(pagina))
        entradas += pagina
    return entradas


# ───────────────────────────────────────────────────────────── línea de comandos

def _imprimir_resumen(r: Resumen, dry_run: bool) -> None:
    print("\nPor sección (leídas · útiles):")
    for seccion in SECCIONES:
        if r.por_seccion[seccion]:
            print(f"  {SECCIONES[seccion]:24} {r.por_seccion[seccion]:4} · {r.utiles_por_seccion[seccion]:4}")
    print(f"\nLeídas:                 {r.leidas}")
    print(f"Descartadas (sin teléfono ni dirección): {r.descartadas}")
    print(f"Útiles (sin repetir entre secciones):    {r.utiles}")
    if dry_run:
        print(f"Cargaría (nuevas):      {r.nuevas}")
        print(f"Ya existentes:          {r.ya_existentes}")
        print(f"Marcadas como repetidas: {r.repetidas}")
        print("\nSimulación: no se escribió nada ni se consultó el mapa. Repetir sin --dry-run para cargarlas.")
        return
    print(f"Nuevas:                 {r.nuevas}")
    print(f"Ya existentes:          {r.ya_existentes}")
    print(f"Con punto en el mapa:   {r.con_punto}")
    print(f"Sin punto:              {r.sin_punto}")
    print(f"Marcadas como repetidas: {r.repetidas}")


def main(argv: list[str] | None = None, repo=None, *, descargar: Callable[[str], str] | None = None,
         pedir: Callable[[dict], list] | None = None, dormir: Callable[[float], None] = time.sleep) -> int:
    ap = argparse.ArgumentParser(prog="importar_turismo", description="Importa los negocios de la página de turismo "
                                 "de una ciudad a Importados (fuente 'turismo').")
    ap.add_argument("--ciudad", required=True, help=f"slug de la ciudad ({', '.join(SITIOS)})")
    ap.add_argument("--dry-run", action="store_true", help="muestra lo que cargaría, sin escribir ni consultar el mapa")
    ap.add_argument("--limite", type=int, default=None, help="cargar sólo los primeros N negocios útiles")
    args = ap.parse_args(argv)

    sitio = SITIOS.get(args.ciudad)
    if not sitio:
        print(f"No hay un lector de turismo para «{args.ciudad}». Hay: {', '.join(SITIOS)}.", file=sys.stderr)
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

    print(f"Ciudad: {ciudad['nombre']} · sitio: {sitio['base']} · {len(sitio['paginas'])} páginas, "
          f"una por segundo{' · SIMULACIÓN' if args.dry_run else ''}")
    try:
        entradas = leer_sitio(sitio, descargar=descargar, dormir=dormir)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    resumen = cargar(repo, entradas, ciudad, dry_run=args.dry_run, limite=args.limite, pedir=pedir)
    _imprimir_resumen(resumen, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
