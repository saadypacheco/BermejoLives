"""Leer teléfonos en el texto que sale de una foto (docs/telefonos-en-fotos.md).

Módulo PURO: sin red, sin base, sin disco. Recibe el texto que devolvió el OCR (o Gemini) y devuelve los
números que parecen teléfonos de verdad, normalizados a E.164 con «+».

POR QUÉ TANTO FILTRO
====================
Un lector de fotos devuelve todo lo que parece un número: fechas de una promoción, horarios, precios,
años, el NIT del cartel, códigos de producto. Cada uno que se cuela es una propuesta falsa que una persona
tiene que descartar a mano (y 6000 portadas son muchas propuestas). Y al revés: tirar un teléfono bueno es
perder un WhatsApp que el comercio no tiene cargado. El criterio es: **ante la duda, se descarta lo que
tiene forma de otra cosa y se conserva lo que tiene forma de teléfono**; la persona que revisa decide.

QUÉ ENTRA
=========
- Bolivia: celular de 8 dígitos que empieza en 6 o 7 (`+591XXXXXXXX`), con o sin el 591. Fijo: código de
  área de un dígito (2, 3 o 4) + 7 dígitos, o sea 8 en total y empieza en 2, 3 o 4 (`tipo='fijo'`).
  Un número de 7 dígitos sin código de área NO entra: no se sabe de qué ciudad es.
- Argentina (ciudades de frontera): `54` + 10 dígitos, o 10 dígitos que empiezan con un código de área de
  la región. El 9 de celular se normaliza: `+549…` es celular y `+54…` no marca nada.
  UN NÚMERO ARGENTINO SIN EL 9 NI EL «15» SALE COMO `fijo`: los celulares y los fijos de Salta o Orán
  comparten rango (387 4xx-xxxx existe de los dos lados), así que no hay forma de adivinarlo; `fijo` es lo
  conservador porque no entra en el lote automático (la persona lo puede usar como WhatsApp a mano).

QUÉ SE TIRA
===========
Menos de 8 dígitos útiles, fechas, horarios, precios con decimales, años sueltos, números repetidos o
escalonados (`11111111`, `12345678`), lo que está pegado a «NIT», «CI», «cód», «Bs», «$»…, y **los números
de URUKU** (los públicos y los de respaldo; ver `numeros_de_uruku`).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

PREFIJO_BO = "591"
PREFIJO_AR = "54"
#: Códigos de área argentinos de la región de frontera (Orán, Tartagal/Salvador Mazza, La Quiaca, Salta,
#: Jujuy), del más largo al más corto: el prefijo más específico gana.
AREAS_AR = ("3878", "3875", "3885", "3886", "387", "388")
#: Cuántos comercios con el mismo número lo vuelven «compartido» (galería, administración, agente).
UMBRAL_COMPARTIDO = 4
MAX_TEXTO_LEIDO = 60

#: Los números de URUKU que NUNCA son del comercio: el público (67671888), el explorador (67677803), el
#: Anfitrión de los volantes viejos, el de la API oficial de Meta y el Registrador que sólo lee
#: (frontend/lib/contacto.ts). A esto se suman los de la config (`numeros_de_uruku`).
NUMEROS_URUKU_FIJOS = frozenset({
    "59167671888", "59167677803", "59175314737", "59167991916", "59164610187",
})

# Palabras que, pegadas ANTES del número, dicen que no es un teléfono.
_ANTES = frozenset({
    "nit", "ci", "i.", "t.", "ruc", "cuit", "cuil", "dni", "cod", "cod.", "cód", "cód.", "codigo", "código",
    "ref", "ref.", "sku", "art", "art.", "articulo", "artículo", "factura", "fact", "fact.", "lote", "serie",
    "precio", "bs", "bs.", "bob", "usd", "us$", "ars", "$", "cp", "cuenta", "cta", "cta.", "iva", "stock",
    "tarjeta", "nro.factura", "autorizacion", "autorización", "aut", "aut.",
})
# Palabras que, pegadas DESPUÉS del número, dicen que es un precio, una hora o una medida.
_DESPUES = frozenset({
    "bs", "bs.", "bob", "usd", "$", "pesos", "bolivianos", "dolares", "dólares", "hs", "hs.", "hrs", "hrs.", "horas",
    "am", "pm", "años", "kg", "gr", "grs", "ml", "cm", "mm", "mts", "litros", "unidades", "off", "%",
})

# Letras (con tildes), el símbolo de peso, números con sus separadores. Lo demás (comas, dos puntos sueltos,
# guiones largos…) separa y no cuenta.
_RE_TOKEN = re.compile(r"(?P<palabra>[^\W\d_]+\.?|\$|%)|(?P<num>\+?\(?\d[\d()./:\-]*)")
_RE_FECHA = re.compile(r"^(\d{1,4})[/.\-](\d{1,2})[/.\-](\d{1,4})$")
_RE_ANIO = re.compile(r"^(19|20)\d{2}$")
_RE_DECIMALES = re.compile(r"^\d[\d.]*[.,]\d{1,2}$")


@dataclass(frozen=True)
class Telefono:
    """Un número leído: `numero` en E.164 con «+», `tipo` `celular` o `fijo`, `texto_leido` lo que se vio."""
    numero: str
    tipo: str
    texto_leido: str


# ───────────────────────────────────────────────────────────── los números de URUKU

def numeros_de_uruku() -> frozenset[str]:
    """Los números de URUKU en E.164 SIN «+» (`59167671888`): los fijos de arriba y los del `.env`
    (`WA_CONTACTO_PUBLICO`, `BOT_WHATSAPP_NUMERO`, `WA_NUMEROS_PROPIOS`, `WA_NUMEROS_GRUPO`,
    `WA_NUMEROS_EXPLORADOR`, `WA_CONTACTO_EXPLORADOR`). Se lee cada vez: el costo es mínimo y así un cambio
    del `.env` se ve sin reiniciar la lectura."""
    from app.core.config import _numeros_propios, settings
    from app.core.telefono import normalizar_whatsapp

    out = set(NUMEROS_URUKU_FIJOS)
    for crudo in (settings.wa_contacto_publico, settings.bot_whatsapp_numero, settings.wa_contacto_explorador):
        n = normalizar_whatsapp(crudo) if crudo else None
        if n:
            out.add(n)
    for variable, crudo in (("WA_NUMEROS_PROPIOS", settings.wa_numeros_propios),
                            ("WA_NUMEROS_GRUPO", settings.wa_numeros_grupo),
                            ("WA_NUMEROS_EXPLORADOR", settings.wa_numeros_explorador)):
        if crudo and crudo.strip():
            out |= set(_numeros_propios(crudo, variable))
    return frozenset(out)


def clave_de_comparacion(valor: str | None) -> str:
    """Una forma única para comparar el mismo número escrito distinto: sólo dígitos, con el 591 puesto a los
    locales y sin el 9 de celular argentino. Vacío si no hay dígitos."""
    digitos = re.sub(r"\D", "", str(valor or ""))
    if digitos.startswith("00"):
        digitos = digitos[2:]
    if not digitos:
        return ""
    if digitos.startswith("549") and len(digitos) == 13:
        return "54" + digitos[3:]
    if len(digitos) == 8 and digitos[0] in "234567":
        return PREFIJO_BO + digitos
    return digitos


def es_de_uruku(numero: str | None) -> bool:
    clave = clave_de_comparacion(numero)
    return bool(clave) and any(clave_de_comparacion(u) == clave for u in numeros_de_uruku())


def mismo_numero(a: str | None, b: str | None) -> bool:
    """¿Es el mismo teléfono aunque uno tenga «+591», espacios o el 9 argentino y el otro no?"""
    ca, cb = clave_de_comparacion(a), clave_de_comparacion(b)
    return bool(ca) and ca == cb


# ───────────────────────────────────────────────────────────── presentación

def whatsapp_de(numero: str) -> str:
    """El número como se guarda en `comercios.whatsapp` (E.164 sin «+»)."""
    return re.sub(r"\D", "", numero)


def numero_visible(numero: str) -> str:
    """El número como se lee en voz alta: `+591 7012 3456`, `+591 4 661 2345`, `+54 9 3878 51-2345`."""
    d = whatsapp_de(numero)
    if d.startswith("591") and len(d) == 11:
        resto = d[3:]
        if resto[0] in "67":
            return f"+591 {resto[:4]} {resto[4:]}"
        return f"+591 {resto[0]} {resto[1:4]} {resto[4:]}"
    if (d.startswith("549") and len(d) == 13) or (d.startswith("54") and len(d) == 12):
        celular = d.startswith("549") and len(d) == 13
        resto = d[3:] if celular else d[2:]
        area = _area_ar(resto) or resto[:3]
        abonado = resto[len(area):]
        return f"+54 {'9 ' if celular else ''}{area} {abonado[:-4]}-{abonado[-4:]}"
    return f"+{d}"


# ───────────────────────────────────────────────────────────── normalizar un número

def _area_ar(digitos: str) -> str | None:
    return next((a for a in AREAS_AR if digitos.startswith(a)), None)


def _parece_repetido(nacional: str) -> bool:
    """`11111111`, `70707070`, `12345678`, `76543210`: lo que no es un número de nadie."""
    if len(set(nacional)) <= 2:
        return True
    pasos = {(int(b) - int(a)) % 10 for a, b in zip(nacional, nacional[1:])}
    return pasos <= {1} or pasos <= {9}


def _es_fecha_compacta(d: str) -> bool:
    """`20261105`, `05112026`: una fecha escrita sin separadores."""
    if len(d) != 8:
        return False
    for y, m, dd in ((d[:4], d[4:6], d[6:]), (d[4:], d[2:4], d[:2]), (d[4:], d[:2], d[2:4])):
        if y[:2] in ("19", "20") and 1 <= int(m) <= 12 and 1 <= int(dd) <= 31:
            return True
    return False


def normalizar(valor: str | None) -> Telefono | None:
    """El teléfono de UN número escrito como sea (`+591 7012-3456`, `(4) 661 2345`, `387 15 4123456`), o None
    si no es un teléfono de Bolivia ni de la frontera argentina. No mira el contexto (eso lo hace `extraer`)."""
    if not valor:
        return None
    digitos = re.sub(r"\D", "", str(valor))
    if digitos.startswith("00"):
        digitos = digitos[2:]
    if not digitos or len(digitos) > 15 or _es_fecha_compacta(digitos):
        return None
    texto = str(valor).strip()[:MAX_TEXTO_LEIDO]

    # ── Bolivia ──
    nacional_bo = None
    if digitos.startswith(PREFIJO_BO) and len(digitos) == 11:
        nacional_bo = digitos[3:]
    elif len(digitos) == 8:
        nacional_bo = digitos
    if nacional_bo and nacional_bo[0] in "23467":
        if _parece_repetido(nacional_bo):
            return None
        return Telefono("+591" + nacional_bo, "celular" if nacional_bo[0] in "67" else "fijo", texto)

    # ── Argentina ──
    explicito = False                       # escribió el 9 (o el 15): es celular
    ar = None
    if digitos.startswith(PREFIJO_AR) and len(digitos) in (12, 13):
        resto = digitos[2:]
        if len(resto) == 11 and resto[0] == "9":
            explicito, resto = True, resto[1:]
        ar = resto if len(resto) == 10 else None
    elif len(digitos) == 11 and digitos[0] == "0":
        ar = digitos[1:]                    # (0387) 412 3456: el 0 de discado nacional
    elif len(digitos) == 10:
        ar = digitos
    elif len(digitos) == 13 and digitos[0] == "0":
        # 0387 15 4123456: sin el 0, área + «15» + abonado; el «15» es el que marca el celular
        sin_cero = digitos[1:]
        area = _area_ar(sin_cero)
        if area and sin_cero[len(area):len(area) + 2] == "15":
            explicito, ar = True, area + sin_cero[len(area) + 2:]
    elif len(digitos) == 12:
        area = _area_ar(digitos)
        if area and digitos[len(area):len(area) + 2] == "15":
            explicito, ar = True, area + digitos[len(area) + 2:]
    if ar and len(ar) == 10 and _area_ar(ar):
        if _parece_repetido(ar[len(_area_ar(ar)):]):
            return None
        return Telefono(("+549" if explicito else "+54") + ar, "celular" if explicito else "fijo", texto)
    return None


# ───────────────────────────────────────────────────────────── extraer de un texto

def _es_fecha(tok: str) -> bool:
    m = _RE_FECHA.match(tok)
    if not m:
        return False
    a, b, c = (int(x) for x in m.groups())
    if len(m.group(1)) == 4:                              # AAAA-MM-DD
        return 1 <= b <= 12 and 1 <= c <= 31
    return 1 <= a <= 31 and 1 <= b <= 12 and (len(m.group(3)) in (2, 4))   # DD-MM-AA(AA)


def _envenenado(tok: str) -> bool:
    """Un pedazo que, por su forma, no puede ser parte de un teléfono: hora (`20:00`), fecha, fracción
    (`24/7`), precio con decimales (`1250.50`)."""
    limpio = tok.strip("().-")
    return (":" in tok or "/" in tok or _es_fecha(limpio) or
            bool(_RE_DECIMALES.match(limpio) and len(re.sub(r"\D", "", limpio)) >= 5))


def _limpio(tok: str) -> str:
    """El pedazo sin separadores colgando (`70123456.`, `(4`)."""
    return tok.strip(".-/:")


def _es_hhmm(d: str) -> bool:
    return len(d) == 4 and int(d[:2]) <= 24 and int(d[2:]) < 60


def _parece_horario_o_anio(tokens: list[str]) -> bool:
    """`20 00 22 00`, `2000 2200`, `2024 2025`: pedazos que juntos arman 8 dígitos pero son horas o años."""
    d = [re.sub(r"\D", "", t) for t in tokens]
    if len(d) == 4 and all(len(x) == 2 for x in d):
        return int(d[0]) <= 24 and int(d[1]) < 60 and int(d[2]) <= 24 and int(d[3]) < 60
    if len(d) == 2 and all(len(x) == 4 for x in d):
        return all(_RE_ANIO.match(x) or _es_hhmm(x) for x in d)
    return False


def extraer(texto: str | None) -> list[Telefono]:
    """Los teléfonos que hay en un texto, sin repetir, en el orden en que aparecen.

    `texto` es lo que devolvió el lector: el OCR (una línea por renglón leído) o la lista de Gemini (un
    número por línea, tal como estaba escrito). Un teléfono puede venir partido en pedazos separados por
    espacios (`70 123 456`, `+591 7012 3456`): se prueba juntar pedazos seguidos, del grupo más largo al más
    corto, y se queda con el primero que es un número válido."""
    if not texto:
        return []
    propios = {clave_de_comparacion(p) for p in numeros_de_uruku()}
    vistos: set[str] = set()
    out: list[Telefono] = []
    for linea in str(texto).splitlines():
        tokens = [(m.lastgroup, m.group()) for m in _RE_TOKEN.finditer(linea)]
        i = 0
        while i < len(tokens):
            if tokens[i][0] != "num":
                i += 1
                continue
            j = i
            while j < len(tokens) and tokens[j][0] == "num":
                j += 1
            corrida = [_limpio(t) for _, t in tokens[i:j]]
            antes = tokens[i - 1][1].lower() if i > 0 else ""
            despues = tokens[j][1].lower() if j < len(tokens) else ""
            i = j
            if antes in _ANTES or despues in _DESPUES:
                continue
            for tel in _telefonos_de_la_corrida(corrida, propios):
                if tel.numero not in vistos:
                    vistos.add(tel.numero)
                    out.append(tel)
    return out


def _telefonos_de_la_corrida(corrida: list[str], propios: set[str]) -> list[Telefono]:
    """Parte una corrida de pedazos numéricos en teléfonos (el grupo válido más largo primero). `propios` son
    las claves de comparación de los números de URUKU: esos se saltean."""
    salida: list[Telefono] = []
    n = len(corrida)
    k = 0
    while k < n:
        avance = 1
        for fin in range(min(n, k + 6), k, -1):
            grupo = corrida[k:fin]
            if any(_envenenado(t) for t in grupo) or _parece_horario_o_anio(grupo):
                continue
            tel = normalizar(" ".join(grupo))
            if not tel:
                continue
            avance = fin - k
            if clave_de_comparacion(tel.numero) not in propios:
                salida.append(Telefono(tel.numero, tel.tipo, " ".join(grupo)[:MAX_TEXTO_LEIDO]))
            break
        k += avance
    return salida
