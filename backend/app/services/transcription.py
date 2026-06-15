"""Transcripción self-hosted con faster-whisper (sin API key, corre en el VPS).

El modelo se carga una vez (lru_cache) y se descarga la 1ª vez a HF_HOME
(volumen montado en producción para no re-bajarlo en cada build).
"""
from functools import lru_cache
from io import BytesIO

import structlog

from app.core.config import settings

logger = structlog.get_logger()


@lru_cache(maxsize=1)
def _model():
    from faster_whisper import WhisperModel

    logger.info("whisper.cargando", model=settings.whisper_model, device=settings.whisper_device)
    return WhisperModel(settings.whisper_model, device=settings.whisper_device, compute_type="int8")


def transcribir_local(data: bytes) -> str:
    """Transcribe el audio (bytes) a texto en español. Bloqueante (CPU)."""
    segments, _info = _model().transcribe(BytesIO(data), language="es", vad_filter=True)
    return " ".join(s.text.strip() for s in segments).strip()
