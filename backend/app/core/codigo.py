"""Código de identificación del comercio.

Se genera en el alta (primera pasada, en la calle) y se le deja al comercio en
papel. Sirve para que pueda mandar ofertas por WhatsApp **desde cualquier
número**, sin tener número propio cargado, sin login y sin haber pagado: escribe
el código en el mensaje y la publicación se atribuye a su local.

No es una contraseña. Todo lo que entra pasa por moderación humana, así que un
código equivocado no publica nada: genera algo pendiente que el admin rechaza.
Por eso alcanza con que no sea *adivinable*, no con que sea secreto.

Es además el identificador estable del comercio de cara al dueño: el celular
puede cambiar, el código no.
"""
from __future__ import annotations

import re
import secrets

from app.core.clave_comercio import RE_FORMA_DE_CLAVE

PREFIJO = "URUKU"

# Sin caracteres que se confundan al dictarlos o al leerlos de un papel:
# 0/O, 1/I/L. Quedan 31 símbolos → 31^4 ≈ 923.000 combinaciones.
_ALFABETO = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
_LARGO = 4

# Acepta 'URUKU-K7M2', 'uruku k7m2', 'URUKUK7M2' y el código pelado 'K7M2'.
_RE_CON_PREFIJO = re.compile(rf"{PREFIJO}[\s\-_.]*([{_ALFABETO}]{{{_LARGO}}})", re.IGNORECASE)
_RE_PELADO = re.compile(rf"\b([{_ALFABETO}]{{{_LARGO}}})\b", re.IGNORECASE)


def generar_codigo() -> str:
    """Devuelve un código nuevo de 4 caracteres (sin el prefijo)."""
    return "".join(secrets.choice(_ALFABETO) for _ in range(_LARGO))


def formatear(codigo: str) -> str:
    """'K7M2' → 'URUKU-K7M2'. Lo que se le dicta o imprime al comercio."""
    return f"{PREFIJO}-{codigo.upper()}"


def normalizar(codigo: str | None) -> str | None:
    """Deja el código en su forma canónica, o None si no es válido."""
    if not codigo:
        return None
    limpio = re.sub(rf"^{PREFIJO}[\s\-_.]*", "", str(codigo).strip(), flags=re.IGNORECASE).upper()
    if len(limpio) != _LARGO or any(c not in _ALFABETO for c in limpio):
        return None
    return limpio


def extraer_codigo(texto: str | None) -> str | None:
    """Busca un código dentro del texto de un mensaje de WhatsApp.

    Prioriza el que viene con prefijo: es el que se le enseñó a escribir al
    comercio, y evita confundir una palabra cualquiera del mensaje con un código.
    El match pelado es el plan B para el que sólo escribe los 4 caracteres.
    """
    if not texto:
        return None
    con_prefijo = _RE_CON_PREFIJO.search(texto)
    if con_prefijo:
        return con_prefijo.group(1).upper()
    # El plan B no puede tomar como código un tramo de una CLAVE: `MESA-K7M2P9` tiene un
    # «MESA» que cumple todo lo de un código pelado. Antes de buscar se tapa lo que tiene
    # forma de clave (prefijo + 6 del azar).
    sin_claves = RE_FORMA_DE_CLAVE.sub(" ", texto)
    pelado = _RE_PELADO.search(sin_claves)
    return pelado.group(1).upper() if pelado else None


#: Lo que de una fila de `comercios` sólo ve el equipo: el código vigente, el anterior
#: (0149, lo guarda para las publicaciones que entraron antes del cambio) y el id con
#: que el celular del agente reintenta un alta (0149).
_SOLO_ADMIN = ("codigo", "codigo_formateado", "codigo_anterior", "alta_uid")


def sin_codigo(fila: dict | None) -> dict | None:
    """La fila de un comercio SIN el código (`codigo`, `codigo_formateado`, `codigo_anterior`).

    El código `URUKU-XXXX` es sólo del admin (docs/clave-automatica.md): ninguna
    respuesta de `/comercio/*`, `/campo/*` ni del autoregistro lo lleva. Devuelve
    una copia; no toca la fila original (la ingesta y el admin siguen usándola)."""
    if fila is None:
        return None
    return {k: v for k, v in fila.items() if k not in _SOLO_ADMIN}
