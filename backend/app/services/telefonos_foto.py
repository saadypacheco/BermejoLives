"""Leer los teléfonos que se ven en las portadas de los comercios (docs/telefonos-en-fotos.md).

QUÉ HACE
========
Una tanda toma unas portadas que todavía no se leyeron, las lee de a una y guarda cada número como una
PROPUESTA en `telefonos_detectados`. **Nada se escribe solo en la ficha del comercio**: una persona aplica o
descarta cada propuesta desde el panel (`api/telefonos_foto.py`).

MOTORES (costo cero por defecto, docs/contenido-redes-tecnico.md §17)
=====================================================================
- `tesseract`: OCR local gratis. Preproceso con Pillow (gris, lado mayor 1600, autocontraste) y dos pasadas:
  la imagen y su negativo (carteles claros sobre fondo oscuro). Lista blanca de dígitos y puntuación de
  teléfono para que no invente letras.
- `gemini`: sólo con el interruptor de costo `gemini_phone_scan` prendido Y con GEMINI_API_KEY. La foto va
  a 1024 px y el modelo contesta sólo los números.
- `gemini-relevamiento`: el relevamiento por fotos que ya existe (`vision.analizar_fotos`) devuelve también los
  teléfonos; se guardan sin llamadas de más (`guardar_del_relevamiento`).

Los números salen de `core/telefonos_foto.extraer`: es ahí donde se descartan fechas, horarios, precios, NIT y
los números de URUKU.

POR QUÉ UN ERROR NO SIEMPRE QUEDA REGISTRADO
============================================
Una foto que no se puede leer (archivo roto, el modelo rechaza la imagen) se registra con su error: la
tanda sigue y el error se reintenta a los 7 días. Pero si el que falla es el servicio (cuota de Gemini, red,
Tesseract sin instalar), la foto NO se marca: si se marcara, un corte de diez minutos dejaría decenas de
portadas sin leer por una semana. En ese caso la tanda se corta y la próxima vuelta reintenta las mismas.
"""
from __future__ import annotations

import shutil
from io import BytesIO
from typing import Callable

import structlog

from app.core.telefonos_foto import (MAX_TEXTO_LEIDO, UMBRAL_COMPARTIDO, Telefono, extraer,
                                     mismo_numero)
from app.services import cost_switches
from app.services.vision import (LectorFallo, LectorTransitorio, VisionNoConfigurada,
                                 _descargar, leer_telefonos_foto)

logger = structlog.get_logger()

MOTOR_TESSERACT = "tesseract"
MOTOR_GEMINI = "gemini"
MOTOR_RELEVAMIENTO = "gemini-relevamiento"

LADO_OCR = 1600
TIMEOUT_OCR_SEG = 30
#: `--psm 11` = texto suelto, sin suponer renglones (carteles, stickers); lista blanca de lo que tiene un teléfono.
CONFIG_OCR = "--psm 11 -c tessedit_char_whitelist=0123456789+-.()"

_avisado_sin_tesseract = False


def reiniciar_aviso() -> None:
    global _avisado_sin_tesseract
    _avisado_sin_tesseract = False


# ───────────────────────────────────────────────────────────── motores

def tesseract_disponible() -> bool:
    """¿Está el binario `tesseract` y el paquete `pytesseract`?"""
    if shutil.which("tesseract") is None:
        return False
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        return False
    return True


def motor_activo(crepo) -> str:
    """`gemini` si el dueño prendió el interruptor Y hay clave; si no, el lector gratis."""
    from app.core.config import settings

    if cost_switches.esta_prendido(crepo, cost_switches.GEMINI_PHONE_SCAN) and settings.gemini_api_key:
        return MOTOR_GEMINI
    return MOTOR_TESSERACT


def preparar_imagenes(data: bytes) -> list:
    """Las imágenes que se le pasan al OCR: la foto en gris, a `LADO_OCR` px de lado mayor y con el contraste
    estirado, y su negativo. Lanza `LectorFallo` si los bytes no son una imagen."""
    from PIL import Image, ImageOps

    try:
        im = ImageOps.exif_transpose(Image.open(BytesIO(data))).convert("L")
        escala = LADO_OCR / max(im.size)
        if escala != 1:
            im = im.resize((max(1, round(im.width * escala)), max(1, round(im.height * escala))),
                           Image.Resampling.LANCZOS)
        im = ImageOps.autocontrast(im)
        return [im, ImageOps.invert(im)]
    except Exception:  # noqa: BLE001
        raise LectorFallo("La foto no se pudo abrir como imagen") from None


def leer_con_tesseract(data: bytes) -> str:
    """El texto que Tesseract lee en la foto (las dos pasadas, una a continuación de la otra).

    `LectorFallo` si la foto no sirve o Tesseract tarda más de `TIMEOUT_OCR_SEG`; `LectorTransitorio` si el
    programa no está instalado."""
    try:
        import pytesseract
    except ImportError:
        raise LectorTransitorio("Falta el paquete pytesseract") from None
    textos = []
    for im in preparar_imagenes(data):
        try:
            textos.append(pytesseract.image_to_string(im, config=CONFIG_OCR, timeout=TIMEOUT_OCR_SEG))
        except pytesseract.TesseractNotFoundError:
            raise LectorTransitorio("Tesseract no está instalado") from None
        except RuntimeError as exc:                       # el timeout de pytesseract
            raise LectorFallo(f"Tesseract no pudo leer la foto: {exc}"[:200]) from None
        except Exception as exc:  # noqa: BLE001
            raise LectorFallo(f"Tesseract falló: {type(exc).__name__}") from None
    return "\n".join(textos)


# ───────────────────────────────────────────────────────────── guardar

def _fila(comercio: dict, foto_url: str, motor: str, tel: Telefono) -> dict:
    coincide = (mismo_numero(tel.numero, comercio.get("whatsapp"))
                or mismo_numero(tel.numero, comercio.get("telefono")))
    return {"comercio_id": comercio["id"], "numero": tel.numero, "tipo": tel.tipo,
            "texto_leido": tel.texto_leido[:MAX_TEXTO_LEIDO], "foto_url": foto_url, "motor": motor,
            "estado": "coincide" if coincide else "pendiente"}


def guardar_detectados(trepo, comercio: dict, foto_url: str, motor: str, telefonos: list[Telefono]) -> int:
    """Guarda los teléfonos como propuestas y devuelve cuántas filas nuevas se crearon.

    Un número que ya es el WhatsApp o el teléfono del comercio entra como `coincide`. Uno que ya estaba
    guardado para ese comercio (aplicado o descartado por una persona) no se toca. Después se recuenta cuántos
    comercios tienen cada número nuevo: con `UMBRAL_COMPARTIDO` o más se marca `compartido`."""
    if not telefonos:
        return 0
    creadas = trepo.insert_detectados([_fila(comercio, foto_url, motor, t) for t in telefonos])
    for numero in {f["numero"] for f in creadas}:
        comercios = {f["comercio_id"] for f in trepo.list_por_numero(numero)}
        if len(comercios) >= UMBRAL_COMPARTIDO:
            trepo.marcar_compartido(numero)
            logger.info("telefonos_foto.compartido", numero_terminado_en=numero[-4:], comercios=len(comercios))
    return len(creadas)


def guardar_del_relevamiento(trepo, comercio: dict, urls: list[str], propuesta: dict) -> int:
    """Guarda los teléfonos que trajo el relevamiento por fotos (`vision.analizar_fotos`), gratis: ya se pagó
    esa llamada. NUNCA lanza: un fallo acá no puede tumbar el análisis del comercio.

    Sin el campo `telefonos` en la propuesta (una propuesta vieja o armada a mano), con error o sin ninguna
    foto analizada, no hace nada. La portada (la primera URL) queda registrada como leída por este motor."""
    try:
        textos = propuesta.get("telefonos")
        if textos is None or propuesta.get("error") or not propuesta.get("fotos_analizadas") or not urls:
            return 0
        telefonos = extraer("\n".join(str(t) for t in textos))
        n = guardar_detectados(trepo, comercio, urls[0], MOTOR_RELEVAMIENTO, telefonos)
        trepo.registrar_escaneada(urls[0], MOTOR_RELEVAMIENTO, comercio["id"], len(telefonos))
        return n
    except Exception:  # noqa: BLE001
        logger.warning("telefonos_foto.relevamiento_fallo", comercio=(comercio or {}).get("id"), exc_info=True)
        return 0


# ───────────────────────────────────────────────────────────── la tanda

def procesar_portada(trepo, fila: dict, motor: str, ocr: Callable[[bytes], str],
                     gemini: Callable[[bytes], list[str]]) -> tuple[int, bool]:
    """Lee UNA portada y guarda lo que encuentre. Devuelve `(números nuevos propuestos, se pudo leer)`.

    `fila` es `{comercio_id, portada_url, whatsapp, telefono, ciudad_id}`. Si la foto no se puede bajar o
    leer, la registra con su error y devuelve `(0, False)`; si el que falla es el servicio, deja pasar
    `LectorTransitorio`/`VisionNoConfigurada` para que la tanda se corte sin marcar la foto."""
    url, comercio_id = fila["portada_url"], fila["comercio_id"]
    comercio = {"id": comercio_id, "whatsapp": fila.get("whatsapp"), "telefono": fila.get("telefono")}
    data = _descargar(url)
    if not data:
        trepo.registrar_escaneada(url, motor, comercio_id, 0, "No se pudo bajar la foto")
        return 0, False
    try:
        texto = "\n".join(gemini(data)) if motor == MOTOR_GEMINI else ocr(data)
    except LectorFallo as exc:
        trepo.registrar_escaneada(url, motor, comercio_id, 0, str(exc))
        return 0, False
    telefonos = extraer(texto)
    nuevos = guardar_detectados(trepo, comercio, url, motor, telefonos)
    trepo.registrar_escaneada(url, motor, comercio_id, len(telefonos))
    return nuevos, True


def tanda(trepo, crepo, limite: int = 20, ocr: Callable[[bytes], str] | None = None,
          gemini: Callable[[bytes], list[str]] | None = None) -> dict:
    """Una vuelta del worker: lee hasta `limite` portadas de a una.

    Devuelve `{motor, tomadas, leidas, numeros, errores, cortada, sin_lector}`. `tomadas == 0` quiere decir que
    no hay nada para leer (o que falta el lector). Se corta en la primera falla del servicio, sin marcar la foto."""
    global _avisado_sin_tesseract
    motor = motor_activo(crepo)
    out = {"motor": motor, "tomadas": 0, "leidas": 0, "numeros": 0, "errores": 0,
           "cortada": False, "sin_lector": False}
    ocr = ocr or leer_con_tesseract
    gemini = gemini or leer_telefonos_foto
    if motor == MOTOR_TESSERACT and ocr is leer_con_tesseract and not tesseract_disponible():
        if not _avisado_sin_tesseract:
            _avisado_sin_tesseract = True
            logger.warning("telefonos_foto.sin_tesseract",
                           detalle="el programa tesseract (o el paquete pytesseract) no está instalado: el worker no toma trabajos")
        out["sin_lector"] = True
        return out
    filas = trepo.portadas_sin_escanear(motor, limite)
    out["tomadas"] = len(filas)
    for fila in filas:
        try:
            nuevos, leida = procesar_portada(trepo, fila, motor, ocr, gemini)
            out["numeros"] += nuevos
            out["leidas" if leida else "errores"] += 1
        except (LectorTransitorio, VisionNoConfigurada) as exc:
            logger.warning("telefonos_foto.servicio_caido", motor=motor, error=str(exc)[:200])
            out["cortada"] = True
            break
        except Exception as exc:  # noqa: BLE001 - una portada no puede frenar a las demás
            out["errores"] += 1
            logger.warning("telefonos_foto.portada_fallo", comercio=fila.get("comercio_id"), exc_info=True)
            try:
                trepo.registrar_escaneada(fila["portada_url"], motor, fila["comercio_id"], 0,
                                          f"Error interno: {type(exc).__name__}")
            except Exception:  # noqa: BLE001
                out["cortada"] = True
                break
    logger.info("telefonos_foto.tanda", **out)
    return out
