"""La IP del cliente, para los límites de pedidos y de intentos fallidos.

Detrás de Traefik el pedido trae `X-Forwarded-For`. El PRIMER valor lo inventa el
cliente (manda el encabezado que quiera y Traefik le agrega su dirección al
final); el ÚLTIMO es el que agregó el proxy confiable, o sea la IP con la que
nos llegó de verdad. Sin el encabezado (desarrollo, tests) se usa la conexión.
"""
from __future__ import annotations

from fastapi import Request

_MAX_LARGO = 64


def ip_cliente(request: Request) -> str:
    partes: list[str] = []
    for linea in request.headers.getlist("x-forwarded-for"):
        partes.extend(p.strip() for p in linea.split(","))
    ultimo = next((p for p in reversed(partes) if p), "")
    if ultimo:
        return ultimo[:_MAX_LARGO]
    return request.client.host if request.client else "?"
