"""Traer las oficinas de la Aduana Nacional a `comercios_importados` (docs/vigia-fuentes.md, «Aduana: cómo se corre»).

    docker exec buscadonde-backend python -m app.services.importar_aduana --dry-run
    docker exec buscadonde-backend python -m app.services.importar_aduana

QUÉ ES
======

La Aduana Nacional de Bolivia publica dos páginas con las oficinas de todo el país (fronteras, aeropuertos, aduanas
interiores, gerencias regionales):

  /pagina-de-direcciones   una tarjeta por oficina: nombre, dirección, teléfono y un mapa de OpenStreetMap con su
                           punto (paginada: `?page=N`)
  /horariosAduana          una tabla por gerencia regional: oficina, lugar de atención y horarios

Se toman SÓLO los datos (nombre de la oficina, dirección, teléfono, horario, punto) y el enlace de origen: ningún
texto largo de la página se copia. Las dos se unen por el nombre de la oficina; una oficina que sólo aparece en los
horarios (sin dirección) no entra.

NADA SE PUBLICA SOLO
====================

Todo entra como `estado='nuevo'` a la cola de Importados con el rubro NO comercial `aduana` (migración 0199) y una
persona lo promueve, de a uno. Una oficina de la Aduana es un servicio público: al promover no es un comercio con
plan, y el teléfono va a `telefono`, nunca a `whatsapp`. Volver a correrlo no duplica ni pisa nada (`fuente_id` =
`aduana:<nombre de la oficina>`).

CIUDAD
======

Todo el país en una corrida. Cada oficina se asigna a una ciudad de la tabla `ciudades` por su localidad: la ciudad
que nombra la oficina («Aduana Frontera Bermejo») o su dirección y, si no, la que contiene su punto. Las que no
caen en una ciudad de la tabla se cuentan como `fuera_de_ciudad`: no se inventa una. El punto que da la Aduana se
guarda como `aproximada` (a confirmar) sólo si queda a menos de `MAX_KM_PUNTO` de su ciudad.

CORTESÍA
========

Un pedido por página de direcciones (4) y uno de horarios, con 2 s de pausa, un User-Agent genérico (nunca un
correo) y sólo hacia `www.aduana.gob.bo`. Los tests no salen a la red: `leer` es un falso.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import urlsplit

import structlog

from app.core.telefonos_foto import normalizar as normalizar_telefono
from app.core.telefonos_foto import numero_visible
from app.services import tarjetas
from app.services.cargas import metros_entre
from app.services.importar_anh import (DEPARTAMENTOS, PaginaInesperada, normalizar, TIMEOUT_SEG,
                                       USER_AGENT)
from app.services.importar_overture import RADIO_KM, RADIOS
from app.services.importar_turismo import indice_nombres, mismo_nombre

logger = structlog.get_logger()

FUENTE = "aduana"
RUBRO = "aduana"                                     # migración 0199 (no comercial)
URL_DIRECCIONES = "https://www.aduana.gob.bo/pagina-de-direcciones"
URL_HORARIOS = "https://www.aduana.gob.bo/horariosAduana"
HOST = "www.aduana.gob.bo"
PAUSA_SEG = 2.0
MAX_PAGINAS = 10                                     # tope de seguridad del paginado
MAX_TEXTO = tarjetas.MAX_TEXTO_LEIDO
MAX_HORARIO = 500
MAX_KM_PUNTO = 25.0                                  # el punto más lejos que esto de su ciudad no se usa
MAX_KM_CONTRADICCION = 200.0                         # un nombre que dice «Oruro» con el punto a 700 km no es Oruro
LAT_BO, LNG_BO = (-23.0, -9.5), (-69.8, -57.4)       # la caja de Bolivia (la frontera con Chile y Perú entra)


# ───────────────────────────────────────────────────────────── lectura (HTTP → HTML → filas crudas)

def _punto(lat, lng) -> tuple[float, float] | None:
    try:
        la, lo = float(lat), float(lng)
    except (TypeError, ValueError):
        return None
    return (la, lo) if LAT_BO[0] <= la <= LAT_BO[1] and LNG_BO[0] <= lo <= LNG_BO[1] else None


class _Tarjetas(HTMLParser):
    """Las tarjetas de `/pagina-de-direcciones`: el texto de cada `div.card-body` y el punto de su enlace de mapa
    (`…openstreetmap.org/?mlat=<lat>&mlon=<lng>`). Y los números de página del paginado (`?page=N`)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tarjetas: list[dict] = []
        self.paginas: set[int] = set()
        self._actual: dict | None = None
        self._en_mapa = False

    def handle_endtag(self, tag):
        if tag == "a" and self._en_mapa:           # el enlace «Abrir mapa» cierra la tarjeta (lo que sigue es el pie)
            self._en_mapa = False
            self._cerrar()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "div" and "card-body" in (a.get("class") or "").split():
            self._cerrar()
            self._actual = {"texto": [], "lat": None, "lng": None}
        elif tag == "a":
            href = a.get("href") or ""
            m = re.search(r"[?&]page=(\d+)", href)
            if m and "openstreetmap" not in href:
                self.paginas.add(int(m.group(1)))
            if self._actual is not None and "openstreetmap.org" in href:
                m = re.search(r"mlat=([-\d.]*)&(?:amp;)?mlon=([-\d.]*)", href)
                if m:
                    self._actual["lat"], self._actual["lng"] = m.group(1), m.group(2)
                self._en_mapa = True
        elif tag in ("p", "br") and self._actual is not None:
            self._actual["texto"].append("\n")

    def handle_data(self, data):
        if self._actual is not None:
            self._actual["texto"].append(data)

    def _cerrar(self):
        if self._actual is not None:
            self.tarjetas.append(self._actual)
            self._actual = None

    def close(self):
        super().close()
        self._cerrar()


_RE_ETIQUETA = re.compile(r"(Nombre de oficina|Direcci[oó]n|Tel[eé]fonos?)\s*:", re.IGNORECASE)


def _valores(texto: str) -> dict[str, str]:
    """`{nombre, direccion, telefono}` de una tarjeta: lo que sigue a cada rótulo hasta el siguiente. Si un rótulo
    se repite (la página a veces escribe «Dirección: Dirección: …») vale el último con contenido."""
    out: dict[str, str] = {}
    marcas = list(_RE_ETIQUETA.finditer(texto))
    for i, m in enumerate(marcas):
        fin = marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)
        valor = " ".join(texto[m.end():fin].replace("Abrir mapa", " ").split())
        n = normalizar(m.group(1))
        clave = "nombre" if n.startswith("nombre") else "direccion" if n.startswith("direccion") else "telefono"
        if valor or clave not in out:
            out[clave] = valor
    return out


def parsear_direcciones(html: str, *, url: str = URL_DIRECCIONES) -> tuple[list[dict], set[int]]:
    """`(oficinas, páginas)` de una página de direcciones. Cada oficina:
    `{nombre, direccion, telefono, lat, lng, url}`. Lanza `PaginaInesperada` si no hay tarjetas."""
    p = _Tarjetas()
    p.feed(html)
    p.close()
    oficinas = []
    for t in p.tarjetas:
        v = _valores("".join(t["texto"]))
        if not v.get("nombre"):
            continue
        punto = _punto(t["lat"], t["lng"])
        oficinas.append({"nombre": v["nombre"], "direccion": v.get("direccion", ""),
                         "telefono": v.get("telefono", ""),
                         "lat": punto[0] if punto else None, "lng": punto[1] if punto else None, "url": url})
    if not oficinas:
        raise PaginaInesperada("no se encontraron las tarjetas de oficinas (¿cambió el diseño de la página?)")
    return oficinas, p.paginas


class _Tablas(HTMLParser):
    """Todas las tablas de la página: `[{titulos: [...], filas: [[celda, ...], ...]}]`."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tablas: list[dict] = []
        self._tabla: dict | None = None
        self._fila: list[str] | None = None
        self._celda: list[str] | None = None
        self._es_titulo = False

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._tabla = {"titulos": [], "filas": []}
        elif self._tabla is None:
            return
        elif tag == "tr":
            self._fila = []
        elif tag in ("td", "th") and self._fila is not None:
            self._celda, self._es_titulo = [], tag == "th"

    def handle_endtag(self, tag):
        if self._tabla is None:
            return
        if tag in ("td", "th") and self._celda is not None and self._fila is not None:
            texto = " ".join("".join(self._celda).split())
            (self._tabla["titulos"] if self._es_titulo else self._fila).append(texto)
            self._celda = None
        elif tag == "tr" and self._fila is not None:
            if self._fila:
                self._tabla["filas"].append(self._fila)
            self._fila = None
        elif tag == "table":
            self.tablas.append(self._tabla)
            self._tabla = None

    def handle_data(self, data):
        if self._celda is not None:
            self._celda.append(data)


def parsear_horarios(html: str) -> list[dict]:
    """Las filas de `/horariosAduana`: `{oficina, lugar, ordinarios, extraordinarios}`. Lanza `PaginaInesperada` si
    no hay ninguna tabla con las columnas «Oficina» y «Lugar de atención»."""
    p = _Tablas()
    p.feed(html)
    p.close()
    filas: list[dict] = []
    for t in p.tablas:
        cols: dict[str, int] = {}
        for i, titulo in enumerate(t["titulos"]):
            n = normalizar(titulo)
            for clave, palabra in (("oficina", "oficina"), ("lugar", "lugar"), ("ordinarios", "ordinarios"),
                                   ("extraordinarios", "extraordinarios")):
                if palabra in n:
                    cols.setdefault(clave, i)
        if "oficina" not in cols or "lugar" not in cols:
            continue
        for f in t["filas"]:
            def celda(k, f=f):
                return f[cols[k]] if k in cols and cols[k] < len(f) else ""
            if celda("oficina"):
                filas.append({"oficina": celda("oficina"), "lugar": celda("lugar"),
                              "ordinarios": celda("ordinarios"), "extraordinarios": celda("extraordinarios")})
    if not filas:
        raise PaginaInesperada("no se encontró la tabla de horarios (¿cambió el diseño de la página?)")
    return filas


def _pedir(url: str) -> tuple[str, str]:
    """`(html, url final)`. El único lugar que sale a la red; no sale de `www.aduana.gob.bo`."""
    import httpx

    r = httpx.get(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "es"}, timeout=TIMEOUT_SEG,
                  follow_redirects=True)
    r.raise_for_status()
    if urlsplit(str(r.url)).hostname != HOST:
        raise ValueError(f"La Aduana redirigió fuera de {HOST}: {r.url}")
    try:
        html = r.content.decode("utf-8")
    except UnicodeDecodeError:
        html = r.content.decode("latin-1")
    return html, str(r.url)


def leer_aduana(*, pedir: Callable[[str], tuple[str, str]] | None = None, pausa: float = PAUSA_SEG) -> dict:
    """`{"direcciones": [...], "horarios": [...]}`: todas las páginas de direcciones y la de horarios. Lanza si la
    Aduana no contesta o cambió las páginas."""
    pedir = pedir or _pedir
    html, url = pedir(URL_DIRECCIONES)
    direcciones, paginas = parsear_direcciones(html, url=URL_DIRECCIONES)
    for n in sorted(x for x in paginas if 0 < x < MAX_PAGINAS):
        time.sleep(pausa)
        html, _ = pedir(f"{URL_DIRECCIONES}?page={n}")
        mas, _ = parsear_direcciones(html, url=URL_DIRECCIONES)
        direcciones += mas
    time.sleep(pausa)
    html, _ = pedir(URL_HORARIOS)
    return {"direcciones": direcciones, "horarios": parsear_horarios(html)}


# ───────────────────────────────────────────────────────────── normalizar (puro)

_TIPOS = (("oficina central", "Oficina central"), ("gerencia regional", "Gerencia regional"),
          ("puesto de control", "Puesto de control"), ("aeropuerto", "Aeropuerto"), ("postal", "Postal"),
          ("zona franca", "Zona franca"), ("frontera", "Frontera"), ("interior", "Interior"),
          ("exterior", "Exterior"))


def tipo_de(nombre: str | None) -> str:
    """El tipo de oficina para `subcategoria`: Frontera, Interior, Aeropuerto…"""
    n = normalizar(nombre)
    return next((etiqueta for clave, etiqueta in _TIPOS if clave in n), "Oficina")


def nombre_limpio(nombre: str | None) -> str:
    return " ".join(str(nombre or "").split())[:200]


def direccion_limpia(texto: str | None) -> str | None:
    """La dirección sin el rótulo repetido, el punto final ni los enlaces."""
    t = " ".join(str(texto or "").split())
    t = re.sub(r"^Direcci[oó]n\s*:\s*", "", t, flags=re.IGNORECASE).strip(" .")[:200]
    return None if not t or re.search(r"https?://|www\.", t, re.IGNORECASE) else t


def slug_oficina(nombre: str | None) -> str:
    return normalizar(nombre).replace(" ", "-")


def fuente_id_de(nombre: str | None) -> str:
    return f"{FUENTE}:{slug_oficina(nombre)}"


_RE_INTERNO = re.compile(r"\b(?:int(?:erno)?s?\.?)\s*[\d\s\-–y,]*", re.IGNORECASE)


def telefonos_de(crudo: str | None, area_por_defecto: str = "") -> list:
    """Los teléfonos de un texto de la Aduana (`(4) 6642937-6648600 (Int. 6001)`, `Teléfonos: 2818050-2818358`).
    Se descartan el fax y los internos; un fijo de 7 dígitos lleva el código de área que da la página (`(4)`) o, si no
    lo da, el del departamento de la ciudad. Lo que no es un teléfono de Bolivia se ignora."""
    texto = re.split(r"\bfax\b", str(crudo or ""), flags=re.IGNORECASE)[0]
    texto = _RE_INTERNO.sub(" ", texto)
    texto = re.sub(r"\(\s*591\s*\)", " ", texto)
    m = re.search(r"\(\s*(\d)\s*\)", texto)
    area = m.group(1) if m else None
    texto = re.sub(r"\(\s*\d\s*\)", " ", texto)
    suelta = re.search(r"(?<!\d)(\d)\s*-\s*(?=\d{7}(?!\d))", texto)                # «(591) - 2 - 2128008»
    if suelta:
        area = area or suelta.group(1)
        texto = texto.replace(suelta.group(0), "")
    area = area or area_por_defecto
    out = []
    for digitos in re.findall(r"(?<!\d)\d{7,8}(?!\d)", texto):
        if len(digitos) == 7 and area:
            digitos = area + digitos
        t = normalizar_telefono(digitos)
        if t and all(t.numero != x.numero for x in out):
            out.append(t)
    return out


_DIAS = "lunes|martes|miercoles|miércoles|jueves|viernes|sabado|sábado|domingo"


def _horas_legibles(texto: str) -> str:
    t = " ".join(str(texto or "").split())
    t = re.sub(rf"\b({_DIAS}) - ({_DIAS})\b", r"\1 a \2", t, flags=re.IGNORECASE)
    return re.sub(r"\b(\d{1,2}:\d{2})\s+(\d{1,2}:\d{2})\b", r"\1 a \2", t)


def horario_de(filas: list[dict]) -> str | None:
    """El horario de una oficina en una línea: `Lugar: ordinarios; extraordinarios · Otro lugar: …`."""
    partes = []
    for f in filas:
        dias = "; ".join(x for x in (_horas_legibles(f.get("ordinarios")), _horas_legibles(f.get("extraordinarios")))
                         if x)
        if dias:
            partes.append(f"{' '.join(str(f.get('lugar') or '').split())}: {dias}".strip(": "))
    return " · ".join(partes)[:MAX_HORARIO] or None


_SOBRAN = frozenset({"de", "la", "el", "administracion", "oficina"})


def _clave_horario(nombre: str | None) -> tuple[str, ...]:
    return tuple(w for w in normalizar(nombre).split() if w not in _SOBRAN)


def horarios_de_oficina(nombre: str, horarios: list[dict]) -> tuple[list[dict], set[tuple]]:
    """Las filas de horarios de una oficina (`(filas, claves usadas)`): la de nombre igual o, si no hay, la que es
    un comienzo del nombre («Aduana Interior Oruro» para «Aduana Interior Oruro - Pasto Grande») o a la inversa."""
    mia = _clave_horario(nombre)
    claves = {_clave_horario(h["oficina"]) for h in horarios}
    if mia in claves:
        elegida = mia
    else:
        candidatas = [c for c in claves if c and mia and (mia[:len(c)] == c or c[:len(mia)] == mia)]
        if not candidatas:
            return [], set()
        elegida = max(candidatas, key=len)
    return [h for h in horarios if _clave_horario(h["oficina"]) == elegida], {elegida}


def unir(datos: dict) -> tuple[list[dict], int]:
    """Las oficinas con sus horarios y la cantidad de oficinas de la página de horarios que no tienen dirección."""
    horarios = datos.get("horarios") or []
    usadas: set[tuple] = set()
    oficinas = []
    for o in datos.get("direcciones") or []:
        filas, claves = horarios_de_oficina(o["nombre"], horarios)
        usadas |= claves
        oficinas.append({**o, "horarios": filas})
    sin_direccion = len({_clave_horario(h["oficina"]) for h in horarios} - usadas)
    return oficinas, sin_direccion


# ───────────────────────────────────────────────────────────── ciudad

def ciudades_del_pais(repo) -> list[dict]:
    """Las ciudades de la tabla `ciudades` con su centro (`lat`/`lng`) y su departamento."""
    out = []
    for c in repo.list_ciudades() or []:
        fila = repo.get_ciudad(c["slug"]) or {}
        if fila.get("lat") is not None and fila.get("lng") is not None:
            out.append(fila)
    return out


def _primera_ciudad(texto: str | None, ciudades: list[dict]) -> dict | None:
    """La ciudad cuyo nombre aparece primero en el texto (palabras enteras, sin tildes)."""
    t = f" {normalizar(texto)} "
    mejor: tuple[int, int, dict] | None = None
    for c in ciudades:
        n = normalizar(c.get("nombre"))
        pos = t.find(f" {n} ") if n else -1
        if pos >= 0 and (mejor is None or (pos, -len(n)) < (mejor[0], mejor[1])):
            mejor = (pos, -len(n), c)
    return mejor[2] if mejor else None


def _ciudad_de_la_direccion(direccion: str | None, ciudades: list[dict]) -> dict | None:
    """La ciudad que es el primer o el último tramo de la dirección (`YACUIBA, AVDA. LOS DEMOS`; `Madrid 390 entre
    América y Colón, Oruro`). Una ciudad en el medio («Carretera a Oruro», «Carretera Antigua Puerto Quijarro») es
    un camino, no la localidad."""
    tramos = [normalizar(t) for t in re.split(r"[,;:]|\s[-–]\s", str(direccion or "")) if t.strip()]
    if not tramos:
        return None
    return next((c for c in ciudades if normalizar(c.get("nombre")) in (tramos[0], tramos[-1])), None)


def asignar_ciudad(o: dict, ciudades: list[dict], *, punto_unico: bool = True) -> dict | None:
    """La ciudad de URUKU de una oficina, o None (`fuera_de_ciudad`; no se inventa una). Primero la que nombra la
    oficina, después la localidad de su dirección (siempre que el punto no las contradiga: a más de
    MAX_KM_CONTRADICCION no es esa), y si no, la que contiene su punto (sólo si el punto no se repite en otra
    oficina: algunas copian el de otra)."""
    def contradice(c: dict) -> bool:
        d = metros_entre(o.get("lat"), o.get("lng"), c["lat"], c["lng"])
        return d is not None and d > MAX_KM_CONTRADICCION * 1000

    for c in (_primera_ciudad(o.get("nombre"), ciudades), _ciudad_de_la_direccion(o.get("direccion"), ciudades)):
        if c and not contradice(c):
            return c
    if o.get("lat") is None or o.get("lng") is None or not punto_unico:
        return None
    mejor: tuple[float, dict] | None = None
    for c in ciudades:
        d = metros_entre(o["lat"], o["lng"], c["lat"], c["lng"])
        if d is not None and d <= RADIOS.get(c.get("slug"), RADIO_KM) * 1000 and (mejor is None or d < mejor[0]):
            mejor = (d, c)
    return mejor[1] if mejor else None


def area_de(ciudad: dict) -> str:
    d = DEPARTAMENTOS.get(normalizar(ciudad.get("departamento")).replace(" ", "-"))
    return d.area if d else ""


# ───────────────────────────────────────────────────────────── armar la fila

def armar_fila(o: dict, *, ciudad: dict, rubros_validos: Callable[[str], bool], usar_punto: bool = True) -> dict:
    """Una oficina (con sus horarios) → una fila de `comercios_importados` (nueva, sin revisar). Los teléfonos van
    todos a `telefono`: nunca a `whatsapp` (es el número que la Aduana publica para llamar)."""
    tels = telefonos_de(o.get("telefono"), area_de(ciudad))[:3]
    telefono = " / ".join(numero_visible(t.numero) for t in tels)[:80] or None
    lat = lng = None
    if usar_punto and o.get("lat") is not None and o.get("lng") is not None:
        d = metros_entre(o["lat"], o["lng"], ciudad["lat"], ciudad["lng"])
        if d is not None and d <= MAX_KM_PUNTO * 1000:
            lat, lng = round(float(o["lat"]), 6), round(float(o["lng"]), 6)
    nombre = nombre_limpio(o["nombre"])
    tipo = tipo_de(nombre)
    horario = horario_de(o.get("horarios") or [])
    direccion = direccion_limpia(o.get("direccion"))
    texto = "\n".join(x for x in (
        f"Aduana Nacional · oficinas · {ciudad.get('nombre')}",
        f"Oficina: {nombre} ({tipo})",
        f"Dirección: {direccion}" if direccion else None,
        f"Teléfono: {telefono}" if telefono else None,
        f"Horario: {horario}" if horario else None,
        f"Punto de la Aduana: {lat:.6f}, {lng:.6f} (a confirmar)" if lat is not None else None,
        f"Origen: {o.get('url') or URL_DIRECCIONES}",
    ) if x)[:MAX_TEXTO]
    return {
        "fuente": FUENTE, "fuente_id": fuente_id_de(nombre), "ciudad_id": ciudad["id"],
        "nombre": nombre, "categoria": "oficina_aduana", "subcategoria": tipo,
        "rubro_slug": RUBRO if rubros_validos(RUBRO) else None,
        "lat": lat, "lng": lng, "telefono": telefono, "whatsapp": None, "website": None, "email": None,
        "horario": horario, "direccion": direccion,
        "tags": {"aduana": {"oficina": nombre, "tipo": tipo, "municipio": ciudad.get("nombre"),
                            "url": o.get("url") or URL_DIRECCIONES, "url_horarios": URL_HORARIOS,
                            "horarios": o.get("horarios") or [], "telefono_original": o.get("telefono") or None,
                            "punto_aduana": ({"lat": o["lat"], "lng": o["lng"]} if o.get("lat") is not None
                                             else None)}},
        "estado": "nuevo", "ubicacion": "aproximada" if lat is not None else "no_encontrada",
        "foto_ref": None, "texto_leido": texto, "lector": None, "duplicado_de": None,
        "fuente_url": o.get("url") or URL_DIRECCIONES,
    }


def buscar_repetido(nombre: str, telefonos: list, indice_tel: dict, nombres: list[dict], repo) -> dict | None:
    """El comercio de URUKU que ya es esta oficina: mismo teléfono o nombre parecido en la misma ciudad (el punto de
    la Aduana es a mano y se corre varias cuadras: no sirve para medir cercanía)."""
    por_tel = tarjetas.buscar_repetido(repo, telefonos, indice_tel) if telefonos else None
    if por_tel:
        return por_tel
    return next(({"id": c["id"], "nombre": c["nombre"]} for c in nombres if mismo_nombre(nombre, c["nombre"])), None)


# ───────────────────────────────────────────────────────────── cargar

@dataclass
class Resumen:
    leidas: int = 0
    filas_horarios: int = 0
    horarios_sin_direccion: int = 0
    descartadas: Counter = field(default_factory=Counter)
    nuevas: int = 0
    ya_estaban: int = 0
    repetidas: int = 0
    con_telefono: int = 0
    con_horario: int = 0
    con_punto: int = 0
    sin_rubro: int = 0
    por_ciudad: Counter = field(default_factory=Counter)


def cargar(repo, datos: dict, ciudades: list[dict], *, dry_run: bool = False, limite: int | None = None,
           usar_punto: bool = True, mostrar: Callable[[str], None] = print) -> Resumen:
    oficinas, sin_direccion = unir(datos)
    r = Resumen(leidas=len(oficinas), filas_horarios=len(datos.get("horarios") or []),
                horarios_sin_direccion=sin_direccion)
    rubros: dict[str, bool] = {}

    def valido(slug: str) -> bool:
        if slug not in rubros:
            rubros[slug] = bool(repo.get_rubro_id(slug))
        return rubros[slug]

    repetidos_de_punto = Counter((round(o["lat"], 5), round(o["lng"], 5)) for o in oficinas
                                 if o.get("lat") is not None)
    vistos: set[str] = set()
    utiles: list[tuple[dict, dict]] = []
    for o in oficinas:
        if len(nombre_limpio(o["nombre"])) < 2:
            r.descartadas["sin_nombre"] += 1
            continue
        if fuente_id_de(o["nombre"]) in vistos:                       # la página repite la tarjeta
            r.descartadas["repetida_en_la_pagina"] += 1
            continue
        unico = o.get("lat") is None or repetidos_de_punto[(round(o["lat"], 5), round(o["lng"], 5))] == 1
        ciudad = asignar_ciudad(o, ciudades, punto_unico=unico)
        if not ciudad:
            r.descartadas["fuera_de_ciudad"] += 1
            continue
        vistos.add(fuente_id_de(o["nombre"]))
        utiles.append((o, ciudad))
    utiles.sort(key=lambda x: (normalizar(x[1].get("nombre")), normalizar(x[0].get("nombre"))))
    if limite is not None:
        utiles = utiles[: max(0, limite)]
    indice_tel = tarjetas.indice_telefonos(repo) if utiles else {}
    por_ciudad: dict[str, list[dict]] = {}
    for o, ciudad in utiles:
        fila = armar_fila(o, ciudad=ciudad, rubros_validos=valido, usar_punto=usar_punto)
        if dry_run and repo.get_importado_por_fuente(FUENTE, fila["fuente_id"]):    # al guardar lo dice el INSERT
            r.ya_estaban += 1
            continue
        if ciudad["id"] not in por_ciudad:
            por_ciudad[ciudad["id"]] = indice_nombres(repo, ciudad["id"])
        telefonos = telefonos_de(o.get("telefono"), area_de(ciudad))
        repetido = buscar_repetido(fila["nombre"], telefonos, indice_tel, por_ciudad[ciudad["id"]], repo)
        if repetido:
            fila["duplicado_de"] = repetido["id"]
        if not dry_run and repo.crear_importado(fila) is None:          # ya estaba (misma fuente_id)
            r.ya_estaban += 1
            continue
        r.nuevas += 1
        r.repetidas += 1 if repetido else 0
        r.con_telefono += 1 if fila["telefono"] else 0
        r.con_horario += 1 if fila["horario"] else 0
        r.con_punto += 1 if fila["lat"] is not None else 0
        r.sin_rubro += 0 if fila["rubro_slug"] else 1
        r.por_ciudad[ciudad.get("nombre") or ciudad["id"]] += 1
        if dry_run and r.nuevas <= 20:
            mostrar(f"  {fila['nombre'][:44]:44} | {str(ciudad.get('nombre'))[:14]:14} | {fila['subcategoria']:17} | "
                    f"{'horario' if fila['horario'] else 'sin horario':11} | "
                    f"{'con punto' if fila['lat'] is not None else 'sin punto'}"
                    + ("  (ya está en URUKU)" if repetido else ""))
    logger.info("importar_aduana.cargado", nuevas=r.nuevas, ya_estaban=r.ya_estaban, repetidas=r.repetidas,
                guardado=not dry_run)
    return r


def _imprimir(r: Resumen, dry_run: bool, mostrar: Callable[[str], None]) -> None:
    mostrar(f"\nLeídas de la Aduana:     {r.leidas}  (oficinas de la página de direcciones)")
    mostrar(f"Filas de horarios:       {r.filas_horarios}  ({r.horarios_sin_direccion} oficinas de horarios sin "
            "dirección: no entran)")
    mostrar(f"Descartadas:             {sum(r.descartadas.values())}  "
            + ", ".join(f"{k}: {v}" for k, v in r.descartadas.most_common()))
    mostrar(f"{'Entrarían' if dry_run else 'Nuevas en Importados'}:    {r.nuevas}")
    mostrar(f"Ya estaban:              {r.ya_estaban}")
    mostrar(f"Ya están en URUKU:       {r.repetidas}  (marcadas como repetidas para revisar)")
    mostrar(f"Con teléfono:            {r.con_telefono}")
    mostrar(f"Con horario:             {r.con_horario}")
    mostrar(f"Con punto de la Aduana:  {r.con_punto}  (aproximado, a confirmar)")
    mostrar(f"Sin rubro (se elige en el panel): {r.sin_rubro}")
    mostrar("Por ciudad: " + (", ".join(f"{k} {v}" for k, v in r.por_ciudad.most_common()) or "-"))
    if dry_run:
        mostrar("\nSimulación: no se guardó nada. Repetir sin --dry-run para cargarlas (nada se publica solo).")


def main(argv: list[str] | None = None, repo=None, *, leer: Callable[..., dict] | None = None,
         mostrar: Callable[[str], None] = print) -> int:
    ap = argparse.ArgumentParser(prog="importar_aduana",
                                 description="Trae las oficinas de la Aduana Nacional a Importados (nada se "
                                             "publica solo).")
    ap.add_argument("--dry-run", action="store_true", help="muestra lo que cargaría, sin guardar nada")
    ap.add_argument("--limite", type=int, default=None, help="cargar sólo las primeras N (por ciudad y nombre)")
    ap.add_argument("--sin-punto", action="store_true",
                    help="ignora el punto que trae la Aduana: las filas salen sin punto, para el ubicador")
    args = ap.parse_args(argv)
    if args.limite is not None and args.limite < 1:
        print("--limite tiene que ser 1 o más.", file=sys.stderr)
        return 2
    if repo is None:
        from app.db.repository import get_repo
        repo = get_repo()
    ciudades = ciudades_del_pais(repo)
    if not ciudades:
        print("No hay ciudades (con centro) en la tabla `ciudades`.", file=sys.stderr)
        return 2
    mostrar(f"Aduana Nacional · {len(ciudades)} ciudades en la tabla{' · SIMULACIÓN' if args.dry_run else ''}")
    mostrar("Leyendo la Aduana (5 páginas, con pausa)…")
    try:
        datos = (leer or leer_aduana)()
    except Exception as exc:  # noqa: BLE001
        print(f"No se pudo leer la Aduana: {type(exc).__name__}: {str(exc)[:300]}", file=sys.stderr)
        return 1
    r = cargar(repo, datos, ciudades, dry_run=args.dry_run, limite=args.limite, usar_punto=not args.sin_punto,
               mostrar=mostrar)
    _imprimir(r, args.dry_run, mostrar)
    return 0


if __name__ == "__main__":
    sys.exit(main())
