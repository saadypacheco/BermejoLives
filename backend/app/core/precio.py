"""Sacar el precio de un texto escrito como escribe un comerciante de Bermejo.

"Pizarra 220 bolivianos", "zapatillas 250 bs", "Bs. 1.200", "a 80", "$150",
"US$ 40". Una oferta que llega por WhatsApp casi nunca viene con el precio en
un campo: viene en la frase. Si no se saca de ahí, la tarjeta del sitio no lo
muestra, y una oferta sin precio en la lista es una oferta que nadie abre.

Es un extractor conservador: prefiere no encontrar precio a inventar uno. Un
"220" suelto sin moneda cerca no cuenta — podría ser un talle, una cantidad,
un año.
"""
from __future__ import annotations

import re

# Monedas como las escribe la gente. El orden importa: "us$" y "usd" antes que
# "$" solo, y "bolivianos" antes que "bs" (que es su prefijo).
_MONEDAS = [
    (r"us\$|usd|d[oó]lares?", "USD"),
    (r"\$", "ARS"),                       # en Bermejo, "$" a secas son pesos argentinos
    (r"bolivianos?|bs\.?", "BOB"),
    (r"pesos?", "ARS"),
]

_NUMERO = r"(\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[,.](\d{1,2}))?"


def _a_float(entero: str, decimales: str | None) -> float:
    limpio = re.sub(r"[.\s]", "", entero)
    return float(f"{limpio}.{decimales}" if decimales else limpio)


def extraer_precio(texto: str | None) -> tuple[float, str] | None:
    """Devuelve (monto, moneda) o None si no hay un precio claro.

    Busca número seguido de moneda ("220 bolivianos", "250 bs") y moneda
    seguida de número ("Bs. 1.200", "$150", "US$ 40"). Si hay varios, se queda
    con el primero: en "de 300 a 250 bs" lo que importa es que hay precio, y
    el moderador puede corregirlo.
    """
    if not texto:
        return None
    t = texto.lower()

    for patron, moneda in _MONEDAS:
        # número + moneda
        m = re.search(rf"{_NUMERO}\s*(?:{patron})(?![a-z])", t)
        if m:
            return _a_float(m.group(1), m.group(2)), moneda
        # moneda + número
        m = re.search(rf"(?:{patron})\s*{_NUMERO}", t)
        if m:
            return _a_float(m.group(1), m.group(2)), moneda
    return None


def parece_oferta(texto: str | None) -> bool:
    """¿El texto habla de un precio o de una oferta? Es lo que separa "oferta"
    de "novedad" cuando no hay foto."""
    if not texto:
        return False
    t = texto.lower()
    return "oferta" in t or "promo" in t or "descuento" in t or extraer_precio(t) is not None
