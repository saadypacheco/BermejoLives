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
import time

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


# Los 503 y 429 de Gemini son transitorios: el modelo está saturado y la misma
# llamada funciona segundos después. Sin reintento, el admin ve un error y tiene
# que volver a apretar el botón por algo que se resuelve solo.
REINTENTOS = 3
ESPERA_BASE = 1.5   # segundos; se duplica en cada intento
_ESTADOS_REINTENTABLES = {429, 500, 502, 503, 504}
# Más que esto y conviene devolver el error: el admin está esperando
# frente a la pantalla y reintentar gasta cuota que ya está agotada.
ESPERA_MAX_RAZONABLE = 20   # segundos


def _retry_after(r: "httpx.Response") -> float:
    """Segundos que pide esperar el servidor.

    Gemini no siempre manda la cabecera Retry-After: en los 429 por cuota lo dice
    dentro del cuerpo ("Please retry in 34.2s"). Ignorar ese número significa
    reintentar antes de tiempo, fallar igual, y encima gastar otra request de la
    misma cuota que ya está agotada.
    """
    try:
        cabecera = float(r.headers.get("retry-after") or 0)
        if cabecera:
            return cabecera
    except (TypeError, ValueError):
        pass
    try:
        mensaje = str(r.json())
    except Exception:  # noqa: BLE001
        return 0.0
    m = re.search(r"retry in ([\d.]+)s", mensaje, re.IGNORECASE)
    return float(m.group(1)) if m else 0.0


def _cuota_agotada(r: "httpx.Response") -> bool:
    """Distingue "estás yendo muy rápido" de "se te acabó la cuota".

    Reintentar cuando la cuota se agotó no sirve —el límite no se repone en
    segundos— y cada intento consume otra request de esa misma cuota.
    """
    try:
        return "free_tier" in str(r.json()) or "RESOURCE_EXHAUSTED" in str(r.json())
    except Exception:  # noqa: BLE001
        return False


def _post_con_reintentos(url: str, payload: dict) -> "httpx.Response":
    ultimo = None
    for intento in range(REINTENTOS):
        try:
            r = httpx.post(url, json=payload, timeout=TIMEOUT_MODELO)
            if r.status_code not in _ESTADOS_REINTENTABLES:
                return r
            ultimo = r
            # El 429 es límite de frecuencia, no saturación: hay que esperar más,
            # y el servidor suele decir cuánto en Retry-After. Ignorarlo hace que
            # los tres intentos se quemen dentro de la misma ventana bloqueada.
            espera = ESPERA_BASE * (2 ** intento)
            if r.status_code == 429:
                sugerida = _retry_after(r)
                # Si la cuota está agotada y el servidor pide esperar más de lo
                # que un humano va a tolerar frente a la pantalla, se corta acá:
                # insistir sólo quema requests de la cuota agotada.
                if _cuota_agotada(r) and sugerida > ESPERA_MAX_RAZONABLE:
                    logger.info("vision.cuota_agotada", espera_sugerida=sugerida)
                    return r
                espera = max(espera * 4, sugerida)
            logger.info("vision.reintento", intento=intento + 1, status=r.status_code,
                        espera=round(espera, 1))
            if intento < REINTENTOS - 1:
                time.sleep(espera)
            continue
        except httpx.TimeoutException:
            ultimo = None
            logger.info("vision.reintento", intento=intento + 1, motivo="timeout")
            if intento < REINTENTOS - 1:
                time.sleep(ESPERA_BASE * (2 ** intento))
    if ultimo is not None:
        return ultimo
    # Todos los intentos fueron timeout: se deja que el caller lo trate como fallo.
    raise httpx.TimeoutException(f"El modelo no respondió tras {REINTENTOS} intentos")


def _prompt(rubros: list[dict]) -> str:
    lista = "\n".join(f"- {r['slug']}: {r.get('nombre', r['slug'])}" for r in rubros if r.get("slug"))
    return f"""Sos un relevador de comercios en Bermejo, Bolivia — una ciudad de frontera.
Mirás fotos de la fachada o la vidriera de un local y decís qué vende.

Devolvé SOLO un JSON, sin markdown, con esta forma exacta:
{{
  "nombre_cartel": "lo que dice el cartel del local, tal cual está escrito",
  "productos": "lista de 4 a 8 productos separados por coma, en singular y en la palabra que usaría un cliente",
  "descripcion": "una o dos frases sobre el negocio, en español rioplatense, sin adjetivos publicitarios",
  "subcategoria": "el tipo específico de negocio en 1 o 2 palabras (ej: peluches, celulares, ropa de bebé)",
  "sinonimos": {{"producto": "otra forma, otra forma mas"}},
  "rubro_slugs": ["slug1", "slug2"],
  "categoria_sugerida": "",
  "confianza": 0.0
}}

Reglas:
- `rubro_slugs`: SOLO slugs de la lista de abajo. Todos los que apliquen — un local
  que vende neumáticos y también zapatillas lleva los dos. Si no podés determinar
  ninguno, devolvé [].
- `categoria_sugerida`: si el negocio NO encaja bien en ninguno de los rubros de
  la lista, o si merecería una categoría más específica que la que elegiste,
  escribí acá el nombre que le pondrías (2 o 3 palabras, en singular). Si la
  lista lo cubre bien, dejalo vacío. Es para detectar qué categorías le faltan
  al sistema, así que no fuerces: sugerí sólo cuando de verdad falta algo.
- `nombre_cartel`: leé el cartel, la marquesina o la vidriera y transcribí el
  NOMBRE del negocio tal cual está escrito, respetando mayúsculas y
  abreviaturas. Es el dato que no se puede deducir de ninguna otra forma: si no
  está acá, hay que volver caminando hasta el local a copiarlo.
  Poné "" si no se lee, si dudás, o si lo que ves es un rubro y no un nombre
  ("ROPA", "BAZAR", "MODA Y ROPA" son lo que vende, no cómo se llama).
  Un nombre inventado es peor que ninguno: queda escrito como si fuera cierto y
  nadie vuelve a revisarlo. Ante la duda, vacío.
- `productos`: SOLO lo que se ve en las fotos. No completes con lo que "suele"
  vender un negocio así.
- `sinonimos`: Bermejo es frontera con Argentina, y cada producto se llama
  distinto de un lado y del otro. Es un OBJETO: una clave por cada producto que
  pusiste, y como valor las otras palabras con las que un comprador podría
  buscarlo — el término argentino, el boliviano, el genérico y el de marca si se
  usa como genérico.
  Ejemplo: {{"remera": "polera, camiseta", "campera": "casaca, chamarra"}}
  Va producto por producto y no una lista suelta porque estos sinónimos se
  guardan en un diccionario compartido: lo que aprendas de ESTA vidriera va a
  hacer que se encuentren todos los demás locales que venden lo mismo. Una lista
  sin saber a qué producto pertenece cada palabra no sirve para eso.
  Sólo palabras que nombren LA MISMA COSA: "remera" y "ropa" no son sinónimos,
  uno es la categoría del otro. Un sinónimo de más manda al comprador a un local
  que no tiene lo que busca, y eso es peor que no encontrar nada.
  Si un producto no tiene otra forma de decirse, no lo incluyas.
- `subcategoria`: en SINGULAR y con la palabra más común. Si se te ocurren dos
  términos unidos ("bolsos y mochilas"), elegí uno solo y mandá el otro en
  `sinonimos` — dos comercios iguales con la subcategoría escrita al revés
  quedan contados como categorías distintas y ninguna sirve de filtro.
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
        return {"productos": "", "descripcion": "", "subcategoria": "", "sinonimos": "",
                "nombre_cartel": "",
                "rubro_slugs": [], "confianza": 0.0, "fotos_analizadas": 0,
                "error": "No se pudo descargar ninguna foto"}

    url_api = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}")
    r = None
    try:
        r = _post_con_reintentos(url_api, {"contents": [{"parts": partes}]})
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
        if "429" in detalle:
            ayuda = (" — se agotó la cuota del modelo. Suele pasar cuando la API key "
                     "pertenece a un proyecto SIN facturación asociada: ahí se aplica el "
                     "límite gratuito (20 requests). Revisá que la key sea del mismo "
                     "proyecto que la cuenta de facturación.")
        elif "404" in detalle:
            ayuda = (f" — el modelo '{settings.gemini_model}' no existe para esta API key. "
                     "Verificá GEMINI_MODEL contra los modelos que la key tiene habilitados.")
        return {"productos": "", "descripcion": "", "subcategoria": "", "sinonimos": "",
                "nombre_cartel": "",
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
        "nombre_cartel": (out.get("nombre_cartel") or "").strip(),
        "productos": (out.get("productos") or "").strip(),
        "descripcion": (out.get("descripcion") or "").strip(),
        "subcategoria": (out.get("subcategoria") or "").strip(),
        # Se pasa tal cual (objeto o texto): lo interpreta desde_propuesta().
        "sinonimos": out.get("sinonimos") or "",
        "categoria_sugerida": (out.get("categoria_sugerida") or "").strip(),
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
