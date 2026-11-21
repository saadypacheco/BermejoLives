"""El prompt FIJO y versionado de las fotos con IA (docs/fotos-estilo-uruku.md §2).

Está en inglés a propósito: los modelos de imagen respetan mejor el «sin texto» en inglés. NUNCA lleva datos del
comercio (ni nombre, ni rubro, ni ciudad): es el mismo para todos y es lo que se copia para pegar en ChatGPT.

Si se cambia una palabra hay que subir `PROMPT_VERSION` (el test `test_fotos_estilo_prompt.py` ata el sha256 del texto
a la versión): la versión queda registrada en cada uso (`photo_style_uses.prompt_version`).
"""
from __future__ import annotations

PROMPT_VERSION = "fotos-estilo-v1"

BASE = (
    "Edit the attached photo into a clean, premium advertising photo. Keep it REAL: same place, same products, same "
    "shapes, same product colors, same number of items; do not invent, add or remove products; do not alter faces. "
    "Natural, even, slightly warm light; recover shadows; vivid but true colors; no heavy filters, no HDR, no "
    "stock-photo look. Remove price tags, price numbers, product codes, stock tables, watermarks and stickers added on "
    "top. Do NOT write any text, letters, numbers or logos; leave the store's own sign exactly as it is. Keep the "
    "bottom quarter free of key details. One photo, no borders, no frames."
)
COVER = (
    "COVER: storefront or shop interior; straighten vertical lines; tidy loose clutter in front; aspect 3:2."
)
GALLERY = (
    "GALLERY: product photo; center the main product on a clean light catalogue background with a soft shadow; "
    "aspect 4:5."
)

#: `target` de la API (`cover` | `gallery`) -> `aspectRatio` que se le pide a Gemini.
ASPECTO = {"cover": "3:2", "gallery": "4:5"}


def prompt(target: str) -> str:
    """El prompt completo para `cover` o `gallery`. ValueError con cualquier otro valor."""
    if target == "cover":
        return f"{BASE}\n{COVER}"
    if target == "gallery":
        return f"{BASE}\n{GALLERY}"
    raise ValueError("target inválido")


def instrucciones() -> dict:
    """Lo que devuelve el GET `fotos-estilo` en `instructions`: la versión y los dos textos para pegar en ChatGPT."""
    return {"version": PROMPT_VERSION, "cover": prompt("cover"), "gallery": prompt("gallery")}
