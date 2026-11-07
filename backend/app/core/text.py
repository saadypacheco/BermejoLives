"""Utilidades de texto: slugificar y obtener un slug único."""
import re
import unicodedata


def slugify(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", nfkd.lower()).strip("-")
    return slug or "comercio"


def slug_unico(repo, base: str) -> str:
    slug = base
    n = 2
    while repo.slug_existe(slug):
        slug = f"{base}-{n}"
        n += 1
    return slug


# ── enmascarado de datos personales ─────────────────────────────────────────────────────────────────
# Los DOS patrones tienen una copia idéntica en la migración 0194_busquedas_enmascarar.sql (que enmascara las
# búsquedas ya guardadas): si se cambia uno, se cambia el otro (tests/test_enmascarar_busquedas.py lo comprueba).
# Son un dialecto común de Python y de Postgres (ARE): sin lookarounds ni límites de palabra, con `(?:...)`.
#: Mails, también «juan (at) gmail (dot) com», «juan [at] gmail . com» y «juan @ gmail . com» (con espacios sueltos).
PATRON_MAIL = (r"\w[\w.+-]*\s?(?:@|\(\s?at\s?\)|\[\s?at\s?\])\s?\w[\w-]*"
               r"(?:\s?(?:\.|\(\s?dot\s?\)|\[\s?dot\s?\])\s?\w[\w-]*)+")
#: 6 o más dígitos aunque vengan con espacios, puntos, guiones o paréntesis en el medio («+591 712-34567»,
#: «(591) 71 23 45 67»). El separador del final NO se come: «71234567 zapatos» queda «# zapatos».
PATRON_DIGITOS = r"\+?\d(?:[ .()-]*\d){5,}"
_RE_MAIL = re.compile(PATRON_MAIL, re.IGNORECASE)
_RE_DIGITOS = re.compile(PATRON_DIGITOS)


def enmascarar_texto(texto: str | None, *, marca_mail: str = "[mail]", marca_digitos: str = "#", largo: int = 100) -> str:
    """El texto sin datos personales: mails (y sus variantes «(at)», «[at]») → `marca_mail`; 6 o más dígitos
    (con separadores) → `marca_digitos`. Los espacios se juntan ANTES de enmascarar (así un «6 4 3 2 1 0» partido
    con varios espacios igual se encuentra). Tope de `largo` caracteres."""
    limpio = re.sub(r"\s+", " ", texto or "")
    limpio = _RE_MAIL.sub(marca_mail, limpio)
    limpio = _RE_DIGITOS.sub(marca_digitos, limpio)
    return limpio.strip()[:largo]


def limpiar_ref(valor: str | None, largo: int = 64) -> str | None:
    """El `?ref=` (origen de una llegada o de un contacto), limpio.

    UNA sola regla para `/visita` y `/lead`: antes cada uno tenía su lista de
    caracteres y el mismo ref con «:» quedaba con dos claves distintas, así que
    la llegada y el contacto no se podían cruzar. Minúsculas, sólo
    [a-z0-9_.-], tope de `largo`. Vacío → None.

    Antes de limpiar se enmascaran mails y teléfonos (el `?ref=` también es texto libre que llega de afuera y
    se guarda): «qr-71234567» queda «qr-n»."""
    enmascarado = enmascarar_texto((valor or "").strip().lower(), marca_mail="mail", marca_digitos="n", largo=400)
    limpio = re.sub(r"[^a-z0-9_.-]", "", enmascarado)[:largo]
    return limpio or None
