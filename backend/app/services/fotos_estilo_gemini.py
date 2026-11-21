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

import httpx
import structlog

from app.core import gemini
from app.core.config import settings
from app.services import fotos_estilo_prompt as prompts

logger = structlog.get_logger()

#: Lo máximo que se acepta de la imagen que vuelve (ya decodificada del base64).
MAX_BYTES_RESPUESTA = 20 * 1024 * 1024
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
    for cand in cuerpo.get("candidates") or []:
        for parte in ((cand.get("content") or {}).get("parts") or []):
            datos = parte.get("inlineData") or parte.get("inline_data")
            if isinstance(datos, dict) and datos.get("data"):
                try:
                    return base64.b64decode(datos["data"], validate=False)
                except (binascii.Error, ValueError):
                    return None
    return None


def reestilizar(jpeg: bytes, target: str) -> bytes:
    """Manda la foto a Gemini y devuelve los bytes de la imagen que vuelve (sin validar: lo hace quien llama).

    `GeminiNoDisponible` (sin llamada), `GeminiTimeout` o `GeminiFallo`."""
    motivo = motivo_no_disponible()
    if motivo:
        raise GeminiNoDisponible(motivo)
    if target not in prompts.ASPECTO:
        raise ValueError("target inválido")
    seg = max(1, int(settings.gemini_image_timeout_seg or 60))
    try:
        with httpx.Client(timeout=httpx.Timeout(seg, connect=min(10, seg)), follow_redirects=False,
                          transport=_TRANSPORTE) as cliente:
            r = cliente.post(gemini.url_generar_imagen(), headers=gemini.cabeceras(), json=armar_pedido(jpeg, target))
    except httpx.TimeoutException as exc:
        raise GeminiTimeout("Gemini no contestó a tiempo") from exc
    except httpx.HTTPError as exc:
        raise GeminiFallo(limpiar_error(f"No se pudo hablar con Gemini ({type(exc).__name__})")) from exc

    try:
        cuerpo = r.json()
    except ValueError:
        cuerpo = {}
    if not isinstance(cuerpo, dict):
        cuerpo = {}
    if r.status_code != 200:
        error = cuerpo.get("error")
        detalle = error.get("message") if isinstance(error, dict) else None
        raise GeminiFallo(limpiar_error(f"Gemini respondió {r.status_code}" + (f": {detalle}" if detalle else "")))
    imagen = _primera_imagen(cuerpo)
    if not imagen:
        bloqueo = (cuerpo.get("promptFeedback") or {}).get("blockReason")
        raise GeminiFallo(limpiar_error("Gemini no devolvió una imagen" + (f" ({bloqueo})" if bloqueo else "")))
    if len(imagen) > MAX_BYTES_RESPUESTA:
        raise GeminiFallo("La imagen que devolvió Gemini es demasiado grande")
    return imagen
