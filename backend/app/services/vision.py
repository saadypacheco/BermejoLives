"""Clasificación de un comercio a partir de las fotos del local.

El problema que resuelve: en el recorrido no se puede elegir rubro de una lista
de 42 ni escribir un inventario — se sacan 1-2 fotos y se sigue. Todo lo demás
(qué vende, de qué rubro es, cómo describirlo) está EN la foto de la vidriera.

Devuelve una PROPUESTA, nunca un hecho. Quien decide es el admin: el modelo es
elocuente aunque no vea nada, así que ante una persiana cerrada va a inventar
algo plausible. Por eso `confianza` y por eso nada se escribe sin aprobación.
"""
from __future__ import annotations

import base64
import json
import re

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger()

TIMEOUT_DESCARGA = 8   # interactivo: mejor fallar rápido que colgar el panel
TIMEOUT_MODELO = 45
MAX_FOTOS = 3          # más no aporta y multiplica el costo
MAX_BYTES_FOTO = 4 * 1024 * 1024


class VisionNoConfigurada(RuntimeError):
    """Falta GEMINI_API_KEY: el análisis no puede correr."""


def _leer_local(url: str) -> bytes | None:
    """Las fotos las guarda y las sirve el propio backend, así que casi siempre
    están en su disco. Leerlas de ahí evita que el contenedor tenga que salir a
    internet para pedirse un archivo a sí mismo — una vuelta que es lenta cuando
    anda y se cuelga cuando la red interna no resuelve el dominio público.
    """
    from pathlib import Path

    base = settings.fotos_public_base_url.rstrip("/")
    if not url.startswith(base):
        return None
    relativo = url[len(base):].lstrip("/").split("?")[0]
    # Nunca salir del volumen de fotos, aunque la URL venga con '..'.
    try:
        raiz = Path(settings.fotos_dir).resolve()
        destino = (raiz / relativo).resolve()
        if not str(destino).startswith(str(raiz)) or not destino.is_file():
            return None
        data = destino.read_bytes()
        return data if len(data) <= MAX_BYTES_FOTO else None
    except Exception:  # noqa: BLE001
        return None


def _descargar(url: str) -> bytes | None:
    local = _leer_local(url)
    if local is not None:
        return local
    try:
        r = httpx.get(url, timeout=TIMEOUT_DESCARGA, follow_redirects=True)
        r.raise_for_status()
        if len(r.content) > MAX_BYTES_FOTO:
            logger.warning("vision.foto_grande", url=url, bytes=len(r.content))
            return None
        return r.content
    except Exception as exc:  # noqa: BLE001
        logger.warning("vision.descarga_fallo", url=url, error=str(exc))
        return None


def _prompt(rubros: list[dict]) -> str:
    lista = "\n".join(f"- {r['slug']}: {r.get('nombre', r['slug'])}" for r in rubros if r.get("slug"))
    return f"""Sos un relevador de comercios en Bermejo, Bolivia — una ciudad de frontera.
Mirás fotos de la fachada o la vidriera de un local y decís qué vende.

Devolvé SOLO un JSON, sin markdown, con esta forma exacta:
{{
  "productos": "lista de 4 a 8 productos separados por coma, en singular y en la palabra que usaría un cliente",
  "descripcion": "una o dos frases sobre el negocio, en español rioplatense, sin adjetivos publicitarios",
  "subcategoria": "el tipo específico de negocio en 1 o 2 palabras (ej: peluches, celulares, ropa de bebé)",
  "rubro_slugs": ["slug1", "slug2"],
  "confianza": 0.0
}}

Reglas:
- `rubro_slugs`: SOLO slugs de la lista de abajo. Todos los que apliquen — un local
  que vende neumáticos y también zapatillas lleva los dos. Si no podés determinar
  ninguno, devolvé [].
- `productos`: SOLO lo que se ve en las fotos. No completes con lo que "suele"
  vender un negocio así.
- `confianza`: 0.0 a 1.0. Cuánto de lo que decís está realmente visible.
  Si la persiana está cerrada, hay poca luz, o sólo se ve un cartel sin
  mercadería, la confianza es BAJA (menos de 0.4) aunque el cartel diga el rubro.
  Preferí admitir que no ves a completar con lo probable.
- Si las fotos no muestran un comercio, devolvé confianza 0 y listas vacías.

Rubros disponibles:
{lista}"""


def _sin_secretos(texto: str) -> str:
    """Saca la API key de cualquier texto que vaya a mostrarse.

    httpx incluye la URL completa en el mensaje de sus errores, y la URL de
    Gemini lleva ?key=... — así que un 404 terminaba mostrando la clave entera
    en el panel del admin. Cualquiera con acceso a esa pantalla, o a una captura,
    se la lleva.
    """
    if not texto:
        return texto
    limpio = re.sub(r"([?&]key=)[^&\s\"']+", r"\g<1><oculta>", texto)
    if settings.gemini_api_key:
        limpio = limpio.replace(settings.gemini_api_key, "<oculta>")
    return limpio


def _parsear(texto: str) -> dict:
    limpio = texto.strip().strip("`")
    if limpio.lower().startswith("json"):
        limpio = limpio[4:]
    m = re.search(r"\{.*\}", limpio, re.S)
    return json.loads(m.group(0) if m else limpio)


def analizar_fotos(urls: list[str], rubros: list[dict]) -> dict:
    """Analiza hasta MAX_FOTOS y devuelve la propuesta.

    Lanza VisionNoConfigurada si falta la key. Cualquier otro fallo devuelve una
    propuesta vacía con confianza 0: es preferible "no sé" a un dato inventado.
    """
    if not settings.gemini_api_key:
        raise VisionNoConfigurada("Falta GEMINI_API_KEY")

    partes: list[dict] = [{"text": _prompt(rubros)}]
    usadas = 0
    for url in urls[:MAX_FOTOS]:
        data = _descargar(url)
        if not data:
            continue
        partes.append({"inline_data": {"mime_type": "image/jpeg",
                                       "data": base64.b64encode(data).decode()}})
        usadas += 1

    if usadas == 0:
        return {"productos": "", "descripcion": "", "subcategoria": "",
                "rubro_slugs": [], "confianza": 0.0, "fotos_analizadas": 0,
                "error": "No se pudo descargar ninguna foto"}

    url_api = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}")
    r = None
    try:
        r = httpx.post(url_api, json={"contents": [{"parts": partes}]}, timeout=TIMEOUT_MODELO)
        r.raise_for_status()
        cuerpo = r.json()
        texto = cuerpo["candidates"][0]["content"]["parts"][0]["text"]
        out = _parsear(texto)
        # Consumo real de ESTA llamada. Sin esto el costo sólo se puede estimar,
        # o mirar agregado en el panel de Google: acá se ve por comercio, que es
        # lo que permite decidir si conviene bajar a un modelo más barato o
        # mandar menos fotos.
        uso = cuerpo.get("usageMetadata") or {}
    except Exception as exc:  # noqa: BLE001
        # El crudo es lo único que distingue "no vio nada" de "la llamada
        # falló": sin esto las dos cosas se ven idénticas en el panel.
        crudo = ""
        if r is not None:                      # si falló la conexión, no hay respuesta
            try:
                crudo = str(r.json())[:600]
            except Exception:  # noqa: BLE001
                crudo = str(getattr(r, "text", ""))[:600]
        detalle = _sin_secretos(str(exc))
        crudo = _sin_secretos(crudo)
        logger.warning("vision.modelo_fallo", error=detalle, crudo=crudo)
        # Un 404 acá casi siempre es el nombre del modelo, no la key: conviene
        # decirlo, porque el mensaje crudo de httpx no lo sugiere.
        ayuda = ""
        if "404" in detalle:
            ayuda = (f" — el modelo '{settings.gemini_model}' no existe para esta API key. "
                     "Verificá GEMINI_MODEL contra los modelos que la key tiene habilitados.")
        return {"productos": "", "descripcion": "", "subcategoria": "",
                "rubro_slugs": [], "confianza": 0.0, "fotos_analizadas": usadas,
                "error": f"El modelo falló: {detalle}{ayuda}", "crudo": crudo}

    # El modelo devuelve seguido el NOMBRE del rubro ("Juguetería", "🧸 Juguetería,
    # librería y escolar") en vez del slug, aunque el prompt pida el slug. Exigir
    # coincidencia exacta descartaba todo y el comercio quedaba sin categorías sin
    # que se viera por qué. Se acepta slug o nombre, sin tildes ni mayúsculas.
    def _clave(t: str) -> str:
        import unicodedata
        sin_tildes = "".join(c for c in unicodedata.normalize("NFD", t or "")
                             if unicodedata.category(c) != "Mn")
        return re.sub(r"[^a-z0-9]+", "", sin_tildes.lower())

    equivalencias: dict[str, str] = {}
    for r in rubros:
        slug = r.get("slug")
        if not slug:
            continue
        equivalencias[_clave(slug)] = slug
        if r.get("nombre"):
            equivalencias[_clave(r["nombre"])] = slug

    propuestos, descartados = [], []
    for crudo_slug in (out.get("rubro_slugs") or []):
        real = equivalencias.get(_clave(str(crudo_slug)))
        if real and real not in propuestos:
            propuestos.append(real)
        elif not real:
            descartados.append(str(crudo_slug))
    if descartados:
        logger.info("vision.slugs_invalidos", descartados=descartados)

    logger.info("vision.uso", fotos=usadas, tokens=uso.get("totalTokenCount"),
                modelo=settings.gemini_model, confianza=out.get("confianza"))

    return {
        "productos": (out.get("productos") or "").strip(),
        "descripcion": (out.get("descripcion") or "").strip(),
        "subcategoria": (out.get("subcategoria") or "").strip(),
        "rubro_slugs": propuestos,
        "confianza": float(out.get("confianza") or 0),
        "fotos_analizadas": usadas,
        "slugs_descartados": descartados,
        "tokens": {
            "entrada": uso.get("promptTokenCount"),
            "salida": uso.get("candidatesTokenCount"),
            "total": uso.get("totalTokenCount"),
        },
        # Lo que respondió el modelo, tal cual. Es la única forma de saber si una
        # confianza baja es honesta o si el prompt está pidiendo mal las cosas.
        "crudo": texto[:1500],
    }
