"""Clasificación de productos por IA (Gemini Flash, solo texto).

`clasificar(titulo, descripcion, categorias)` devuelve el slug de la categoría más
adecuada, o **None** si no hay `GEMINI_API_KEY` o falla. En ese caso el caller usa un
fallback gratis (la categoría por defecto / el rubro del comercio).
"""
import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger()


def clasificar(titulo: str, descripcion: str | None, categorias: list[dict]) -> str | None:
    slugs = [c["slug"] for c in categorias if c.get("slug")]
    if not slugs or not settings.gemini_api_key:
        return None

    lista = "\n".join(f"- {c['slug']}: {c.get('nombre', c['slug'])}" for c in categorias if c.get("slug"))
    prompt = (
        "Sos un clasificador de productos de un marketplace. Elegí la categoría MÁS "
        "adecuada para el producto y respondé SOLO con el slug exacto, sin explicar.\n\n"
        f"Categorías disponibles:\n{lista}\n\n"
        f"Producto:\nTítulo: {titulo}\nDescripción: {descripcion or '-'}\n\n"
        "Respondé solo el slug:"
    )
    try:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
        )
        r = httpx.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
        r.raise_for_status()
        texto = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip().lower()
    except Exception as exc:  # noqa: BLE001
        logger.warning("clasificar.error", error=str(exc))
        return None

    # El modelo puede devolver texto extra; buscamos el primer slug que aparezca.
    for s in slugs:
        if s in texto:
            return s
    return None
