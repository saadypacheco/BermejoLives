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


def moderar_publicacion(titulo: str, descripcion: str | None) -> dict:
    """Revisión IA de contenido antes de publicar (asistente del moderador humano).

    Devuelve ``{"veredicto": "aprobar"|"rechazar"|"dudoso", "motivo": str, "confianza": float}``.
    Sin ``GEMINI_API_KEY`` (o si el modelo falla) devuelve veredicto ``"dudoso"`` para
    que la publicación caiga a revisión humana — nunca aprueba automáticamente a ciegas.
    """
    if not settings.gemini_api_key:
        return {"veredicto": "dudoso", "motivo": "IA no configurada; revisión humana.", "confianza": 0.0}

    prompt = (
        "Sos moderador de contenido de URUKU, un directorio de comercios locales de "
        "Bermejo (Bolivia). Revisá esta publicación y decidí si puede publicarse.\n"
        "RECHAZÁ si hay: contenido ofensivo o violento, spam, estafa evidente, venta de "
        "productos ilegales (drogas, armas), datos de contacto falsos, o si el título y la "
        "descripción no tienen ningún sentido. En caso de duda razonable, marcá 'dudoso' "
        "para que lo vea una persona. Si es un producto/comercio normal, 'aprobar'.\n\n"
        f"Título: {titulo}\nDescripción: {descripcion or '-'}\n\n"
        "Devolvé SOLO un JSON (sin markdown): "
        '{"veredicto": "aprobar"|"rechazar"|"dudoso", "motivo": "breve, máx 15 palabras", '
        '"confianza": 0.0-1.0}'
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
        logger.warning("moderar_publicacion.error", error=str(exc))
        return {"veredicto": "dudoso", "motivo": "No se pudo consultar la IA; revisión humana.", "confianza": 0.0}

    veredicto = str(data.get("veredicto", "dudoso")).strip().lower()
    if veredicto not in {"aprobar", "rechazar", "dudoso"}:
        veredicto = "dudoso"
    try:
        confianza = max(0.0, min(1.0, float(data.get("confianza", 0.0))))
    except (TypeError, ValueError):
        confianza = 0.0
    return {"veredicto": veredicto, "motivo": str(data.get("motivo", ""))[:200], "confianza": confianza}


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


def sugerir_rubros_explicado(nombre: str, texto: str, rubros: list[dict]) -> dict | None:
    """1-3 rubros para UN comercio, con el motivo en una línea.

    Es la misma pregunta que `sugerir_rubros`, con dos diferencias que sólo
    importan cuando hay una persona mirando:

    - **Dice por qué.** El que revisa no necesita que le adivinen el rubro:
      necesita entender de dónde salió el error para no repetirlo. "Hotel Reina"
      cayó en blanquería porque la foto describía sábanas y toallas; con esa
      frase a la vista, la corrección se hace una vez y la palabra que se agrega
      al diccionario es la correcta.
    - **Se pide de a uno, a pedido.** No corre sola sobre 1080 comercios: la
      dispara alguien que ya está mirando esa ficha, y paga una llamada.

    Devuelve None si no hay `GEMINI_API_KEY` o si el modelo falla. El panel
    muestra igual lo que dice el diccionario, que es lo que clasifica de verdad;
    esto es una opinión más, no la fuente.
    """
    slugs = [r["slug"] for r in rubros if r.get("slug")]
    if not slugs or not settings.gemini_api_key or not (nombre or texto).strip():
        return None

    lista = "\n".join(f"- {r['slug']}: {r.get('nombre', r['slug'])}"
                      for r in rubros if r.get("slug"))
    prompt = (
        "Sos quien clasifica los negocios de URUKU, un directorio de comercios de "
        "Bermejo (Bolivia). Elegí entre 1 y 3 rubros para este negocio, el más "
        "adecuado primero.\n\n"
        f"Nombre del negocio: {nombre}\n"
        f"Lo que se sabe de él (productos vistos en la foto, categoría, nombre): {texto}\n\n"
        f"Rubros disponibles:\n{lista}\n\n"
        "IMPORTANTE: el nombre del negocio suele ser la señal más fuerte, y la "
        "descripción de la foto confunde — un hotel cuya foto muestra sábanas y "
        "toallas NO es una blanquería, y un taller cuya foto muestra una gaseosa en "
        "el mostrador no es un almacén.\n\n"
        'Devolvé SOLO un JSON (sin markdown): {"rubros": ["slug1"], '
        '"motivo": "una frase de máximo 20 palabras que explique por qué"}'
    )
    try:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
        )
        r = httpx.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
        r.raise_for_status()
        crudo = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip().strip("`")
        if crudo.lower().startswith("json"):
            crudo = crudo[4:].strip()
        data = json.loads(crudo)
    except Exception as exc:  # noqa: BLE001
        logger.warning("sugerir_rubros_explicado.error", error=str(exc))
        return None

    elegidos = [s for s in (data.get("rubros") or []) if s in slugs][:3]
    if not elegidos:
        return None
    return {"rubros": elegidos, "motivo": str(data.get("motivo", ""))[:200]}
