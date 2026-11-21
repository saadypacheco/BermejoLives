"""Llamar a Gemini para transformar UNA foto (docs/fotos-estilo-uruku.md §2 y §8).

`reestilizar(jpeg, target) -> bytes` manda el prompt fijo (`fotos_estilo_prompt`, sin datos del comercio) y la foto
inline, y devuelve la primera imagen que vuelve. Lo demás (recortar antes, validar lo que vuelve, la plantilla, el
tope, el registro del costo y el lock) lo hace `fotos_estilo`.

- La clave va en la cabecera (`core/gemini.cabeceras`), nunca en la URL. Todo texto de error pasa por
  `gemini.sin_secretos` y se corta a 300 caracteres: ni el `detail` ni el registro pueden llevarla.
- Se piden `generationConfig.responseModalities: ["IMAGE"]` y `generationConfig.imageConfig.aspectRatio`
  (`3:2` la portada, `4:5` la galería). La respuesta se lee de `candidates[].content.parts[]`, en `inlineData`
  (REST) o `inline_data` (algunos clientes).
- Sincrónica y bloqueante hasta `GEMINI_IMAGE_TIMEOUT_SEG`: se llama dentro de `run_in_threadpool` y con el lock tomado.
"""
from __future__ import annotations

import base64
import binascii
import json
import time

import httpx
import structlog

from app.core import gemini
from app.core.config import settings
from app.services import fotos_estilo_prompt as prompts

logger = structlog.get_logger()

#: Lo máximo que se acepta de la imagen que vuelve (ya decodificada del base64).
MAX_BYTES_RESPUESTA = 20 * 1024 * 1024
#: Lo máximo que se lee de la respuesta HTTP entera (el base64 de una imagen de 20 MB pesa ~27 MB).
MAX_BYTES_HTTP = 30 * 1024 * 1024
MAX_ERROR = 300

#: Sólo para pruebas: un `httpx.BaseTransport` (p. ej. `httpx.MockTransport`) que reemplaza a la red.
_TRANSPORTE: httpx.BaseTransport | None = None


class GeminiNoDisponible(Exception):
    """Falta la clave, el modelo o el costo: no se llamó a Gemini. El endpoint responde 503."""


class GeminiFallo(Exception):
    """Gemini contestó con error o sin imagen (o la imagen no sirve). Mensaje ya limpio de secretos. El endpoint responde 502.

    `cobrada`: ¿hubo imagen (y entonces se cobra)? Un error HTTP o una respuesta sin imagen no se cobra; una imagen
    que volvió pero no sirve, sí."""

    def __init__(self, mensaje: str, cobrada: bool = False):
        super().__init__(mensaje)
        self.cobrada = cobrada


class GeminiTimeout(Exception):
    """Gemini no contestó a tiempo. El endpoint responde 504; igual se registra y cuenta como gasto."""


def motivo_no_disponible() -> str | None:
    """Por qué no se puede llamar a Gemini con lo que hay en el .env (None si está todo). No mira el interruptor."""
    if not (settings.gemini_api_key or "").strip():
        return "falta la clave de Gemini"
    if not (settings.gemini_image_model or "").strip():
        return "falta configurar el modelo de imagen"
    if not (settings.gemini_image_cost_usd and settings.gemini_image_cost_usd > 0):
        return "falta configurar el costo por imagen"
    return None


def limpiar_error(texto: str | None) -> str:
    """Un texto de error listo para mostrar y registrar: sin la clave y de 300 caracteres como máximo."""
    return gemini.sin_secretos(" ".join(str(texto or "").split()))[:MAX_ERROR]


def armar_pedido(jpeg: bytes, target: str) -> dict:
    """El cuerpo JSON del pedido. Separado para poder probar que no lleva nada del comercio."""
    return {
        "contents": [{"parts": [
            {"text": prompts.prompt(target)},
            {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(jpeg).decode("ascii")}},
        ]}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {"aspectRatio": prompts.ASPECTO[target]},
        },
    }


def _primera_imagen(cuerpo: dict) -> bytes | None:
    """La primera imagen de `candidates[].content.parts[]` (`inlineData` o `inline_data`), ya decodificada. Todo se mira con
    `isinstance`: una respuesta con otra forma (una lista donde va un dict, un número) no rompe, da None."""
    candidatos = cuerpo.get("candidates")
    for cand in candidatos if isinstance(candidatos, list) else []:
        contenido = cand.get("content") if isinstance(cand, dict) else None
        partes = contenido.get("parts") if isinstance(contenido, dict) else None
        for parte in partes if isinstance(partes, list) else []:
            datos = (parte.get("inlineData") or parte.get("inline_data")) if isinstance(parte, dict) else None
            crudo = datos.get("data") if isinstance(datos, dict) else None
            if isinstance(crudo, str) and crudo:
                try:
                    return base64.b64decode(crudo, validate=False)
                except (binascii.Error, ValueError):
                    return None
    return None


def _leer_respuesta(r: httpx.Response, deadline: float) -> bytes:
    """El cuerpo de la respuesta con DOS topes: `MAX_BYTES_HTTP` y el tiempo TOTAL (`deadline`, monotónico). `httpx.Timeout`
    vale por fase (conexión, lectura de cada trozo): un servidor que gotea bytes lo estiraría sin fin."""
    trozos: list[bytes] = []
    total = 0
    for trozo in r.iter_bytes():
        total += len(trozo)
        if total > MAX_BYTES_HTTP:
            raise GeminiFallo("La respuesta de Gemini es demasiado grande", cobrada=r.status_code == 200)
        if time.monotonic() > deadline:
            raise GeminiTimeout("Gemini no contestó a tiempo")
        trozos.append(trozo)
    return b"".join(trozos)


def reestilizar(jpeg: bytes, target: str) -> bytes:
    """Manda la foto a Gemini y devuelve los bytes de la imagen que vuelve (sin validar: lo hace quien llama).

    `GeminiNoDisponible` (sin llamada), `GeminiTimeout` o `GeminiFallo`: CUALQUIER otra cosa que pase adentro sale como
    `GeminiFallo` (nunca un 500). Tiempo total acotado por `GEMINI_IMAGE_TIMEOUT_SEG`. Un `ConnectTimeout` es `GeminiFallo`
    sin cobrar (el pedido ni llegó a Google); un timeout de lectura sí es `GeminiTimeout` (se cobra: puede haberse generado)."""
    motivo = motivo_no_disponible()
    if motivo:
        raise GeminiNoDisponible(motivo)
    if target not in prompts.ASPECTO:
        raise ValueError("target inválido")
    try:
        return _reestilizar(jpeg, target)
    except (GeminiNoDisponible, GeminiFallo, GeminiTimeout):
        raise
    except Exception as exc:  # noqa: BLE001
        raise GeminiFallo(limpiar_error(f"Error inesperado al hablar con Gemini ({type(exc).__name__})")) from exc


def _reestilizar(jpeg: bytes, target: str) -> bytes:
    seg = max(1, int(settings.gemini_image_timeout_seg or 60))
    deadline = time.monotonic() + seg
    try:
        with httpx.Client(timeout=httpx.Timeout(seg, connect=min(10, seg)), follow_redirects=False,
                          transport=_TRANSPORTE) as cliente:
            with cliente.stream("POST", gemini.url_generar_imagen(), headers=gemini.cabeceras(),
                                json=armar_pedido(jpeg, target)) as r:
                estado = r.status_code
                crudo = _leer_respuesta(r, deadline)
    except (httpx.ConnectTimeout, httpx.PoolTimeout) as exc:
        raise GeminiFallo(limpiar_error(f"No se pudo conectar con Gemini ({type(exc).__name__})")) from exc
    except httpx.TimeoutException as exc:
        raise GeminiTimeout("Gemini no contestó a tiempo") from exc
    except httpx.HTTPError as exc:
        raise GeminiFallo(limpiar_error(f"No se pudo hablar con Gemini ({type(exc).__name__})")) from exc

    try:
        cuerpo = json.loads(crudo)
    except ValueError:
        cuerpo = {}
    if not isinstance(cuerpo, dict):
        cuerpo = {}
    if estado != 200:
        error = cuerpo.get("error")
        detalle = error.get("message") if isinstance(error, dict) else None
        raise GeminiFallo(limpiar_error(f"Gemini respondió {estado}" + (f": {detalle}" if isinstance(detalle, str) and detalle else "")))
    imagen = _primera_imagen(cuerpo)
    if not imagen:
        feedback = cuerpo.get("promptFeedback")
        bloqueo = feedback.get("blockReason") if isinstance(feedback, dict) else None
        raise GeminiFallo(limpiar_error("Gemini no devolvió una imagen" + (f" ({bloqueo})" if isinstance(bloqueo, str) and bloqueo else "")))
    if len(imagen) > MAX_BYTES_RESPUESTA:
        raise GeminiFallo("La imagen que devolvió Gemini es demasiado grande", cobrada=True)    # hubo imagen: se cobra
    return imagen
