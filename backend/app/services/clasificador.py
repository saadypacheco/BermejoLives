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


def sugerir_rubros(descripcion: str, rubros: list[dict]) -> list[str]:
    """De una descripción libre (ej. transcripción de audio del agente de campo),
    sugiere 1-3 rubros. [] si no hay GEMINI_API_KEY o falla (el caller cae a un
    fallback, ej. 'otros', para no bloquear el alta)."""
    slugs = [r["slug"] for r in rubros if r.get("slug")]
    if not slugs or not settings.gemini_api_key or not descripcion.strip():
        return []

    lista = "\n".join(f"- {r['slug']}: {r.get('nombre', r['slug'])}" for r in rubros if r.get("slug"))
    prompt = (
        "A partir de esta descripción de un negocio, elegí entre 1 y 3 rubros de "
        "la lista que mejor apliquen (los más específicos primero).\n\n"
        f"Descripción: {descripcion}\n\n"
        f"Rubros disponibles:\n{lista}\n\n"
        'Devolvé SOLO un JSON (sin markdown): {"rubro_slugs": ["slug1", "slug2"]}'
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
        logger.warning("sugerir_rubros.error", error=str(exc))
        return []

    candidatos = data.get("rubro_slugs") or []
    return [s for s in candidatos if s in slugs][:3]


def comparar_fotos(foto_guardada: bytes, foto_nueva: bytes) -> str | None:
    """Compara dos fotos de un local (la ya registrada vs. una nueva que alguien
    subió pidiendo cambiar el WhatsApp del comercio). Devuelve 'alta'/'media'/
    'baja' como AYUDA VISUAL para el admin — nunca aprueba nada por sí sola,
    la foto de un local es pública y cualquiera puede sacarla."""
    import base64

    if not settings.gemini_api_key:
        return None
    try:
        parts = [
            {"text": (
                "Comparás dos fotos de un local comercial. La primera es la foto ya "
                "registrada en la plataforma; la segunda es una foto nueva que alguien "
                "subió diciendo que es el mismo local (para recuperar el acceso a la cuenta). "
                "Respondé SOLO una palabra: 'alta' si es muy probable que sea el mismo local, "
                "'media' si no queda claro, o 'baja' si parecen lugares distintos."
            )},
            {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(foto_guardada).decode()}},
            {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(foto_nueva).decode()}},
        ]
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
        )
        r = httpx.post(url, json={"contents": [{"parts": parts}]}, timeout=30)
        r.raise_for_status()
        texto = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip().lower()
    except Exception as exc:  # noqa: BLE001
        logger.warning("comparar_fotos.error", error=str(exc))
        return None

    for etiqueta in ("alta", "media", "baja"):
        if etiqueta in texto:
            return etiqueta
    return None
