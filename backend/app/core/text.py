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
