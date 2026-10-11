"""Validación de los enlaces que carga un comercio, un agente o el admin.

POR QUÉ EXISTE
==============

`sitio_web`, `facebook_url`, `instagram_url`, `tiktok_url`, `como_llegar`,
`canal_wa_url` y `catalogo_url` terminan en el `href` de la ficha pública. Un
`javascript:...` guardado ahí se ejecuta en el navegador de QUIEN LO TOCA, con
acceso al localStorage donde vive su token: es robo de sesión por el simple
hecho de mirar una ficha. Se frena al guardar, que es el único lugar donde
alcanza (el sitio lee la base con anon, sin pasar por el backend).

LA REGLA
========

- Con esquema (`algo:` al principio), sólo `http` o `https`, con dominio.
- Nunca usuario antes del dominio: `https://uruku.bo@evil.com` se lee como
  uruku.bo pero va a evil.com.
- Sin esquema se acepta: los agentes cargan «@mitienda» o «mitienda.com» y el
  sitio arma el enlace.
- Sin caracteres de control: los navegadores ignoran tabuladores y saltos de
  línea DENTRO del esquema, y `java\\tscript:` pasaría una revisión ingenua.
"""
import ipaddress
import re
from urllib.parse import urlsplit

MAX_ENLACE = 500

_ESQUEMA = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")
#: 2130706433, 0x7f.0.0.1, 017700000001…: formas de escribir una IP que
#: `ipaddress` no entiende pero el navegador sí.
_IP_RARA = re.compile(r"^(0x[0-9a-f]+|\d+)(\.(0x[0-9a-f]+|\d+))*$", re.IGNORECASE)

#: Los campos de redes y ubicación que aceptan un enlace o un usuario suelto.
CAMPOS_RED = {
    "sitio_web": "El sitio web",
    "facebook_url": "El enlace de Facebook",
    "instagram_url": "El enlace de Instagram",
    "tiktok_url": "El enlace de TikTok",
    "como_llegar": "El enlace de «Cómo llegar»",
}


def tiene_esquema(valor: str) -> bool:
    return bool(_ESQUEMA.match(valor))


def _sin_control(valor: str) -> bool:
    return not any(ord(c) < 32 or ord(c) == 127 for c in valor)


def _es_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return bool(_IP_RARA.match(host))


def validar_http(valor: str, etiqueta: str, *, estricto: bool = False) -> str:
    """`valor` ya sin espacios en los bordes y NO vacío. Devuelve el enlace o
    lanza ValueError con el mensaje en español.

    `estricto` es para los enlaces que se abren tal cual (canal, catálogo):
    además rechaza las IP escritas a mano (también en decimal o hexa).
    """
    malo = ValueError(f"{etiqueta} tiene que ser un enlace que empiece con http:// o https://.")
    if len(valor) > MAX_ENLACE or not _sin_control(valor) or any(c.isspace() for c in valor):
        raise malo
    try:
        partes = urlsplit(valor)
        host = partes.hostname
        partes.port  # noqa: B018 — un puerto inválido lanza ValueError acá
    except ValueError as exc:
        raise malo from exc
    if partes.scheme.lower() not in ("http", "https") or not partes.netloc or not host:
        raise malo
    if "@" in partes.netloc:
        # El usuario antes del dominio es el truco del enlace que parece otro.
        raise ValueError(f"{etiqueta} no puede llevar un usuario antes del dominio (nada de «usuario@»).")
    if estricto and _es_ip(host):
        raise ValueError(f"{etiqueta} tiene que ser un dominio, no una dirección IP.")
    return valor


def validar_red(valor: str | None, etiqueta: str) -> str | None:
    """Un campo de redes: sin esquema se acepta; con esquema, sólo http(s)."""
    if valor is None:
        return None
    limpio = str(valor).strip()
    if not limpio:
        return limpio
    if len(limpio) > MAX_ENLACE or not _sin_control(limpio):
        raise ValueError(f"{etiqueta} no es válido.")
    if tiene_esquema(limpio):
        return validar_http(limpio, etiqueta)
    return limpio


def sanear_red(valor: str | None, etiqueta: str = "El enlace") -> str | None:
    """Como `validar_red`, pero para datos que NO escribe una persona al guardar
    (una importación de un mapa abierto): lo que no pasa se descarta en vez de
    frenar todo el alta."""
    try:
        return validar_red(valor, etiqueta) or None
    except ValueError:
        return None


def validar_redes(patch: dict) -> None:
    """Valida in situ los campos de redes que vengan en `patch`. ValueError si
    alguno tiene un esquema peligroso o un usuario antes del dominio."""
    for campo, etiqueta in CAMPOS_RED.items():
        if campo in patch:
            patch[campo] = validar_red(patch[campo], etiqueta)
