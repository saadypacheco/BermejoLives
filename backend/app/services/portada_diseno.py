"""Portada de diseño para la ficha pública (docs/portada-diseno.md; el estilo, docs/fotos-estilo-uruku.md §1).

Arma una imagen apaisada de 1600 x 1000 (JPEG) con la foto de portada del comercio, una franja `#08110C` degradada
abajo (alfa 0 en y=420 a 235 en y=1000), un brillo verde detrás del texto, el RUBRO en una píldora verde (kick), el
NOMBRE y la CIUDAD, y el logo de URUKU «color · modo oscuro» SIEMPRE abajo a la derecha. Sin velo arriba y sin marco.

NINGÚN TEXTO LO ESCRIBE UN MODELO DE IA
=======================================
Todo lo que se dibuja sale de la base (`comercios`, `rubros`, `ciudades`) y se pone con Pillow. Sin emojis:
Poppins no los tiene y el manual de identidad los prohíbe. Ni la mejora ni la IA tiñen la foto: el verde lo pone la
plantilla.

SIN IA, GRATIS
==============
    cubrir(...) + mejorar_gratis(...) + dibujar_portada(...)    el recorte, una mejora automática suave de luz, color y
                                                                nitidez (Pillow) y el diseño. Costo 0.

Con IA (Gemini) o con una imagen hecha afuera, la foto de entrada es otra pero la plantilla es esta misma
(`dibujar_portada`): lo orquesta `fotos_estilo`, que también tiene el lock.

Guardar en el disco de fotos es `guardar` (un archivo `<slug>/diseno-<token>.jpg`).

DEFENSAS (el backend corre con UN solo worker: un pedido pesado frena a todos)
==============================================================================
- La foto se RECORTA antes de escalar (`resize(..., box=)`): la salida es siempre 1600 x 1000 y nunca hay un
  intermedio enorme. Una portada de 1 x 1280 px pediría gigapíxeles si se agrandara entera antes de recortar.
- Se rechazan las fotos con el lado menor < 200 px o de proporción mayor a 4:1 (`PortadaInadecuada`).
- Los textos se cortan (120 caracteres el nombre, 28 el kick) ANTES de medirlos, y el ajuste de renglones usa búsqueda binaria.
- Este módulo NO tiene lock: «una transformación a la vez» es `fotos_estilo._TRANSFORMAR` (cubre portada, galería y
  los tres caminos).
"""
from __future__ import annotations

import secrets
import unicodedata
from functools import lru_cache
from io import BytesIO

import structlog
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps, ImageStat

from app.services import fotos_galeria, fotos_origen, imagenes
from app.services.content_render_job import ASSETS, fuente, sin_emojis

logger = structlog.get_logger()

ANCHO, ALTO = 1600, 1000
CALIDAD_JPEG = 85
MARGEN = 80
BLANCO = (255, 255, 255)
GRIS_CLARO = (210, 226, 216)          # #D2E2D8: texto secundario del kit
FRANJA = (8, 17, 12)                  # #08110C: nunca negro puro
ACENTO = (52, 210, 127)               # #34D27F: kick y ciudad
BRILLO = (38, 185, 105)               # rgba(38,185,105): el resplandor verde detrás del texto
#: Los archivos de diseño llevan este prefijo: `soltar_archivo` NO borra nada que no lo tenga, así que
#: jamás toca una foto de galería ni una portada.
PREFIJO_ARCHIVO = fotos_galeria.PREFIJO_DISENO

#: Las dos columnas de `comercios` que se vacían juntas cuando la foto de portada cambia, se vuelve atrás o el
#: diseño queda vencido (cambió el nombre, el rubro o la ciudad).
COLUMNAS_VACIAS = {"portada_diseno_url": None, "portada_diseno_propuesta_url": None}

#: Largo máximo de lo que se dibuja (igual que `tarjetas.MAX_NOMBRE`; no se importa ese módulo por su peso).
MAX_NOMBRE = 120
MAX_SUBTITULO = 80
MAX_KICK = 28
#: Lo que se acepta como foto de entrada y lo que se lee del disco.
FORMATOS = ("JPEG", "PNG", "WEBP")
MAX_BYTES_FOTO = fotos_origen.MAX_BYTES_FOTO
LADO_MENOR_MIN = 200
PROPORCION_MAX = 4

# Geometría del diseño (docs/fotos-estilo-uruku.md §1). El texto vive en x 80..1188 (1108 px = 1600 - 80 - 300 - 64 - 48)
# y el logo en x 1236..1536: ningún texto pasa de x 1188, así que el logo nunca lo pisa.
ZONA_X0, ZONA_X1 = MARGEN, 1188
ANCHO_TEXTO = ZONA_X1 - ZONA_X0
ANCLA_Y = 936                          # el bloque de texto se ancla abajo en y = 936
LOGO_ANCHO = 300
LOGO_X0 = 1236
NOMBRE_MAX_PX, NOMBRE_MIN_PX = 104, 56
KICK_PX, CIUDAD_PX = 30, 46
KICK_ALTO, KICK_PAD, KICK_SEPARACION = 54, 26, 22
CIUDAD_ALTO = 56


class PortadaInadecuada(ValueError):
    """La foto de portada es muy chica o muy angosta para armar el diseño. El endpoint responde 400 con este texto."""


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
        limpia = ImageOps.exif_transpose(img).convert("RGB")
        limpia.info.clear()                   # el comentario (COM) del JPEG y el EXIF no pasan: viajarían a la portada
        return limpia
    except PortadaInadecuada:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ValueError("El archivo no es una imagen válida") from exc


def caja_cubrir(tamano: tuple[int, int], aspecto_w: float, aspecto_h: float, pos: int | None = None) -> tuple[float, float, float, float]:
    """La caja `(x0, y0, x1, y1)` MÁS GRANDE de una imagen de `tamano` con la proporción `aspecto_w : aspecto_h`.

    `pos` (0..100) es lo mismo que el CSS `object-position: center <pos>%` que usan el panel y la ficha: el recorte
    arranca en `pos %` del tramo que sobra (arriba = pos/100 * (alto - alto de la caja)), NO centrado en `pos`.
    Sin `pos`, 50 (el centro). Horizontalmente siempre va centrado. La comparten `cubrir` y el recorte que va a Gemini."""
    pos = 50 if pos is None else max(0, min(100, int(pos)))
    ancho, alto = tamano
    escala = max(aspecto_w / ancho, aspecto_h / alto)
    caja_w, caja_h = min(ancho, aspecto_w / escala), min(alto, aspecto_h / escala)
    x0 = max(0.0, min(ancho - caja_w, (ancho - caja_w) / 2))
    y0 = max(0.0, min(alto - caja_h, pos / 100 * (alto - caja_h)))
    return x0, y0, x0 + caja_w, y0 + caja_h


def cubrir(img: Image.Image, ancho_final: int, alto_final: int, pos: int | None = None) -> Image.Image:
    """La foto recortada para llenar `ancho_final` x `alto_final`, SIN agrandarla entera antes: se calcula la caja que
    se ve sobre la foto original (`caja_cubrir`) y se escala sólo eso (`resize(..., box=)`)."""
    return img.resize((ancho_final, alto_final), Image.LANCZOS, box=caja_cubrir(img.size, ancho_final, alto_final, pos))


def _franja(base: Image.Image, desde_y: int = 420, alfa_max: int = 235) -> None:
    """La franja `#08110C` de abajo: opacidad 0 en `desde_y` y `alfa_max` / 255 en el borde de abajo (nunca negro puro)."""
    alto = ALTO - desde_y
    if alto <= 0:
        return
    capa = Image.new("L", (1, alto))
    for y in range(alto):
        t = y / max(alto - 1, 1)
        capa.putpixel((0, y), round(alfa_max * (t ** 1.4)))
    base.paste(Image.new("RGB", (ANCHO, alto), FRANJA), (0, desde_y), capa.resize((ANCHO, alto)))


def _brillo(base: Image.Image, centro: tuple[int, int], radio: int, desenfoque: int, alfa: float) -> None:
    """Un resplandor verde (`rgba(38,185,105,alfa)`) desenfocado, detrás del texto."""
    mascara = Image.new("L", base.size, 0)
    cx, cy = centro
    ImageDraw.Draw(mascara).ellipse((cx - radio, cy - radio, cx + radio, cy + radio), fill=round(255 * alfa))
    mascara = mascara.filter(ImageFilter.GaussianBlur(desenfoque))
    base.paste(Image.new("RGB", base.size, BRILLO), (0, 0), mascara)


@lru_cache(maxsize=8)
def _logo_color(ancho: int) -> Image.Image:
    """El logo «color · modo oscuro» (1738 x 563) a `ancho` px. Sin sombras ni efectos. Se arma una vez por ancho."""
    logo = Image.open(ASSETS / "uruku-horizontal-color.png").convert("RGBA")
    return logo.resize((ancho, round(logo.height * ancho / logo.width)), Image.LANCZOS)


def logo_color(ancho: int) -> Image.Image:
    """Una copia del logo a `ancho` px (la de caché no se entrega: nadie la puede ensuciar)."""
    return _logo_color(ancho).copy()


def disponer_portada(nombre: str, rubro: str | None, ciudad: str | None) -> dict:
    """Dónde va cada cosa en la portada (docs/fotos-estilo-uruku.md §1), sin dibujar nada. Lo usa `dibujar_portada`
    y lo mira el test de que el logo y el texto no se cruzan nunca.

    Devuelve `{nombre_px, lineas, kick, ciudad, cajas, logo}`; `cajas` y `logo` son `(x0, y0, x1, y1)`. El bloque se
    ancla abajo en `ANCLA_Y`: ciudad, nombre (hasta 2 renglones, 104 → 56 px) y kick (la píldora), de abajo hacia arriba."""
    # Se corta ANTES de limpiar y medir: lo que llega de afuera (el registro anónimo) puede ser larguísimo.
    nombre = limpiar_texto((nombre or "")[:MAX_NOMBRE]) or "Comercio"
    px, lineas = ajustar_nombre(nombre, ANCHO_TEXTO, NOMBRE_MAX_PX, NOMBRE_MIN_PX)

    kick = limpiar_texto((rubro or "")[:MAX_SUBTITULO])
    if len(kick) > MAX_KICK:
        kick = kick[:MAX_KICK - 1].rstrip() + "…"
    kick = kick.upper()
    ciudad_txt = _cortar(limpiar_texto((ciudad or "")[:MAX_SUBTITULO]), "semibold", CIUDAD_PX, ANCHO_TEXTO)

    cajas: dict = {"kick": None, "nombre": [], "ciudad": None}
    cursor = ANCLA_Y
    if ciudad_txt:
        w = round(_largo(ciudad_txt, "semibold", CIUDAD_PX))
        cajas["ciudad"] = (ZONA_X0, cursor - CIUDAD_ALTO, ZONA_X0 + w, cursor)
        cursor -= CIUDAD_ALTO + 6
    paso = round(px * 1.14)
    for i in range(len(lineas) - 1, -1, -1):
        w = round(_largo(lineas[i], "bold", px))
        cajas["nombre"].insert(0, (ZONA_X0, cursor - paso, ZONA_X0 + w, cursor))
        cursor -= paso
    if kick:
        w = round(_largo(kick, "bold", KICK_PX)) + 2 * KICK_PAD
        cursor -= KICK_SEPARACION
        cajas["kick"] = (ZONA_X0, cursor - KICK_ALTO, ZONA_X0 + min(w, ANCHO_TEXTO), cursor)

    logo_w = LOGO_ANCHO
    logo_h = round(_logo_color(logo_w).height)
    return {"nombre_px": px, "lineas": lineas, "kick": kick, "ciudad": ciudad_txt, "paso": paso, "cajas": cajas,
            "logo": (LOGO_X0, ANCLA_Y - logo_h, LOGO_X0 + logo_w, ANCLA_Y)}


def dibujar_portada(base: Image.Image, nombre: str, rubro: str | None, ciudad: str | None) -> Image.Image:
    """Pone la franja, el brillo, el kick, el nombre, la ciudad y el logo sobre la foto ya encuadrada (1600 x 1000)."""
    d = disponer_portada(nombre, rubro, ciudad)
    _franja(base)
    _brillo(base, (380, 900), 420, 80, 0.30)

    draw = ImageDraw.Draw(base)
    cajas, px = d["cajas"], d["nombre_px"]
    if cajas["kick"]:
        x0, y0, x1, y1 = cajas["kick"]
        draw.rounded_rectangle((x0, y0, x1, y1), radius=(y1 - y0) // 2, fill=ACENTO)
        draw.text(((x0 + x1) / 2, (y0 + y1) / 2 + round(KICK_PX * 0.35)), d["kick"], font=fuente("bold", KICK_PX),
                  fill=FRANJA, anchor="ms")
    f = fuente("bold", px)
    for linea, (x0, y0, x1, y1) in zip(d["lineas"], cajas["nombre"]):
        draw.text((x0, y1 - round(px * 0.26)), linea, font=f, fill=BLANCO, anchor="ls")
    if cajas["ciudad"]:
        x0, y0, x1, y1 = cajas["ciudad"]
        draw.text((x0, y1 - round(CIUDAD_PX * 0.26)), d["ciudad"], font=fuente("semibold", CIUDAD_PX), fill=ACENTO,
                  anchor="ls")

    lx0, ly0, _, _ = d["logo"]
    logo = logo_color(LOGO_ANCHO)
    base.paste(logo, (lx0, ly0), logo)
    return base


def _jpeg(img: Image.Image) -> bytes:
    out = BytesIO()
    limpia = img.convert("RGB")
    limpia.info.clear()                       # ni el comentario del JPEG de la foto ni su EXIF viajan al archivo
    limpia.save(out, format="JPEG", quality=CALIDAD_JPEG, optimize=True)
    return out.getvalue()


# ───────────────────────────────────────────────────────────── disco

def guardar(slug: str, jpeg: bytes) -> str | None:
    """Guarda el JPEG en el disco de fotos como `<slug>/diseno-<token>.jpg` y devuelve su URL pública
    (None si falló). Nombre único cada vez: la URL cambia al regenerar y ningún caché sirve la imagen vieja."""
    return imagenes.guardar_foto_local(f"{slug}/{PREFIJO_ARCHIVO}{secrets.token_hex(16)}.jpg", jpeg)


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


def leer_portada(comercio: dict, remoto: bool = True) -> bytes | None:
    """Los bytes de la foto de portada: del disco del backend con la validación ESTRICTA de rutas (nuestra URL,
    `<carpeta>/<archivo>.jpg`, sin `..` ni enlaces que salgan del volumen) o, sólo si `FOTOS_LECTURA_REMOTA_BASES` lo
    permite (QA), por HTTPS (`fotos_origen.leer_foto_origen`). None si no hay portada, no es una foto nuestra, no se
    puede leer o pesa de más. Se llama SIN `slug`: un comercio renombrado deja sus fotos en la carpeta del slug viejo.

    `remoto=False` (la tarjeta de la portada, `fotos_tarjeta`): sólo el disco local. La lectura por HTTPS es de la portada de
    diseño y de los caminos de `fotos_estilo`, nada más."""
    try:
        return fotos_origen.leer_foto_origen(comercio.get("portada_url"), remoto=remoto)
    except Exception:  # noqa: BLE001
        return None


def respuesta(comercio: dict, proposal_method: str | None = None) -> dict:
    """Lo que devuelven los endpoints de la portada de diseño (`CoverDesign`, docs/fotos-estilo-uruku.md §6).
    `proposal_method` (`free` | `gemini` | `external`) sale del último registro de uso que dejó esa propuesta."""
    propuesta = comercio.get("portada_diseno_propuesta_url") or None
    return {"portada_diseno_url": comercio.get("portada_diseno_url") or None,
            "portada_diseno_propuesta_url": propuesta,
            "proposal_method": proposal_method if propuesta else None}
