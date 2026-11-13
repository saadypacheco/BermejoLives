"""Ubicar direcciones bolivianas por esquina o por cuadra (docs/importar-turismo.md, «Ubicar por esquinas»).

POR QUÉ
=======
Las direcciones llegan como «Z/Central, Calle La Madrid #282 esq. Sucre» o «C/Sucre entre Corrado y Domingo Paz
#0966». Nominatim no entiende «Z/», «B/», «esq.» ni «entre», y Tarija no tiene numeración en OpenStreetMap: aun
limpia, la dirección cae en la calle y no en el número. La forma boliviana de dar una dirección es la esquina o
la cuadra, así que se ubica así (en este orden):

  1. «A esq. B»      -> el punto donde se tocan una cuadra de A y una de B (los extremos de las cuadras son las
                        esquinas: `calles_tramos` guarda una fila por cuadra).
  2. «A entre B y C» -> el medio entre la esquina A-B y la esquina A-C (si están a 600 m o menos).
  3. Nominatim con la dirección limpia («Calle La Madrid 282»): punto aproximado sobre la calle.
  4. Nada: queda sin punto y se marca a mano.

SIN ADIVINAR: los nombres se comparan con tolerancia (tildes, abreviaturas, «La Madrid» = «Madrid», «Gral.» =
«General»), pero si dos calles DISTINTAS empatan, o una esquina cae en dos lugares lejanos, no hay punto. Todo
punto sigue siendo aproximado hasta que una persona lo confirma. Todo lo que se devuelve cae dentro de la caja
de la ciudad (la misma de `tarjetas.buscar_direccion`).

COMANDO (se corre a mano dentro del contenedor del backend)
===========================================================
    python -m app.services.ubicar_direccion --ciudad tarija --dry-run
    python -m app.services.ubicar_direccion --ciudad tarija [--limite N]

Vuelve a ubicar los importados `estado='nuevo'` de fuente turismo/tarjeta que quedaron sin punto y tienen
dirección. Sin `--dry-run` guarda `lat`/`lng` con `ubicacion='aproximada'`. Si Nominatim falla 5 veces seguidas
deja de pedirle, pero sigue con las esquinas.
"""
from __future__ import annotations

import argparse
import math
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable

import structlog

from app.services import tarjetas
from app.services.calles_mapa import proyector

logger = structlog.get_logger()

METODOS = ("esquina", "cuadra", "calle")
ESQUINA_TOL_M = 20.0            # dos extremos de cuadras a esta distancia o menos son la misma esquina
AGRUPAR_M = 2 * ESQUINA_TOL_M   # los puntos de una esquina (avenidas de doble mano) se juntan a esta distancia
CUADRA_MAX_M = 600.0            # «entre A y B»: las dos esquinas no pueden estar más lejos que esto
FALLAS_NOMINATIM_SEGUIDAS = 5
TOPE_LISTADO = 1000             # PostgREST corta en 1000 sin avisar


# ═══════════════════════════════════════════════════════════ normalizar nombres de calle

#: Variantes del apóstrofe («O'Connor», «O´connor», «O’connor»): todas pasan a «'».
_RE_APOSTROFES = re.compile(r"[´`’‘ʼ′ʹ]")

ABREVIATURAS = {
    "gral": "general", "mcal": "mariscal", "cnl": "coronel", "cnel": "coronel", "crnl": "coronel",
    "dr": "doctor", "dra": "doctora", "tte": "teniente", "cap": "capitan", "pdte": "presidente",
    "pte": "presidente", "ing": "ingeniero", "lic": "licenciado", "prof": "profesor", "hno": "hermano",
    "sta": "santa", "sto": "santo",
}
#: Palabras que no distinguen una calle de otra («La Madrid» = «Madrid», «6 de Junio» = «6 Junio»).
_RELLENO = {"la", "las", "el", "los", "de", "del"}
#: Títulos: «General Trigo» y «Trigo» pueden ser la misma calle (nivel 1 de la comparación).
_TITULOS = {"general", "mariscal", "coronel", "capitan", "teniente", "presidente", "doctor", "doctora",
            "ingeniero", "licenciado", "profesor", "hermano", "padre", "monsenor", "don", "dona"}
_TIPOS_PALABRA = {"calle", "avenida", "av", "avda", "pasaje", "pje", "psje", "camino", "c"}


def normalizar(texto: str | None) -> str:
    """Un nombre de calle en minúsculas, sin tildes ni puntuación, con las abreviaturas escritas («Gral.» ->
    «general»). El apóstrofe se conserva unificado: «O´connor» -> «o'connor»."""
    s = _RE_APOSTROFES.sub("'", str(texto or ""))
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    s = re.sub(r"[^a-z0-9' ]+", " ", s)
    tokens = [t.strip("'") for t in s.split()]
    return " ".join(ABREVIATURAS.get(t, t) for t in tokens if t)


def _sin_tipo(tokens: list[str]) -> list[str]:
    """Quita «calle», «avenida», «pasaje»… del principio (en OSM el nombre trae el tipo: «Calle Sucre»)."""
    if len(tokens) > 1 and tokens[0] in _TIPOS_PALABRA:
        return tokens[1:]
    return tokens


def clave_exacta(nombre: str | None) -> tuple[str, ...]:
    """La clave de comparación de un nombre (nivel 0): sin tipo, sin relleno, sin apóstrofes."""
    tokens = _sin_tipo(normalizar(nombre).split())
    return tuple(t.replace("'", "") for t in tokens if t not in _RELLENO)


def clave_sin_titulos(nombre: str | None) -> tuple[str, ...]:
    """Nivel 1: lo mismo, sin títulos («General Trigo» -> «trigo»)."""
    return tuple(t for t in clave_exacta(nombre) if t not in _TITULOS)


def _distancia_edicion_a_lo_sumo_1(a: str, b: str) -> bool:
    """¿Se pasa de a a b con a lo sumo una inserción, borrado o cambio de letra?"""
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) > len(b):
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    if len(a) == len(b):
        return a[i + 1:] == b[i + 1:]
    return a[i:] == b[i + 1:]


# ═══════════════════════════════════════════════════════════ partir la dirección

@dataclass(frozen=True)
class Partes:
    """Lo que dice una dirección. Los nombres vienen normalizados (`normalizar`) y sin «Calle»/«Av.»."""
    calle: str | None = None
    numero: str | None = None
    esquina: str | None = None
    entre: tuple[str, str] | None = None
    tipo: str | None = None          # 'calle' · 'avenida' · 'pasaje' (lo que decía la dirección) o None
    #: La calle como se escribió (con tildes y mayúsculas, sin «Calle»/«Av.»): para la consulta a Nominatim.
    calle_texto: str | None = field(default=None, compare=False)


#: «B/Senac», «Z/Central», «Bo. X», «Barrio X», «Zona X», «Urb. X»: zona o barrio, no la calle.
_RE_ZONA = re.compile(r"^\s*(?:(?:z|b|bo|zona|barrio|urb|urbanizacion|urbanización)\s*[/.]\s*"
                      r"|(?:zona|barrio|urb|urbanizacion|urbanización)\b\.?\s+)", re.IGNORECASE)
#: Dónde empieza una calle: «Calle», «C/», «Av.», «Avenida», «Pasaje»… (no «Avaroa»: pide el punto o el espacio).
_RE_TIPO_EN_TEXTO = re.compile(r"(?<![A-Za-zÁ-ú])(?:avenida\b|avda\.?|av\.|av(?=\s)|calle\b|pasaje\b|pje\.?|c/|c\.(?=\s*\S))",
                               re.IGNORECASE)
_RE_TIPO_INICIO = re.compile(r"^\s*(?:(?P<av>avenida|avda|av)\.\s*|(?P<av2>avenida|avda|av)\s+"
                             r"|(?P<c>calle|c)\.\s*|(?P<c2>calle)\s+|(?P<c3>c)/\s*"
                             r"|(?P<p>pasaje|pje|psje)\.?\s+)", re.IGNORECASE)
#: Pegado: «FatimaAv. La Paz», «B/San Roque C/Sucre» -> con espacio.
_RE_PEGADO = re.compile(r"([a-záéíóúüñ])(?=(?:Av\.|Av\s|Avenida\b|Calle\b|C/))")
_RE_NUMERO = re.compile(r"(?:#|\bN[º°o]\.?|\bNro\.?)\s*(\d{1,6})", re.IGNORECASE)
#: Referencias que no son la dirección: «pasando la Av. Fuerza…», «Frente al Avión».
_RE_REFERENCIA = re.compile(r"\b(?:pasando|frente|enfrente|diagonal|cerca|al\s+lado|junto|detr[aá]s|contiguo|"
                            r"pr[oó]ximo|saliendo|a\s+(?:una|dos|media|\d+)\s+cuadras?|a\s+media\s+cuadra)\b.*$",
                            re.IGNORECASE)
_RE_CLAVE = re.compile(r"\b(entre|esquina|esq|casi)\b\.?", re.IGNORECASE)
_RE_ELIPSIS = re.compile(r"…|\.{3,}")


def _nombre_de(texto: str | None) -> tuple[str | None, str | None]:
    """`(nombre normalizado, tipo)` de un pedazo como «C/Avaroa» o «Av. Los Ceibos». Un nombre con menos de 3
    letras (y sin números) es basura de un texto cortado y se descarta."""
    t = (texto or "").strip(" ,.;:-")
    t = re.sub(r"\s+y\s*$", "", t, flags=re.IGNORECASE).strip(" ,.;:-")
    tipo = None
    m = _RE_TIPO_INICIO.match(t)
    if m:
        tipo = "avenida" if (m.group("av") or m.group("av2")) else ("pasaje" if m.group("p") else "calle")
        t = t[m.end():]
    nombre = normalizar(t)
    letras = sum(ch.isalpha() for ch in nombre)
    if not nombre or not (letras >= 3 or any(ch.isdigit() for ch in nombre)):
        return None, tipo
    return nombre, tipo


def _texto_de(texto: str) -> str:
    """El nombre tal como se escribió, sin el tipo del principio («C/Sucre» -> «Sucre»)."""
    t = (texto or "").strip(" ,.;:-")
    m = _RE_TIPO_INICIO.match(t)
    return re.sub(r"\s+", " ", t[m.end():] if m else t).strip(" ,.;:-")


def partir_direccion(texto: str | None) -> Partes:
    """Parte una dirección en calle, número, esquina y «entre». Pura y tolerante: lo que no entiende queda en None.

    «Z/Central, Calle La Madrid #282 esq. Sucre» -> calle «la madrid», número «282», esquina «sucre».
    «C/Sucre entre Corrado y Domingo Paz #0966»  -> calle «sucre», número «966», entre («corrado», «domingo paz»).
    Se descartan zona y barrio, «C/», «Calle», «Av.», «Nº», «#», las referencias («frente a…», «pasando la…») y
    los textos cortados con «…». «casi» cuenta como esquina. Un «entre» con un solo nombre legible se toma como
    esquina con ese nombre."""
    t = _RE_APOSTROFES.sub("'", str(texto or "")).replace("\n", ", ")
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return Partes()
    truncada = bool(_RE_ELIPSIS.search(t))
    t = _RE_ELIPSIS.sub(" ", t)
    t = _RE_PEGADO.sub(r"\1 ", t)
    t = re.sub(r"[()\[\]]", ",", t)

    # 1. segmentos: se van la zona y el barrio, y lo que viene antes de la primera calle («Parque Bolívar,»)
    segmentos: list[str] = []
    for seg in re.split(r"[,;]", t):
        seg = seg.strip()
        if not seg:
            continue
        m = _RE_ZONA.match(seg)
        if m:
            resto = seg[m.end():]
            tipo = _RE_TIPO_EN_TEXTO.search(resto)
            if not tipo:
                continue
            seg = resto[tipo.start():]
        segmentos.append(seg)
    if not segmentos:
        return Partes()
    desde = next((i for i, s in enumerate(segmentos) if _RE_TIPO_EN_TEXTO.search(s)), None)
    if desde is not None:
        segmentos = segmentos[desde:]
        primero = _RE_TIPO_EN_TEXTO.search(segmentos[0])
        segmentos[0] = segmentos[0][primero.start():]
    else:                                                  # sin «Calle»/«Av.»: el segmento con número, o el primero
        con_numero = next((s for s in segmentos if re.search(r"\d", s)), segmentos[0])
        segmentos = [con_numero]
    t = " ".join(segmentos)

    # 2. número explícito (#, Nº, No, Nro): puede venir al final, detrás de la esquina
    numero = None
    m = _RE_NUMERO.search(t)
    if m:
        numero = str(int(m.group(1)))
        t = _RE_NUMERO.sub(" ", t)
    cortada = _RE_REFERENCIA.search(t)
    if cortada:
        t = t[:cortada.start()]
        truncada = False
    t = re.sub(r"\s+", " ", t).strip()

    # 3. calle / esquina / entre
    clave = _RE_CLAVE.search(t)
    principal = t[:clave.start()] if clave else t
    resto = t[clave.end():] if clave else ""
    calle, tipo = _nombre_de(principal.strip())
    calle_texto = _texto_de(principal) if calle else None
    if numero is None and principal.strip():
        m = re.match(r"^(.*[^\W\d_].*?)\s+(\d{1,5})\s*$", principal.strip())
        if m:                                              # «Calle La Madrid 282»; «Calle 15 de Abril» no
            calle, tipo = _nombre_de(m.group(1))
            calle_texto = _texto_de(m.group(1)) if calle else None
            numero = str(int(m.group(2)))

    esquina: str | None = None
    entre: tuple[str, str] | None = None
    if clave:
        siguiente = _RE_CLAVE.search(resto)                # «esq. X entre …»: sólo vale lo primero
        if siguiente:
            resto = resto[:siguiente.start()]
        piezas = re.split(r"\s+y\s+", resto.strip(), maxsplit=1) if clave.group(1).lower() == "entre" else [resto]
        if truncada and piezas and piezas[-1].strip():     # la última palabra quedó cortada: no se confía
            piezas[-1] = " ".join(piezas[-1].split()[:-1])
        nombres = [n for n in (_nombre_de(p)[0] for p in piezas) if n]
        if clave.group(1).lower() == "entre":
            if len(nombres) == 2:
                entre = (nombres[0], nombres[1])
            elif len(nombres) == 1:
                esquina = nombres[0]
        elif nombres:
            esquina = nombres[0]
    return Partes(calle=calle, numero=numero, esquina=esquina, entre=entre, tipo=tipo, calle_texto=calle_texto)


# ═══════════════════════════════════════════════════════════ geometría (pura)

def _punto(p) -> tuple[float, float] | None:
    try:
        lat, lng = float(p[0]), float(p[1])
    except (TypeError, ValueError, IndexError, KeyError):
        return None
    return (lat, lng) if math.isfinite(lat) and math.isfinite(lng) else None


def extremos(cuadras: list[list]) -> list[tuple[float, float]]:
    """Los dos extremos (las esquinas) de cada cuadra, sin repetir."""
    vistos: dict[tuple[float, float], tuple[float, float]] = {}
    for geom in cuadras:
        for p in (geom[0], geom[-1]) if geom else ():
            pt = _punto(p)
            if pt:
                vistos.setdefault((round(pt[0], 6), round(pt[1], 6)), pt)
    return list(vistos.values())


def _agrupar(puntos: list[tuple[float, float]], radio_m: float) -> list[tuple[float, float]]:
    """Junta los puntos a `radio_m` o menos unos de otros (cadena) y devuelve el centro de cada grupo."""
    if not puntos:
        return []
    xy = proyector(sum(p[0] for p in puntos) / len(puntos))
    planos = [xy(*p) for p in puntos]
    grupo = list(range(len(puntos)))

    def raiz(i: int) -> int:
        while grupo[i] != i:
            grupo[i] = grupo[grupo[i]]
            i = grupo[i]
        return i

    for i in range(len(puntos)):
        for j in range(i + 1, len(puntos)):
            if math.hypot(planos[i][0] - planos[j][0], planos[i][1] - planos[j][1]) <= radio_m:
                grupo[raiz(i)] = raiz(j)
    por_grupo: dict[int, list[tuple[float, float]]] = {}
    for i, p in enumerate(puntos):
        por_grupo.setdefault(raiz(i), []).append(p)
    return [(sum(p[0] for p in g) / len(g), sum(p[1] for p in g) / len(g)) for g in por_grupo.values()]


def esquinas_entre(cuadras_a: list[list], cuadras_b: list[list],
                   tol_m: float = ESQUINA_TOL_M) -> list[tuple[float, float]]:
    """Los lugares donde se tocan las calles A y B: un punto por esquina (centro), o [] si no se tocan.

    Una esquina es un extremo de cuadra de A y un extremo de cuadra de B a `tol_m` o menos. Las avenidas de doble
    mano dan varios pares pegados: se juntan en uno solo."""
    pa, pb = extremos(cuadras_a), extremos(cuadras_b)
    if not pa or not pb:
        return []
    xy = proyector(sum(p[0] for p in pa + pb) / len(pa + pb))
    qa, qb = [xy(*p) for p in pa], [xy(*p) for p in pb]
    medios = []
    for (la, a), (lb, b) in ((x, y) for x in zip(pa, qa) for y in zip(pb, qb)):
        if math.hypot(a[0] - b[0], a[1] - b[1]) <= tol_m:
            medios.append(((la[0] + lb[0]) / 2, (la[1] + lb[1]) / 2))
    return _agrupar(medios, AGRUPAR_M)


def distancia_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    xy = proyector((a[0] + b[0]) / 2)
    pa, pb = xy(*a), xy(*b)
    return math.hypot(pa[0] - pb[0], pa[1] - pb[1])


def punto_de_esquina(cuadras_a: list[list], cuadras_b: list[list]) -> tuple[float, float] | None:
    """El punto de «A esq. B»: la única esquina donde se tocan. Dos esquinas distintas = ambiguo = None."""
    pts = esquinas_entre(cuadras_a, cuadras_b)
    return pts[0] if len(pts) == 1 else None


def punto_de_cuadra(cuadras_a: list[list], cuadras_b: list[list], cuadras_c: list[list],
                    max_m: float = CUADRA_MAX_M) -> tuple[float, float] | None:
    """El punto de «A entre B y C»: el medio entre la esquina A-B y la esquina A-C, si están a `max_m` o menos
    (y no son la misma esquina). Si hay más de un par posible, no se adivina: None."""
    ab, ac = esquinas_entre(cuadras_a, cuadras_b), esquinas_entre(cuadras_a, cuadras_c)
    pares = [(p, q) for p in ab for q in ac if ESQUINA_TOL_M < distancia_m(p, q) <= max_m]
    if len(pares) != 1:
        return None
    (p, q) = pares[0]
    return ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)


# ═══════════════════════════════════════════════════════════ las calles de la ciudad

class Calles:
    """Las cuadras de una ciudad agrupadas por nombre de calle, para buscar por nombre tolerante."""

    def __init__(self, tramos: list[dict] | None):
        self._por_clave: dict[tuple[str, ...], dict] = {}
        for t in tramos or []:
            nombre = str(t.get("nombre") or "").strip()
            geom = [p for p in (_punto(x) for x in (t.get("geom") or [])) if p]
            clave = clave_exacta(nombre)
            if not clave or len(geom) < 2 or t.get("activo") is False:
                continue
            grupo = self._por_clave.setdefault(clave, {"nombre": nombre, "cuadras": []})
            grupo["cuadras"].append(geom)
        self._sin_titulos: dict[tuple[str, ...], set] = {}
        for clave in self._por_clave:
            sin = tuple(t for t in clave if t not in _TITULOS)
            if sin:
                self._sin_titulos.setdefault(sin, set()).add(clave)

    def __bool__(self) -> bool:
        return bool(self._por_clave)

    def __len__(self) -> int:
        return len(self._por_clave)

    def buscar(self, nombre: str | None) -> tuple[tuple[str, ...], dict] | None:
        """`(clave, grupo)` de la calle con ese nombre, o None si no está o hay dudas.

        Nivel 0: mismo nombre (sin tildes, tipo ni artículos). Nivel 1: igual sin títulos («Trigo» = «General
        Trigo»). Nivel 2: una letra de diferencia (sin números de por medio: «15» y «16» son calles distintas).
        Un nivel que da dos calles distintas es un empate: no se sigue bajando ni se elige."""
        q0 = clave_exacta(nombre)
        if not q0:
            return None
        if q0 in self._por_clave:
            return q0, self._por_clave[q0]
        q1 = tuple(t for t in q0 if t not in _TITULOS)
        if q1:
            claves = self._sin_titulos.get(q1, set())
            if len(claves) == 1:
                k = next(iter(claves))
                return k, self._por_clave[k]
            if len(claves) > 1:
                return None
        unida = " ".join(q0)
        if len(unida) >= 8 and not any(ch.isdigit() for ch in unida):
            parecidas = [k for k in self._por_clave
                         if not any(ch.isdigit() for ch in " ".join(k))
                         and _distancia_edicion_a_lo_sumo_1(unida, " ".join(k))]
            if len(parecidas) == 1:
                return parecidas[0], self._por_clave[parecidas[0]]
        return None


def cargar_calles(repo, ciudad: dict | None) -> Calles:
    """Lee UNA vez las cuadras de la ciudad. Sin ciudad, o si la base falla, queda vacío (se sigue con Nominatim)."""
    cid = (ciudad or {}).get("id")
    if not cid:
        return Calles([])
    try:
        return Calles(repo.list_calles_tramos(cid))
    except Exception as exc:  # noqa: BLE001
        logger.warning("ubicar_direccion.sin_calles", error=type(exc).__name__)
        return Calles([])


def _en_la_caja(ciudad: dict | None, punto: tuple[float, float], radio_km: float) -> bool:
    lat_c, lng_c = tarjetas._numero((ciudad or {}).get("lat")), tarjetas._numero((ciudad or {}).get("lng"))
    if lat_c is None or lng_c is None:
        return True
    oeste, norte, este, sur = tarjetas.caja_de_la_ciudad(lat_c, lng_c, float(radio_km))
    return oeste <= punto[1] <= este and sur <= punto[0] <= norte


def _por_geometria(calles: Calles, partes: Partes) -> tuple[str, tuple[float, float], str] | None:
    """`(metodo, (lat, lng), descripción)` por esquina o cuadra, o None."""
    a = calles.buscar(partes.calle)
    if not a:
        return None
    if partes.entre:
        b, c = calles.buscar(partes.entre[0]), calles.buscar(partes.entre[1])
        if b and c and len({a[0], b[0], c[0]}) == 3:
            p = punto_de_cuadra(a[1]["cuadras"], b[1]["cuadras"], c[1]["cuadras"])
            if p:
                return "cuadra", p, f"{a[1]['nombre']} entre {b[1]['nombre']} y {c[1]['nombre']}"
    if partes.esquina:
        b = calles.buscar(partes.esquina)
        if b and a[0] != b[0]:
            p = punto_de_esquina(a[1]["cuadras"], b[1]["cuadras"])
            if p:
                return "esquina", p, f"{a[1]['nombre']} esquina {b[1]['nombre']}"
    return None


_PALABRA_TIPO = {"calle": "Calle", "avenida": "Avenida", "pasaje": "Pasaje"}


def consulta_limpia(partes: Partes, original: str) -> str:
    """La dirección para Nominatim: «Calle la madrid 282». Si no se entendió la calle, el texto original."""
    if not partes.calle:
        return re.sub(r"\s+", " ", original).strip()
    return " ".join(x for x in (_PALABRA_TIPO.get(partes.tipo or ""), partes.calle_texto or partes.calle, partes.numero) if x)


def ubicar(repo, direccion: str | None, ciudad: dict | None, *, tramos: "Calles | list[dict] | None" = None,
           pedir: Callable[[dict], list] | None = None, radio_km: float = tarjetas.RADIO_CIUDAD_KM,
           usar_mapas: bool = True) -> dict | None:
    """El punto de una dirección dentro de la ciudad: `{lat, lng, display_name, metodo}` o None.

    `metodo` es 'esquina', 'cuadra' (con las calles de la ciudad) o 'calle' (Nominatim sobre la dirección
    limpia). `tramos` es la lista de `calles_tramos` o un `Calles` ya armado (la corrida masiva lo lee una sola
    vez); sin él se lee de `repo`, y sólo si la dirección trae esquina o «entre». Con `usar_mapas=False` no se
    consulta Nominatim. Lanza `tarjetas.UbicacionNoDisponible` si hace falta Nominatim y no contesta."""
    original = re.sub(r"\s+", " ", str(direccion or "")).strip()[:tarjetas.MAX_DIRECCION]
    if len(original) < 4:
        return None
    partes = partir_direccion(original)

    if partes.calle and (partes.esquina or partes.entre):
        calles = tramos if isinstance(tramos, Calles) else (Calles(tramos) if tramos is not None
                                                            else cargar_calles(repo, ciudad))
        hallado = _por_geometria(calles, partes) if calles else None
        if hallado and _en_la_caja(ciudad, hallado[1], radio_km):
            metodo, (lat, lng), descripcion = hallado
            ciudad_nombre = str((ciudad or {}).get("nombre") or "").strip()
            return {"lat": round(lat, 6), "lng": round(lng, 6), "metodo": metodo,
                    "display_name": (f"{descripcion}, {ciudad_nombre}" if ciudad_nombre else descripcion)[:300]}

    if not usar_mapas:
        return None
    limpia = consulta_limpia(partes, original)
    punto = tarjetas.buscar_direccion(limpia, ciudad, pedir=pedir, radio_km=radio_km)
    # Si la limpia no aparece, el texto como vino (lo que hacía antes la carga de tarjetas): una dirección que
    # Nominatim ya encontraba no puede dejar de encontrarse por haberla limpiado.
    if not punto and limpia.strip().lower() != str(original).strip().lower():
        punto = tarjetas.buscar_direccion(original, ciudad, pedir=pedir, radio_km=radio_km)
    return {**punto, "metodo": "calle"} if punto else None


# ═══════════════════════════════════════════════════════════ línea de comandos

FUENTES = ("turismo", "tarjeta")


def main(argv: list[str] | None = None, repo=None, *, pedir: Callable[[dict], list] | None = None,
         mostrar: Callable[[str], None] = print) -> int:
    ap = argparse.ArgumentParser(prog="ubicar_direccion", description="Vuelve a ubicar los importados sin punto "
                                 "(fuente turismo o tarjeta) por esquina, cuadra o calle.")
    ap.add_argument("--ciudad", required=True, help="slug de la ciudad (p. ej. tarija)")
    ap.add_argument("--dry-run", action="store_true", help="muestra lo que ubicaría, sin guardar nada")
    ap.add_argument("--limite", type=int, default=None, help="probar sólo con los primeros N")
    args = ap.parse_args(argv)
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

    candidatos: list[dict] = []
    for fuente in FUENTES:
        filas = repo.list_importados("nuevo", ciudad["id"], None, limite=TOPE_LISTADO, fuente=fuente)
        if len(filas) >= TOPE_LISTADO:
            mostrar(f"Aviso: hay {TOPE_LISTADO} o más de fuente «{fuente}»; volver a correr para seguir con el resto.")
        candidatos += [f for f in filas if f.get("lat") is None and len(str(f.get("direccion") or "").strip()) >= 4]
    if args.limite is not None:
        candidatos = candidatos[: args.limite]

    calles = cargar_calles(repo, ciudad)
    mostrar(f"Ciudad: {ciudad['nombre']} · {len(candidatos)} importados sin punto con dirección · "
            f"{len(calles)} calles cargadas{' · SIMULACIÓN' if args.dry_run else ''}")
    if not calles:
        mostrar("Esta ciudad no tiene calles cargadas (se importan desde el panel, «Calles y horarios»): "
                "sólo se usa Nominatim.")

    fallas = 0

    def contado(params: dict) -> list:                   # cuenta las fallas SEGUIDAS de Nominatim
        nonlocal fallas
        try:
            filas = (pedir or tarjetas._pedir_nominatim)(params)
        except Exception:
            fallas += 1
            raise
        fallas = 0
        return filas

    usar_mapas = True
    cuenta: Counter = Counter()
    sin_punto: list[dict] = []
    for f in candidatos:
        try:
            punto = ubicar(repo, f["direccion"], ciudad, tramos=calles, pedir=contado, usar_mapas=usar_mapas)
        except tarjetas.UbicacionNoDisponible:
            punto = None
            if usar_mapas and fallas >= FALLAS_NOMINATIM_SEGUIDAS:
                usar_mapas = False
                mostrar(f"Nominatim falló {fallas} veces seguidas: se deja de pedirle, se sigue sólo con las esquinas.")
        if not punto:
            cuenta["sin_punto"] += 1
            sin_punto.append(f)
            continue
        cuenta[punto["metodo"]] += 1
        mostrar(f"  [{punto['metodo']:7}] {str(f.get('nombre') or '-')[:34]:34} | {str(f['direccion'])[:60]}")
        if not args.dry_run:
            repo.marcar_importado(f["id"], {"lat": punto["lat"], "lng": punto["lng"], "ubicacion": "aproximada"})
        logger.info("ubicar_direccion.ubicado", importado=f.get("id"), metodo=punto["metodo"],
                    guardado=not args.dry_run)

    mostrar(f"\nRevisados:       {len(candidatos)}")
    mostrar(f"Por esquina:     {cuenta['esquina']}")
    mostrar(f"Por cuadra:      {cuenta['cuadra']}")
    mostrar(f"Por calle:       {cuenta['calle']}")
    mostrar(f"Sin encontrar:   {cuenta['sin_punto']}")
    for f in sin_punto:
        mostrar(f"  - {str(f.get('nombre') or '-')[:34]:34} | {str(f['direccion'])[:70]}")
    if args.dry_run:
        mostrar("\nSimulación: no se guardó nada. Repetir sin --dry-run para guardar los puntos (aproximados).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
