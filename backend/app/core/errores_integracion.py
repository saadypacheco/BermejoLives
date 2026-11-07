"""Error de la API de integración: `{ "error": { "code", "message", "details" } }`.

Es el formato del contrato (docs/integracion-marketing.md §Errores): un `code` estable que el cliente puede
comparar y un mensaje en español. Lo convierte a JSON el handler registrado en `main.py`.
"""
from __future__ import annotations


class IntegracionError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict | None = None,
                 headers: dict[str, str] | None = None):
        super().__init__(f"{status} {code}: {message}")
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}
        self.headers = headers or {}
