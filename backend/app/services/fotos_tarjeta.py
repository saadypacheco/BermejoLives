"""La portada en versión «tarjeta» para los carruseles del home (docs/home-ciudades.md §11).

QUÉ ES
======
La portada original, recortada a 4:3 según el encuadre del comercio (`portada_pos`), reducida a 800 px de ancho,
mejorada con `portada_diseno.mejorar_gratis` y guardada como JPEG de calidad 80 en `/fotos/<slug>/card-<token>.jpg`.
Junto con la imagen se calcula `portada_calidad` (0 a 100), que el sitio usa para ordenar los carruseles. Todo con
Pillow: sin IA y sin costo.

CUÁNDO SE ARMA
==============
- Al subir o cambiar la portada (`services/portada.py`: `poner_nueva` y `usar_de_galeria`) y al crear un comercio con
  foto (registro y alta de campo).
- Al cambiar el encuadre (`PUT /admin/comercio/{id}` con `portada_pos`).
- En lote, a mano: `python -m app.services.fotos_tarjeta --todas [--ciudad <slug>] [--rehacer]`.
En los tres primeros, una falla de la tarjeta NUNCA rompe la operación principal: `armar_seguro` registra y sigue.

EL RECORTE (`caja_recorte`)
===========================
Igual que `portada_diseno._cubrir` y que el CSS `object-fit: cover; object-position: center <pos>%` del panel y la
ficha: el recorte de 4:3 sale centrado en horizontal y, en vertical, arranca en `pos/100 * (alto - alto_visible)`
(0 = arriba, 50 = centro, 100 = abajo). Es `resize(..., box=)` sobre la foto original: nunca hay un intermedio grande.

EL PUNTAJE `portada_calidad` (`puntaje`)
========================================
Se mide sobre la tarjeta YA mejorada (800 x 600). Tres señales, cada una normalizada a 0..1:

  color    Hasler-Süsstrunk (2003): M = sqrt(var_rg + var_yb) + 0,3 * sqrt(media_rg² + media_yb²), con
           rg = R - G y yb = (R + G) / 2 - B. M ~15 es pálida, ~33 normal, ~59 muy colorida:
           color = min(1, M / 60).
  nitidez  varianza del laplaciano (kernel 3x3 [0 1 0; 1 -4 1; 0 1 0]) de la luminancia reducida a 400 px de ancho.
           Una foto movida o borrosa da < 5; una nítida, 100 o más. En escala logarítmica entre 5 y 500:
           nitidez = clamp((ln var - ln 5) / (ln 500 - ln 5)). El kernel de Pillow guarda el resultado en 8 bits
           (con offset 128 y escala 4): las aristas muy fuertes se saturan a ±512, que acota su influencia.
  luz      luminancia media (0..255). Entre 70 y 180 es luz buena (1); hacia 20 (casi negro) o 240 (casi blanco)
           baja linealmente a 0.

  calidad = round(100 * (0,55 * nitidez + 0,45 * color) * (0,4 + 0,6 * luz))

La luz es una penalización: una foto nítida y colorida pero casi negra o quemada conserva como mucho el 40 % de
su puntaje. Las funciones de medición son puras (reciben una imagen y devuelven números): se prueban solas.

DISCO
=====
`guardar` escribe `<slug>/card-<token de 64 bits>.jpg`. `soltar_archivo` sólo borra archivos `card-*.jpg` del propio
comercio (nunca una portada, una foto de galería ni un diseño) y `soltar_huerfano` sólo si ninguna columna lo apunta
ya. Una tarjeta es un derivado que se puede regenerar: el comando no borra jamás una foto original.
"""
from __future__ import annotations

import argparse
import math
import secrets
import sys
import time
from io import BytesIO

import structlog
from PIL import Image, ImageFilter, ImageStat

from app.services import fotos_galeria, imagenes, portada_diseno

logger = structlog.get_logger()

#: La tarjeta: 800 x 600 (4:3), JPEG de calidad 80.
ANCHO, ALTO = 800, 600
CALIDAD_JPEG = 80
#: Los archivos de tarjeta llevan este prefijo: `soltar_archivo` no borra nada que no lo tenga.
PREFIJO_ARCHIVO = "card-"

#: Las dos columnas de `comercios` que se vacían juntas cuando la foto de portada cambia (la tarjeta era de la anterior).
COLUMNAS_VACIAS = {"portada_card_url": None, "portada_calidad": None}

# ── pesos y referencias del puntaje (documentados arriba) ────────────────────
PESO_NITIDEZ = 0.55
PESO_COLOR = 0.45
#: La luz resta: el factor va de PISO_LUZ (luz mala) a 1 (luz buena).
PISO_LUZ = 0.4
COLOR_REF = 60.0                    # Hasler-Süsstrunk de una foto «muy colorida»
VARIANZA_MIN, VARIANZA_MAX = 5.0, 500.0
LUZ_BUENA = (70.0, 180.0)
LUZ_EXTREMOS = (20.0, 240.0)
ANCHO_COLOR = 160                   # se mide sobre una miniatura: 19.200 píxeles bastan
ANCHO_NITIDEZ = 400
_LAPLACIANO = ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=4, offset=128)


# ───────────────────────────────────────────────────────────── el recorte

def caja_recorte(ancho: int, alto: int, pos: int | None) -> tuple[float, float, float, float]:
    """La caja `(x0, y0, x1, y1)` de la foto original que se ve en un recorte 4:3, con la regla del CSS
    `object-position: center <pos>%`: horizontal centrado; vertical, `y0 = pos/100 * (alto - alto_visible)`.
    `pos` fuera de 0..100 se acota y `None` es 50. Nunca se agranda ni se sale de la foto."""
    pos = 50 if pos is None else max(0, min(100, int(pos)))
    if ancho * 3 >= alto * 4:        # tan ancha o más que 4:3: se ve todo el alto y sobra a los costados
        caja_w, caja_h = alto * 4 / 3, float(alto)
    else:                            # más alta que 4:3: se ve todo el ancho y sobra arriba y abajo
        caja_w, caja_h = float(ancho), ancho * 3 / 4
    x0 = (ancho - caja_w) / 2
    y0 = pos / 100 * (alto - caja_h)
    return (x0, y0, x0 + caja_w, y0 + caja_h)


def recortar(img: Image.Image, pos: int | None) -> Image.Image:
    """La foto recortada a 4:3 y llevada a 800 x 600 sin armar intermedios grandes (`resize(box=)`)."""
    return img.resize((ANCHO, ALTO), Image.LANCZOS, box=caja_recorte(img.width, img.height, pos))


# ───────────────────────────────────────────────────────────── el puntaje (funciones puras)

def _reducida(img: Image.Image, ancho: int) -> Image.Image:
    if img.width <= ancho:
        return img
    return img.resize((ancho, max(1, round(img.height * ancho / img.width))), Image.BOX)


def colorido(img: Image.Image) -> float:
    """Métrica de colorido de Hasler-Süsstrunk, tal cual (sin normalizar). 0 para una imagen gris; ~15 pálida,
    ~33 normal, ~59 muy colorida."""
    rs, gs, bs = _reducida(img.convert("RGB"), ANCHO_COLOR).split()
    r, g, b = rs.tobytes(), gs.tobytes(), bs.tobytes()
    n = len(r)
    if not n:
        return 0.0
    s_rg = s2_rg = s_yb = s2_yb = 0.0
    for i in range(n):
        rg = r[i] - g[i]
        yb = 0.5 * (r[i] + g[i]) - b[i]
        s_rg += rg
        s2_rg += rg * rg
        s_yb += yb
        s2_yb += yb * yb
    m_rg, m_yb = s_rg / n, s_yb / n
    var_rg = max(0.0, s2_rg / n - m_rg * m_rg)
    var_yb = max(0.0, s2_yb / n - m_yb * m_yb)
    return math.sqrt(var_rg + var_yb) + 0.3 * math.sqrt(m_rg * m_rg + m_yb * m_yb)


def varianza_laplaciano(img: Image.Image) -> float:
    """La varianza del laplaciano de la luminancia (sin normalizar): alta = nítida, baja = borrosa o lisa.
    El borde de 1 px (que el filtro no calcula) se descarta."""
    gris = _reducida(img.convert("L"), ANCHO_NITIDEZ)
    if gris.width < 3 or gris.height < 3:
        return 0.0
    lap = gris.filter(_LAPLACIANO).crop((1, 1, gris.width - 1, gris.height - 1))
    hist = lap.histogram()
    n = sum(hist)
    if not n:
        return 0.0
    media = sum(((v - 128) * 4) * c for v, c in enumerate(hist)) / n
    cuad = sum((((v - 128) * 4) ** 2) * c for v, c in enumerate(hist)) / n
    return max(0.0, cuad - media * media)


def luz_media(img: Image.Image) -> float:
    """La luminancia media de la imagen, 0 (negro) a 255 (blanco)."""
    return float(ImageStat.Stat(_reducida(img.convert("L"), ANCHO_COLOR)).mean[0])


def norm_color(m: float) -> float:
    return max(0.0, min(1.0, m / COLOR_REF))


def norm_nitidez(varianza: float) -> float:
    v = max(varianza, 1e-9)
    t = (math.log(v) - math.log(VARIANZA_MIN)) / (math.log(VARIANZA_MAX) - math.log(VARIANZA_MIN))
    return max(0.0, min(1.0, t))


def norm_luz(media: float) -> float:
    """1 con luz buena (70..180), bajando linealmente a 0 hacia 20 (negro) y 240 (blanco)."""
    bueno_min, bueno_max = LUZ_BUENA
    ext_min, ext_max = LUZ_EXTREMOS
    if media < bueno_min:
        t = (media - ext_min) / (bueno_min - ext_min)
    elif media > bueno_max:
        t = (ext_max - media) / (ext_max - bueno_max)
    else:
        t = 1.0
    return max(0.0, min(1.0, t))


def combinar(color: float, nitidez: float, luz: float) -> int:
    """El puntaje 0..100 a partir de las tres señales ya normalizadas (0..1)."""
    base = PESO_NITIDEZ * nitidez + PESO_COLOR * color
    factor = PISO_LUZ + (1 - PISO_LUZ) * luz
    return max(0, min(100, round(100 * base * factor)))


def puntaje(img: Image.Image) -> dict:
    """`{color, nitidez, luz, calidad}` de una imagen: las tres señales normalizadas (0..1) y el puntaje 0..100."""
    color = norm_color(colorido(img))
    nitidez = norm_nitidez(varianza_laplaciano(img))
    luz = norm_luz(luz_media(img))
    return {"color": color, "nitidez": nitidez, "luz": luz, "calidad": combinar(color, nitidez, luz)}


# ───────────────────────────────────────────────────────────── la tarjeta

def generar_tarjeta(foto: bytes, pos: int | None) -> tuple[bytes, int]:
    """`(jpeg, calidad)` de la tarjeta de una portada. Lanza `portada_diseno.PortadaInadecuada` (foto muy chica o
    muy angosta) o `ValueError` (no es una imagen válida), con los mismos topes de seguridad que el diseño."""
    img = portada_diseno._abrir(foto)
    tarjeta = portada_diseno.mejorar_gratis(recortar(img, pos))
    calidad = puntaje(tarjeta)["calidad"]
    out = BytesIO()
    tarjeta.convert("RGB").save(out, format="JPEG", quality=CALIDAD_JPEG, optimize=True)
    return out.getvalue(), calidad


# ───────────────────────────────────────────────────────────── disco

def guardar(slug: str, jpeg: bytes) -> str | None:
    """Guarda el JPEG como `<slug>/card-<token>.jpg` y devuelve su URL pública (None si falló). Nombre único cada
    vez (64 bits al azar): la URL cambia al rehacer y ningún caché sirve la tarjeta vieja."""
    return imagenes.guardar_foto_local(f"{slug}/{PREFIJO_ARCHIVO}{secrets.token_hex(8)}.jpg", jpeg)


def soltar_archivo(comercio: dict, url: str | None) -> None:
    """Borra del disco una tarjeta de ESTE comercio. Nunca lanza y nunca toca otra cosa: sólo `<slug>/card-*.jpg`."""
    try:
        ruta = fotos_galeria._ruta_en_disco(url, comercio.get("slug"))
        if ruta is not None and ruta.name.startswith(PREFIJO_ARCHIVO):
            ruta.unlink(missing_ok=True)
    except Exception:  # noqa: BLE001
        logger.warning("fotos_tarjeta.archivo_borrar_fallo", url=url, exc_info=True)


def soltar_huerfano(repo, comercio: dict, url: str | None) -> None:
    """Borra del disco la tarjeta `url` si YA NO la apunta `comercios.portada_card_url`. Relee la fila después de
    escribir; si no se puede releer, no borra nada (un archivo de más es barato; uno de menos es una tarjeta rota)."""
    if not url:
        return
    try:
        fresca = repo.get_comercio(comercio["id"]) or {}
    except Exception:  # noqa: BLE001
        logger.warning("fotos_tarjeta.releer_fallo", comercio=comercio.get("id"), exc_info=True)
        return
    if fresca.get("portada_card_url") != url:
        soltar_archivo(comercio, url)


# ───────────────────────────────────────────────────────────── armar y guardar

SIN_FOTO, PORTADA_CAMBIO = "sin_foto", "portada_cambio"


def _armar(repo, comercio: dict) -> tuple[dict | None, str | None]:
    """`(columnas escritas, None)` o `(None, motivo)`: `SIN_FOTO` (no hay portada o su archivo no está en el disco) o
    `PORTADA_CAMBIO` (la portada o el encuadre cambiaron mientras se armaba: la tarjeta ya era de otra foto)."""
    foto = portada_diseno.leer_portada(comercio, remoto=False)       # la tarjeta lee sólo del disco local
    if foto is None:
        return None, SIN_FOTO
    jpeg, calidad = generar_tarjeta(foto, comercio.get("portada_pos"))
    url = guardar(comercio["slug"], jpeg)
    if not url:
        raise RuntimeError("No se pudo guardar la tarjeta en el disco")
    try:
        anterior = (repo.get_comercio(comercio["id"]) or comercio).get("portada_card_url") or comercio.get("portada_card_url")
        # UPDATE condicional: sólo si la portada y el encuadre siguen siendo los de esta foto. Si otro pedido los
        # cambió entre leer y escribir, no se pisa nada y esta tarjeta (de la foto vieja) se suelta.
        escrita = repo.actualizar_portada_card(
            comercio["id"], {"portada_card_url": url, "portada_calidad": calidad},
            comercio.get("portada_url"), comercio.get("portada_pos"))
    except Exception:
        soltar_archivo(comercio, url)        # recién creada: que no quede huérfana
        raise
    if not escrita:
        soltar_archivo(comercio, url)
        return None, PORTADA_CAMBIO
    if anterior and anterior != url:
        soltar_huerfano(repo, comercio, anterior)
    logger.info("fotos_tarjeta.armada", comercio=comercio["id"], calidad=calidad, bytes=len(jpeg))
    return {"portada_card_url": url, "portada_calidad": calidad}, None


def armar_para_comercio(repo, comercio: dict) -> dict | None:
    """Arma la tarjeta de la portada de `comercio`, la guarda y actualiza `portada_card_url` y `portada_calidad`.
    Devuelve `{portada_card_url, portada_calidad}` (lo escrito) o None si no había nada que hacer (sin portada, la
    foto no está en el disco, o la portada o el encuadre cambiaron mientras se armaba). Suelta la tarjeta anterior
    si nadie más la apunta. Puede lanzar (`PortadaInadecuada`, `ValueError`, errores de la base): quien no quiere
    que eso corte lo que hace usa `armar_seguro`."""
    return _armar(repo, comercio)[0]


def armar_seguro(repo, comercio: dict) -> dict | None:
    """`armar_para_comercio` que NUNCA lanza: la tarjeta es un derivado y una falla suya no puede romper subir la
    portada ni cambiar el encuadre. Se registra y se sigue (None)."""
    try:
        return armar_para_comercio(repo, comercio)
    except Exception as exc:  # noqa: BLE001
        logger.warning("fotos_tarjeta.fallo", comercio=(comercio or {}).get("id"), error=type(exc).__name__,
                       detalle=str(exc)[:200])
        return None


# ───────────────────────────────────────────────────────────── línea de comandos

LOTE = 200


def rellenar(repo, ciudad_id: str | None, *, rehacer: bool = False, pausa: float = 0.2,
             dormir=time.sleep, imprimir=print) -> dict:
    """Arma las tarjetas de los comercios que ya tienen portada. Devuelve el resumen. Lee del disco y nunca borra
    una foto original (sólo suelta la tarjeta anterior al rehacer)."""
    r = {"revisados": 0, "armadas": 0, "ya_tenian": 0, "sin_foto_en_disco": 0, "portada_cambio": 0,
         "inadecuadas": 0, "errores": 0}
    despues = None
    while True:
        lote = repo.list_comercios_con_portada(ciudad_id, despues, LOTE)
        if not lote:
            break
        for c in lote:
            despues = c["id"]
            r["revisados"] += 1
            if c.get("portada_card_url") and not rehacer:
                r["ya_tenian"] += 1
                continue
            try:
                hecho, motivo = _armar(repo, c)
            except (portada_diseno.PortadaInadecuada, ValueError):
                r["inadecuadas"] += 1
                continue
            except Exception as exc:  # noqa: BLE001
                r["errores"] += 1
                logger.warning("fotos_tarjeta.fallo", comercio=c["id"], error=type(exc).__name__)
                continue
            if hecho is None:
                # La portada cambió mientras se armaba (otro pedido): no es un problema del disco; se arma sola la próxima.
                r["portada_cambio" if motivo == PORTADA_CAMBIO else "sin_foto_en_disco"] += 1
            else:
                r["armadas"] += 1
            if r["revisados"] % 25 == 0:
                imprimir(f"  ... {r['revisados']} revisados, {r['armadas']} armadas")
            dormir(pausa)                         # va despacio: con un solo worker no se le roba el CPU al sitio
        if len(lote) < LOTE:
            break
    return r


def main(argv: list[str] | None = None, repo=None, *, dormir=time.sleep) -> int:
    ap = argparse.ArgumentParser(prog="fotos_tarjeta", description="Arma la versión tarjeta (800 x 600, 4:3) de las "
                                 "portadas que ya existen. Lee del disco y no borra ninguna portada original.")
    ap.add_argument("--todas", action="store_true", help="recorre todos los comercios activos con portada")
    ap.add_argument("--ciudad", help="sólo los de esta ciudad (slug)")
    ap.add_argument("--rehacer", action="store_true", help="rehace también las que ya tienen tarjeta")
    ap.add_argument("--pausa", type=float, default=0.2, help="segundos entre una y otra (por defecto 0,2)")
    args = ap.parse_args(argv)
    if not args.todas:
        print("Falta --todas (recorre todas las portadas). Para una sola, se arma sola al subirla.", file=sys.stderr)
        return 2
    if repo is None:
        from app.db.repository import get_repo
        repo = get_repo()
    ciudad_id = None
    if args.ciudad:
        ciudad = repo.get_ciudad(args.ciudad)
        if not ciudad:
            print(f"No existe la ciudad «{args.ciudad}».", file=sys.stderr)
            return 2
        ciudad_id = ciudad["id"]
    print(f"Armando tarjetas{' de ' + args.ciudad if args.ciudad else ''}{' (rehaciendo todas)' if args.rehacer else ''}...")
    r = rellenar(repo, ciudad_id, rehacer=args.rehacer, pausa=max(0.0, args.pausa), dormir=dormir)
    print(f"\nRevisados:                  {r['revisados']}")
    print(f"Tarjetas armadas:           {r['armadas']}")
    print(f"Ya tenían tarjeta:          {r['ya_tenian']}")
    print(f"Foto no está en el disco:   {r['sin_foto_en_disco']}")
    print(f"Portada cambió al armarla:   {r['portada_cambio']}")
    print(f"Foto muy chica o inválida:  {r['inadecuadas']}")
    print(f"Con error:                  {r['errores']}")
    print("\nNo se borró ninguna portada original.")
    return 0 if not r["errores"] else 1


if __name__ == "__main__":
    sys.exit(main())
