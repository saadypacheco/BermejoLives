"""Cargar comercios desde fotos de tarjetas de presentación (docs/carga-tarjetas.md).

QUÉ HACE
========
Una foto de tarjeta entra por Comercios › Importados y queda como una fila de `comercios_importados` con
`fuente = 'tarjeta'`. Nada llega al sitio hasta que una persona la revisa y toca «Promover».

Pasos de UNA foto (`procesar`):
1. validar el tipo por los bytes (JPEG, PNG o WebP; la extensión y el Content-Type no cuentan) y el tamaño;
2. `fuente_id = 'tarjeta:' + sha256(archivo)`: la misma foto subida dos veces no crea dos filas;
3. leer el texto: Tesseract (gratis, por defecto) o Gemini (sólo con el interruptor `gemini_tarjetas` prendido
   Y con GEMINI_API_KEY; ante una falla de Gemini se sigue con Tesseract);
4. sacar los campos con reglas simples. NUNCA se inventa nada: lo que no se encuentra queda en null;
5. ubicar la dirección (esquina o cuadra con las calles de la ciudad y, si no, Nominatim acotado a la ciudad
   elegida; `services/ubicar_direccion.py`), sólo si hay dirección;
6. marcar el repetido si algún teléfono ya es de un comercio activo;
7. guardar la foto en el disco PRIVADO (`privado:`) y la fila.

COSTO CERO POR DEFECTO: el lector es el mismo Tesseract de «Teléfonos en fotos» y Nominatim es gratis. Se respeta
su política de uso: 1 pedido por segundo como máximo (global del proceso), User-Agent propio, caché por consulta y
nada de consultas masivas (una por tarjeta con dirección).

PRIVACIDAD: la foto y el texto leído pueden traer datos personales. Nada de esto se loguea (ni el texto ni los
teléfonos) y el endpoint de la foto exige sesión de panel.
"""
from __future__ import annotations

import hashlib
import math
import re
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Callable

import structlog

from app.core.config import settings
from app.core.telefonos_foto import (Telefono, clave_de_comparacion, es_de_uruku, extraer, numero_visible,
                                     whatsapp_de)
from app.services import archivos_privados, cost_switches, enlaces
from app.services import telefonos_foto as ocr_base
from app.services.vision import LectorFallo, LectorTransitorio, VisionNoConfigurada

logger = structlog.get_logger()

FUENTE = "tarjeta"
LECTOR_TESSERACT = "tesseract"
LECTOR_GEMINI = "gemini"

MAX_ARCHIVOS = 5   # por pedido: el panel manda las fotos elegidas (hasta 20) en tandas de 5
MAX_BYTES = 10 * 1024 * 1024
MAX_TEXTO_LEIDO = 8000

#: `--psm 3` = la página entera con su estructura (una tarjeta es un bloque con columnas y logo). Sin lista blanca:
#: acá hay que leer letras, no sólo dígitos.
CONFIG_OCR = "--psm 3"
IDIOMAS = ("spa", "eng")


# ───────────────────────────────────────────────────────────── el archivo

def tipo_de_imagen(data: bytes) -> str | None:
    """`jpeg`, `png` o `webp` según los PRIMEROS BYTES del archivo, o None. No se confía en el nombre ni en el
    Content-Type que manda el navegador."""
    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def sha256_de(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fuente_id_de(data: bytes) -> str:
    return f"{FUENTE}:{sha256_de(data)}"


def nombre_para_mostrar(nombre: str | None) -> str:
    """El nombre del archivo para el listado de errores: sin carpetas, sin caracteres de control y corto."""
    limpio = re.sub(r"[\x00-\x1f\x7f]", "", str(nombre or "")).replace("\\", "/").split("/")[-1].strip()
    return (limpio or "foto")[:80]


# ───────────────────────────────────────────────────────────── el lector

_idioma_ocr: str | None = None


def _idioma_tesseract() -> str:
    """`spa+eng` si Tesseract tiene los dos datos de idioma; si no, `eng` (la imagen mínima sólo trae el inglés:
    se lee igual, con peores acentos). Se pregunta una vez por proceso."""
    global _idioma_ocr
    if _idioma_ocr is None:
        try:
            import pytesseract

            instalados = set(pytesseract.get_languages(config=""))
            _idioma_ocr = "+".join(i for i in IDIOMAS if i in instalados) or "eng"
        except Exception:  # noqa: BLE001
            return "eng"
    return _idioma_ocr


def leer_con_tesseract(data: bytes) -> str:
    """El texto que Tesseract lee en la tarjeta, con el mismo preproceso de «Teléfonos en fotos» (gris, lado mayor
    1600 px, autocontraste). Si la primera pasada casi no leyó nada se prueba con el negativo (letras claras sobre
    fondo oscuro).

    `LectorFallo` si la foto no sirve o Tesseract tarda demasiado; `LectorTransitorio` si no está instalado."""
    try:
        import pytesseract
    except ImportError:
        raise LectorTransitorio("Falta el paquete pytesseract") from None
    mejor = ""
    for im in ocr_base.preparar_imagenes(data):
        try:
            texto = pytesseract.image_to_string(im, lang=_idioma_tesseract(), config=CONFIG_OCR,
                                                timeout=ocr_base.TIMEOUT_OCR_SEG)
        except pytesseract.TesseractNotFoundError:
            raise LectorTransitorio("Tesseract no está instalado") from None
        except RuntimeError as exc:                         # el timeout de pytesseract
            raise LectorFallo(f"Tesseract no pudo leer la foto: {exc}"[:200]) from None
        except Exception as exc:  # noqa: BLE001
            raise LectorFallo(f"Tesseract falló: {type(exc).__name__}") from None
        if len(re.findall(r"[^\W_]", texto)) > len(re.findall(r"[^\W_]", mejor)):
            mejor = texto
        if len(re.findall(r"[^\W_]", mejor)) >= 12:          # con la imagen normal alcanzó
            break
    return mejor


def motor_activo(crepo) -> str:
    """`gemini` sólo si el dueño prendió `gemini_tarjetas` Y hay clave; si no, el lector gratis."""
    if cost_switches.esta_prendido(crepo, cost_switches.GEMINI_TARJETAS) and settings.gemini_api_key:
        return LECTOR_GEMINI
    return LECTOR_TESSERACT


def leer_texto(data: bytes, motor: str, *, ocr: Callable[[bytes], str] | None = None,
               gemini: Callable[[bytes], str] | None = None) -> tuple[str, str]:
    """`(texto, lector)`. Con `gemini`, una falla del modelo cae a Tesseract (la tarjeta no se pierde)."""
    ocr = ocr or leer_con_tesseract
    if motor == LECTOR_GEMINI:
        if gemini is None:
            from app.services.vision import leer_texto_tarjeta as gemini
        try:
            return gemini(data), LECTOR_GEMINI
        except (LectorTransitorio, LectorFallo, VisionNoConfigurada) as exc:
            logger.warning("tarjetas.gemini_fallo_uso_tesseract", error=type(exc).__name__)
    return ocr(data), LECTOR_TESSERACT


# ───────────────────────────────────────────────────────────── los campos

_RE_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")
_RE_URL = re.compile(
    r"(?<![@\w.\-/])((?:https?://)?(?:www\.)?[a-z0-9][a-z0-9\-]*(?:\.[a-z0-9\-]+)*\."
    r"(?:com\.bo|com\.ar|com|bo|ar|net|org|store|shop|info|biz|tienda|app|online|site|co)"
    r"(?:/[^\s,;]*)?)(?![\w@])", re.I)
_RE_REDES = (
    ("instagram", re.compile(r"(?:instagram\.com/|insta(?:gram)?\s*[:\-]?\s*@?|\big\s*[:\-]\s*@?)([A-Za-z0-9._]{2,30})", re.I),
     "https://instagram.com/{}"),
    ("facebook", re.compile(r"(?:facebook\.com/|fb\.com/|\bfb\s*[:\-]\s*/?|\bfacebook\s*[:\-]\s*/?)([A-Za-z0-9._\-]{2,50})", re.I),
     "https://facebook.com/{}"),
    ("tiktok", re.compile(r"(?:tiktok\.com/@?|\btiktok\s*[:\-]\s*@?)([A-Za-z0-9._]{2,30})", re.I),
     "https://tiktok.com/@{}"),
)
_RE_ARROBA = re.compile(r"(?<![\w@])@([A-Za-z0-9._]{3,30})\b")
_DOMINIOS_RED = ("instagram.com", "facebook.com", "fb.com", "tiktok.com", "wa.me", "linktr.ee")

#: Las palabras de calle (la spec: calle/c./av./avenida/esq./nº/#/entre/zona/barrio) y algunas más de la zona
#: (pasaje, kilómetro, ruta, puesto o local con número).
_PALABRAS_DIR = (r"calle|c/|c\.|av\.?|avda\.?|avenida|esq\.?|esquina|n[º°o]\.?\s*\d|nro\.?|n[úu]mero|entre|zona|barrio|b/|"
                 r"bo\.|urb\.?|urbanizaci[óo]n|pasaje|pje\.?|km\.?\s*\d|ruta\s*\d|manzano?|mza\.?|edif\.?|edificio|"
                 r"local\s*\d|puesto\s*\d")
_FIN_PALABRA = r"(?=$|[\s,;.:)\d/])"
#: Una línea es dirección si EMPIEZA con una de esas palabras («Av. Costanera 440», «Barrio Los Pinos»), si trae un
#: «#12» o «Nº 12», o si junto a la palabra hay un número. Una palabra suelta en el medio de un renglón NO alcanza:
#: «Panadería La Esquina» es un nombre, no una dirección.
_RE_DIR_AL_INICIO = re.compile(rf"^(?:{_PALABRAS_DIR}){_FIN_PALABRA}", re.I)
_RE_DIR_CON_NUMERO = re.compile(rf"(?:^|[\s,;(])(?:{_PALABRAS_DIR}){_FIN_PALABRA}", re.I)
_RE_DIR_ENTRE_CALLES = re.compile(r"\bentre\b.+\b(?:y|e)\b", re.I)
_RE_NUMERAL = re.compile(r"#\s*\d|\bs/n\b", re.I)


def _es_direccion(linea: str) -> bool:
    return bool(_RE_DIR_AL_INICIO.search(linea) or _RE_NUMERAL.search(linea) or _RE_DIR_ENTRE_CALLES.search(linea)
                or (any(c.isdigit() for c in linea) and _RE_DIR_CON_NUMERO.search(linea)))


#: «Dirección:», «Dir.», «Ubicación:» al principio de la línea (el rótulo no es parte de la dirección).
_RE_ROTULO_DIR = re.compile(r"^\s*(?:direcci[óo]n|dir\.?|domicilio|ubicaci[óo]n|ubicados?\s+en|estamos\s+en)\s*[:\-]?\s*", re.I)
_RE_ROTULO_CONTACTO = re.compile(
    r"^\s*(?:tel[eé]?f?o?n?o?s?\.?|cel(?:ular)?\.?|celulares?|whats\s*app|wsp|wpp|w\.?a\.?|fono|llamar?|contacto|"
    r"e-?mail|correo|web|sitio|p[áa]gina|www)\b\s*[:\-.]?", re.I)
_RE_OFICIO = re.compile(
    r"\b(?:gerente|director|directora|propietari[oa]|due[ñn]o|encargad[oa]|lic\.?|ing\.?|dr\.?|dra\.?|arq\.?|sr\.?|sra\.?|"
    r"atendemos|atenci[óo]n|horarios?|lunes|martes|s[áa]bados?|domingos?|hs\.?|desde|hasta|delivery|env[íi]os?|"
    r"vendemos|se\s+hacen|realizamos|trabajos?|servicios?\s+de|ofrecemos|especialistas?\s+en)\b", re.I)

MAX_NOMBRE = 120
MAX_DIRECCION = 200
MAX_LINEAS_DIRECCION = 2


def _letras(linea: str) -> list[str]:
    return [c for c in linea if c.isalpha()]


def _limpia(linea: str) -> str:
    """Un renglón sin los bordes de ruido del OCR (guiones, barras, puntos sueltos) y con los espacios juntos."""
    return re.sub(r"\s+", " ", linea).strip(" \t|_~`´'\"*-–—•·.,:;=<>[]{}\\/")


def _sin_digitos_de_telefono(linea: str) -> bool:
    """¿La línea NO tiene un número largo (teléfono, NIT)? Una calle con su número (`Av. Costanera 440`) pasa."""
    return not any(len(re.sub(r"\D", "", t)) >= 7 for t in re.findall(r"\+?\d[\d\s().\-]{5,}\d", linea))


def _es_ruido(linea: str, minimo: float = 0.6) -> bool:
    """¿Es basura del OCR? Pocas letras, o demasiado símbolo y dígito entre ellas. Las direcciones, que llevan
    números, piden menos letras (`minimo` más bajo)."""
    letras = _letras(linea)
    if len(letras) < 3:
        return True
    return len(letras) / max(1, len(linea.replace(" ", ""))) < minimo


def _puntaje_nombre(linea: str, posicion: int) -> float:
    letras = _letras(linea)
    mayus = sum(1 for c in letras if c.isupper()) / len(letras)
    palabras = linea.split()
    p = 0.0
    if mayus >= 0.7:
        p += 3
    elif linea[:1].isupper():
        p += 1
    p += {0: 2, 1: 1}.get(posicion, 0)
    if _RE_OFICIO.search(linea):
        p -= 3
    if len(palabras) > 6:
        p -= 2
    if len(linea) < 4:
        p -= 1
    if any(c.isdigit() for c in linea):
        p -= 1
    return p


@dataclass
class Campos:
    """Lo que se pudo leer de la tarjeta. Todo opcional: lo que no se encuentra queda en None / vacío."""
    nombre: str | None = None
    direccion: str | None = None
    telefonos: list[Telefono] = field(default_factory=list)
    email: str | None = None
    website: str | None = None
    redes: dict[str, str] = field(default_factory=dict)


def _email(texto: str) -> str | None:
    m = _RE_EMAIL.search(texto)
    if not m:
        return None
    correo = m.group(0).strip(".").lower()
    return correo if len(correo) <= 120 else None


def _web(texto: str, correo: str | None) -> str | None:
    """El sitio de la tarjeta: el primer dominio que no es un correo ni una red social."""
    sin_correos = _RE_EMAIL.sub(" ", texto)
    for m in _RE_URL.finditer(sin_correos):
        crudo = m.group(1).rstrip(".,;")
        host = re.sub(r"^https?://", "", crudo, flags=re.I).split("/")[0].lower()
        if any(host == d or host.endswith("." + d) for d in _DOMINIOS_RED):
            continue
        url = crudo if re.match(r"https?://", crudo, re.I) else "https://" + crudo
        try:
            return enlaces.validar_http(url, "El sitio web")
        except ValueError:
            continue
    return None


def _redes(texto: str) -> dict[str, str]:
    out: dict[str, str] = {}
    sin_correos = _RE_EMAIL.sub(" ", texto)
    for red, patron, plantilla in _RE_REDES:
        m = patron.search(sin_correos)
        if m:
            usuario = m.group(1).strip("._-/")
            if usuario and usuario.lower() not in ("com", "www", "http", "https"):
                out[red] = plantilla.format(usuario)
    if not out:
        m = _RE_ARROBA.search(sin_correos)
        if m:
            out["arroba"] = m.group(1)
    return out


def extraer_campos(texto: str | None) -> Campos:
    """Los campos de la tarjeta a partir del texto crudo del lector. Reglas, no adivinanza: lo que no se reconoce
    queda en None."""
    campos = Campos()
    crudo = (texto or "")[:MAX_TEXTO_LEIDO]
    if not crudo.strip():
        return campos
    campos.telefonos = [t for t in extraer(crudo) if not es_de_uruku(t.numero)]
    campos.email = _email(crudo)
    campos.website = _web(crudo, campos.email)
    campos.redes = _redes(crudo)

    lineas = [_limpia(x) for x in crudo.splitlines()]
    lineas = [x for x in lineas if x]
    direccion: list[str] = []
    candidatas: list[tuple[int, str]] = []
    for i, linea in enumerate(lineas):
        if _RE_EMAIL.search(linea) or _RE_ROTULO_CONTACTO.match(linea) or not _sin_digitos_de_telefono(linea):
            continue
        if _RE_URL.search(linea) or _RE_ARROBA.search(linea) or any(p.search(linea) for _, p, _ in _RE_REDES):
            continue
        if _es_direccion(linea) or _RE_ROTULO_DIR.match(linea):
            sin_rotulo = _limpia(_RE_ROTULO_DIR.sub("", linea))
            if sin_rotulo and not _es_ruido(sin_rotulo, 0.4) and len(direccion) < MAX_LINEAS_DIRECCION:
                direccion.append(sin_rotulo)
            continue
        if not _es_ruido(linea):
            candidatas.append((i, linea))
    if direccion:
        campos.direccion = ", ".join(direccion)[:MAX_DIRECCION]
    if candidatas:
        orden = list(range(len(candidatas)))
        mejor = max(orden, key=lambda k: (_puntaje_nombre(candidatas[k][1], k), -k))
        if _puntaje_nombre(candidatas[mejor][1], mejor) > -2:
            campos.nombre = candidatas[mejor][1][:MAX_NOMBRE]
    return campos


def repartir_telefonos(telefonos: list[Telefono]) -> tuple[str | None, str | None]:
    """`(whatsapp, telefono)`: el primero que sea celular va a `whatsapp` (E.164 sin «+», como se guarda en la
    ficha) y el resto, en su forma legible, a `telefono` (varios separados por « / »)."""
    vistos: set[str] = set()
    unicos = []
    for t in telefonos:
        k = clave_de_comparacion(t.numero)
        if k not in vistos:
            vistos.add(k)
            unicos.append(t)
    wa = next((t for t in unicos if t.tipo == "celular"), None)
    resto = [t for t in unicos if t is not wa]
    return (whatsapp_de(wa.numero) if wa else None,
            " / ".join(numero_visible(t.numero) for t in resto)[:80] or None)


# ───────────────────────────────────────────────────────────── repetidos

def indice_telefonos(repo) -> dict[str, dict]:
    """`{clave de comparación: {id, nombre}}` de los comercios ACTIVOS (whatsapp y teléfono). Se arma una vez por
    pedido y sirve para todas las tarjetas del lote."""
    indice: dict[str, dict] = {}
    for c in repo.list_telefonos_comercios():
        for valor in (c.get("whatsapp"), c.get("telefono")):
            for parte in re.split(r"[/;,]", str(valor or "")):
                k = clave_de_comparacion(parte)
                if k and len(k) >= 8:
                    indice.setdefault(k, {"id": c["id"], "nombre": c.get("nombre")})
    return indice


def buscar_repetido(repo, telefonos: list[Telefono], indice: dict[str, dict]) -> dict | None:
    """El comercio activo que ya tiene alguno de esos teléfonos (whatsapp, teléfono o número autorizado)."""
    for t in telefonos:
        propio = indice.get(clave_de_comparacion(t.numero))
        if propio:
            return propio
        autorizado = repo.get_comercio_por_numero(whatsapp_de(t.numero))
        if autorizado and autorizado.get("activo", True):
            return {"id": autorizado["id"], "nombre": autorizado.get("nombre")}
    return None


# ───────────────────────────────────────────────────────────── ubicación (Nominatim)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "URUKU/1.0 (+https://uruku.bo)"
TIMEOUT_NOMINATIM = 8
INTERVALO_NOMINATIM = 1.0          # política de uso: 1 pedido por segundo como máximo
RADIO_CIUDAD_KM = 15
PAISES = "bo,ar"
CACHE_MAX = 500
CACHE_SEG = 7 * 24 * 3600

_candado = threading.Lock()
_ultimo_pedido = 0.0
_cache: "OrderedDict[tuple, tuple[float, dict | None]]" = OrderedDict()


#: Se puede reemplazar en los tests para no esperar el segundo de verdad.
_dormir = time.sleep


class UbicacionNoDisponible(RuntimeError):
    """Nominatim no contestó (red, timeout, error del servicio). No es «no encontrada»."""


def reiniciar_cache() -> None:
    global _ultimo_pedido
    with _candado:
        _cache.clear()
        _ultimo_pedido = 0.0


def caja_de_la_ciudad(lat: float, lng: float, radio_km: float = RADIO_CIUDAD_KM) -> tuple[float, float, float, float]:
    """`(oeste, norte, este, sur)`: la caja de ~`radio_km` alrededor del centro, en el orden de `viewbox`."""
    dlat = radio_km / 111.0
    dlng = radio_km / (111.0 * max(0.2, math.cos(math.radians(lat))))
    return lng - dlng, lat + dlat, lng + dlng, lat - dlat


def _pedir_nominatim(params: dict) -> list:
    """El único lugar que sale a la red. Los tests lo reemplazan: nunca pegan a Nominatim."""
    import httpx

    r = httpx.get(NOMINATIM_URL, params=params, headers={"User-Agent": USER_AGENT, "Accept-Language": "es"},
                  timeout=TIMEOUT_NOMINATIM, follow_redirects=False)
    r.raise_for_status()
    datos = r.json()
    return datos if isinstance(datos, list) else []


def _numero(valor) -> float | None:
    try:
        n = float(valor)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def buscar_direccion(direccion: str, ciudad: dict | None, *, pedir: Callable[[dict], list] | None = None,
                     radio_km: float = RADIO_CIUDAD_KM) -> dict | None:
    """El punto de una dirección DENTRO de la ciudad, o None si Nominatim no la encuentra.

    Devuelve `{lat, lng, display_name}`. Con el centro de la ciudad (`ciudades.lat/lng`) la búsqueda va acotada a
    una caja de ~`radio_km` (por defecto 15 km; `bounded=1`): una calle con el mismo nombre en otra ciudad no
    cuenta. Los lugares de afuera de la ciudad (docs/lugares-turismo.md) piden una caja más grande. Sin centro se
    agrega el nombre de la ciudad a la consulta. Sólo Bolivia y Argentina. Caché por consulta Y radio (la misma
    consulta con otra caja es otra respuesta); un pedido por segundo en todo el proceso. Lanza
    `UbicacionNoDisponible` si el servicio no contesta (eso no se cachea)."""
    global _ultimo_pedido
    texto = re.sub(r"\s+", " ", str(direccion or "")).strip()[:MAX_DIRECCION]
    if len(texto) < 4:
        return None
    nombre_ciudad = str((ciudad or {}).get("nombre") or "").strip()
    lat_c, lng_c = _numero((ciudad or {}).get("lat")), _numero((ciudad or {}).get("lng"))
    clave = (texto.lower(), str((ciudad or {}).get("id") or ""), float(radio_km))
    ahora = time.monotonic()
    with _candado:
        visto = _cache.get(clave)
        if visto and ahora - visto[0] < CACHE_SEG:
            _cache.move_to_end(clave)
            return visto[1]
        params = {"q": f"{texto}, {nombre_ciudad}" if nombre_ciudad else texto, "format": "jsonv2", "limit": 1,
                  "countrycodes": PAISES, "addressdetails": 0}
        caja = None
        if lat_c is not None and lng_c is not None:
            caja = caja_de_la_ciudad(lat_c, lng_c, float(radio_km))
            params["viewbox"] = ",".join(f"{v:.6f}" for v in caja)
            params["bounded"] = 1
        # El candado se mantiene durante la espera y el pedido: así el intervalo vale para TODOS los hilos.
        espera = INTERVALO_NOMINATIM - (time.monotonic() - _ultimo_pedido)
        if espera > 0:
            _dormir(espera)
        _ultimo_pedido = time.monotonic()
        try:
            filas = (pedir or _pedir_nominatim)(params)
        except Exception as exc:  # noqa: BLE001
            logger.warning("tarjetas.nominatim_fallo", error=type(exc).__name__)
            raise UbicacionNoDisponible("El servicio de mapas no contestó") from None
        resultado = None
        for fila in filas[:1]:
            lat, lng = _numero((fila or {}).get("lat")), _numero((fila or {}).get("lon"))
            if lat is None or lng is None or not (-90 <= lat <= 90 and -180 <= lng <= 180):
                continue
            if caja and not (caja[0] <= lng <= caja[2] and caja[3] <= lat <= caja[1]):
                continue                                    # no se confía: tiene que caer dentro de la ciudad
            resultado = {"lat": round(lat, 6), "lng": round(lng, 6),
                         "display_name": str((fila or {}).get("display_name") or "")[:300]}
        _cache[clave] = (time.monotonic(), resultado)
        while len(_cache) > CACHE_MAX:
            _cache.popitem(last=False)
        return resultado


# ───────────────────────────────────────────────────────────── una tarjeta completa

@dataclass
class Resultado:
    fila: dict | None = None
    motivo: str | None = None          # si no se creó la fila: por qué (en español, para mostrar)


def armar_fila(campos: Campos, *, fuente_id: str, ciudad_id: str, lector: str, texto: str, foto_ref: str,
               punto: dict | None, repetido: dict | None) -> dict:
    """La fila de `comercios_importados` de una tarjeta (nuevo, sin revisar)."""
    whatsapp, telefono = repartir_telefonos(campos.telefonos)
    tags: dict = {"tarjeta": {"telefonos_leidos": len(campos.telefonos)}}
    if campos.redes:
        tags["redes"] = campos.redes
    return {
        "fuente": FUENTE, "fuente_id": fuente_id, "ciudad_id": ciudad_id,
        "nombre": campos.nombre, "categoria": None, "rubro_slug": None,
        "lat": punto["lat"] if punto else None, "lng": punto["lng"] if punto else None,
        "telefono": telefono, "whatsapp": whatsapp, "website": campos.website, "email": campos.email,
        "direccion": campos.direccion, "tags": tags, "estado": "nuevo",
        "ubicacion": "aproximada" if punto else "no_encontrada",
        "foto_ref": foto_ref, "texto_leido": (texto or "")[:MAX_TEXTO_LEIDO], "lector": lector,
        "duplicado_de": repetido["id"] if repetido else None,
    }


def procesar(repo, crepo, data: bytes, ciudad: dict, indice: dict[str, dict], *,
             ocr: Callable[[bytes], str] | None = None, gemini: Callable[[bytes], str] | None = None,
             pedir: Callable[[dict], list] | None = None) -> Resultado:
    """Lee UNA foto y crea su fila. Nunca lanza por la foto: devuelve el `motivo` (en español) si no se pudo.
    Lo único que deja pasar es `LectorTransitorio` (Tesseract sin instalar): el lote lo informa por foto."""
    from app.services.imagenes import procesar_imagen

    if not data:
        return Resultado(motivo="El archivo está vacío")
    if len(data) > MAX_BYTES:
        return Resultado(motivo="La foto pesa más de 10 MB")
    if tipo_de_imagen(data) is None:
        return Resultado(motivo="No es una imagen JPEG, PNG o WebP")
    fuente_id = fuente_id_de(data)
    if repo.get_importado_por_fuente(FUENTE, fuente_id):
        return Resultado(motivo="Esa foto ya estaba cargada")
    try:
        jpeg = procesar_imagen(data)                      # valida que sea una imagen de verdad y quita metadatos
    except Exception:  # noqa: BLE001
        return Resultado(motivo="La imagen está dañada o es demasiado grande")

    motor = motor_activo(crepo)
    try:
        texto, lector = leer_texto(data, motor, ocr=ocr, gemini=gemini)
    except LectorFallo as exc:
        return Resultado(motivo=str(exc)[:160] or "No se pudo leer la foto")
    except LectorTransitorio:
        return Resultado(motivo="El lector de texto no está disponible ahora, probá más tarde")

    campos = extraer_campos(texto)
    punto = None
    if campos.direccion:
        try:
            from app.services import ubicar_direccion        # acá adentro: ubicar_direccion importa este módulo
            punto = ubicar_direccion.ubicar(repo, campos.direccion, ciudad, pedir=pedir)
        except UbicacionNoDisponible:
            punto = None                                  # queda «no_encontrada»: la persona lo reintenta
    repetido = buscar_repetido(repo, campos.telefonos, indice)

    ref = archivos_privados.guardar("tarjetas", fuente_id.split(":", 1)[1][:16], jpeg)
    if not ref:
        return Resultado(motivo="No se pudo guardar la foto en el servidor")
    fila = armar_fila(campos, fuente_id=fuente_id, ciudad_id=ciudad["id"], lector=lector, texto=texto,
                      foto_ref=ref, punto=punto, repetido=repetido)
    creada = repo.crear_importado(fila)
    if creada is None:                                    # otra subida simultánea ganó: se borra la foto de más
        ruta = archivos_privados.ruta_segura(ref)
        try:
            if ruta is not None:
                ruta.unlink(missing_ok=True)
        except OSError:
            pass
        return Resultado(motivo="Esa foto ya estaba cargada")
    logger.info("tarjetas.leida", importado=creada.get("id"), lector=lector, telefonos=len(campos.telefonos),
                con_nombre=bool(campos.nombre), con_direccion=bool(campos.direccion), con_punto=bool(punto),
                repetido=bool(repetido))
    return Resultado(fila=creada)


# ───────────────────────────────────────────────────────────── lo que sale por la API

def importado_salida(fila: dict, nombres_repetidos: dict[str, str] | None = None) -> dict:
    """Un importado como lo ve el panel. La referencia privada de la foto NO sale (es una ruta del disco): se
    informa `tiene_foto`. Suma `duplicado_nombre` cuando hay un repetido, para mostrarlo en la revisión."""
    out = {k: v for k, v in fila.items() if k != "foto_ref"}
    out["tiene_foto"] = bool(fila.get("foto_ref"))
    for k in ("email", "ubicacion", "texto_leido", "lector"):
        out.setdefault(k, None)
    if fila.get("duplicado_de"):
        out["duplicado_nombre"] = (nombres_repetidos or {}).get(fila["duplicado_de"])
    if fila.get("fuente") == "turismo":
        # La subcategoría con la que va a quedar el comercio al promoverlo (Guía de turismo, Radio móvil…).
        from app.services.subcategorias_turismo import subcategoria_de_importado
        out["subcategoria_legible"] = subcategoria_de_importado(fila)
    return out
