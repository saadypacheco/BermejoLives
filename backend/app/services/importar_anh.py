"""Traer las estaciones de servicio de la ANH a `comercios_importados` (docs/vigia-fuentes.md, «ANH: cómo se corre»).

    docker exec buscadonde-backend python -m app.services.importar_anh --departamento tarija --dry-run
    docker exec buscadonde-backend python -m app.services.importar_anh --departamento tarija

QUÉ ES
======

La Agencia Nacional de Hidrocarburos publica, por departamento, quiénes tienen licencia para vender combustible:
`contenido.php?s=40&R=<actividad>&D=<departamento>`. Se leen dos actividades:

  R=1  comercialización de combustibles líquidos en estación de servicio
  R=2  comercialización de gas natural vehicular (GNV) en estación de servicio

Cada fila trae razón social, dirección, teléfono, licencia, combustibles que vende y el departamento. NO trae el
municipio (la columna «Ubicación» repite el departamento): la ciudad sale de dónde cae el punto o de cómo empieza
la dirección. Sí trae un punto (`setMark(lat, lng, nombre)` del botón «Mostrar ubicación»): se guarda como
`aproximada`, para que una persona lo confirme. Con `--sin-punto` se ignora y la fila sale sin punto
(`no_encontrada`, para el ubicador: `python -m app.services.ubicar_direccion --ciudad X`).

La misma estación aparece en las dos actividades (líquidos y GNV): se une en una sola fila.

NADA SE PUBLICA SOLO
====================

Todo entra como `estado='nuevo'` a la cola de Importados y una persona lo promueve, de a uno. Correrlo de nuevo no
duplica ni pisa nada: la `fuente_id` es el código de licencia de la ANH (sin el «LIC09/2026», que cambia en cada
renovación) o, si la página no trae uno, un hash del nombre y la dirección.

CORTESÍA
========

Dos pedidos por departamento, con 2 s de pausa, un User-Agent genérico (nunca un correo) y sólo hacia
`www.anh.gob.bo`. Los tests no salen a la red: `leer` es un falso que devuelve filas con la forma de `parsear_pagina`.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import urlsplit

import structlog

from app.core.telefonos_foto import normalizar as normalizar_telefono
from app.services import tarjetas
from app.services.cargas import metros_entre
from app.services.importar_overture import RADIO_KM, RADIOS
from app.services.importar_turismo import indice_nombres, mismo_nombre

logger = structlog.get_logger()

FUENTE = "anh"
RUBRO = "estacion-servicio"                  # migración 0076
BASE_URL = "https://www.anh.gob.bo/w2019/contenido.php?s=40&R={actividad}&D={codigo}"
HOST = "www.anh.gob.bo"                      # el sitio redirige /w2019/ a /w2026/: se sigue, pero sólo dentro del host
USER_AGENT = "URUKU-importador/1.0"
PAUSA_SEG = 2.0
TIMEOUT_SEG = 30
MAX_TEXTO = tarjetas.MAX_TEXTO_LEIDO
METROS_REPETIDO = 120
MAX_KM_PUNTO = 25.0                          # un punto más lejos que esto de su ciudad es un error de carga
#: Caja de Bolivia: un punto fuera de ella (o 0,0) no es de la ANH sino un error.
LAT_BO, LNG_BO = (-23.0, -9.5), (-69.8, -57.4)

#: actividad de la ANH (`R=`) → etiqueta
ACTIVIDADES: dict[int, str] = {1: "liquidos", 2: "gnv"}
ETIQUETA_ACTIVIDAD = {"liquidos": "combustibles líquidos", "gnv": "GNV"}


@dataclass(frozen=True)
class Departamento:
    slug: str
    codigo: int            # el `D=` de la ANH (los 9 confirmados en los enlaces de la propia página, 18/11/2026)
    nombre: str            # como está en `ciudades.departamento`
    area: str              # código de área de los fijos (la ANH los publica con 7 dígitos, sin el área)


DEPARTAMENTOS: dict[str, Departamento] = {d.slug: d for d in (
    Departamento("chuquisaca", 1, "Chuquisaca", "4"),
    Departamento("la-paz", 2, "La Paz", "2"),
    Departamento("cochabamba", 3, "Cochabamba", "4"),
    Departamento("oruro", 4, "Oruro", "2"),
    Departamento("potosi", 5, "Potosí", "2"),
    Departamento("tarija", 6, "Tarija", "4"),
    Departamento("santa-cruz", 7, "Santa Cruz", "3"),
    Departamento("beni", 8, "Beni", "3"),
    Departamento("pando", 9, "Pando", "3"),
)}


# ───────────────────────────────────────────────────────────── texto

def _sin_tildes(texto: str | None) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(texto or "")) if unicodedata.category(c) != "Mn")


def normalizar(texto: str | None) -> str:
    """Minúsculas, sin tildes, comillas ni signos: para comparar y para el hash."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", _sin_tildes(texto).lower()).split())


def resolver_departamento(valor: str) -> Departamento | None:
    """`tarija`, `Tarija`, `santa cruz`, `Potosí`… → el departamento, o None."""
    return DEPARTAMENTOS.get(normalizar(valor).replace(" ", "-"))


_SIGLAS = frozenset({"s.r.l.", "s.a.", "s.a.m.", "ypfb", "y.p.f.b.", "gnv", "g.n.v.", "glp", "s/n", "srl", "sa"})
_MINUSCULAS = frozenset({"de", "del", "y", "e", "a", "en", "con"})
#: La ANH escribe sin tildes lo que el cartel lleva con ellas.
_TILDES = {"estacion": "Estación", "circunvalacion": "Circunvalación", "union": "Unión", "bolivar": "Bolívar"}
_RE_SIGLA_PUNTOS = re.compile(r"^(?:[a-z]\.)+[a-z]*$", re.IGNORECASE)


def legible(texto: str | None, *, maximo: int = 200) -> str:
    """Pasa «ESTACION DE SERVICIO "EL TERO TERO"» a «Estación de Servicio El Tero Tero»: la ANH escribe todo en
    mayúsculas y entre comillas. Respeta las siglas (S.R.L., YPFB, GNV, J.A.M.E.). Lo que ya viene con minúsculas
    no se toca."""
    t = " ".join(str(texto or "").replace('"', " ").replace("“", " ").replace("”", " ").split())
    if t and t == t.upper():
        palabras = []
        for i, p in enumerate(t.split(" ")):
            bajo = p.lower()
            if bajo in _SIGLAS or _RE_SIGLA_PUNTOS.match(p) or "/" in p or (len(p) <= 4 and any(x.isdigit() for x in p)):
                palabras.append(p.upper())
            elif i > 0 and bajo in _MINUSCULAS:
                palabras.append(bajo)
            else:
                palabras.append("-".join(_TILDES.get(x) or x.capitalize() for x in bajo.split("-")))
        t = " ".join(palabras)
    return t[:maximo]


# ───────────────────────────────────────────────────────────── lectura (HTTP → HTML → filas crudas)

class PaginaInesperada(ValueError):
    """La página no tiene la tabla o las columnas esperadas: la ANH cambió el diseño."""


class _Tabla(HTMLParser):
    """Lee `<table id='search_table'>`: los títulos de las columnas y, por fila, el texto de cada celda (los `<br>`
    son saltos de línea) y el `setMark(lat, lng, …)` del botón de ubicación."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.encontrada = False
        self.titulos: list[str] = []
        self.filas: list[list[dict]] = []
        self._en_tabla = False
        self._fila: list[dict] | None = None
        self._celda: dict | None = None
        self._titulo: list[str] | None = None
        self._en_enlace = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        # La tabla de la ANH es `id='search_table'`, pero en la de GNV de Oruro, Chuquisaca, Potosí, Beni y Pando el
        # id viene vacío (`id=''`, visto el 19/11/2026): también vale la primera `table-bordered`. Que sea la tabla
        # de estaciones lo deciden después sus columnas (razón social y contacto).
        es_la_tabla = a.get("id") == "search_table" or "table-bordered" in (a.get("class") or "").split()
        if tag == "table" and es_la_tabla and not self.encontrada:
            self._en_tabla = self.encontrada = True
        elif not self._en_tabla:
            return
        elif tag == "tr":
            self._fila = []
        elif tag == "th":
            self._titulo = []
        elif tag == "td" and self._fila is not None:
            self._celda = {"texto": [], "marca": None}
        elif tag == "br" and self._celda is not None:
            self._celda["texto"].append("\n")
        elif tag == "a" and self._celda is not None:
            self._en_enlace = True
            m = re.search(r"setMark\(\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)", a.get("onclick") or "")
            if m:
                self._celda["marca"] = (m.group(1), m.group(2))

    def handle_endtag(self, tag):
        if not self._en_tabla:
            return
        if tag == "a":
            self._en_enlace = False
        elif tag == "th" and self._titulo is not None:
            self.titulos.append(" ".join("".join(self._titulo).split()))
            self._titulo = None
        elif tag == "td" and self._celda is not None and self._fila is not None:
            self._fila.append(self._celda)
            self._celda = None
        elif tag == "tr" and self._fila is not None:
            if self._fila:
                self.filas.append(self._fila)
            self._fila = None
        elif tag == "table":
            self._en_tabla = False

    def handle_data(self, data):
        if self._titulo is not None:
            self._titulo.append(data)
        elif self._celda is not None and not self._en_enlace:
            self._celda["texto"].append(data)


def _lineas(celda: dict) -> list[str]:
    return [" ".join(x.split()) for x in "".join(celda["texto"]).split("\n") if x.strip()]


def _punto(marca) -> tuple[float, float] | None:
    """El `setMark` de la ANH → `(lat, lng)` si cae en Bolivia; None si falta o es un error de carga (0,0, signo
    cambiado…)."""
    if not marca:
        return None
    try:
        lat, lng = float(marca[0]), float(marca[1])
    except (TypeError, ValueError):
        return None
    if not (LAT_BO[0] <= lat <= LAT_BO[1] and LNG_BO[0] <= lng <= LNG_BO[1]):
        return None
    return lat, lng


def parsear_pagina(html: str, *, url: str = "", actividad: str = "liquidos") -> list[dict]:
    """El HTML de una página de la ANH → una fila cruda por estación:
    `{nombre, direccion, telefono, licencia, productos, ubicacion_texto, lat, lng, url, actividad}`.
    Lanza `PaginaInesperada` si no encuentra la tabla o las columnas «razón social» y «contacto»."""
    p = _Tabla()
    p.feed(html)
    p.close()
    if not p.encontrada:
        raise PaginaInesperada("no se encontró la tabla de la ANH (¿cambió el diseño de la página?)")
    columnas: dict[str, int] = {}
    for i, titulo in enumerate(p.titulos):
        t = normalizar(titulo)
        for clave, palabra in (("nombre", "razon"), ("contacto", "contacto"), ("licencia", "licencia"),
                               ("productos", "producto"), ("ubicacion", "ubicacion")):
            if palabra in t:
                columnas.setdefault(clave, i)
    if not p.titulos:                                      # sin <th>: el orden de siempre
        columnas = {"nombre": 0, "contacto": 1, "licencia": 2, "productos": 3, "ubicacion": 4}
    if "nombre" not in columnas or "contacto" not in columnas:
        raise PaginaInesperada(f"faltan las columnas razón social y contacto (títulos: {p.titulos})")

    def celda(fila: list[dict], clave: str) -> dict:
        i = columnas.get(clave)
        return fila[i] if i is not None and i < len(fila) else {"texto": [], "marca": None}

    filas = []
    for fila in p.filas:
        nombre = " ".join(_lineas(celda(fila, "nombre")))
        direccion = telefono = ""
        for linea in _lineas(celda(fila, "contacto")):
            etiqueta, _, valor = linea.partition(":")
            e = normalizar(etiqueta)
            if e.startswith("direccion"):
                direccion = valor.strip()
            elif e.startswith(("telefono", "celular")):
                telefono = (telefono + " / " + valor.strip()) if telefono else valor.strip()
        punto = _punto(celda(fila, "ubicacion")["marca"])
        filas.append({
            "nombre": nombre, "direccion": direccion, "telefono": telefono,
            "licencia": " ".join(_lineas(celda(fila, "licencia"))),
            "productos": " ".join(_lineas(celda(fila, "productos"))),
            "ubicacion_texto": " ".join(_lineas(celda(fila, "ubicacion"))),
            "lat": punto[0] if punto else None, "lng": punto[1] if punto else None,
            "url": url, "actividad": actividad,
        })
    return filas


def _pedir(url: str) -> tuple[str, str]:
    """`(html, url final)`. El único lugar que sale a la red. Sigue el redirect del sitio (/w2019/ → /w2026/) pero no
    sale de `www.anh.gob.bo`."""
    import httpx

    r = httpx.get(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "es"}, timeout=TIMEOUT_SEG,
                  follow_redirects=True)
    r.raise_for_status()
    if urlsplit(str(r.url)).hostname != HOST:
        raise ValueError(f"La ANH redirigió fuera de {HOST}: {r.url}")
    try:
        html = r.content.decode("utf-8")
    except UnicodeDecodeError:
        html = r.content.decode("latin-1")
    return html, str(r.url)


def leer_anh(depto: Departamento, *, pedir: Callable[[str], tuple[str, str]] | None = None,
             pausa: float = PAUSA_SEG) -> list[dict]:
    """Las filas crudas de las dos actividades del departamento. Lanza si la ANH no contesta o cambió la página."""
    filas: list[dict] = []
    for i, (actividad, nombre) in enumerate(ACTIVIDADES.items()):
        if i:
            time.sleep(pausa)
        html, url = (pedir or _pedir)(BASE_URL.format(actividad=actividad, codigo=depto.codigo))
        filas += parsear_pagina(html, url=url, actividad=nombre)
    return filas


# ───────────────────────────────────────────────────────────── normalizar (puro)

_RE_LICENCIA = re.compile(r"\b(ANH\d{3,6})-([A-Z]+\d{1,3})(?:-LIC[\d/]*)?", re.IGNORECASE)
_PRODUCTOS = ("GASOLINA ESPECIAL (+)", "GASOLINA ESPECIAL", "GASOLINA PREMIUM", "GASOLINA DE AVIACION",
              "SUPER ETANOL 92", "ETANOL", "DIESEL OIL", "DIESEL", "KEROSENE", "JET FUEL", "GAS NATURAL VEHICULAR",
              "GAS LICUADO DE PETROLEO", "GLP", "GNV")
_RE_PRODUCTOS = re.compile(r"(?<![A-Z0-9])(?:" + "|".join(re.escape(p) for p in _PRODUCTOS) + r")(?![A-Z0-9])",
                          re.IGNORECASE)


def codigo_licencia(licencia: str | None) -> str | None:
    """`ANH00804-CLES02-LIC09/2026` → `ANH00804-CLES02` (sin la renovación, que cambia cada año)."""
    m = _RE_LICENCIA.search(str(licencia or ""))
    return f"{m.group(1)}-{m.group(2)}".upper() if m else None


def operador_de(licencia: str | None) -> str | None:
    c = codigo_licencia(licencia)
    return c.split("-")[0] if c else None


def combustibles_de(productos: str | None) -> list[str]:
    """`DIESEL OIL GASOLINA ESPECIAL (+)` → `['Diesel oil', 'Gasolina especial (+)']`. Lo que no se reconoce queda
    como vino (en una sola entrada), así un producto nuevo de la ANH no se pierde."""
    texto = " ".join(str(productos or "").split())
    out = []
    for m in _RE_PRODUCTOS.finditer(texto):
        v = m.group(0).capitalize() if m.group(0).upper() not in ("GNV", "GLP") else m.group(0).upper()
        if v not in out:
            out.append(v)
    resto = " ".join(_RE_PRODUCTOS.sub(" ", texto).split())
    if len(resto) >= 3:
        out.append(resto.capitalize()[:60])
    return out


_RE_SEP_TEL = re.compile(r"\s*(?:[/,;]|\s-\s|\sy\s)\s*", re.IGNORECASE)


def telefonos_de(crudo: str | None, area: str) -> list:
    """Los teléfonos de un texto de la ANH. Los fijos vienen con 7 dígitos, sin el código de área (`6637692`): se
    les antepone el del departamento. Lo que no es un teléfono de Bolivia se ignora."""
    out = []
    for parte in _RE_SEP_TEL.split(str(crudo or "")):
        digitos = re.sub(r"\D", "", parte)
        if len(digitos) == 7 and digitos[0] in "2346789":
            digitos = area + digitos
        t = normalizar_telefono(digitos) if digitos else None
        if t and all(t.numero != x.numero for x in out):
            out.append(t)
    return out


def _clave_unir(c: dict) -> tuple:
    return (operador_de(c.get("licencia")) or "", normalizar(c.get("nombre")))


def unir_actividades(crudas: list[dict]) -> list[dict]:
    """Una fila por estación: la misma (operador de la ANH + nombre) que aparece en líquidos y en GNV se une. La
    primera que llega manda (líquidos viene antes: su dirección y su punto son los de la ficha). Cada una suma sus
    combustibles, licencias, teléfonos y actividades. Sin código de licencia no se une nada."""
    out: list[dict] = []
    por_clave: dict[tuple, dict] = {}
    for c in crudas:
        clave = _clave_unir(c)
        previa = por_clave.get(clave) if clave[0] else None
        base = {"licencias": [c.get("licencia")] if c.get("licencia") else [],
                "actividades": [c.get("actividad")] if c.get("actividad") else [],
                "productos_lista": [c.get("productos")] if c.get("productos") else [],
                "telefonos_crudos": [c["telefono"]] if c.get("telefono") else [],
                "urls": [c["url"]] if c.get("url") else [], "unidas": 0}
        if previa is None:
            fila = {**c, **base}
            out.append(fila)
            if clave[0]:
                por_clave[clave] = fila
            continue
        for k, v in base.items():
            if k != "unidas":
                previa[k] += [x for x in v if x not in previa[k]]
        previa["unidas"] += 1
        if previa.get("lat") is None and c.get("lat") is not None:
            previa["lat"], previa["lng"] = c["lat"], c["lng"]
        if not previa.get("direccion") and c.get("direccion"):
            previa["direccion"] = c["direccion"]
    return out


def fuente_id_de(depto: Departamento, c: dict) -> str:
    """`anh:<departamento>:<código de licencia>`, o con un hash corto del nombre y la dirección si no hay uno."""
    codigo = codigo_licencia(c.get("licencia"))
    if not codigo:
        codigo = hashlib.sha1(f"{normalizar(c.get('nombre'))}|{normalizar(c.get('direccion'))}".encode()).hexdigest()[:10]
    return f"{FUENTE}:{depto.slug}:{codigo}"


def motivo_descarte(c: dict) -> str | None:
    """Por qué una fila no entra (`sin_nombre`), o None. La ciudad se decide aparte (`fuera_de_ciudad`)."""
    return "sin_nombre" if len(str(c.get("nombre") or "").strip()) < 2 else None


# ───────────────────────────────────────────────────────────── ciudad

def ciudades_del_departamento(repo, depto: Departamento) -> list[dict]:
    """Las ciudades de la tabla `ciudades` que son del departamento, con su centro (`lat`/`lng`)."""
    out = []
    for c in repo.list_ciudades() or []:
        fila = repo.get_ciudad(c["slug"]) or {}
        if normalizar(fila.get("departamento")) == normalizar(depto.nombre) and fila.get("lat") is not None \
                and fila.get("lng") is not None:
            out.append(fila)
    return out


def localidad_de(direccion: str | None) -> str:
    """Lo que abre la dirección antes del primer separador: `YACUIBA, AVDA. LOS LIBERTADORES` → `yacuiba`.
    `CARRETERA TARIJA - SAN LORENZO` da `carretera tarija` (no es la ciudad: es el camino)."""
    primero = re.split(r"[,;]|\s*[-–]\s*", str(direccion or ""), maxsplit=1)[0]
    return normalizar(primero)


def asignar_ciudad(c: dict, ciudades: list[dict]) -> dict | None:
    """La ciudad de URUKU de una estación, o None (`fuera_de_ciudad`; no se inventa una). Primero el municipio que
    nombra la dirección; si no, la ciudad cuyo radio contiene el punto."""
    loc = localidad_de(c.get("direccion"))
    if loc:
        for ciu in ciudades:
            if normalizar(ciu.get("nombre")) == loc:
                return ciu
    if c.get("lat") is None or c.get("lng") is None:
        return None
    mejor: tuple[float, dict] | None = None
    for ciu in ciudades:
        d = metros_entre(c["lat"], c["lng"], ciu["lat"], ciu["lng"])
        if d is not None and d <= RADIOS.get(ciu.get("slug"), RADIO_KM) * 1000 and (mejor is None or d < mejor[0]):
            mejor = (d, ciu)
    return mejor[1] if mejor else None


# ───────────────────────────────────────────────────────────── armar la fila

def _texto_para_el_revisor(depto: Departamento, c: dict, combustibles: list[str], telefonos_visibles: str | None,
                           punto: bool) -> str:
    lineas = [f"ANH · estaciones de servicio · {depto.nombre}"]
    if c.get("licencias"):
        lineas.append("Licencia: " + " · ".join(c["licencias"]))
    if combustibles:
        lineas.append("Combustibles: " + ", ".join(combustibles))
    if c.get("direccion"):
        lineas.append(f"Dirección: {c['direccion']}")
    if telefonos_visibles:
        lineas.append(f"Teléfono: {telefonos_visibles}")
    if punto:
        lineas.append(f"Punto de la ANH: {c['lat']:.6f}, {c['lng']:.6f} (a confirmar)")
    if c.get("url"):
        lineas.append(f"Origen: {c['url']}")
    return "\n".join(lineas)[:MAX_TEXTO]


def armar_fila(c: dict, *, depto: Departamento, ciudad: dict, rubros_validos: Callable[[str], bool],
               usar_punto: bool = True) -> dict:
    """Una estación (ya unida) → una fila de `comercios_importados` (nuevo, sin revisar)."""
    tels = telefonos_de(" / ".join(c.get("telefonos_crudos") or [c.get("telefono") or ""]), depto.area)[:4]
    whatsapp, telefono = tarjetas.repartir_telefonos(tels)
    combustibles: list[str] = []
    for p in c.get("productos_lista") or [c.get("productos")]:
        combustibles += [x for x in combustibles_de(p) if x not in combustibles]
    lat = lng = None
    if usar_punto and c.get("lat") is not None and c.get("lng") is not None:
        d = metros_entre(c["lat"], c["lng"], ciudad["lat"], ciudad["lng"])
        if d is not None and d <= MAX_KM_PUNTO * 1000:
            lat, lng = round(float(c["lat"]), 6), round(float(c["lng"]), 6)
    direccion = legible(c.get("direccion")) or None
    visibles = " / ".join(x for x in (whatsapp, telefono) if x) or None
    fila_texto = {**c, "direccion": direccion, "lat": lat, "lng": lng, "url": (c.get("urls") or [c.get("url")])[0]}
    return {
        "fuente": FUENTE, "fuente_id": fuente_id_de(depto, c), "ciudad_id": ciudad["id"],
        "nombre": legible(c.get("nombre")) or str(c["nombre"]).strip()[:200], "categoria": "estacion_servicio",
        "rubro_slug": RUBRO if rubros_validos(RUBRO) else None,
        "lat": lat, "lng": lng,
        "telefono": telefono, "whatsapp": whatsapp, "website": None, "email": None,
        "horario": None, "direccion": direccion,
        "tags": {"anh": {"departamento": depto.nombre, "departamento_codigo": depto.codigo,
                         "combustibles": combustibles, "municipio": ciudad.get("nombre"),
                         "localidad": localidad_de(c.get("direccion")) or None,
                         "url": fila_texto["url"], "urls": c.get("urls") or [], "licencias": c.get("licencias") or [],
                         "actividades": c.get("actividades") or [], "razon_social": c.get("nombre"),
                         "punto_anh": ({"lat": c["lat"], "lng": c["lng"]} if c.get("lat") is not None else None)}},
        "estado": "nuevo", "ubicacion": "aproximada" if lat is not None else "no_encontrada",
        "foto_ref": None, "texto_leido": _texto_para_el_revisor(depto, fila_texto, combustibles, visibles,
                                                                  lat is not None),
        "lector": None, "duplicado_de": None, "fuente_url": fila_texto["url"] or None,
    }


def _sin_genericas(nombre: str | None) -> str:
    """El nombre sin lo que comparten todas las estaciones («Estación de Servicio», la sociedad): lo que queda es lo
    que la distingue."""
    n = normalizar(nombre)
    n = re.sub(r"\b(estacion(es)? de servicios?|estacion(es)?|servicios?|gnv|ypfb|s r l|s a|srl|sa|sucursal \d*)\b", " ", n)
    return " ".join(n.split())


def buscar_repetido(fila: dict, comercios: list[dict], indice_tel: dict, nombres: list[dict], repo) -> dict | None:
    """El comercio de URUKU que ya es esta estación: mismo teléfono; con punto, nombre parecido a menos de
    METROS_REPETIDO; sin punto, nombre parecido en la misma ciudad."""
    tels = [t for t in (normalizar_telefono(x) for x in (fila.get("whatsapp"), fila.get("telefono")) if x) if t]
    # `telefono` puede traer varios («46722353 / 6637692»): se parten
    for x in re.split(r"\s*/\s*", str(fila.get("telefono") or "")):
        t = normalizar_telefono(x) if x else None
        if t and all(t.numero != y.numero for y in tels):
            tels.append(t)
    por_tel = tarjetas.buscar_repetido(repo, tels, indice_tel) if tels else None
    if por_tel:
        return por_tel
    propio = _sin_genericas(fila["nombre"])
    if fila.get("lat") is not None:
        for c in comercios:
            d = metros_entre(fila["lat"], fila["lng"], c.get("lat"), c.get("lng"))
            if d is not None and d <= METROS_REPETIDO and (
                    mismo_nombre(fila["nombre"], c.get("nombre")) or (propio and mismo_nombre(propio, _sin_genericas(c.get("nombre"))))):
                return c
        return None
    if not propio:
        return None
    return next(({"id": c["id"], "nombre": c["nombre"]} for c in nombres
                 if mismo_nombre(propio, _sin_genericas(c["nombre"]))), None)


# ───────────────────────────────────────────────────────────── cargar

@dataclass
class Resumen:
    leidas: int = 0
    unidas: int = 0
    descartadas: Counter = field(default_factory=Counter)
    nuevas: int = 0
    ya_estaban: int = 0
    repetidas: int = 0
    con_whatsapp: int = 0
    con_telefono: int = 0
    con_punto: int = 0
    sin_rubro: int = 0
    por_ciudad: Counter = field(default_factory=Counter)


def cargar(repo, crudas: list[dict], depto: Departamento, ciudades: list[dict], *, dry_run: bool = False,
           limite: int | None = None, usar_punto: bool = True, mostrar: Callable[[str], None] = print) -> Resumen:
    r = Resumen(leidas=len(crudas))
    rubros: dict[str, bool] = {}

    def valido(slug: str) -> bool:
        if slug not in rubros:
            rubros[slug] = bool(repo.get_rubro_id(slug))
        return rubros[slug]

    estaciones = unir_actividades(crudas)
    r.unidas = len(crudas) - len(estaciones)
    utiles: list[tuple[dict, dict]] = []
    for c in estaciones:
        motivo = motivo_descarte(c)
        ciudad = None if motivo else asignar_ciudad(c, ciudades)
        if motivo or not ciudad:
            r.descartadas[motivo or "fuera_de_ciudad"] += 1
            continue
        utiles.append((c, ciudad))
    utiles.sort(key=lambda x: (normalizar(x[1].get("nombre")), normalizar(x[0].get("nombre"))))
    if limite is not None:
        utiles = utiles[: max(0, limite)]
    por_ciudad: dict[str, tuple] = {}
    for c, ciudad in utiles:
        fila = armar_fila(c, depto=depto, ciudad=ciudad, rubros_validos=valido, usar_punto=usar_punto)
        if dry_run and repo.get_importado_por_fuente(FUENTE, fila["fuente_id"]):    # al guardar lo dice el INSERT
            r.ya_estaban += 1
            continue
        if ciudad["id"] not in por_ciudad:
            por_ciudad[ciudad["id"]] = (repo.comercios_con_coords(ciudad["id"]),
                                        tarjetas.indice_telefonos(repo), indice_nombres(repo, ciudad["id"]))
        comercios, indice_tel, nombres = por_ciudad[ciudad["id"]]
        repetido = buscar_repetido(fila, comercios, indice_tel, nombres, repo)
        if repetido:
            fila["duplicado_de"] = repetido["id"]
        if not dry_run and repo.crear_importado(fila) is None:          # ya estaba (misma fuente_id)
            r.ya_estaban += 1
            continue
        r.nuevas += 1
        r.repetidas += 1 if repetido else 0
        r.con_whatsapp += 1 if fila["whatsapp"] else 0
        r.con_telefono += 1 if fila["telefono"] else 0
        r.con_punto += 1 if fila["lat"] is not None else 0
        r.sin_rubro += 0 if fila["rubro_slug"] else 1
        r.por_ciudad[ciudad.get("nombre") or ciudad["id"]] += 1
        if dry_run and r.nuevas <= 15:
            mostrar(f"  {fila['nombre'][:42]:42} | {str(ciudad.get('nombre'))[:10]:10} | "
                    f"{(fila['telefono'] or fila['whatsapp'] or '-')[:18]:18} | "
                    f"{'con punto' if fila['lat'] is not None else 'sin punto':9}"
                    + ("  (ya está en URUKU)" if repetido else ""))
    logger.info("importar_anh.cargado", departamento=depto.slug, nuevas=r.nuevas, ya_estaban=r.ya_estaban,
                repetidas=r.repetidas, guardado=not dry_run)
    return r


def _imprimir(r: Resumen, dry_run: bool, mostrar: Callable[[str], None]) -> None:
    mostrar(f"\nLeídos de la ANH:        {r.leidas}  (filas de líquidos y de GNV)")
    mostrar(f"Unidos (misma estación en líquidos y GNV): {r.unidas}")
    mostrar(f"Descartados:             {sum(r.descartadas.values())}  "
            + ", ".join(f"{k}: {v}" for k, v in r.descartadas.most_common()))
    mostrar(f"{'Entrarían' if dry_run else 'Nuevos en Importados'}:    {r.nuevas}")
    mostrar(f"Ya estaban:              {r.ya_estaban}")
    mostrar(f"Ya están en URUKU:       {r.repetidas}  (marcados como repetidos para revisar)")
    mostrar(f"Con WhatsApp (celular):  {r.con_whatsapp}")
    mostrar(f"Con teléfono fijo:       {r.con_telefono}")
    mostrar(f"Con punto de la ANH:     {r.con_punto}  (aproximado, a confirmar)")
    mostrar(f"Sin rubro (se elige en el panel): {r.sin_rubro}")
    mostrar("Por ciudad: " + (", ".join(f"{k} {v}" for k, v in r.por_ciudad.most_common()) or "-"))
    if dry_run:
        mostrar("\nSimulación: no se guardó nada. Repetir sin --dry-run para cargarlos (nada se publica solo).")


def main(argv: list[str] | None = None, repo=None, *, leer: Callable[..., list[dict]] | None = None,
         mostrar: Callable[[str], None] = print) -> int:
    ap = argparse.ArgumentParser(prog="importar_anh",
                                 description="Trae las estaciones de servicio de la ANH a Importados (nada se "
                                             "publica solo).")
    ap.add_argument("--departamento", required=True,
                    help="departamento: " + ", ".join(DEPARTAMENTOS) + " (p. ej. tarija)")
    ap.add_argument("--dry-run", action="store_true", help="muestra lo que cargaría, sin guardar nada")
    ap.add_argument("--limite", type=int, default=None, help="cargar sólo las primeras N (por ciudad y nombre)")
    ap.add_argument("--sin-punto", action="store_true",
                    help="ignora el punto que trae la ANH: las filas salen sin punto, para el ubicador")
    args = ap.parse_args(argv)
    depto = resolver_departamento(args.departamento)
    if not depto:
        print(f"Departamento desconocido «{args.departamento}». Usar: {', '.join(DEPARTAMENTOS)}.", file=sys.stderr)
        return 2
    if args.limite is not None and args.limite < 1:
        print("--limite tiene que ser 1 o más.", file=sys.stderr)
        return 2
    if repo is None:
        from app.db.repository import get_repo
        repo = get_repo()
    ciudades = ciudades_del_departamento(repo, depto)
    if not ciudades:
        print(f"No hay ciudades de {depto.nombre} (con centro) en la tabla `ciudades`.", file=sys.stderr)
        return 2
    mostrar(f"Departamento: {depto.nombre} (D={depto.codigo}) · ciudades: {', '.join(c['nombre'] for c in ciudades)}"
            f"{' · SIMULACIÓN' if args.dry_run else ''}")
    mostrar("Leyendo la ANH (2 páginas, con pausa)…")
    try:
        crudas = (leer or leer_anh)(depto)
    except Exception as exc:  # noqa: BLE001
        print(f"No se pudo leer la ANH: {type(exc).__name__}: {str(exc)[:300]}", file=sys.stderr)
        return 1
    r = cargar(repo, crudas, depto, ciudades, dry_run=args.dry_run, limite=args.limite,
               usar_punto=not args.sin_punto, mostrar=mostrar)
    _imprimir(r, args.dry_run, mostrar)
    return 0


if __name__ == "__main__":
    sys.exit(main())
