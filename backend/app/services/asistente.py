"""Uruku Ayuda: el asistente del sitio, y el mismo núcleo como asistente de un comercio.

ESCALONADO, como pide el plan (docs/uruku-ai-plan.md):

  Nivel 0  Sin modelo. Horario, dirección, teléfono, dólar, clima, "dónde
           consigo X" (la misma búsqueda del sitio), mercados y galerías, las
           preguntas frecuentes de URUKU y el SABER LOCAL que se carga desde el
           admin. Cubre la mayoría de lo que la gente pregunta, y cuesta cero.
  Nivel 1  Gemini, con los datos de la base adentro del prompt: los comercios
           que encontró la búsqueda, el saber local que se parece a la
           pregunta, las cotizaciones. Nunca el catálogo entero. Y con una
           regla que el modelo tiene que devolver por escrito: si los datos no
           alcanzan, `seguro: false`, y se cae al nivel siguiente.
  Nivel 3  Humano. La pregunta queda anotada como SIN RESPUESTA. En el admin
           se contesta una vez y pasa a ser saber local: la próxima vez la
           contesta el Nivel 0. Así el asistente aprende de lo que la gente
           pregunta, no de lo que alguien imaginó que preguntaría.

CON `comercio_id`, el mismo núcleo atiende a los clientes de UN comercio con
los datos de ese comercio (horario, dirección, ofertas, qué vende). El humano
del Nivel 3 ahí es el dueño del local. Es el "asistente 24/7" del plan
Empleado Digital: quién puede usarlo lo decide `planes.funcion`, no este
archivo.

Los datos salen de la base, no del modelo: un precio inventado se paga en el
mostrador, con un cliente que vino por eso.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

import httpx
import structlog

from app.core.config import settings
from app.services import horario as hor

logger = structlog.get_logger()

TZ = ZoneInfo("America/La_Paz")
SITIO = "https://uruku.bo"

# Cuántos comercios se muestran en una respuesta. Cinco entran en una pantalla
# de celular sin scroll; el "ver todos" lleva al buscador.
MAX_COMERCIOS = 5


@dataclass
class Respuesta:
    texto: str
    nivel: int                                   # 0 | 1 | 3
    intent: str
    fuentes: list[dict] = field(default_factory=list)   # {tipo, nombre, url}
    sugerencias: list[str] = field(default_factory=list)
    sin_respuesta: bool = False


# --------------------------------------------------------------------------- texto

_STOP = set("""a al algo alguna algun ante bs bolivianos cerca como con cual cuales cuanto cuanta cuantos
de del donde el ella ellos en es esta este esto hay hola la las lo los me mi mis muy no o para pero por que
quien se si sin sobre su sus tiene tienen un una unas unos y ya yo tengo quiero busco necesito consigo
compro comprar vende venden venda saber decime dime podes puede puedo por favor gracias buenas buenos dias
tardes noches uruku bermejo ciudad""".split())


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9ñ\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _terminos(pregunta: str) -> list[str]:
    return [t for t in _norm(pregunta).split() if t not in _STOP and len(t) > 1]


_RELLENO = set("a al de del la el lo los las que hora horas horario local negocio comercio tienda es esta estan "
               "abre abren cierra cierran abierto abiertos hoy ahora queda esta ubicacion direccion telefono "
               "whatsapp numero contacto celular como llego llegar donde cual cuales tiene tienen".split())


def _despues_de(pregunta: str, patron: str) -> str:
    """El nombre del local que viene después de la intención: "¿a qué hora abre
    Rústico?" → "rustico". Se sacan las palabras de relleno que quedan entre
    la intención y el nombre ("a que hora abre" tiene tres)."""
    m = re.search(patron + r"\s+(.+)$", _norm(pregunta))
    if not m:
        return ""
    tokens = m.group(1).split()
    while tokens and tokens[0] in _RELLENO:
        tokens.pop(0)
    while tokens and tokens[-1] in _RELLENO:
        tokens.pop()
    return " ".join(tokens)


def _url(c: dict) -> str:
    return f"{SITIO}/comercios/{c.get('slug')}"


def _fuente(c: dict) -> dict:
    return {"tipo": "comercio", "nombre": c.get("nombre"), "url": _url(c), "detalle": c.get("subcategoria") or c.get("direccion") or ""}


def _wa(numero: str | None) -> str | None:
    return f"https://wa.me/{numero}" if numero else None


def _maps(c: dict) -> str | None:
    if c.get("lat") and c.get("lng"):
        return f"https://www.google.com/maps/search/?api=1&query={c['lat']},{c['lng']}"
    if c.get("direccion"):
        return "https://www.google.com/maps/search/?api=1&query=" + quote_plus(f"{c['direccion']}, Bermejo, Bolivia")
    return None


# --------------------------------------------------------------------------- preguntas frecuentes

# Lo que URUKU es, dicho una vez. Cada entrada: patrón sobre la pregunta
# normalizada → respuesta. Es Nivel 0: se contesta sin modelo y siempre igual.
FAQ: list[tuple[str, str, str]] = [
    (r"\bque es uruku|\bpara que sirve|\bque hace uruku|\bcomo funciona",
     "URUKU es el directorio de Bermejo: todo lo que se vende en la ciudad, en el mapa, con el WhatsApp "
     "de cada local. Buscás lo que necesitás, ves quién lo tiene, le escribís directo y sabés cómo llegar. "
     "No cobra comisión: la compra es entre vos y el comercio.",
     "que_es"),
    (r"(registr|sum|pon|carg|public|sub|anot)\w*.*(negocio|local|comercio|tienda|empresa)|como me registro|como me sumo",
     f"Registrar tu negocio es gratis y lleva dos minutos: {SITIO}/autoregistro?modo=registro. "
     "Cargás nombre, qué vendés, ubicación y WhatsApp, y ya aparecés en el mapa y en las búsquedas.",
     "registrar"),
    (r"(publicar|subir|mandar|cargar).*(oferta|promo|novedad|foto)|como (publico|subo) (una )?oferta",
     "Las ofertas se publican mandando una foto al grupo de WhatsApp que URUKU le crea a cada local "
     "(«URUKU · nombre del local»), con el precio si lo tiene. Sale en la ficha del negocio y en el canal "
     "de ofertas de Bermejo. Si tu local todavía no tiene el grupo, registralo y te lo creamos.",
     "publicar_oferta"),
    # Los planes se contestan aparte, leyendo la base: ver _nivel0_planes.
    (r"\bcomision|se paga por venta|cobran por vender",
     "URUKU no cobra comisión por venta. La compra es directa entre el comprador y el comercio, por WhatsApp "
     "o en el local, y el comercio cobra como siempre.",
     "comision"),
    (r"reclamo|queja|denunci|me estafaron|no me entregaron",
     f"URUKU no interviene en la compra, pero sí quiere saber si un comercio hizo algo mal: dejá tu reclamo "
     f"en {SITIO}/reclamos y lo revisamos. Si es una estafa, hacé también la denuncia en la policía.",
     "reclamo"),
    (r"\bcanal\b.*(whatsapp|ofertas)|ofertas del dia|ver (las )?ofertas",
     f"Las ofertas de toda la ciudad están en {SITIO}/buscar?of=1, y también en el canal de WhatsApp "
     "de URUKU, que podés seguir desde el sitio.",
     "ofertas"),
]

SUGERENCIAS_INICIALES = [
    "¿Dónde cambio dólares?",
    "¿Qué hay abierto ahora?",
    "Busco zapatillas",
    "¿Cómo publico mi negocio?",
]


# --------------------------------------------------------------------------- Nivel 0: el sitio

def _num(v) -> str:
    """11.2 → "11,2"; 1510.0 → "1.510". Como se escribe acá, no como lo guarda la base."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    s = f"{int(f):,}" if f == int(f) else f"{f:,.2f}".rstrip("0").rstrip(".")
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _cotizaciones(repo) -> str | None:
    """Las dos que importan acá: dólar y peso argentino, en bolivianos. La
    tercera (dólar en pesos) es de la otra orilla y sólo confunde."""
    filas = [c for c in (repo.list_cotizaciones() or []) if c.get("valor") and (c.get("unidad") or "Bs") == "Bs"]
    if not filas:
        return None
    partes = [f"{c.get('etiqueta')} {_num(c.get('valor'))} Bs" + (f" (por {c['detalle']})" if c.get("detalle") else "")
              for c in sorted(filas, key=lambda x: x.get("orden", 0))]
    return "Hoy: " + " · ".join(partes) + "."


URL_CASAS_DE_CAMBIO = f"{SITIO}/buscar?rubro=cambio&vista=mapa"
URL_CAMBIO = f"{SITIO}/cambio"

_MONEDA = {
    "ARS": r"pesos?(?: argentinos?)?|\$|ars|arg",
    "BOB": r"bolivianos?|\bbs\b|bob",
    "USD": r"dolares?|usd|u\$s|verdes",
}
_NOMBRE = {"ARS": "pesos argentinos", "BOB": "bolivianos", "USD": "dólares"}
_SIMBOLO = {"ARS": "$", "BOB": "Bs", "USD": "US$"}


def _tasas(repo) -> dict:
    """Bs por 1 USD, Bs por 1 ARS, ARS por 1 USD, y la fecha más vieja."""
    por = {c.get("clave"): c for c in (repo.list_cotizaciones() or [])}

    def v(k):
        x = (por.get(k) or {}).get("valor")
        return float(x) if x else None
    fechas = sorted(str(c.get("actualizado_en")) for c in por.values() if c.get("actualizado_en"))
    ars = v("ars_bob")   # la tabla lo guarda por 1.000 pesos
    return {"usd_bob": v("usd_bob"), "ars_bob": ars / 1000 if ars else None, "usd_ars": v("usd_ars"),
            "actualizado_en": fechas[0] if fechas else None}


def _convertir(monto: float, de: str, a: str, t: dict) -> float | None:
    if de == a:
        return monto
    if de == "USD" and a == "ARS" and t["usd_ars"]:
        return monto * t["usd_ars"]
    if de == "ARS" and a == "USD" and t["usd_ars"]:
        return monto / t["usd_ars"]
    bs = monto if de == "BOB" else (monto * t["ars_bob"] if de == "ARS" and t["ars_bob"] else (monto * t["usd_bob"] if de == "USD" and t["usd_bob"] else None))
    if bs is None:
        return None
    if a == "BOB":
        return bs
    if a == "ARS":
        return bs / t["ars_bob"] if t["ars_bob"] else None
    return bs / t["usd_bob"] if t["usd_bob"] else None


def _nivel0_conversion(repo, pregunta: str) -> Respuesta | None:
    """«¿Cuánto son 5.000 pesos en bolivianos?» → el número, con la fecha de la
    cotización y el conversor. Sin monto no es conversión (es cotización)."""
    # Sin la normalización dura: "5.000" tiene que seguir siendo cinco mil, y
    # el "$" tiene que sobrevivir para saber que son pesos.
    p = unicodedata.normalize("NFD", (pregunta or "").lower())
    p = "".join(c for c in p if unicodedata.category(c) != "Mn")
    p = re.sub(r"[^a-z0-9ñ$.,\s]", " ", p)
    m = re.search(r"(\d[\d.,]*)\s*(?:mil\s*)?(" + "|".join(_MONEDA.values()) + r")", p)
    if not m:
        return None
    try:
        monto = float(m.group(1).replace(".", "").replace(",", "."))
    except ValueError:
        return None
    if "mil" in p[m.start():m.end()]:
        monto *= 1000
    de = next(k for k, pat in _MONEDA.items() if re.fullmatch(pat, m.group(2)))
    resto = p[m.end():]
    a = next((k for k, pat in _MONEDA.items() if k != de and re.search(r"(?:en|a|de)\s+(?:" + pat + ")", resto)), None)
    if a is None:
        a = "BOB" if de != "BOB" else "ARS"
    t = _tasas(repo)
    r = _convertir(monto, de, a, t)
    if r is None:
        return Respuesta(texto=f"No tengo cargada la cotización para eso. Mirá el conversor: {URL_CAMBIO}",
                         nivel=0, intent="conversion", sin_respuesta=True)
    fecha = ""
    if t["actualizado_en"]:
        try:
            dias = (datetime.now(TZ) - datetime.fromisoformat(t["actualizado_en"].replace("Z", "+00:00"))).days
            fecha = " de hoy" if dias <= 0 else f" de hace {dias} día{'s' if dias != 1 else ''}"
        except ValueError:
            fecha = ""
    texto = (f"{_SIMBOLO[de]} {_num(monto)} {_NOMBRE[de]} son unos {_SIMBOLO[a]} {_num(round(r, 2))} {_NOMBRE[a]}, "
             f"con la cotización{fecha}. Cada casa de cambio tiene la suya: compará. Conversor y casas de cambio: {URL_CAMBIO}")
    return Respuesta(texto=texto, nivel=0, intent="conversion",
                     sugerencias=["¿Dónde cambio dólares?", "¿A cuánto está el dólar?"])


def _casas_de_cambio(repo, ahora: datetime) -> Respuesta:
    """«¿Dónde cambio dólares?» es DÓNDE, no A CUÁNTO. La respuesta es lo que
    el sitio tiene y nadie más: las casas de cambio, cuáles están abiertas
    ahora, y el mapa para ir. La cotización va al final, como dato extra."""
    casas = list(repo.buscar_comercios("", 40, rubro="cambio") or [])
    cot = _cotizaciones(repo)
    if not casas:
        texto = f"Todavía no tengo casas de cambio cargadas en el mapa. Mirá el rubro acá: {URL_CASAS_DE_CAMBIO}"
        return Respuesta(texto=texto + (f"\n{cot}" if cot else ""), nivel=0, intent="casas_de_cambio", sin_respuesta=True)

    def _estado(c):
        return hor.abierto_ahora(c.get("horario"), ahora).estado if c.get("horario") else "desconocido"
    # Las abiertas primero; después las que no dicen; las cerradas al final.
    orden = {"abierto": 0, "desconocido": 1, "cerrado": 2}
    casas.sort(key=lambda c: orden[_estado(c)])
    abiertas = [c for c in casas if _estado(c) == "abierto"]
    # Se nombran las primeras, tengan o no dirección: la ubicación la tiene
    # el mapa, y ésa es la acción principal de esta respuesta.
    mostrar = casas[:MAX_COMERCIOS]
    lineas = []
    for c in mostrar:
        et = (hor.etiqueta(hor.abierto_ahora(c["horario"], ahora), ahora) or "").lower() if c.get("horario") else ""
        extra = [x for x in [c.get("direccion"), et] if x]
        lineas.append(f"• {c.get('nombre')}" + (f" — {' · '.join(extra)}" if extra else ""))
    cabeza = (f"Hay {len(casas)} casas de cambio en Bermejo" +
              (f", {len(abiertas)} abiertas ahora" if abiertas else "") +
              (f". Las primeras {len(mostrar)}:" if len(casas) > len(mostrar) else ":"))
    texto = (cabeza + "\n" + "\n".join(lineas) +
             f"\nVer las {len(casas)} en el mapa: {URL_CASAS_DE_CAMBIO}" + (f"\n{cot}" if cot else ""))
    return Respuesta(texto=texto, nivel=0, intent="casas_de_cambio", fuentes=[_fuente(c) for c in mostrar],
                     sugerencias=[f"Horario de {mostrar[0].get('nombre')}", "¿A cuánto está el dólar?"])


def _clima(repo) -> str | None:
    c = repo.get_clima() or {}
    if c.get("temp_c") is None:
        return None
    desc = f", {c['descripcion']}" if c.get("descripcion") else ""
    return f"En Bermejo ahora hay {round(c['temp_c'])}°{desc}."


def _comercio_por_nombre(repo, nombre: str) -> list[dict]:
    """Los comercios que se LLAMAN así. Por la búsqueda del sitio (que entiende
    acentos: "rustico" encuentra "Rústico") y quedándose con los que tienen el
    nombre adentro del nombre, no con los que venden algo parecido."""
    nombre = nombre.strip()
    if len(nombre) < 2:
        return []
    n = _norm(nombre)
    filas = list(repo.buscar_comercios(nombre, 10) or [])
    return [c for c in filas if n in _norm(c.get("nombre", ""))][:3]


def _elegir(repo, nombre: str) -> tuple[dict | None, Respuesta | None]:
    """Uno solo por el nombre, o la pregunta de cuál."""
    cands = _comercio_por_nombre(repo, nombre)
    if not cands:
        return None, None
    if len(cands) == 1 or _norm(cands[0].get("nombre", "")) == _norm(nombre):
        return repo.get_comercio(cands[0]["id"]) or cands[0], None
    return None, Respuesta(
        texto="¿Cuál de estos? " + " · ".join(c.get("nombre", "") for c in cands),
        nivel=0, intent="desambiguar", fuentes=[_fuente(c) for c in cands],
        sugerencias=[f"Horario de {c.get('nombre')}" for c in cands[:3]],
    )


def _texto_horario(c: dict, ahora: datetime) -> str:
    h = c.get("horario")
    if not h:
        return f"{c.get('nombre')} no tiene el horario cargado. Escribile por WhatsApp y preguntale."
    e = hor.abierto_ahora(h, ahora)
    et = hor.etiqueta(e, ahora)
    return f"{c.get('nombre')}: {h}." + (f" Ahora: {et.lower()}." if et else "")


def _nivel0_comercio_nombrado(repo, pregunta: str, ahora: datetime) -> Respuesta | None:
    """Preguntas sobre UN comercio nombrado en la pregunta."""
    p = _norm(pregunta)
    intents = [
        (r"(?:horario|hora(?:s)?|abre|abren|cierra|cierran|esta abierto|estan abiertos|abierto)", "horario"),
        (r"(?:direccion|donde queda|donde esta|ubicacion|como llego|como llegar)", "direccion"),
        (r"(?:telefono|whatsapp|numero|contacto|celular)", "contacto"),
    ]
    for patron, intent in intents:
        if not re.search(patron, p):
            continue
        nombre = _despues_de(pregunta, patron)
        if not nombre:
            continue
        c, pregunta_cual = _elegir(repo, nombre)
        if pregunta_cual:
            return pregunta_cual
        if not c:
            continue
        if intent == "horario":
            texto = _texto_horario(c, ahora)
        elif intent == "direccion":
            texto = (f"{c.get('nombre')} queda en {c.get('direccion')}." if c.get("direccion")
                     else f"{c.get('nombre')} no tiene la dirección cargada, pero está en el mapa de su ficha.")
            if _maps(c):
                texto += f" Cómo llegar: {_maps(c)}"
        else:
            if c.get("whatsapp"):
                texto = f"El WhatsApp de {c.get('nombre')} es +{c['whatsapp']}: {_wa(c['whatsapp'])}"
            elif c.get("telefono"):
                texto = f"El teléfono de {c.get('nombre')} es {c['telefono']}."
            else:
                texto = f"{c.get('nombre')} no tiene teléfono cargado. En su ficha está el mapa para ir."
        return Respuesta(texto=texto, nivel=0, intent=intent, fuentes=[_fuente(c)],
                         sugerencias=[f"Dirección de {c.get('nombre')}", f"Horario de {c.get('nombre')}"])
    return None


def _nivel0_busqueda(repo, pregunta: str, ahora: datetime) -> Respuesta | None:
    p = _norm(pregunta)
    m = re.search(r"(?:donde (?:consigo|compro|venden|hay|encuentro)|quien vende|busco|necesito|quiero comprar|hay)\s+(.+)$", p)
    if not m:
        return None
    q = " ".join(t for t in m.group(1).split() if t not in _STOP)
    if not q:
        return None
    return _buscar_y_contestar(repo, q, ahora)


def _buscar_y_contestar(repo, q: str, ahora: datetime) -> Respuesta | None:
    filas = list(repo.buscar_comercios(q, MAX_COMERCIOS) or [])
    if not filas:
        return Respuesta(
            texto=f"No encontré «{q}» en Bermejo todavía. Probá con otra palabra, o mirá el mapa: {SITIO}/buscar?q={q.replace(' ', '+')}",
            nivel=0, intent="buscar", sin_respuesta=True,
            sugerencias=["¿Qué hay abierto ahora?", "¿Dónde cambio dólares?"],
        )
    total = filas[0].get("total") or len(filas)
    lineas = []
    for c in filas:
        extra = []
        if c.get("subcategoria"):
            extra.append(c["subcategoria"])
        if c.get("direccion"):
            extra.append(c["direccion"])
        et = hor.etiqueta(hor.abierto_ahora(c.get("horario"), ahora), ahora) if c.get("horario") else None
        if et:
            extra.append(et.lower())
        lineas.append(f"• {c.get('nombre')}" + (f" — {' · '.join(extra)}" if extra else ""))
    cabeza = f"Encontré {total} para «{q}»" + (f"; los primeros {len(filas)}:" if total > len(filas) else ":")
    pie = f"\nTodos, en el mapa: {SITIO}/buscar?q={q.replace(' ', '+')}" if total > len(filas) else ""
    return Respuesta(texto=cabeza + "\n" + "\n".join(lineas) + pie, nivel=0, intent="buscar",
                     fuentes=[_fuente(c) for c in filas],
                     sugerencias=[f"Horario de {filas[0].get('nombre')}", f"Dirección de {filas[0].get('nombre')}"])


def _nivel0_abierto_ahora(repo, pregunta: str, ahora: datetime) -> Respuesta | None:
    p = _norm(pregunta)
    if not re.search(r"(que|cual|cuales|algo|alguno|hay).*abiert|abierto ahora|abre ahora|abierto (hoy|a esta hora)", p):
        return None
    # "¿qué farmacia hay abierta?" → se busca por lo que queda sin las palabras de abierto.
    resto = " ".join(t for t in p.split() if t not in _STOP and not re.match(r"abiert|abre|ahora|hoy|hora|esta", t))
    filas = list(repo.buscar_comercios(resto, 60) or []) if resto else list(repo.buscar_comercios("", 60) or [])
    abiertos = [c for c in filas if c.get("horario") and hor.abierto_ahora(c["horario"], ahora).estado == "abierto"]
    if not abiertos:
        return Respuesta(texto=("No encuentro nada que figure abierto ahora" + (f" para «{resto}»" if resto else "") +
                                ". Muchos locales no tienen el horario cargado: mirá la ficha y escribiles."),
                         nivel=0, intent="abierto_ahora", sin_respuesta=not resto,
                         sugerencias=["Busco farmacia", "Busco comida"])
    abiertos = abiertos[:MAX_COMERCIOS]
    lineas = [f"• {c.get('nombre')} — {hor.etiqueta(hor.abierto_ahora(c['horario'], ahora), ahora).lower()}" for c in abiertos]
    return Respuesta(texto=("Abiertos ahora" + (f" para «{resto}»" if resto else "") + ":\n" + "\n".join(lineas)),
                     nivel=0, intent="abierto_ahora", fuentes=[_fuente(c) for c in abiertos])


def _nivel0_lugares(repo, pregunta: str) -> Respuesta | None:
    p = _norm(pregunta)
    if not re.search(r"mercado|galeria|feria|paseo|shopping|donde (esta|queda) (el|la) (mercado|galeria|feria)", p):
        return None
    lugares = [l for l in (repo.list_lugares(None) or []) if l.get("activo", True)]
    if not lugares:
        return None
    lineas = [f"• {l.get('nombre')}" + (f" ({l.get('tipo')})" if l.get("tipo") else "") for l in lugares[:8]]
    return Respuesta(texto="Los mercados y galerías de Bermejo:\n" + "\n".join(lineas) +
                     f"\nEn el mapa: {SITIO}/mapa", nivel=0, intent="lugares",
                     sugerencias=["Busco ropa", "Busco zapatillas"])


def _saber_local(repo, pregunta: str, minimo: int = 2) -> tuple[dict | None, int]:
    """La entrada de saber local que más se parece a la pregunta, y cuántas
    palabras distintas comparten.

    Para contestar SIN modelo hacen falta dos palabras en común, o una sola si
    es una etiqueta y la pregunta es corta ("¿qué días hay feria?" → "feria").
    Con una palabra suelta en una pregunta larga no: "cambio de aceite" no es
    "¿dónde cambio dólares?" por compartir "cambio"."""
    terms = set(_terminos(pregunta))
    if not terms:
        return None, 0
    mejor, puntos, mejor_peso = None, 0, -1
    for s in repo.list_saber_local(True) or []:
        etiquetas = {_norm(e) for e in (s.get("etiquetas") or [])}
        en_etiquetas = terms & etiquetas
        en_pregunta = terms & set(_terminos(s.get("pregunta", "")))
        en_respuesta = terms & set(_terminos(s.get("respuesta", "")))
        p = len(en_etiquetas | en_pregunta | en_respuesta)
        if p == 1 and en_etiquetas and len(terms) <= 2:
            p = 2
        # Entre dos con las mismas palabras en común, gana la que las tiene en
        # la pregunta o en las etiquetas: "documentos para pasar" es la de
        # documentos aunque "pasar" sea etiqueta de la de cruzar.
        peso = 2 * len(en_etiquetas) + 2 * len(en_pregunta) + len(en_respuesta)
        if (p, peso) > (puntos, mejor_peso):
            mejor, puntos, mejor_peso = s, p, peso
    return (mejor, puntos) if puntos >= minimo else (None, puntos)


def _nivel0_planes(repo) -> Respuesta:
    """Los planes, de la tabla: nombre, precio y la frase de cada uno. Lo
    mismo que /planes, así el asistente nunca dice un precio viejo."""
    planes = [p for p in (repo.list_planes(True) or []) if p.get("visible", True)]
    if not planes:
        return Respuesta(texto=f"Los planes están en {SITIO}/planes.", nivel=0, intent="faq_planes")
    lineas = []
    for p in sorted(planes, key=lambda x: x.get("orden", 0)):
        precio = "gratis" if not p.get("precio_mes") else f"Bs {_num(p['precio_mes'])}/mes"
        desc = (p.get("descripcion") or "").strip().rstrip(".")
        lineas.append(f"• {p.get('nombre')} — {precio}" + (f": {desc}" if desc else ""))
    return Respuesta(texto="Los planes de URUKU:\n" + "\n".join(lineas) + f"\nTodo el detalle y cómo pagar: {SITIO}/planes",
                     nivel=0, intent="faq_planes", sugerencias=["¿Cómo publico mi negocio?", "¿Cobran comisión?"])


def _nivel0_sitio(repo, pregunta: str, ahora: datetime) -> Respuesta | None:
    p = _norm(pregunta)
    if re.fullmatch(r"(hola|buenas|buen dia|buenos dias|buenas tardes|buenas noches|hey|holis)( uruku)?", p):
        return Respuesta(texto="¡Hola! Soy la ayuda de URUKU. Preguntame dónde conseguir algo en Bermejo, "
                               "si un local está abierto, el dólar, o cómo publicar tu negocio.",
                         nivel=0, intent="saludo", sugerencias=SUGERENCIAS_INICIALES)
    if re.fullmatch(r"(gracias|muchas gracias|ok gracias|genial|perfecto|dale)( uruku)?", p):
        return Respuesta(texto="¡De nada! Cualquier otra cosa, acá estoy.", nivel=0, intent="gracias",
                         sugerencias=SUGERENCIAS_INICIALES)
    for patron, texto, intent in FAQ:
        if re.search(patron, p):
            return Respuesta(texto=texto, nivel=0, intent="faq_" + intent)
    if re.search(r"cuanto (cuesta|sale|vale)|precio(s)? de (los )?plan|\bplan(es)?\b|es gratis|hay que pagar|chatbot para mi", p):
        return _nivel0_planes(repo)
    # Dos preguntas distintas con las mismas palabras: DÓNDE cambiar (un
    # lugar) y A CUÁNTO está (un número). "cambio dólares" / "casa de cambio"
    # / "cambiar plata" son la primera; "a cuánto", "cotización", "el dólar
    # hoy" son la segunda.
    if re.search(r"donde .*(cambi|dolar|peso)|casa(s)? de cambio|cambista|cambiar (plata|dolar|peso|billete)|cambio (de )?(dolar|peso|plata)", p):
        return _casas_de_cambio(repo, ahora)
    r = _nivel0_conversion(repo, pregunta)
    if r:
        return r
    if re.search(r"\bdolar|cotiza|cambio\b|peso(s)? argentino|cuanto esta el peso|blue", p):
        t = _cotizaciones(repo)
        if t:
            return Respuesta(texto=t + f"\nConversor: {URL_CAMBIO} · Casas de cambio, en el mapa: {URL_CASAS_DE_CAMBIO}",
                             nivel=0, intent="cotizacion", sugerencias=["¿Cuánto son 10.000 pesos en bolivianos?", "¿Dónde cambio dólares?"])
    if re.search(r"\bclima|\btiempo\b|lluev|llover|calor|frio|temperatura", p):
        t = _clima(repo)
        if t:
            return Respuesta(texto=t, nivel=0, intent="clima")
    r = _nivel0_comercio_nombrado(repo, pregunta, ahora)
    if r:
        return r
    r = _nivel0_abierto_ahora(repo, pregunta, ahora)
    if r:
        return r
    r = _nivel0_lugares(repo, pregunta)
    if r:
        return r
    s, _ = _saber_local(repo, pregunta)
    if s:
        return Respuesta(texto=s["respuesta"], nivel=0, intent="saber_local",
                         fuentes=[{"tipo": "saber", "nombre": s.get("pregunta"), "url": ""}])
    r = _nivel0_busqueda(repo, pregunta, ahora)
    if r:
        return r
    return None


# --------------------------------------------------------------------------- Nivel 0: un comercio

def _ofertas_de(repo, comercio_id: str) -> list[dict]:
    pubs = repo.list_publicaciones_de_comercio(comercio_id) or []
    return [p for p in pubs if p.get("estado") in (None, "aprobado", "aprobada", "publicada")]


def _nivel0_comercio(repo, c: dict, pregunta: str, ahora: datetime) -> Respuesta | None:
    p = _norm(pregunta)
    nombre = c.get("nombre", "el local")
    if re.search(r"horario|hora(s)?\b|abre|abren|cierra|cierran|abierto|abiertos", p):
        return Respuesta(texto=_texto_horario(c, ahora), nivel=0, intent="horario")
    if re.search(r"direccion|donde (queda|esta|estan)|ubicacion|como (llego|llegar)|mapa", p):
        texto = f"{nombre} queda en {c['direccion']}." if c.get("direccion") else f"{nombre} está en el mapa de su ficha."
        if _maps(c):
            texto += f" Cómo llegar: {_maps(c)}"
        return Respuesta(texto=texto, nivel=0, intent="direccion")
    if re.search(r"telefono|whatsapp|numero|contacto|celular|llamar", p):
        if c.get("whatsapp"):
            return Respuesta(texto=f"El WhatsApp de {nombre} es +{c['whatsapp']}: {_wa(c['whatsapp'])}", nivel=0, intent="contacto")
        if c.get("telefono"):
            return Respuesta(texto=f"El teléfono de {nombre} es {c['telefono']}.", nivel=0, intent="contacto")
    if re.search(r"oferta|promo|descuento|precio|cuanto (sale|cuesta|vale|esta)|carta|menu", p):
        ofertas = _ofertas_de(repo, c["id"])
        if not ofertas:
            return Respuesta(texto=f"{nombre} no tiene ofertas publicadas ahora. Preguntale por WhatsApp: {_wa(c.get('whatsapp')) or 'en su ficha'}",
                             nivel=0, intent="ofertas", sin_respuesta=True)
        lineas = []
        for o in ofertas[:8]:
            precio = f" — {o['precio']} {o.get('moneda') or 'Bs'}" if o.get("precio") else ""
            lineas.append(f"• {o.get('titulo') or 'Oferta'}{precio}")
        return Respuesta(texto=f"Lo que {nombre} tiene publicado:\n" + "\n".join(lineas) + f"\nVer todo: {_url(c)}#ofertas",
                         nivel=0, intent="ofertas")
    return None


# --------------------------------------------------------------------------- Nivel 1: Gemini

def _gemini(prompt: str) -> str | None:
    """Una llamada, texto adentro y texto afuera. None si no hay clave o falla:
    el que llama decide qué hacer sin modelo, nunca explota."""
    if not settings.gemini_api_key:
        return None
    try:
        r = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}",
            json={"contents": [{"parts": [{"text": prompt}]}],
                  "generationConfig": {"temperature": 0.2, "maxOutputTokens": 400}},
            timeout=settings.asistente_timeout_seg,
        )
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:  # noqa: BLE001 — cualquier falla del modelo es "sin modelo"
        logger.warning("asistente.gemini_fallo", error=str(e)[:200])
        return None


def _json_de(texto: str | None) -> dict | None:
    if not texto:
        return None
    m = re.search(r"\{.*\}", texto, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


_REGLAS = (
    "Reglas: contestá en español, cercano y corto (máximo 3 frases, sin markdown). Usá SOLO los datos de abajo. "
    "Si los datos no alcanzan para contestar con certeza, poné \"seguro\": false y decí que no lo sabés — no inventes "
    "precios, horarios, direcciones ni nombres. Nunca des datos de contacto que no estén en los datos. "
    "Devolvé JSON exactamente así: {\"respuesta\": \"...\", \"seguro\": true|false, \"sugerencias\": [\"...\", \"...\"]}"
)


def _nivel1_sitio(repo, pregunta: str, ahora: datetime) -> Respuesta | None:
    terms = _terminos(pregunta)
    q = " ".join(terms[:4])
    comercios = list(repo.buscar_comercios(q, MAX_COMERCIOS) or []) if q else []
    saber, _ = _saber_local(repo, pregunta, minimo=1)
    datos = []
    if comercios:
        datos.append("Comercios que coinciden con la consulta (nombre · qué vende · dirección · horario):\n" + "\n".join(
            f"- {c.get('nombre')} · {c.get('subcategoria') or ''} · {c.get('direccion') or 'sin dirección'} · {c.get('horario') or 'sin horario'} · {_url(c)}"
            for c in comercios))
    if saber:
        datos.append(f"Saber local (escrito por el equipo de URUKU): P: {saber.get('pregunta')} R: {saber.get('respuesta')}")
    cot = _cotizaciones(repo)
    if cot:
        datos.append(cot)
    datos.append("Sobre URUKU: directorio de comercios de Bermejo (Bolivia) con mapa, búsqueda por lo que se vende y "
                 "WhatsApp directo. Registrar un negocio es gratis en uruku.bo/autoregistro. Las ofertas se publican "
                 "mandando una foto al grupo de WhatsApp del local. Sin comisión por venta.")
    prompt = (f"Sos «Uruku Ayuda», el asistente de URUKU. Fecha y hora en Bermejo: {ahora.strftime('%A %d/%m %H:%M')}.\n"
              f"{_REGLAS}\n\nDATOS:\n" + "\n\n".join(datos) + f"\n\nPREGUNTA: {pregunta.strip()}")
    j = _json_de(_gemini(prompt))
    if not j or not j.get("respuesta"):
        return None
    return Respuesta(texto=str(j["respuesta"]).strip(), nivel=1, intent="modelo",
                     fuentes=[_fuente(c) for c in comercios[:3]] + ([{"tipo": "saber", "nombre": saber.get("pregunta"), "url": ""}] if saber else []),
                     sugerencias=[str(s) for s in (j.get("sugerencias") or [])][:3],
                     sin_respuesta=not bool(j.get("seguro", False)))


def _nivel1_comercio(repo, c: dict, pregunta: str, ahora: datetime) -> Respuesta | None:
    ofertas = _ofertas_de(repo, c["id"])
    datos = [
        f"Comercio: {c.get('nombre')}. Qué vende: {c.get('prod_obs_human') or c.get('prod_det_ia') or c.get('descripcion') or 'sin detalle'}.",
        f"Dirección: {c.get('direccion') or 'sin cargar'}. Horario: {c.get('horario') or 'sin cargar'}. "
        f"WhatsApp: {('+' + c['whatsapp']) if c.get('whatsapp') else 'sin cargar'}.",
    ]
    if c.get("descripcion"):
        datos.append(f"Descripción: {c['descripcion']}")
    if ofertas:
        datos.append("Ofertas publicadas:\n" + "\n".join(
            f"- {o.get('titulo') or 'Oferta'}: {o.get('descripcion') or ''} {('— ' + str(o['precio']) + ' ' + (o.get('moneda') or 'Bs')) if o.get('precio') else ''}".strip()
            for o in ofertas[:15]))
    prompt = (f"Sos el asistente de {c.get('nombre')}, un comercio de Bermejo (Bolivia) que está en URUKU. "
              f"Atendés a sus clientes. Fecha y hora: {ahora.strftime('%A %d/%m %H:%M')}.\n{_REGLAS}\n\nDATOS:\n"
              + "\n\n".join(datos) + f"\n\nPREGUNTA DEL CLIENTE: {pregunta.strip()}")
    j = _json_de(_gemini(prompt))
    if not j or not j.get("respuesta"):
        return None
    return Respuesta(texto=str(j["respuesta"]).strip(), nivel=1, intent="modelo",
                     sugerencias=[str(s) for s in (j.get("sugerencias") or [])][:3],
                     sin_respuesta=not bool(j.get("seguro", False)))


# --------------------------------------------------------------------------- Nivel 3: la persona

def _nivel3_sitio() -> Respuesta:
    return Respuesta(
        texto="Eso todavía no lo sé. Lo anoté para averiguarlo y sumarlo — la próxima vez lo contesto. "
              f"Mientras tanto, probá buscarlo en el mapa: {SITIO}/buscar",
        nivel=3, intent="sin_respuesta", sin_respuesta=True, sugerencias=SUGERENCIAS_INICIALES)


def _nivel3_comercio(c: dict) -> Respuesta:
    wa = _wa(c.get("whatsapp"))
    return Respuesta(
        texto=(f"Eso te lo contesta {c.get('nombre')} directamente" + (f": {wa}" if wa else " — en su ficha está cómo llegar.")
               + " Le dejé anotada tu pregunta."),
        nivel=3, intent="sin_respuesta", sin_respuesta=True)


# --------------------------------------------------------------------------- entrada

def responder(repo, pregunta: str, comercio: dict | None = None, ahora: datetime | None = None) -> Respuesta:
    """La pregunta de una persona → la respuesta, por el nivel más barato que
    la pueda contestar. `comercio` acota el asistente a ese local."""
    ahora = ahora or datetime.now(TZ)
    pregunta = (pregunta or "").strip()
    if not pregunta:
        return Respuesta(texto="¿Qué necesitás?", nivel=0, intent="vacia", sugerencias=SUGERENCIAS_INICIALES)

    if comercio:
        r = _nivel0_comercio(repo, comercio, pregunta, ahora)
        if r:
            return r
        r = _nivel1_comercio(repo, comercio, pregunta, ahora)
        if r and not r.sin_respuesta:
            return r
        return _nivel3_comercio(comercio)

    r = _nivel0_sitio(repo, pregunta, ahora)
    if r:
        return r
    r = _nivel1_sitio(repo, pregunta, ahora)
    if r and not r.sin_respuesta:
        return r
    if r and r.sin_respuesta and r.texto:
        # El modelo dijo con sus palabras que no sabe: se usa su texto, que es
        # más natural que el fijo, pero queda anotado igual.
        r.nivel = 3
        r.intent = "sin_respuesta"
        return r
    return _nivel3_sitio()
