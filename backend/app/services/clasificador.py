"""Clasificación de productos por IA (Gemini Flash, solo texto).

`clasificar(titulo, descripcion, categorias)` devuelve el slug de la categoría más
adecuada, o **None** si no hay `GEMINI_API_KEY` o falla. En ese caso el caller usa un
fallback gratis (la categoría por defecto / el rubro del comercio).
"""
import json

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


def generar_texto_comercio(nombre: str, que_vende: str, rubros: list[dict]) -> dict | None:
    """A partir de "qué vendés" en texto libre, genera una descripción de
    perfil + infiere el rubro más adecuado. None si no hay GEMINI_API_KEY o falla
    (el caller cae a usar `que_vende` tal cual como descripción, sin rubro)."""
    slugs = [r["slug"] for r in rubros if r.get("slug")]
    if not slugs or not settings.gemini_api_key:
        return None

    lista = "\n".join(f"- {r['slug']}: {r.get('nombre', r['slug'])}" for r in rubros if r.get("slug"))
    prompt = (
        "Sos un asistente que arma el perfil de un comercio en Encontralo, un mapa de negocios.\n"
        f"Nombre del negocio: {nombre}\n"
        f"Lo que vende, en palabras del dueño: {que_vende}\n\n"
        f"Rubros disponibles:\n{lista}\n\n"
        "Devolvé SOLO un JSON (sin explicar nada más, sin markdown) con este formato:\n"
        '{"descripcion": "una descripción atractiva de 1-2 oraciones para el perfil del negocio", '
        '"rubro_slug": "el slug más adecuado de la lista de rubros"}'
    )
    try:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
        )
        r = httpx.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
        r.raise_for_status()
        texto = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        texto = texto.strip("`")
        if texto.lower().startswith("json"):
            texto = texto[4:].strip()
        data = json.loads(texto)
    except Exception as exc:  # noqa: BLE001
        logger.warning("generar_texto_comercio.error", error=str(exc))
        return None

    descripcion = (data.get("descripcion") or "").strip()
    rubro_slug = data.get("rubro_slug")
    if not descripcion:
        return None
    return {"descripcion": descripcion, "rubro_slug": rubro_slug if rubro_slug in slugs else None}
