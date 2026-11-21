"""Fotos con estilo URUKU: portada y galería (docs/fotos-estilo-uruku.md).

Tres caminos que terminan igual, en una PROPUESTA privada que una persona aprueba (nada se publica solo):

    free      foto de origen -> recortar al formato -> mejora gratis (Pillow) -> plantilla -> guardar
    gemini    foto de origen -> ¿disponible? ¿tope? -> recortar y achicar a <= 1536 px -> Gemini (prompt fijo, sin texto)
              -> validar lo que vuelve -> recortar al formato -> plantilla -> guardar (+ registro con costo)
    external  imagen hecha afuera (ChatGPT) -> validar y normalizar (sin EXIF, alfa sobre blanco) -> recortar -> plantilla

LA IA SÓLO TOCA LA FOTO
=======================
Los textos y el logo los pone siempre la plantilla (Pillow): ningún texto lo escribe un modelo. El prompt es fijo y no lleva
datos del comercio (`fotos_estilo_prompt`).

UN SOLO LOCK
============
`_TRANSFORMAR` cubre portada, galería y los tres caminos (reemplaza a `portada_diseno._RENDER`): Gemini lo retiene hasta
`GEMINI_IMAGE_TIMEOUT_SEG`. Espera `ESPERA_TRANSFORMAR` segundos y, si no, 409. El backend corre con un solo worker. Todo
esto es SINCRÓNICO: los endpoints lo llaman dentro de `run_in_threadpool`. La foto de origen se lee FUERA del lock.

EL REGISTRO (`photo_style_uses`, sólo insert)
=============================================
Toda llamada a Gemini se registra en un `finally` (ok, error o timeout); el tope diario se cuenta en la base y DENTRO del
lock, así que sobrevive a un reinicio. `free` y `external` se registran sólo cuando salen bien, con costo 0.

Si el insert del registro de Gemini FALLA, la IA queda «no disponible» por el resto del día (`_registro_roto`): sin registro no
hay tope que se pueda contar, y una IA sin tope gasta sin límite. Es un flag EN MEMORIA del proceso (como `_TRANSFORMAR`):
se limpia al reiniciar o al cambiar el día de Bolivia (AGENTS.md §7.13).

Los errores que salen de acá son `EstiloError(status, detail)`: el endpoint los pasa a `HTTPException`.
"""
from __future__ import annotations

import contextlib
import secrets
import threading
from datetime import date
from io import BytesIO

import structlog
from fastapi import UploadFile
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from app.core.config import settings
from app.services import cargas, cost_switches, fotos_estilo_gemini as ge, fotos_estilo_prompt as prompts
from app.services import fotos_galeria, fotos_origen, imagenes, portada_diseno as pd
from app.services.content_render_job import RenderError, fuente

logger = structlog.get_logger()

# ───────────────────────────────────────────────────────────── constantes

#: Portada: 1600 x 1000 (lo arma `portada_diseno`). Galería: 1080 x 1350 (4:5) con la foto en una tarjeta de 920 x 1150.
GAL_ANCHO, GAL_ALTO = 1080, 1350
TARJETA_ANCHO, TARJETA_ALTO = 920, 1150
TARJETA_X, TARJETA_Y = 80, 56
TARJETA_RADIO, TARJETA_BORDE = 44, 3
PIE_Y0, PIE_Y1 = 1206, 1350
PIE_LOGO_ANCHO, PIE_LOGO_X = 260, 740
MINIATURA = (480, 600)
CALIDAD_MINIATURA = 74
CALIDAD_JPEG = 85

#: A Gemini va como mucho este lado mayor, en JPEG q85.
GEMINI_LADO_MAX = 1536

#: La imagen hecha afuera: hasta 15 MB, lado menor >= 512 px, proporción <= 4:1 y hasta 16 megapíxeles (una de 40 MP pasaba
#: los topes de siempre pero con el alfa componiéndose sobre blanco costaba cientos de MB en el único worker).
EXTERNA_MAX_BYTES = 15 * 1024 * 1024
EXTERNA_LADO_MENOR_MIN = 512
EXTERNA_MAX_PIXELES = 16_000_000
PROPORCION_MAX = 4
#: Lo que se necesita de una imagen de afuera para armar la portada (1600 x 1000) o la tarjeta (920 x 1150), con holgura: se achica
#: a esto ANTES de componer el alfa (`draft` en JPEG, `thumbnail` en el resto).
LADO_MAX_ENTRADA = 3200
#: Lo que vuelve de Gemini: lado menor mínimo para aceptarla.
DEVUELTA_LADO_MENOR_MIN = 256
DEVUELTA_MAX_PIXELES = 16_000_000

METODOS = ("free", "gemini", "external")
TARGETS = ("cover", "gallery")

#: Una sola transformación a la vez, y cuánto se espera si hay otra en curso.
_TRANSFORMAR = threading.Lock()
ESPERA_TRANSFORMAR = 5.0
MSG_OCUPADO = "Ya se está armando otra foto, probá en unos segundos"

MSG_CAMBIO_PORTADA = "La foto de portada cambió mientras se armaba: armala de nuevo"
MSG_CAMBIO_DATOS = "Los datos del comercio cambiaron mientras se armaba la portada: armala de nuevo"
MSG_CAMBIO_FOTO = "La foto cambió o se borró mientras se armaba: armala de nuevo"


class EstiloError(Exception):
    """Un error con su código HTTP y su texto en español (el panel lo muestra tal cual)."""

    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


@contextlib.contextmanager
def transformando():
    """Toma el lock de «una transformación a la vez». 409 si después de `ESPERA_TRANSFORMAR` segundos sigue ocupado."""
    if not _TRANSFORMAR.acquire(timeout=ESPERA_TRANSFORMAR):
        raise EstiloError(409, MSG_OCUPADO)
    try:
        yield
    finally:
        _TRANSFORMAR.release()


# ───────────────────────────────────────────────────────────── disponibilidad, tope y costo

def costo_por_imagen() -> float:
    """El costo estimado por imagen en US$ (`GEMINI_IMAGE_COST_USD`), redondeado a lo que guarda la base (4 decimales)."""
    return round(float(settings.gemini_image_cost_usd or 0.0), 4)


def tope_diario() -> int:
    return max(0, int(settings.gemini_fotos_tope_diario or 0))


#: Si el insert de `photo_style_uses` falló, el día de Bolivia en que pasó (None = anda). En memoria del proceso.
_registro_roto: date | None = None


def registro_roto_hoy() -> bool:
    """¿Falló el registro de usos de Gemini HOY (día de Bolivia)? Cambia el día y se olvida."""
    return _registro_roto is not None and _registro_roto == cargas.hoy_bolivia()


def marcar_registro_roto() -> None:
    global _registro_roto
    _registro_roto = cargas.hoy_bolivia()


def reiniciar_registro_roto() -> None:
    """Lo vuelve a poner en «anda» (los tests, y quien arregle la base y no quiera esperar a mañana)."""
    global _registro_roto
    _registro_roto = None


def disponibilidad(crepo, con_tope: bool = True) -> tuple[bool, str | None]:
    """`(disponible, motivo)`. Disponible = interruptor `gemini_fotos` prendido + clave + modelo + costo > 0 + tope diario
    mayor que 0 + el registro de usos andando. El motivo está en español para mostrarlo y NUNCA lleva la clave.

    `con_tope=False` no mira el tope en 0: el POST lo contesta con el 429 «Se llegó al tope de 0 fotos» (el GET de estado sí
    lo anticipa, para que el front no ofrezca un botón que va a fallar)."""
    if not cost_switches.esta_prendido(crepo, cost_switches.GEMINI_FOTOS):
        return False, "el interruptor «Fotos con IA (Gemini)» está apagado"
    motivo = ge.motivo_no_disponible()
    if motivo:
        return False, motivo
    if registro_roto_hoy():
        return False, "no se pudo registrar el último uso de la IA: queda apagada por hoy"
    if con_tope and tope_diario() <= 0:
        return False, "el tope diario de fotos con IA está en 0"
    return True, None


def desde_hoy_iso() -> str:
    """El instante en que empezó el día de hoy en Bolivia (00:00, UTC-4), en ISO UTC, para contar el tope diario."""
    return cargas.iso_z(cargas.limites_dia_utc(cargas.hoy_bolivia())[0])


def usados_hoy(repo) -> int:
    return int(repo.contar_usos_gemini_desde(desde_hoy_iso()))


def _exigir_disponible(crepo) -> None:
    ok, motivo = disponibilidad(crepo, con_tope=False)
    if not ok:
        raise EstiloError(503, f"Fotos con IA no disponible: {motivo}")


# ───────────────────────────────────────────────────────────── imágenes

def _sobre_blanco(img: Image.Image) -> Image.Image:
    """RGB sin canal alfa: lo transparente se pinta sobre BLANCO (convertir a pelo daría negro)."""
    if img.mode == "RGBA":
        fondo = Image.new("RGBA", img.size, (255, 255, 255, 255))
        return Image.alpha_composite(fondo, img).convert("RGB")
    return img.convert("RGB")


def _abrir_validada(datos: bytes, *, lado_menor_min: int, max_pixeles: int) -> Image.Image:
    """Abre una imagen que viene de afuera (la hecha en ChatGPT, o la que devuelve Gemini).

    - Sólo JPEG/PNG/WEBP, hasta `max_pixeles` (se mira el ENCABEZADO, antes de decodificar nada; además del tope general
      de 40 MP de `imagenes`), lado menor >= `lado_menor_min` y proporción <= 4:1.
    - Se achica a `LADO_MAX_ENTRADA` ANTES de componer el alfa sobre blanco (JPEG con `draft`, el resto con `thumbnail`):
      el compuesto no hace falta a 16 MP, y en el único worker cada copia extra pesa.
    - Sin EXIF, sin comentario del JPEG ni ningún otro metadato (`img.info` vacío): se aplica la orientación y sale RGB.

    `ValueError` («no es una imagen válida») o `pd.PortadaInadecuada` (muy chica, angosta o grande). Nunca el texto de Pillow."""
    try:
        imagenes._preparar_pillow()
        img = Image.open(BytesIO(datos), formats=pd.FORMATOS)
        imagenes._exigir_tamano_razonable(img)
        if img.size[0] * img.size[1] > max_pixeles:
            raise pd.PortadaInadecuada(f"La imagen es demasiado grande: hasta {max_pixeles // 1_000_000} megapíxeles")
        menor, mayor = sorted(img.size)
        if menor < lado_menor_min or mayor > PROPORCION_MAX * menor:
            raise pd.PortadaInadecuada("La imagen es muy chica o muy angosta")
        if img.format == "JPEG":
            img.draft("RGB", (LADO_MAX_ENTRADA // 2, LADO_MAX_ENTRADA // 2))
        con_alfa = img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info)
        img.load()
        img = ImageOps.exif_transpose(img).convert("RGBA" if con_alfa else "RGB")
        if max(img.size) > LADO_MAX_ENTRADA:
            img.thumbnail((LADO_MAX_ENTRADA, LADO_MAX_ENTRADA), Image.LANCZOS)
        img = _sobre_blanco(img)
        img.info.clear()
        return img
    except pd.PortadaInadecuada:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ValueError("El archivo no es una imagen válida") from exc


def _jpeg(img: Image.Image, calidad: int = CALIDAD_JPEG) -> bytes:
    out = BytesIO()
    limpia = img.convert("RGB")
    limpia.info.clear()                       # ni el comentario del JPEG ni el EXIF viajan al archivo
    limpia.save(out, format="JPEG", quality=calidad, optimize=True)
    return out.getvalue()


def jpeg_para_gemini(img: Image.Image, target: str, pos: int | None) -> bytes:
    """La foto recortada al formato (3:2 portada, 4:5 galería) y achicada a <= 1536 px, en JPEG q85. Recorta ANTES de
    escalar y NUNCA agranda (una foto chica va como está)."""
    aw, ah = (3, 2) if target == "cover" else (4, 5)
    x0, y0, x1, y1 = pd.caja_cubrir(img.size, aw, ah, pos if target == "cover" else None)
    escala = min(1.0, GEMINI_LADO_MAX / max(x1 - x0, y1 - y0))
    salida = (max(1, round((x1 - x0) * escala)), max(1, round((y1 - y0) * escala)))
    return _jpeg(img.resize(salida, Image.LANCZOS, box=(x0, y0, x1, y1)))


# ───────────────────────────────────────────────────────────── las plantillas

def plantilla_portada(img: Image.Image, nombre: str, rubro: str | None, ciudad: str | None) -> bytes:
    """La portada de diseño en JPEG 1600 x 1000. `img` ya viene recortada a 1600 x 1000 (y mejorada, si es el camino gratis)."""
    try:
        return pd._jpeg(pd.dibujar_portada(img, nombre, rubro, ciudad))
    except RenderError as exc:      # falta una fuente del paquete: error del servidor, no de la foto
        raise RuntimeError(str(exc)) from exc


def _fondo_radial() -> Image.Image:
    """El fondo de la galería: radial `#0F3423` (centro) -> `#0B1E15` -> `#08110C` (bordes). Nunca negro puro."""
    radial = Image.radial_gradient("L").resize((GAL_ANCHO, GAL_ALTO), Image.BICUBIC)     # 0 al centro, 255 al borde
    centro = Image.new("RGB", (GAL_ANCHO, GAL_ALTO), (15, 52, 35))
    medio = Image.new("RGB", (GAL_ANCHO, GAL_ALTO), (11, 30, 21))
    borde = Image.new("RGB", (GAL_ANCHO, GAL_ALTO), pd.FRANJA)
    hacia_medio = radial.point(lambda v: min(255, v * 2))
    hacia_borde = radial.point(lambda v: max(0, v - 128) * 2)
    base = Image.composite(medio, centro, hacia_medio)
    return Image.composite(borde, base, hacia_borde)


def _mascara_tarjeta(radio: int, borde: int = 0, ss: int = 3) -> Image.Image:
    """La máscara de la tarjeta (920 x 1150, esquinas de `radio`). Con `borde` > 0, sólo el ANILLO de ese grosor.
    Se dibuja a `ss` veces el tamaño y se achica, para que las esquinas no queden dentadas."""
    w, h = TARJETA_ANCHO * ss, TARJETA_ALTO * ss
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=radio * ss, fill=255)
    if borde:
        b = borde * ss
        d.rounded_rectangle((b, b, w - 1 - b, h - 1 - b), radius=max(0, radio - borde) * ss, fill=0)
    return m.resize((TARJETA_ANCHO, TARJETA_ALTO), Image.LANCZOS)


def plantilla_galeria(foto: Image.Image) -> Image.Image:
    """La foto de la galería con el estilo URUKU: 1080 x 1350. NO lleva textos de la base: una tarjeta 920 x 1150 con la
    foto (esquinas de 44 px, borde de 3 px `#34D27F`, halo), el fondo radial con brillo, `uruku.bo` y el logo abajo.

    `foto` ya viene recortada a 920 x 1150 (4:5) y, en el camino gratis, mejorada."""
    if foto.size != (TARJETA_ANCHO, TARJETA_ALTO):
        raise ValueError("la foto de la tarjeta tiene que ser de 920 x 1150")
    base = _fondo_radial()
    pd._brillo(base, (GAL_ANCHO // 2, TARJETA_Y + TARJETA_ALTO // 2), 560, 110, 0.55)

    tarjeta = _mascara_tarjeta(TARJETA_RADIO)
    # El halo: el contorno de la tarjeta, desenfocado 18 px, al 45 %, DEBAJO de la foto.
    halo = Image.new("L", base.size, 0)
    halo.paste(tarjeta, (TARJETA_X, TARJETA_Y))
    halo = halo.filter(ImageFilter.GaussianBlur(18)).point(lambda v: round(v * 0.45))
    base.paste(Image.new("RGB", base.size, pd.ACENTO), (0, 0), halo)

    base.paste(foto.convert("RGB"), (TARJETA_X, TARJETA_Y), tarjeta)
    base.paste(Image.new("RGB", (TARJETA_ANCHO, TARJETA_ALTO), pd.ACENTO), (TARJETA_X, TARJETA_Y),
               _mascara_tarjeta(TARJETA_RADIO, TARJETA_BORDE))

    # El pie: `uruku.bo` a la izquierda y el logo a la derecha, centrados en la franja 1206..1350.
    centro_y = (PIE_Y0 + PIE_Y1) // 2
    ImageDraw.Draw(base).text((TARJETA_X, centro_y), "uruku.bo", font=fuente("bold", 40), fill=pd.BLANCO, anchor="lm")
    logo = pd.logo_color(PIE_LOGO_ANCHO)
    base.paste(logo, (PIE_LOGO_X, centro_y - logo.height // 2), logo)
    return base


def miniatura(img: Image.Image) -> bytes:
    """La miniatura de la galería: 480 x 600, JPEG q74."""
    return _jpeg(img.resize(MINIATURA, Image.LANCZOS), CALIDAD_MINIATURA)


# ───────────────────────────────────────────────────────────── disco

miniatura_de = fotos_galeria.miniatura_de       # `…/diseno-<token>.jpg` -> `…/diseno-<token>-t.jpg`


def guardar_galeria(slug: str, jpeg: bytes, thumb: bytes) -> tuple[str, str] | None:
    """Guarda `<slug>/diseno-<token>.jpg` y `<slug>/diseno-<token>-t.jpg`. `(url, url_miniatura)` o None si algo falló
    (y entonces no queda ninguno de los dos archivos)."""
    token = secrets.token_hex(16)
    url = imagenes.guardar_foto_local(f"{slug}/{pd.PREFIJO_ARCHIVO}{token}.jpg", jpeg)
    if not url:
        return None
    url_t = imagenes.guardar_foto_local(f"{slug}/{pd.PREFIJO_ARCHIVO}{token}{fotos_galeria.SUFIJO_MINIATURA}.jpg", thumb)
    if not url_t:
        fotos_galeria.soltar_disenos({"slug": slug}, [url])
        return None
    return url, url_t


# ───────────────────────────────────────────────────────────── el registro de usos

def registrar(repo, *, comercio_id: str, foto_id: str | None, target: str, method: str, result: str, actor: str,
              costo: float = 0.0, error: str | None = None, result_url: str | None = None) -> bool:
    """Deja una fila en `photo_style_uses` (sólo insert). Nunca lanza: si la base falla se avisa en el log y el pedido
    sigue (una foto ya armada, y cobrada, no se tira por esto). Devuelve si se pudo registrar."""
    fila = {
        "comercio_id": comercio_id, "foto_id": foto_id, "target": target, "method": method,
        "model": (settings.gemini_image_model or None) if method == "gemini" else None,
        "prompt_version": prompts.PROMPT_VERSION if method != "free" else None,
        "cost_usd": round(float(costo), 4), "result": result,
        "error": ge.limpiar_error(error) if error else None,
        "result_url": result_url, "actor": actor or "desconocido",
    }
    try:
        repo.registrar_uso_foto_estilo(fila)
        return True
    except Exception:  # noqa: BLE001
        logger.error("fotos_estilo.registro_fallo", comercio=comercio_id, method=method, result=result, exc_info=True)
        return False


# ───────────────────────────────────────────────────────────── armar una foto (con el lock)

def _imagen_base(metodo: str, target: str, *, origen: bytes | None, externa: bytes | None, pos: int | None,
                 estado: dict) -> Image.Image:
    """La imagen ya recortada al formato de la plantilla (portada 1600 x 1000, tarjeta 920 x 1150). Corre con el lock."""
    ancho, alto = (pd.ANCHO, pd.ALTO) if target == "cover" else (TARJETA_ANCHO, TARJETA_ALTO)
    pos = pos if target == "cover" else None
    if metodo == "external":
        return pd.cubrir(_abrir_validada(externa or b"", lado_menor_min=EXTERNA_LADO_MENOR_MIN,
                                         max_pixeles=EXTERNA_MAX_PIXELES), ancho, alto, None)

    foto = pd._abrir(origen or b"")                                  # la foto de origen: mismos topes de siempre
    if metodo == "free":
        return pd.mejorar_gratis(pd.cubrir(foto, ancho, alto, pos))

    # gemini: la foto se recorta y se achica ANTES de mandarla
    estado["llamo"] = True
    devuelta = ge.reestilizar(jpeg_para_gemini(foto, target, pos), target)
    estado["cobrada"] = True                                         # hubo imagen: se cobra aunque no sirva
    try:
        img = _abrir_validada(devuelta, lado_menor_min=DEVUELTA_LADO_MENOR_MIN, max_pixeles=DEVUELTA_MAX_PIXELES)
    except (ValueError, pd.PortadaInadecuada) as exc:
        raise ge.GeminiFallo("La imagen que devolvió Gemini no se pudo usar", cobrada=True) from exc
    return pd.cubrir(img, ancho, alto, None)                          # la IA no tiñe ni la mejora Pillow se aplica


def producir(repo, crepo, *, comercio: dict, target: str, metodo: str, origen: bytes | None, externa: bytes | None,
             pos: int | None, foto_id: str | None, actor: str, nombre: str = "", rubro: str | None = None,
             ciudad: str | None = None) -> dict:
    """Arma UNA foto con el lock tomado y la guarda en el disco. Devuelve `{"url": ..., "thumb_url": ...}` (la miniatura sólo en galería).

    Gemini: el tope diario se cuenta acá adentro, y toda llamada se registra en un `finally` con su costo.
    Errores: `EstiloError` (400 foto inválida, 409 ocupado, 429 tope, 502, 503, 504)."""
    if metodo not in METODOS or target not in TARGETS:
        raise EstiloError(400, "Método inválido")
    if metodo == "gemini":
        _exigir_disponible(crepo)
    estado = {"llamo": False, "cobrada": False, "resultado": "error", "error": None, "url": None}
    with transformando():
        if metodo == "gemini":
            _exigir_disponible(crepo)             # otra vez, ya con el lock: el pedido anterior pudo romper el registro
            tope = tope_diario()
            if usados_hoy(repo) >= tope:
                raise EstiloError(429, f"Se llegó al tope de {tope} fotos con IA por hoy")
        try:
            img = _imagen_base(metodo, target, origen=origen, externa=externa, pos=pos, estado=estado)
            if target == "cover":
                jpeg = plantilla_portada(img, nombre, rubro, ciudad)
                url = pd.guardar(comercio["slug"], jpeg)
                salida = {"url": url, "thumb_url": None}
            else:
                final = plantilla_galeria(img)
                guardado = guardar_galeria(comercio["slug"], _jpeg(final), miniatura(final))
                salida = {"url": guardado[0], "thumb_url": guardado[1]} if guardado else {"url": None, "thumb_url": None}
            if not salida["url"]:
                raise EstiloError(502, "No se pudo guardar la foto, probá de nuevo")
            estado["resultado"], estado["url"] = "ok", salida["url"]
            return salida
        except ge.GeminiNoDisponible as exc:
            estado["error"] = str(exc)
            raise EstiloError(503, f"Fotos con IA no disponible: {exc}") from exc
        except ge.GeminiTimeout as exc:
            estado.update(resultado="timeout", cobrada=True, error=str(exc))
            raise EstiloError(504, "Gemini no contestó a tiempo, probá de nuevo") from exc
        except ge.GeminiFallo as exc:
            estado.update(error=str(exc), cobrada=estado["cobrada"] or exc.cobrada)
            raise EstiloError(502, f"Gemini falló: {ge.limpiar_error(str(exc))}") from exc
        except pd.PortadaInadecuada as exc:
            raise EstiloError(400, str(exc)) from exc
        except ValueError as exc:
            raise EstiloError(400, _mensaje_imagen_invalida(target, metodo)) from exc
        except EstiloError as exc:
            estado["error"] = exc.detail
            raise
        finally:
            _cerrar_registro(repo, estado, comercio=comercio, target=target, metodo=metodo, foto_id=foto_id, actor=actor)


def _mensaje_imagen_invalida(target: str, metodo: str) -> str:
    if metodo == "external":
        return "La imagen no es válida: usá un JPEG, PNG o WEBP"
    return "La foto de portada no es una imagen válida" if target == "cover" else "La foto no es una imagen válida"


def _cerrar_registro(repo, estado: dict, *, comercio: dict, target: str, metodo: str, foto_id: str | None,
                     actor: str) -> None:
    """El `finally` de `producir`: Gemini se registra SIEMPRE que se llamó (ok, error o timeout); free y external sólo si salieron bien."""
    if metodo == "gemini":
        if not estado["llamo"]:
            return                           # nunca se llamó (foto inválida, sin disponibilidad): no cuenta ni cuesta
        anotado = registrar(repo, comercio_id=comercio["id"], foto_id=foto_id, target=target, method="gemini",
                            result=estado["resultado"], actor=actor, costo=costo_por_imagen() if estado["cobrada"] else 0.0,
                            error=estado["error"], result_url=estado["url"])
        if not anotado:
            # Sin registro no hay tope que contar: hasta que el día cambie (o se reinicie) la IA queda no disponible.
            marcar_registro_roto()
            logger.error("fotos_estilo.ia_apagada_por_registro", comercio=comercio["id"])
    elif estado["resultado"] == "ok":
        registrar(repo, comercio_id=comercio["id"], foto_id=foto_id, target=target, method=metodo, result="ok",
                  actor=actor, result_url=estado["url"])


# ───────────────────────────────────────────────────────────── el método de una propuesta

def metodos_por_url(usos: list[dict]) -> dict[str, str]:
    """`{result_url: method}` con el uso MÁS NUEVO (los `usos` vienen del más nuevo al más viejo) que dejó cada archivo."""
    out: dict[str, str] = {}
    for u in usos:
        url = u.get("result_url")
        if url and u.get("result") == "ok" and url not in out:
            out[url] = u["method"]
    return out


def metodo_de(repo, comercio_id: str, url: str | None) -> str | None:
    """El método (`free` | `gemini` | `external`) que armó esta propuesta, o None si no hay registro."""
    if not url:
        return None
    try:
        return metodos_por_url(repo.usos_foto_estilo(comercio_id)).get(url)
    except Exception:  # noqa: BLE001
        logger.warning("fotos_estilo.metodo_fallo", comercio=comercio_id, exc_info=True)
        return None


def item_galeria(fila: dict, metodos: dict[str, str]) -> dict:
    """`GalleryItem` (docs/fotos-estilo-uruku.md §6) de una fila de `comercio_fotos`."""
    propuesta = fila.get("diseno_propuesta_url") or None
    return {
        "foto_id": str(fila["id"]), "photo_url": fila.get("url"), "thumb_url": fila.get("thumb_url"),
        "design_url": fila.get("diseno_url") or None, "design_thumb_url": fila.get("diseno_thumb_url") or None,
        "proposal_url": propuesta, "proposal_method": metodos.get(propuesta) if propuesta else None,
    }


# ───────────────────────────────────────────────────────────── el estado (GET)

def estado(repo, crepo, comercio: dict) -> dict:
    """`PhotoStyleState`: la portada, la galería, si la IA se puede usar y cuánto se gastó, y las instrucciones para ChatGPT."""
    cid = comercio["id"]
    metodos = metodos_por_url(repo.usos_foto_estilo(cid))
    disponible, motivo = disponibilidad(crepo)
    gastos = repo.gastos_gemini_comercio(cid)           # lo cobrado por Gemini: el mismo criterio que `/usos` (cost_usd > 0)
    propuesta = comercio.get("portada_diseno_propuesta_url") or None
    return {
        "comercio": {"id": cid, "nombre": comercio.get("nombre"), "slug": comercio.get("slug")},
        "cover": {"photo_url": comercio.get("portada_url") or None,
                  "design_url": comercio.get("portada_diseno_url") or None,
                  "proposal_url": propuesta, "proposal_method": metodos.get(propuesta) if propuesta else None},
        "gallery": [item_galeria(f, metodos) for f in repo.list_fotos_comercio(cid)],
        # `reason` listo para mostrar (empieza con mayúscula); en el 503 el motivo va en minúscula, después de los dos puntos.
        "gemini": {"available": disponible, "reason": (motivo[:1].upper() + motivo[1:]) if motivo else None,
                   "cost_usd": costo_por_imagen(),
                   "used_today": usados_hoy(repo), "daily_cap": tope_diario(),
                   "merchant_uses": len(gastos),
                   "merchant_cost_usd": round(sum(float(g.get("cost_usd") or 0) for g in gastos), 4)},
        "instructions": prompts.instrucciones(),
    }


def resumen_usos(repo, desde: str | None, hasta: str | None) -> dict:
    """`UsesSummary`: lo gastado con Gemini entre dos días de Bolivia (inclusive). `images` = imágenes cobradas (las que
    salieron bien y los timeouts: costo > 0). Fechas `AAAA-MM-DD`; sin ellas, desde el 1 del mes hasta hoy."""
    hoy = cargas.hoy_bolivia()
    try:
        d = cargas.parse_fecha(desde) if desde else hoy.replace(day=1)
        h = cargas.parse_fecha(hasta) if hasta else hoy
    except ValueError as exc:
        raise EstiloError(400, "Las fechas tienen que ser AAAA-MM-DD") from exc
    if h < d:
        raise EstiloError(400, "La fecha «hasta» no puede ser anterior a «desde»")
    if (h - d).days > 366:
        raise EstiloError(400, "El rango no puede pasar de un año")
    filas = repo.resumen_usos_foto_estilo(cargas.iso_z(cargas.limites_dia_utc(d)[0]),
                                          cargas.iso_z(cargas.limites_dia_utc(h)[1]))
    por_comercio: dict[str, dict] = {}
    for f in filas:
        costo = float(f.get("cost_usd") or 0)
        if costo <= 0:
            continue
        acc = por_comercio.setdefault(str(f["comercio_id"]), {"images": 0, "cost_usd": 0.0})
        acc["images"] += 1
        acc["cost_usd"] += costo
    by_merchant = []
    for cid, acc in por_comercio.items():
        c = repo.get_comercio(cid) or {}
        by_merchant.append({"comercio_id": cid, "nombre": c.get("nombre") or "(sin nombre)", "images": acc["images"],
                            "cost_usd": round(acc["cost_usd"], 4)})
    by_merchant.sort(key=lambda m: (-m["cost_usd"], m["nombre"]))
    return {"desde": d.isoformat(), "hasta": h.isoformat(), "images": sum(m["images"] for m in by_merchant),
            "cost_usd": round(sum(m["cost_usd"] for m in by_merchant), 4), "by_merchant": by_merchant}


# ───────────────────────────────────────────────────────────── la portada: proponer

def proponer_portada(repo, crepo, comercio: dict, *, metodo: str, externa: bytes | None, actor: str) -> dict:
    """Arma la portada de diseño por el camino `metodo` y la deja como PROPUESTA (no publica nada). Devuelve `CoverDesign`.

    Sincrónica: el endpoint la corre en el threadpool. La foto de origen se lee FUERA del lock."""
    if metodo not in METODOS:
        raise EstiloError(400, "Método inválido")
    cid = comercio["id"]
    if not comercio.get("portada_url"):
        raise EstiloError(400, "El comercio no tiene foto de portada")
    if metodo == "gemini":
        _exigir_disponible(crepo)
    origen = None
    if metodo != "external":
        origen = pd.leer_portada(comercio, remoto=True)      # QA: si no está en el disco, por HTTPS (fotos_origen)
        if origen is None:
            raise EstiloError(400, "No se pudo leer la foto de portada desde el servidor")
    rubro = (repo.get_rubro_por_id(comercio.get("rubro_id")) or {}).get("nombre")
    ciudad = (repo.get_ciudad_por_id(comercio.get("ciudad_id")) or {}).get("nombre")

    salida = producir(repo, crepo, comercio=comercio, target="cover", metodo=metodo, origen=origen, externa=externa,
                      pos=comercio.get("portada_pos"), foto_id=None, actor=actor,
                      nombre=comercio.get("nombre") or "", rubro=rubro, ciudad=ciudad)
    url = salida["url"]

    # Armar tarda unos segundos (Gemini, hasta un minuto): si en el medio cambió la foto (o los datos que se dibujan),
    # la propuesta sería de otra foto. Se relee la fila y, si cambió, se suelta el archivo recién creado.
    fresca = repo.get_comercio(cid) or {}
    if fresca.get("portada_url") != comercio.get("portada_url"):
        pd.soltar_archivo(comercio, url)
        raise EstiloError(409, MSG_CAMBIO_PORTADA)
    if any(fresca.get(c) != comercio.get(c) for c in ("nombre", "rubro_id", "ciudad_id", "portada_pos")):
        pd.soltar_archivo(comercio, url)
        raise EstiloError(409, MSG_CAMBIO_DATOS)

    anterior = fresca.get("portada_diseno_propuesta_url")
    try:
        actualizado = repo.update_comercio(cid, {"portada_diseno_propuesta_url": url}, None)
    except Exception:
        pd.soltar_archivo(comercio, url)        # recién creado: que no quede huérfano
        raise
    pd.soltar_huerfanos(repo, comercio, [anterior])    # la propuesta anterior ya no la apunta nada
    logger.info("admin.portada_diseno_propuesta", comercio=cid, by=actor, method=metodo)
    return pd.respuesta(actualizado or {**comercio, "portada_diseno_propuesta_url": url}, metodo)


# ───────────────────────────────────────────────────────────── la galería: proponer, usar, descartar, volver

def _foto_o_404(repo, comercio_id: str, foto_id: str) -> dict:
    fila = repo.get_foto_comercio(foto_id, comercio_id)
    if fila is None:
        raise EstiloError(404, "Foto no encontrada")
    return fila


def _en_uso_de(fila: dict | None) -> set[str]:
    """Todo archivo de diseño que la fila todavía apunta (las tres columnas y la miniatura derivada de la propuesta)."""
    fila = fila or {}
    return {u for u in (*(fila.get(c) for c in fotos_galeria.COLUMNAS_DISENO),
                        miniatura_de(fila.get("diseno_propuesta_url"))) if u}


def soltar_huerfanos_de_foto(repo, comercio: dict, foto_id: str, urls: list[str | None]) -> None:
    """Borra del disco los archivos de diseño `urls` que la fila YA NO apunta. Relee la fila DESPUÉS de escribir: si otro
    pedido volvió a apuntar uno, no se borra. Si no se puede releer, no se borra nada (un archivo de más es barato)."""
    try:
        fresca = repo.get_foto_comercio(foto_id, comercio["id"])
    except Exception:  # noqa: BLE001
        logger.warning("fotos_estilo.releer_fallo", comercio=comercio.get("id"), foto=foto_id, exc_info=True)
        return
    vigentes = _en_uso_de(fresca)
    fotos_galeria.soltar_disenos(comercio, [u for u in urls if u and u not in vigentes])


def proponer_galeria(repo, crepo, comercio: dict, foto_id: str, *, metodo: str, externa: bytes | None,
                     actor: str) -> dict:
    """Arma el diseño de una foto de la galería por el camino `metodo` y lo deja como PROPUESTA. Devuelve `GalleryItem`."""
    if metodo not in METODOS:
        raise EstiloError(400, "Método inválido")
    cid = comercio["id"]
    fila = _foto_o_404(repo, cid, foto_id)
    if metodo == "gemini":
        _exigir_disponible(crepo)
    origen = None
    if metodo != "external":
        # Sin `slug`, como la portada: un comercio renombrado deja sus fotos en la carpeta del slug viejo.
        origen = fotos_origen.leer_foto_origen(fila.get("url"))
        if origen is None:
            raise EstiloError(400, "No se pudo leer la foto desde el servidor")

    salida = producir(repo, crepo, comercio=comercio, target="gallery", metodo=metodo, origen=origen, externa=externa,
                      pos=None, foto_id=str(fila["id"]), actor=actor)
    url, thumb = salida["url"], salida["thumb_url"]

    fresca = repo.get_foto_comercio(foto_id, cid)
    if fresca is None or fresca.get("url") != fila.get("url"):
        fotos_galeria.soltar_disenos(comercio, [url, thumb])
        raise EstiloError(409, MSG_CAMBIO_FOTO)

    anterior = fresca.get("diseno_propuesta_url")
    try:
        repo.update_foto_comercio(fila["id"], cid, {"diseno_propuesta_url": url})
    except Exception:
        fotos_galeria.soltar_disenos(comercio, [url, thumb])
        raise
    soltar_huerfanos_de_foto(repo, comercio, foto_id, [anterior, miniatura_de(anterior)])
    logger.info("admin.foto_diseno_propuesta", comercio=cid, foto=foto_id, by=actor, method=metodo)
    return item_galeria({**_foto_o_404(repo, cid, foto_id)}, {url: metodo})


def _item(repo, comercio_id: str, foto_id: str) -> dict:
    """El `GalleryItem` de una foto, con el método leído del registro."""
    fila = _foto_o_404(repo, comercio_id, foto_id)
    propuesta = fila.get("diseno_propuesta_url")
    metodos = {propuesta: m} if propuesta and (m := metodo_de(repo, comercio_id, propuesta)) else {}
    return item_galeria(fila, metodos)


MSG_PROPUESTA_CAMBIO = "La propuesta cambió, revisá de nuevo"


def usar_diseno(repo, comercio: dict, foto_id: str, *, actor: str) -> dict:
    """La propuesta pasa a la ficha pública (`diseno_url` + su miniatura) y la propuesta queda vacía.

    UPDATE condicional: sólo si la fila TODAVÍA tiene la propuesta que se leyó. Si en el medio otro pedido la reemplazó
    (`proponer_galeria` suelta el archivo viejo), aprobarla publicaría un archivo que ya no existe: 409."""
    cid = comercio["id"]
    fila = _foto_o_404(repo, cid, foto_id)
    propuesta = fila.get("diseno_propuesta_url")
    if not propuesta:
        raise EstiloError(400, "No hay una propuesta de diseño para usar")
    viejos = [fila.get("diseno_url"), fila.get("diseno_thumb_url")]
    cambio = repo.update_foto_comercio(fila["id"], cid, {"diseno_url": propuesta, "diseno_thumb_url": miniatura_de(propuesta),
                                                         "diseno_propuesta_url": None},
                                       si={"diseno_propuesta_url": propuesta})
    if cambio is None:
        raise EstiloError(409, MSG_PROPUESTA_CAMBIO)
    soltar_huerfanos_de_foto(repo, comercio, foto_id, viejos)       # el diseño anterior ya no lo apunta nada
    logger.info("admin.foto_diseno_usado", comercio=cid, foto=foto_id, by=actor)
    return _item(repo, cid, foto_id)


def descartar_propuesta(repo, comercio: dict, foto_id: str, *, actor: str) -> dict:
    """Descarta la propuesta (no toca el diseño vigente). Sin propuesta no hay nada que hacer y no es un error.
    Condicional como `usar_diseno`: si la propuesta ya es otra, 409 (no se descarta la nueva sin haberla visto)."""
    cid = comercio["id"]
    fila = _foto_o_404(repo, cid, foto_id)
    propuesta = fila.get("diseno_propuesta_url")
    if propuesta:
        cambio = repo.update_foto_comercio(fila["id"], cid, {"diseno_propuesta_url": None},
                                           si={"diseno_propuesta_url": propuesta})
        if cambio is None:
            raise EstiloError(409, MSG_PROPUESTA_CAMBIO)
        soltar_huerfanos_de_foto(repo, comercio, foto_id, [propuesta, miniatura_de(propuesta)])
        logger.info("admin.foto_diseno_descartado", comercio=cid, foto=foto_id, by=actor)
    return _item(repo, cid, foto_id)


def volver_a_la_original(repo, comercio: dict, foto_id: str, *, actor: str) -> dict:
    """La ficha deja de usar el diseño de esta foto (la propuesta, si hay, no se toca). La original NUNCA se borra."""
    cid = comercio["id"]
    fila = _foto_o_404(repo, cid, foto_id)
    viejos = [fila.get("diseno_url"), fila.get("diseno_thumb_url")]
    if any(viejos):
        cambio = repo.update_foto_comercio(fila["id"], cid, {"diseno_url": None, "diseno_thumb_url": None},
                                           si={"diseno_url": fila.get("diseno_url")})
        if cambio is None:
            raise EstiloError(409, MSG_PROPUESTA_CAMBIO)
        soltar_huerfanos_de_foto(repo, comercio, foto_id, viejos)
        logger.info("admin.foto_diseno_quitado", comercio=cid, foto=foto_id, by=actor)
    return _item(repo, cid, foto_id)


# ───────────────────────────────────────────────────────────── la imagen subida (/externa)

async def leer_subida(foto: UploadFile) -> bytes:
    """Los bytes de la imagen subida. 400 si está vacía, 413 si pasa de 15 MB (se lee de a trozos: no se baja de más).
    `EstiloError`: el endpoint lo pasa a `HTTPException`."""
    trozos: list[bytes] = []
    total = 0
    while True:
        trozo = await foto.read(1024 * 1024)
        if not trozo:
            break
        total += len(trozo)
        if total > EXTERNA_MAX_BYTES:
            raise EstiloError(413, "La imagen pesa más de 15 MB")
        trozos.append(trozo)
    if not total:
        raise EstiloError(400, "Falta la imagen")
    return b"".join(trozos)
