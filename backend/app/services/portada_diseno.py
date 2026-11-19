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
"""
from __future__ import annotations

import secrets
import unicodedata
from io import BytesIO

import structlog
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps, ImageStat

from app.services import fotos_galeria, imagenes, vision
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

#: Las dos columnas de `comercios` que se vacían juntas cuando la foto de portada cambia o se vuelve atrás.
COLUMNAS_VACIAS = {"portada_diseno_url": None, "portada_diseno_propuesta_url": None}


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


def _cortar(texto: str, peso: str, px: int, ancho: int) -> str:
    """Corta con «…» para que `texto` entre en `ancho` px."""
    if _largo(texto, peso, px) <= ancho:
        return texto
    while texto and _largo(texto + "…", peso, px) > ancho:
        texto = texto[:-1]
    return texto.rstrip() + "…"


def _envolver(texto: str, peso: str, px: int, ancho: int) -> list[str]:
    """Reparte las palabras en renglones de hasta `ancho` px. Una palabra sola más larga que el ancho
    se parte por caracteres (un nombre sin espacios no puede salirse del cuadro)."""
    lineas: list[str] = []
    actual = ""
    for palabra in texto.split():
        while _largo(palabra, peso, px) > ancho and len(palabra) > 1:
            n = len(palabra)
            while n > 1 and _largo(palabra[:n], peso, px) > ancho:
                n -= 1
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
    Al mínimo, si todavía no entra, corta la última línea con «…»."""
    for px in range(maximo, minimo - 1, -4):
        lineas = _envolver(texto, "bold", px, ancho)
        if len(lineas) <= max_lineas:
            return px, lineas
    lineas = _envolver(texto, "bold", minimo, ancho)
    if len(lineas) > max_lineas:
        lineas = lineas[:max_lineas]
        lineas[-1] = _cortar(lineas[-1] + " …", "bold", minimo, ancho)
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
    ValueError si no es una imagen."""
    try:
        imagenes._preparar_pillow()
        img = Image.open(BytesIO(foto))
        imagenes._exigir_tamano_razonable(img)
        img.load()
        return ImageOps.exif_transpose(img).convert("RGB")
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ValueError("El archivo no es una imagen válida") from exc


def _cubrir(img: Image.Image, pos: int | None) -> Image.Image:
    """La foto recortada para llenar 1600 x 1000. `pos` (0..100) es el centro vertical del recorte; sin él, 50."""
    pos = 50 if pos is None else max(0, min(100, int(pos)))
    escala = max(ANCHO / img.width, ALTO / img.height)
    w, h = max(ANCHO, round(img.width * escala)), max(ALTO, round(img.height * escala))
    img = img.resize((w, h), Image.LANCZOS)
    izq = (w - ANCHO) // 2
    arriba = round(pos / 100 * h - ALTO / 2)
    arriba = max(0, min(h - ALTO, arriba))
    return img.crop((izq, arriba, izq + ANCHO, arriba + ALTO))


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
    nombre = limpiar_texto(nombre) or "Comercio"
    px, lineas = ajustar_nombre(nombre, ancho_texto)
    partes = [p for p in (limpiar_texto(rubro), limpiar_texto(ciudad)) if p]
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
    que miran los colores de la foto tal cual). ValueError si `foto` no es una imagen."""
    img = _cubrir(_abrir(foto), pos)
    if mejorar:
        img = mejorar_gratis(img)
    try:
        return _jpeg(_diseno(img, nombre, rubro, ciudad))
    except RenderError as exc:      # falta una fuente del paquete: error del servidor, no de la foto
        raise RuntimeError(str(exc)) from exc


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


def soltar_archivos(comercio: dict, urls: list[str | None]) -> None:
    """Borra del disco los archivos de diseño `urls` de `comercio` (los que `urls_de` anotó antes de vaciar las columnas)."""
    for url in urls:
        soltar_archivo(comercio, url)


def leer_portada(comercio: dict) -> bytes | None:
    """Los bytes de la foto de portada, leídos del disco del backend. None si no hay portada o no está en el disco."""
    url = comercio.get("portada_url")
    return vision._leer_local(url) if url else None


def respuesta(comercio: dict) -> dict:
    """Lo que devuelven los cuatro endpoints."""
    return {"portada_diseno_url": comercio.get("portada_diseno_url") or None,
            "portada_diseno_propuesta_url": comercio.get("portada_diseno_propuesta_url") or None}
