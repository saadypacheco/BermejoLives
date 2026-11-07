"""La IP del cliente, para los límites de pedidos y de intentos fallidos.

Detrás de Traefik el pedido trae `X-Forwarded-For`. El PRIMER valor lo inventa el
cliente (manda el encabezado que quiera y Traefik le agrega su dirección al
final); el ÚLTIMO es el que agregó el proxy confiable, o sea la IP con la que
nos llegó de verdad. Sin el encabezado (desarrollo, tests) se usa la conexión.
"""
from __future__ import annotations

import ipaddress

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


def red_de_ip(ip: str | None) -> str:
    """La «red» de una IP, para los límites, los techos y el voto de «¿te contestó?»: IPv4 exacta, IPv6 agrupada por
    /56 (un hogar o una operadora reparte /56 o /64 a cada conexión: con /64 un atacante rota de a miles), IPv4 mapeada
    como IPv4. Si no parsea (cabecera rara, `testclient`), la clave fija `invalid`."""
    try:
        addr = ipaddress.ip_address((ip or "").strip())
    except ValueError:
        return "invalid"
    if addr.version == 6:
        if addr.ipv4_mapped is not None:
            return str(addr.ipv4_mapped)
        return str(ipaddress.IPv6Network(f"{addr}/56", strict=False).network_address)
    return str(addr)
