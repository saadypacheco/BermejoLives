"""La clave automática del COMERCIO: `PREFIJO-AZAR` (docs/clave-automatica.md).

Ejemplo: `BOUTIQUE-K7M2P9`.

  - PREFIJO: la primera palabra significativa del nombre, sólo para que la
    persona la recuerde (no suma seguridad). Mayúsculas, sin tildes ni ñ, sólo
    letras y números, máximo 8. En un local `sin_cartel` sale de lo que vende
    (subcategoría y, si no hay, rubro). Sin nada utilizable: `LOCAL`. NUNCA
    `URUKU`: se confundiría con el código del comercio.
  - AZAR: 6 caracteres de un alfabeto sin 0/O/1/I/L, con `secrets` (nunca
    `random`). Es lo único que protege la clave.

Al comparar se normaliza (mayúsculas, sin espacios ni guiones): `boutique
k7m2p9` es `BOUTIQUE-K7M2P9`. Se guarda SÓLO el hash de la forma normalizada,
con el mismo hash que las contraseñas (`auth.hash_password`). Una clave vieja
de 6 números normaliza a sí misma, así que sigue entrando hasta que se cambie.

La clave NUNCA va a un log: viaja una sola vez, en la respuesta que la genera.

El comprador (`app/core/clave.py`, 6 números) NO usa este módulo.
"""
from __future__ import annotations

import re
import secrets
import unicodedata

from app.core import auth

# Sin caracteres que se confundan al dictarlos o leerlos de un papel: 0/O, 1/I/L.
ALFABETO = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
LARGO_AZAR = 6
LARGO_PREFIJO_MAX = 8
PREFIJO_SIN_NOMBRE = "LOCAL"
#: Nunca es un prefijo válido: la clave se confundiría con el código URUKU-XXXX.
PREFIJO_PROHIBIDO = "URUKU"

#: Artículos y palabras de relleno que no sirven para recordar el nombre.
_PALABRAS_VACIAS = frozenset({"el", "la", "los", "las", "lo", "de", "del", "y", "e",
                              "mi", "tu", "su", "un", "una"})

# Lo que se descarta al comparar: espacios, guiones (también los largos) y guion bajo.
_RE_SEPARADORES = re.compile(r"[\s\-_‐-―−]+")
_RE_CLAVE = re.compile(r"^[A-Z0-9]{6,24}$")
_MAX_CRUDO = 64          # una «clave» más larga que esto es basura: ni se mira


# ─────────────────────────────────────────────────────────── el prefijo
def _sin_tildes(texto: str) -> str:
    """'Ñandú' -> 'Nandu' (la Ñ cae a N, las tildes se van)."""
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def _palabras(texto: str | None) -> list[str]:
    """Las palabras de un texto ya limpias (mayúsculas, sólo [A-Z0-9]); sin las
    vacías (artículos) ni las que quedan en blanco (un «&» suelto)."""
    if not texto:
        return []
    salida = []
    for crudo in re.split(r"[\s\-/–—.,;:()]+", _sin_tildes(str(texto))):
        if crudo.lower() in _PALABRAS_VACIAS:
            continue
        limpia = re.sub(r"[^A-Za-z0-9]", "", crudo).upper()
        if limpia and limpia.lower() not in _PALABRAS_VACIAS:
            salida.append(limpia)
    return salida


def _primera_utilizable(texto: str | None) -> str | None:
    for palabra in _palabras(texto):
        if palabra != PREFIJO_PROHIBIDO:
            return palabra[:LARGO_PREFIJO_MAX]
    return None


def prefijo_de(nombre: str | None, sin_cartel: bool = False,
               subcategoria: str | None = None, rubro: str | None = None) -> str:
    """El prefijo para recordar la clave. Nunca vacío y nunca `URUKU`.

    Con nombre propio sale del nombre. Un local `sin_cartel` no tiene nombre
    (el que se ve lo arma la base con lo que vende y dónde está), así que sale
    de la subcategoría y, si no hay, del rubro. Sin nada: `LOCAL`."""
    if sin_cartel:
        fuentes = (subcategoria, rubro)
    else:
        fuentes = (nombre,)
    for fuente in fuentes:
        prefijo = _primera_utilizable(fuente)
        if prefijo:
            return prefijo
    return PREFIJO_SIN_NOMBRE


# ─────────────────────────────────────────────────────────── generar
def generar_azar() -> str:
    """Los 6 caracteres al azar (con `secrets`)."""
    return "".join(secrets.choice(ALFABETO) for _ in range(LARGO_AZAR))


def generar_clave(nombre: str | None = None, sin_cartel: bool = False,
                  subcategoria: str | None = None, rubro: str | None = None) -> str:
    """`PREFIJO-AZAR`, p. ej. `BOUTIQUE-K7M2P9`."""
    return f"{prefijo_de(nombre, sin_cartel, subcategoria, rubro)}-{generar_azar()}"


def generar_clave_de_comercio(comercio: dict | None, rubro: str | None = None) -> str:
    """La clave para esa fila de `comercios` (con el nombre del rubro principal,
    que el llamador resuelve, para los locales sin cartel)."""
    c = comercio or {}
    return generar_clave(c.get("nombre"), bool(c.get("sin_cartel")), c.get("subcategoria"), rubro)


def clave_distinta_de(hashes: list[str | None], prefijo: str) -> str:
    """Una clave nueva con ese prefijo que NO coincide con ninguno de esos hashes.

    En un número con varios comercios la clave identifica cuál se abre: al
    generarla se descartan las que ya usa otro comercio del mismo número."""
    otros = [h for h in hashes if h]
    for _ in range(50):
        nueva = f"{prefijo}-{generar_azar()}"
        if not any(auth.verify_password(normalizar(nueva), h) for h in otros):
            return nueva
    raise RuntimeError("no se pudo generar una clave distinta")      # prácticamente imposible


# ─────────────────────────────────────────────────────────── comparar
def normalizar(clave: str | None) -> str:
    """Mayúsculas, sin espacios ni guiones: «boutique k7m2p9» -> «BOUTIQUEK7M2P9»."""
    if not clave:
        return ""
    return _RE_SEPARADORES.sub("", str(clave)).upper()


def es_clave(valor: str | None) -> bool:
    """¿Tiene forma de clave? Las de 6 números de antes y las nuevas, hasta 24
    caracteres ya normalizados. Así no se gasta PBKDF2 en basura."""
    if not valor or len(valor) > _MAX_CRUDO:
        return False
    return bool(_RE_CLAVE.match(normalizar(valor)))


def hash_clave(clave: str) -> str:
    """El hash de la forma NORMALIZADA (el que se guarda)."""
    return auth.hash_password(normalizar(clave))


def clave_coincide(clave: str | None, hash_guardado: str | None) -> bool:
    """¿Esta clave es la que dejó ese hash? Falso si no hay hash o si lo
    tipeado no tiene forma de clave."""
    if not hash_guardado or not es_clave(clave):
        return False
    return auth.verify_password(normalizar(clave), hash_guardado)
