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


def limpiar_ref(valor: str | None, largo: int = 64) -> str | None:
    """El `?ref=` (origen de una llegada o de un contacto), limpio.

    UNA sola regla para `/visita` y `/lead`: antes cada uno tenía su lista de
    caracteres y el mismo ref con «:» quedaba con dos claves distintas, así que
    la llegada y el contacto no se podían cruzar. Minúsculas, sólo
    [a-z0-9_.-], tope de `largo`. Vacío → None."""
    limpio = re.sub(r"[^a-z0-9_.-]", "", (valor or "").strip().lower())[:largo]
    return limpio or None
