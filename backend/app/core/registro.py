"""Configuración de structlog: los tracebacks NO llevan variables locales.

El renderizador por defecto de structlog (`ConsoleRenderer`) usa, si `rich` está
instalado, un traceback con `show_locals=True`: junto a cada frame imprime los valores
de las variables locales. En una excepción dentro del ingreso o de la generación de una
clave eso es la clave (o su hash, o un token) escrita en el log. Acá se arma la misma
configuración de siempre pero con el traceback plano (`plain_traceback`: archivo, línea
y código, sin valores).

Se llama una vez al importar `app.main`. Es idempotente.
"""
from __future__ import annotations

import os
import sys

import structlog


def _con_colores() -> bool:
    """Como el renderizador por defecto de structlog: color sólo en una terminal."""
    if "NO_COLOR" in os.environ:
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return bool(sys.stdout is not None and hasattr(sys.stdout, "isatty") and sys.stdout.isatty())


def configurar_logging() -> None:
    """Los mismos procesadores que trae structlog por defecto, con el traceback plano."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
            structlog.dev.ConsoleRenderer(colors=_con_colores(), exception_formatter=structlog.dev.plain_traceback),
        ],
    )
