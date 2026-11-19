"""Portada de diseño para la ficha pública (docs/portada-diseno.md).

Arma una imagen apaisada de 1600 x 1000 (JPEG) con la foto de portada del comercio, una franja oscura
degradada abajo con el NOMBRE, el RUBRO y la CIUDAD, y el logo blanco de URUKU en una esquina.

NINGÚN TEXTO LO ESCRIBE UN MODELO DE IA
=======================================
Todo lo que se dibuja sale de la base (`comercios`, `rubros`, `ciudades`) y se pone con Pillow. Sin emojis:
Poppins no los tiene y el manual de identidad los prohíbe.

SIN IA, GRATIS
==============
    armar_plantilla(...)   la foto + una mejora automática suave de luz, color y nitidez (`mejorar_gratis`,
                           Pillow) + el diseño. Costo 0.

«Mejorar con IA» (Gemini) quedó afuera el 19/11/2026 por costo (docs/portada-diseno.md).

Guardar en el disco de fotos es `guardar` (un archivo `<slug>/diseno-<token>.jpg`).

DEFENSAS (el backend corre con UN solo worker: un pedido pesado frena a todos)
==============================================================================
- La foto se RECORTA antes de escalar (`resize(..., box=)`): la salida es siempre 1600 x 1000 y nunca hay un
  intermedio enorme. Una portada de 1 x 1280 px pediría gigapíxeles si se agrandara entera antes de recortar.
- Se rechazan las fotos con el lado menor < 200 px o de proporción mayor a 4:1 (`PortadaInadecuada`).
- Los textos se cortan (120 caracteres el nombre) ANTES de medirlos, y el ajuste de renglones usa búsqueda binaria.
- Se arma de a UNA portada por vez (`_RENDER`): si hay otra en curso, `PortadaOcupada` (el endpoint dice 409).
"""
from __future__ import annotations

import secrets
import threading
import unicodedata
from io import BytesIO

import structlog
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps, ImageStat

from app.services import fotos_galeria, imagenes
from app.services.content_render_job import ASSETS, RenderError, fuente, sin_emojis

logger = structlog.get_logger()

ANCHO, ALTO = 1600, 1000
CALIDAD_JPEG = 85
MARGEN = 80
BLANCO = (255, 255, 255)
GRIS_CLARO = (226, 232, 228)
#: Los archivos de diseño llevan este prefijo: `soltar_archivo` NO borra nada que no lo tenga, así que
#: jamás toca una foto de galería ni una portada.
PREFIJO_ARCHIVO = "diseno-"

#: Las dos columnas de `comercios` que se vacían juntas cuando la foto de portada cambia, se vuelve atrás o el
#: diseño queda vencido (cambió el nombre, el rubro o la ciudad).
COLUMNAS_VACIAS = {"portada_diseno_url": None, "portada_diseno_propuesta_url": None}

#: Largo máximo de lo que se dibuja (igual que `tarjetas.MAX_NOMBRE`; no se importa ese módulo por su peso).
MAX_NOMBRE = 120
MAX_SUBTITULO = 80
#: Lo que se acepta como foto de entrada y lo que se lee del disco.
FORMATOS = ("JPEG", "PNG", "WEBP")
MAX_BYTES_FOTO = 8 * 1024 * 1024
LADO_MENOR_MIN = 200
PROPORCION_MAX = 4

#: Una sola portada a la vez, y cuánto se espera si hay otra en curso.
_RENDER = threading.Lock()
ESPERA_RENDER = 5.0


class PortadaInadecuada(ValueError):
    """La foto de portada es muy chica o muy angosta para armar el diseño. El endpoint responde 400 con este texto."""


class PortadaOcupada(RuntimeError):
    """Ya se está armando otra portada. El endpoint responde 409."""


# ───────────────────────────────────────────────────────────── texto

_glifos: dict[tuple[str, int], bool] = {}


def _tiene_glifo(f: ImageFont.FreeTypeFont, ch: str) -> bool:
    """¿La fuente dibuja este carácter? Un glifo ausente sale como el cuadrado de `.notdef`."""
    clave = (ch, id(f))
    if clave not in _glifos:
        try:
            m, nd = f.getmask(ch), f.getmask("￿")
            _glifos[clave] = not (m.size == nd.size and bytes(m) == bytes(nd))
        except Exception:  # noqa: BLE001
            _glifos[clave] = False
    return _glifos[clave]


def limpiar_texto(texto: str | None) -> str:
    """El texto sin emojis, sin controles y sin ningún carácter que Poppins no tenga."""
    base = sin_emojis(unicodedata.normalize("NFC", texto or ""))
    f = fuente("bold", 40)
    limpio = "".join(ch for ch in base
                     if ch == " " or (unicodedata.category(ch)[0] != "C" and _tiene_glifo(f, ch)))
    return " ".join(limpio.split())


def _largo(texto: str, peso: str, px: int) -> float:
    return fuente(peso, px).getlength(texto)


def _prefijo_que_entra(texto: str, peso: str, px: int, ancho: int, minimo: int = 1) -> int:
    """El largo del prefijo más largo de `texto` que entra en `ancho` px (búsqueda binaria: O(n log n), no O(n²)).
    Nunca menos de `minimo` caracteres."""
    lo, hi = minimo, max(len(texto), minimo)
    while lo < hi:
        medio = (lo + hi + 1) // 2
        if _largo(texto[:medio], peso, px) <= ancho:
            lo = medio
        else:
            hi = medio - 1
    return lo


def _con_puntos(texto: str, peso: str, px: int, ancho: int) -> str:
    """`texto` terminado en «…» (pegado, sin espacio antes) y recortado para que entre en `ancho` px."""
    if _largo(texto.rstrip() + "…", peso, px) <= ancho:
        return texto.rstrip() + "…"
    lo, hi = 0, len(texto)
    while lo < hi:
        medio = (lo + hi + 1) // 2
        if _largo(texto[:medio].rstrip() + "…", peso, px) <= ancho:
            lo = medio
        else:
            hi = medio - 1
    return texto[:lo].rstrip() + "…"


def _cortar(texto: str, peso: str, px: int, ancho: int) -> str:
    """Corta con «…» para que `texto` entre en `ancho` px (si ya entra, queda igual)."""
    return texto if _largo(texto, peso, px) <= ancho else _con_puntos(texto, peso, px, ancho)


def _envolver(texto: str, peso: str, px: int, ancho: int) -> list[str]:
    """Reparte las palabras en renglones de hasta `ancho` px. Una palabra sola más larga que el ancho
    se parte por caracteres (un nombre sin espacios no puede salirse del cuadro)."""
    lineas: list[str] = []
    actual = ""
    for palabra in texto.split():
        while len(palabra) > 1 and _largo(palabra, peso, px) > ancho:
            n = _prefijo_que_entra(palabra, peso, px, ancho)
            if actual:
                lineas.append(actual)
                actual = ""
            lineas.append(palabra[:n])
            palabra = palabra[n:]
        prueba = f"{actual} {palabra}".strip()
        if actual and _largo(prueba, peso, px) > ancho:
            lineas.append(actual)
            actual = palabra
        else:
            actual = prueba
    if actual:
        lineas.append(actual)
    return lineas


def ajustar_nombre(texto: str, ancho: int, maximo: int = 104, minimo: int = 52,
                   max_lineas: int = 2) -> tuple[int, list[str]]:
    """El tamaño más grande (hasta `maximo`) con el que el nombre entra en `max_lineas` de `ancho` px.
    Al mínimo, si todavía no entra, corta la última línea con «…» (pegado al texto)."""
    for px in range(maximo, minimo - 1, -4):
        lineas = _envolver(texto, "bold", px, ancho)
        if len(lineas) <= max_lineas:
            return px, lineas
    lineas = _envolver(texto, "bold", minimo, ancho)
    if len(lineas) > max_lineas:
        lineas = lineas[:max_lineas]
        lineas[-1] = _con_puntos(lineas[-1], "bold", minimo, ancho)
    return minimo, lineas or [""]


# ───────────────────────────────────────────────────────────── la foto

def mejorar_gratis(img: Image.Image) -> Image.Image:
    """Mejora automática SUAVE de luz, color y nitidez, con Pillow y sin IA (gratis).

    - Contraste: autocontraste (cutoff 1 %, conserva el tono) mezclado al 70 % con la foto: una foto ya
      pareja casi no cambia.
    - Luz: SÓLO si la foto es oscura (media de luminancia < 100). El brillo sube en proporción a lo oscura
      que es, con tope de 1,35. Una foto clara o bien expuesta no se toca (nunca se «quema»).
    - Color +12 % y nitidez +30 % (se llama con la imagen ya reducida al tamaño final).
    """
    img = img.convert("RGB")
    img = Image.blend(img, ImageOps.autocontrast(img, cutoff=1, preserve_tone=True), 0.7)
    media = ImageStat.Stat(img.convert("L")).mean[0]
    if media < 100:
        img = ImageEnhance.Brightness(img).enhance(min(1.35, 1 + (100 - media) / 100 * 0.6))
    img = ImageEnhance.Color(img).enhance(1.12)
    return ImageEnhance.Sharpness(img).enhance(1.3)


def _abrir(foto: bytes) -> Image.Image:
    """Abre la foto con los mismos topes de seguridad que las subidas (bomba de descompresión).

    - `PortadaInadecuada` si es muy chica (lado menor < 200 px) o muy angosta (proporción > 4:1); se mira el
      ENCABEZADO, antes de decodificar nada.
    - `ValueError` («no es una imagen válida») para todo lo demás: otro formato, archivo roto o gigante. El texto
      es siempre el mismo: nunca se devuelve el mensaje interno de Pillow.
    """
    try:
        imagenes._preparar_pillow()
        img = Image.open(BytesIO(foto), formats=FORMATOS)
        imagenes._exigir_tamano_razonable(img)
        menor, mayor = sorted(img.size)
        if menor < LADO_MENOR_MIN or mayor > PROPORCION_MAX * menor:
            raise PortadaInadecuada("La foto de portada es muy chica o muy angosta para armar el diseño")
        img.load()
        return ImageOps.exif_transpose(img).convert("RGB")
    except PortadaInadecuada:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ValueError("El archivo no es una imagen válida") from exc


def _cubrir(img: Image.Image, pos: int | None) -> Image.Image:
    """La foto recortada para llenar 1600 x 1000, SIN agrandarla entera antes: se calcula la caja que se ve
    sobre la foto original y se escala sólo eso (`resize(..., box=)`).

    `pos` (0..100) es lo mismo que el CSS `object-position: center <pos>%` que usan el panel y la ficha: el recorte
    arranca en `pos %` del tramo que sobra (arriba = pos/100 * (alto escalado - 1000)), NO centrado en `pos`.
    Sin `pos`, 50 (el centro). Horizontalmente siempre va centrado."""
    pos = 50 if pos is None else max(0, min(100, int(pos)))
    ancho, alto = img.size
    escala = max(ANCHO / ancho, ALTO / alto)
    caja_w, caja_h = min(ancho, ANCHO / escala), min(alto, ALTO / escala)
    x0 = max(0.0, min(ancho - caja_w, (ancho - caja_w) / 2))
    y0 = max(0.0, min(alto - caja_h, pos / 100 * (alto - caja_h)))
    return img.resize((ANCHO, ALTO), Image.LANCZOS, box=(x0, y0, x0 + caja_w, y0 + caja_h))


def _degradado(base: Image.Image, desde_y: int, alfa_max: int, hacia_abajo: bool = True) -> None:
    """Oscurece `base` con un degradado negro: de `desde_y` al borde de abajo (hacia_abajo) o del borde de
    arriba a `desde_y`. La opacidad va de 0 a `alfa_max` / 255, más fuerte en el borde."""
    alto = ALTO - desde_y if hacia_abajo else desde_y
    if alto <= 0:
        return
    capa = Image.new("L", (1, alto))
    for y in range(alto):
        t = y / max(alto - 1, 1)
        capa.putpixel((0, y), round(alfa_max * ((t if hacia_abajo else 1 - t) ** 1.4)))
    capa = capa.resize((ANCHO, alto))
    base.paste(Image.new("RGB", (ANCHO, alto), (0, 0, 0)), (0, desde_y if hacia_abajo else 0), capa)


def _diseno(base: Image.Image, nombre: str, rubro: str | None, ciudad: str | None) -> Image.Image:
    """Pone la franja, los textos y el logo sobre la foto ya encuadrada."""
    ancho_texto = ANCHO - 2 * MARGEN
    # Se corta ANTES de limpiar y medir: lo que llega de afuera (el registro anónimo) puede ser larguísimo.
    nombre = limpiar_texto((nombre or "")[:MAX_NOMBRE]) or "Comercio"
    px, lineas = ajustar_nombre(nombre, ancho_texto)
    partes = [p for p in (limpiar_texto((rubro or "")[:MAX_SUBTITULO]),
                          limpiar_texto((ciudad or "")[:MAX_SUBTITULO])) if p]
    sub = _cortar(" · ".join(partes), "medium", 44, ancho_texto) if partes else ""

    paso = round(px * 1.18)
    bloque = paso * len(lineas) + (44 + 24 if sub else 0)
    arriba_bloque = ALTO - 64 - bloque
    _degradado(base, max(0, arriba_bloque - 200), 225)          # la franja de abajo
    _degradado(base, 230, 110, hacia_abajo=False)                # un velo arriba: el logo blanco se lee sobre cualquier foto

    draw = ImageDraw.Draw(base)
    y = arriba_bloque
    f = fuente("bold", px)
    for linea in lineas:
        draw.text((MARGEN, y), linea, font=f, fill=BLANCO)
        y += paso
    if sub:
        draw.text((MARGEN, y + 12), sub, font=fuente("medium", 44), fill=GRIS_CLARO)

    logo = Image.open(ASSETS / "uruku-horizontal-blanco.png").convert("RGBA")
    w = 270
    logo = logo.resize((w, round(logo.height * w / logo.width)), Image.LANCZOS)
    base.paste(logo, (ANCHO - MARGEN // 2 - w, 44), logo)
    return base


def _jpeg(img: Image.Image) -> bytes:
    out = BytesIO()
    img.convert("RGB").save(out, format="JPEG", quality=CALIDAD_JPEG, optimize=True)
    return out.getvalue()


def armar_plantilla(foto: bytes, nombre: str, rubro: str | None, ciudad: str | None, pos: int | None,
                    *, mejorar: bool = True) -> bytes:
    """La portada de diseño en JPEG 1600 x 1000. `mejorar=False` salta la mejora automática (sólo para pruebas
    que miran los colores de la foto tal cual).

    - `PortadaInadecuada` (400): la foto es muy chica o muy angosta.
    - `ValueError` (400): `foto` no es una imagen válida.
    - `PortadaOcupada` (409): ya se está armando otra; se espera `ESPERA_RENDER` segundos antes de rendirse.
    """
    if not _RENDER.acquire(timeout=ESPERA_RENDER):
        raise PortadaOcupada("Ya se está armando otra portada, probá en unos segundos")
    try:
        img = _cubrir(_abrir(foto), pos)
        if mejorar:
            img = mejorar_gratis(img)
        try:
            return _jpeg(_diseno(img, nombre, rubro, ciudad))
        except RenderError as exc:      # falta una fuente del paquete: error del servidor, no de la foto
            raise RuntimeError(str(exc)) from exc
    finally:
        _RENDER.release()


# ───────────────────────────────────────────────────────────── disco

def guardar(slug: str, jpeg: bytes) -> str | None:
    """Guarda el JPEG en el disco de fotos como `<slug>/diseno-<token>.jpg` y devuelve su URL pública
    (None si falló). Nombre único cada vez: la URL cambia al regenerar y ningún caché sirve la imagen vieja."""
    return imagenes.guardar_foto_local(f"{slug}/{PREFIJO_ARCHIVO}{secrets.token_hex(8)}.jpg", jpeg)


def soltar_archivo(comercio: dict, url: str | None) -> None:
    """Borra del disco un archivo de diseño de ESTE comercio. Nunca lanza y nunca toca otra cosa: sólo
    `<slug>/diseno-*.jpg` del propio comercio (nada de galería ni de portadas)."""
    try:
        ruta = fotos_galeria._ruta_en_disco(url, comercio.get("slug"))
        if ruta is not None and ruta.name.startswith(PREFIJO_ARCHIVO):
            ruta.unlink(missing_ok=True)
    except Exception:  # noqa: BLE001
        logger.warning("portada_diseno.archivo_borrar_fallo", url=url, exc_info=True)


def urls_de(comercio: dict) -> list[str | None]:
    """Las URLs de las dos columnas de diseño, para anotarlas ANTES de vaciarlas (el repo puede devolver la misma fila mutada)."""
    return [comercio.get(col) for col in COLUMNAS_VACIAS]


def soltar_huerfanos(repo, comercio: dict, urls: list[str | None]) -> None:
    """Borra del disco los archivos de diseño `urls` que YA NO apunta ninguna de las dos columnas.

    Relee la fila DESPUÉS de escribir (no confía en la copia que se leyó antes): si otro pedido volvió a
    apuntar uno de esos archivos mientras tanto, no se borra. Si no se puede releer la fila, no se borra nada
    (un archivo de más es barato; uno de menos es una portada rota)."""
    try:
        fresca = repo.get_comercio(comercio["id"]) or {}
    except Exception:  # noqa: BLE001
        logger.warning("portada_diseno.releer_fallo", comercio=comercio.get("id"), exc_info=True)
        return
    vigentes = {fresca.get(col) for col in COLUMNAS_VACIAS}
    for url in dict.fromkeys(u for u in urls if u):
        if url not in vigentes:
            soltar_archivo(comercio, url)


def leer_portada(comercio: dict) -> bytes | None:
    """Los bytes de la foto de portada, leídos del disco del backend con la validación ESTRICTA de rutas
    (`fotos_galeria._ruta_en_disco`: nuestra URL, `<carpeta>/<archivo>.jpg`, sin `..` ni enlaces que salgan del
    volumen). None si no hay portada, no es una foto nuestra, no está en el disco o pesa de más."""
    try:
        ruta = fotos_galeria._ruta_en_disco(comercio.get("portada_url"))
        if ruta is None or not ruta.is_file() or ruta.stat().st_size > MAX_BYTES_FOTO:
            return None
        return ruta.read_bytes()
    except Exception:  # noqa: BLE001
        return None


def respuesta(comercio: dict) -> dict:
    """Lo que devuelven los cuatro endpoints."""
    return {"portada_diseno_url": comercio.get("portada_diseno_url") or None,
            "portada_diseno_propuesta_url": comercio.get("portada_diseno_propuesta_url") or None}
