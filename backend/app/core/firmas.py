"""Firmas HMAC para tokens públicos de corta vida (sin guardar nada en la base).

Cada tipo de token tiene su PROPIA clave (`LEAD_TOKEN_SECRET`, `RECUPERAR_TOKEN_SECRET`): no es la del
JWT, así que una filtración de una no permite fabricar las otras. Si la clave de config está vacía se
deriva de `JWT_SECRET` con una etiqueta distinta por tipo (el despliegue sigue andando sin tocar el
`.env`; en producción conviene fijarlas).

Se firma un texto armado con partes separadas por «|». Las partes NO pueden llevar «|» (los ids y los
códigos que se firman acá nunca lo llevan; se rechaza igual por las dudas).
"""
from __future__ import annotations

import hashlib
import hmac

from app.core.config import settings


def _clave(etiqueta: str, explicita: str) -> bytes:
    if (explicita or "").strip():
        return explicita.strip().encode()
    # Derivada: HMAC(JWT_SECRET, "uruku-firma:<etiqueta>"). Etiquetas distintas, claves distintas.
    return hmac.new((settings.jwt_secret or "").encode(), f"uruku-firma:{etiqueta}".encode(),
                    hashlib.sha256).digest()


def firmar(etiqueta: str, explicita: str, *partes: str) -> str:
    """HMAC-SHA256 en hexadecimal (64 caracteres) de las partes, con la clave de `etiqueta`."""
    for p in partes:
        if "|" in str(p):
            raise ValueError("una parte firmada no puede llevar «|»")
    texto = "|".join(str(p) for p in partes)
    return hmac.new(_clave(etiqueta, explicita), texto.encode(), hashlib.sha256).hexdigest()


def coincide(token: str | None, esperado: str) -> bool:
    """Comparación en tiempo constante. Un token vacío o de otro largo no coincide."""
    return bool(token) and hmac.compare_digest(str(token).strip().lower(), esperado)


# ── Lo que firma cada tipo ──────────────────────────────────────────────────────────────────────
def token_de_lead(lead_id: str, sesion: str | None) -> str:
    """El token que el cliente recibe al crear un contacto y reenvía al votar «¿te contestó?»:
    ata el id del contacto a la sesión que lo creó."""
    return firmar("lead", settings.lead_token_secret, "lead", str(lead_id), (sesion or "").strip())


def votante_de(ip: str, sesion: str | None = None) -> str:
    """Quién vota, sin guardar la IP: un hash con la clave de los leads, derivado SÓLO de la red de la IP (IPv4
    exacta, IPv6 /56). La sesión NO entra: es un número que el cliente inventa, y con ella una sola IP con cinco
    sesiones eran cinco «votantes distintos» (y bastaban tres para encender el sello «no responde»). Así, votantes
    distintos = redes distintas. `sesion` se acepta por compatibilidad y se ignora."""
    from app.core.ip import red_de_ip

    return firmar("lead", settings.lead_token_secret, "votante-red", red_de_ip(ip))[:32]


def _segundos(expira) -> str:
    """El vencimiento como segundos enteros: la base devuelve el timestamp con otro formato que el que
    se le mandó («+00:00» con microsegundos, o «Z»); en segundos es el mismo en los dos lados."""
    from datetime import datetime

    try:
        cuando = expira if isinstance(expira, datetime) else datetime.fromisoformat(str(expira).replace("Z", "+00:00"))
        return str(int(cuando.timestamp()))
    except (TypeError, ValueError):
        return ""


def token_de_recuperacion(cuenta_id: str, codigo: str, expira) -> str:
    """El token de una solicitud de «recuperar cuenta»: lo recibe SÓLO quien pidió el código (128 bits).
    Cambia con cada código nuevo (el código y su vencimiento entran en la firma), así que uno viejo no
    sirve. No se guarda en la base: se recalcula con la clave `RECUPERAR_TOKEN_SECRET`."""
    return firmar("recuperar", settings.recuperar_token_secret,
                  "recuperar", str(cuenta_id), str(codigo), _segundos(expira))[:32]
