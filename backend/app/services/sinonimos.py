"""Diccionario de sinónimos de productos, y cómo se aplica a un comercio.

El problema es de frontera. En Bermejo conviven dos vocabularios: el comprador
argentino escribe "remera" y el boliviano "polera", y hoy el que escribe una de
las dos ve la mitad de los locales que hay. El buscador hace stemming en español
—encuentra "zapatillas" buscando "zapatilla"— pero no tiene forma de saber que
"polera" y "remera" son la misma prenda.

Dos decisiones que explican la forma de este módulo:

**Es un diccionario, no un campo por comercio.** Entre 161 comercios no hay 161
vocabularios; hay unos pocos cientos de productos repetidos. Pedirle sinónimos a
la IA comercio por comercio sería pagar la misma respuesta decenas de veces.
Pedidos como diccionario, los sinónimos se calculan una vez y se aplican a todos
—incluidos los que ya estaban cargados, que era la pregunta— y los comercios
nuevos se resuelven sin gastar una llamada.

**Es texto, no imágenes.** Para saber que "campera" también se dice "casaca" no
hace falta ver la foto, alcanza la palabra. Sacar las imágenes de la llamada es
lo que baja el costo de dólares a centavos: los productos ya están escritos en
`prod_det_ia` desde el análisis anterior.
"""
from __future__ import annotations

import json
import re

import structlog

from app.core.config import settings
from app.services.normalizar import sin_tildes, singular

logger = structlog.get_logger()

# Con lotes más grandes el modelo empieza a devolver el JSON cortado y se pierde
# el lote entero; con lotes más chicos se repite la instrucción muchas veces.
TERMINOS_POR_LOTE = 40

# Un término con demasiados sinónimos casi siempre significa que el modelo se
# fue por las ramas ("zapatilla → calzado, moda, vestimenta, indumentaria...").
# Sinónimos de más traen resultados equivocados, que es peor que no traer nada.
MAX_SINONIMOS = 6


def _prompt(terminos: list[str]) -> str:
    lista = "\n".join(f"- {t}" for t in terminos)
    return f"""Sos de Bermejo, Bolivia, ciudad de frontera con Argentina. La gente
que compra acá viene de los dos lados y cada uno le dice distinto a la misma cosa.

Para cada término de la lista, devolvé las OTRAS palabras con las que alguien
podría buscar exactamente ese mismo producto.

Devolvé SOLO un JSON, sin markdown:
{{"termino": "sinonimo1, sinonimo2", "otro termino": "sinonimo1"}}

Reglas:
- Incluí el término argentino, el boliviano, el genérico, y la marca si se usa
  como nombre común (curita, durex).
  Ejemplos: remera -> polera, camiseta · zapatilla -> tenis, championes, calzado
  deportivo · campera -> casaca, chamarra · pollera -> falda · frazada -> cobija,
  manta · celular -> movil, telefono
- SOLO palabras que nombren LA MISMA COSA. "zapatilla" y "zapato" NO son
  sinónimos; "remera" y "ropa" tampoco (uno es la categoría del otro).
  Un sinónimo de más hace que el comprador reciba locales que no tienen lo que
  busca, y eso es peor que no encontrar nada.
- Máximo {MAX_SINONIMOS} por término. Si no se te ocurre ninguno bueno, poné "".
- Sin tildes, en minúsculas, en singular. Sólo la palabra, sin explicar.
- No repitas el término dentro de sus propios sinónimos.

Términos:
{lista}"""


def _normalizar_termino(texto: str) -> str:
    """Clave del diccionario. Comparte reglas con la normalización de
    subcategorías para que "Zapatillas" y "zapatilla" caigan en la misma fila."""
    base = re.sub(r"[^a-z0-9ñ ]+", " ", sin_tildes(texto or "").lower())
    palabras = [singular(p) for p in base.split() if p]
    return " ".join(palabras).strip()


def _limpiar(termino: str, crudo: str) -> str:
    """Deja los sinónimos utilizables de una respuesta del modelo."""
    clave = _normalizar_termino(termino)
    vistos: list[str] = []
    for parte in (crudo or "").split(","):
        s = re.sub(r"[^a-z0-9ñ ]+", " ", sin_tildes(parte).lower()).strip()
        s = " ".join(s.split())
        # Se descarta el término repitiéndose a sí mismo y lo que ya está: no
        # aportan nada al índice y sólo hacen ruido en la revisión a mano.
        if not s or len(s) < 3 or _normalizar_termino(s) == clave or s in vistos:
            continue
        vistos.append(s)
        if len(vistos) >= MAX_SINONIMOS:
            break
    return ", ".join(vistos)


def generar_diccionario(terminos: list[str], post) -> dict[str, str]:
    """Pide sinónimos para una lista de términos. `post` es la función que llama
    al modelo (se inyecta para poder probar esto sin red ni API key).

    Devuelve {termino_normalizado: "sin1, sin2"}. Los términos sin sinónimos
    útiles no aparecen.
    """
    unicos: list[str] = []
    for t in terminos:
        n = _normalizar_termino(t)
        if n and len(n) >= 3 and n not in unicos:
            unicos.append(n)

    salida: dict[str, str] = {}
    for i in range(0, len(unicos), TERMINOS_POR_LOTE):
        lote = unicos[i:i + TERMINOS_POR_LOTE]
        try:
            crudo = post(_prompt(lote))
            datos = _json(crudo)
        except Exception as e:  # noqa: BLE001
            # Un lote que falla no puede tirar abajo los demás: el diccionario
            # es acumulativo y la corrida se puede repetir sobre lo que faltó.
            logger.warning("sinonimos.lote_fallido", desde=i, error=str(e)[:200])
            continue

        for termino, valor in (datos or {}).items():
            if isinstance(valor, list):
                valor = ", ".join(str(v) for v in valor)
            limpio = _limpiar(termino, str(valor or ""))
            if limpio:
                salida[_normalizar_termino(termino)] = limpio

        logger.info("sinonimos.lote", desde=i, pedidos=len(lote), obtenidos=len(salida))

    return salida


def _json(texto: str) -> dict:
    limpio = (texto or "").strip().strip("`").strip()
    if limpio.lower().startswith("json"):
        limpio = limpio[4:].strip()
    m = re.search(r"\{.*\}", limpio, re.S)
    return json.loads(m.group(0) if m else limpio)


def terminos_de_comercio(comercio: dict) -> list[str]:
    """Los términos buscables de un comercio: sus productos y su subcategoría."""
    crudos: list[str] = []
    for campo in ("prod_det_ia", "prod_obs_human"):
        crudos += [p for p in (comercio.get(campo) or "").split(",")]
    if comercio.get("subcategoria"):
        crudos.append(comercio["subcategoria"])

    salida: list[str] = []
    for c in crudos:
        n = _normalizar_termino(c)
        if n and len(n) >= 3 and n not in salida:
            salida.append(n)
    return salida


def sinonimos_para(comercio: dict, diccionario: dict[str, str]) -> str:
    """Los sinónimos que le corresponden a un comercio según el diccionario.

    Se busca término por término y también palabra por palabra: si el comercio
    tiene "remera de algodon" y el diccionario conoce "remera", igual matchea.
    Sin eso, el diccionario sólo serviría para productos escritos de una única
    forma, que es justo lo que no pasa con texto libre.
    """
    encontrados: list[str] = []
    for termino in terminos_de_comercio(comercio):
        candidatos = [termino] + [p for p in termino.split() if len(p) >= 3]
        for c in candidatos:
            for s in (diccionario.get(c) or "").split(","):
                s = s.strip()
                if s and s not in encontrados:
                    encontrados.append(s)
    return ", ".join(encontrados)


def gemini_post(prompt: str) -> str:
    """Llamada de texto al modelo. Sin imágenes: es lo que la vuelve barata."""
    from app.services.vision import _post_con_reintentos, _sin_secretos

    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY no configurada")

    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}")
    r = _post_con_reintentos(url, {"contents": [{"parts": [{"text": prompt}]}]})
    if r.status_code >= 400:
        raise RuntimeError(_sin_secretos(f"HTTP {r.status_code}: {r.text[:300]}"))

    cuerpo = r.json()
    partes = cuerpo["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in partes)


def desde_propuesta(valor) -> tuple[str, dict[str, str]]:
    """Interpreta el campo `sinonimos` de un análisis por fotos.

    Devuelve (texto_para_el_comercio, aportes_al_diccionario).

    El modelo lo devuelve como objeto {producto: "sin1, sin2"}, y de ahí salen
    las dos cosas: el texto plano que se indexa en ese comercio, y las entradas
    que enriquecen el diccionario compartido. Ese segundo uso es el que importa
    a largo plazo — sin él, lo que la IA aprende mirando UNA vidriera se queda en
    ese local y los otros veinte que venden lo mismo no se enteran.

    Acepta también el formato viejo (una lista suelta separada por comas). En ese
    caso el texto sirve igual para indexar, pero NO aporta al diccionario: sin
    saber a qué producto pertenece cada palabra, guardarla sería inventar una
    relación que el modelo nunca afirmó.
    """
    if isinstance(valor, dict):
        aportes: dict[str, str] = {}
        for termino, sins in valor.items():
            if isinstance(sins, list):
                sins = ", ".join(str(x) for x in sins)
            clave = _normalizar_termino(str(termino))
            limpio = _limpiar(str(termino), str(sins or ""))
            if clave and len(clave) >= 3 and limpio:
                aportes[clave] = limpio

        planos: list[str] = []
        for v in aportes.values():
            for s in v.split(","):
                s = s.strip()
                if s and s not in planos:
                    planos.append(s)
        return ", ".join(planos), aportes

    return str(valor or "").strip(), {}
