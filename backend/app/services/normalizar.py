"""Normalización de subcategorías, para que las variantes de lo mismo se cuenten juntas.

El problema es medido, no teórico. Después de analizar 161 vidrieras con IA, el
informe de producción mostró:

    mochilas y bolsos    2        jugueteria    7
    bolsos y mochilas    2        juguetes      4

Son el mismo negocio escrito distinto. Al fragmentarse, ninguna variante junta
suficientes comercios como para justificar un filtro, y el que busca "bolsos"
ve la mitad de los locales que hay.

La subcategoría original NUNCA se toca: es lo que dijo la IA y sirve para
auditar. Lo normalizado va aparte, en `subcategoria_norm`, y es lo que se usa
para agrupar y filtrar.

Cuatro pasos, en orden:

1. minúsculas y sin tildes  — "Juguetería" y "jugueteria" son lo mismo
2. singular                 — "juguetes" y "juguete" son lo mismo
3. sin palabras vacías      — "ropa de bebé" y "ropa bebé" son lo mismo
4. términos ordenados       — "bolsos y mochilas" y "mochilas y bolsos" son lo mismo

El paso 4 es el que resuelve el caso que apareció en los datos, y sólo funciona
después del 2: sin singularizar, "bolso mochila" y "bolsos mochilas" seguirían
siendo distintos.
"""
from __future__ import annotations

import re
import unicodedata

# Se sacan sólo si no son la única palabra: "de" nunca es una subcategoría, pero
# tampoco queremos convertir algo en cadena vacía.
VACIAS = {"de", "del", "la", "el", "los", "las", "y", "e", "para", "con", "a", "en"}


def sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn")


def singular(palabra: str) -> str:
    """Singular aproximado del español. No es un lematizador y no hace falta que
    lo sea: alcanza con que dos formas de la MISMA palabra caigan en la misma
    cadena, aunque esa cadena no sea español correcto.

    Las palabras cortas se dejan como están — "gas" o "tres" no son plurales, y
    recortarlas produce colisiones peores que el problema que resuelven.
    """
    if len(palabra) <= 3:
        return palabra
    if palabra.endswith("ces"):            # lapices -> lapiz
        return palabra[:-3] + "z"
    if palabra.endswith("es") and len(palabra) > 4:
        return palabra[:-2]                # pantalones -> pantalon
    if palabra.endswith("s"):
        return palabra[:-1]                # bolsos -> bolso
    return palabra


def normalizar_subcategoria(texto: str | None) -> str:
    """Forma canónica para agrupar. Devuelve "" si no queda nada aprovechable."""
    if not texto:
        return ""

    base = sin_tildes(texto).lower()
    base = re.sub(r"[^a-z0-9ñ ]+", " ", base)

    palabras = [singular(p) for p in base.split() if p]
    utiles = [p for p in palabras if p not in VACIAS]

    # Si todo eran palabras vacías, conservamos lo que había: es raro, pero es
    # preferible a devolver vacío y perder el dato.
    if not utiles:
        utiles = palabras

    # Ordenar alfabéticamente es lo que hace que "bolsos y mochilas" y
    # "mochilas y bolsos" terminen en la misma clave. El resultado se lee raro
    # ("bolso mochila") y no importa: nadie lo ve, sólo agrupa.
    return " ".join(sorted(set(utiles)))
