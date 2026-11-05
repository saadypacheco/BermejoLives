"""Cómo se le habla a Gemini sin filtrar la clave.

La clave va en la cabecera `x-goog-api-key`, NUNCA en la URL (`?key=`): httpx pone la URL
completa en el texto de sus errores, y de ahí pasa a los registros, al panel del admin y a
las capturas de pantalla. Todo el código que llama al modelo usa `url_generar()` y
`cabeceras()`, y todo texto de error que se muestre o se registre pasa por `sin_secretos()`.
"""
import re

from app.core.config import settings


def url_generar() -> str:
    """URL de `generateContent` del modelo configurado. No lleva la clave."""
    return (f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{settings.gemini_model}:generateContent")


def cabeceras() -> dict[str, str]:
    """Cabeceras de autenticación para Gemini."""
    return {"x-goog-api-key": settings.gemini_api_key}


def sin_secretos(texto: str) -> str:
    """Saca la API key de cualquier texto que vaya a mostrarse o registrarse.

    Cubre la clave pegada en una URL (`?key=...`, de versiones viejas o de un mensaje de
    error que la traiga), la cabecera `x-goog-api-key` y la clave literal."""
    if not texto:
        return texto
    limpio = re.sub(r"([?&]key=)[^&\s\"']+", r"\g<1><oculta>", texto)
    limpio = re.sub(r"(?i)(x-goog-api-key['\"]?\s*[:=]\s*['\"]?)[^\s,'\"}]+", r"\g<1><oculta>", limpio)
    if settings.gemini_api_key:
        limpio = limpio.replace(settings.gemini_api_key, "<oculta>")
    return limpio
