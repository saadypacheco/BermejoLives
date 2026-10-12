"""El ingreso con celular + clave, protegido contra la fuerza bruta.

Lo comparten `/auth/comercio/ingresar` y `/auth/usuario/ingresar`. El orden es:

  1. `abrir_intento`: registra el intento en la base ANTES de gastar PBKDF2 (una
     función SQL lo inserta y cuenta bajo lock, así que pedidos en paralelo se
     ven entre sí). Si el número o la IP ya están bloqueados, corta acá con 429
     (o 401 «clave anulada») sin verificar nada.
  2. El endpoint verifica la clave.
  3. `cerrar_ok` o `cerrar_fallo`. Un ingreso correcto NO borra fallos: sólo
     marca su propio intento como 'ok'. El décimo fallo en 24 horas anula la
     clave (`clave_hash = null`): sólo se vuelve a entrar por WhatsApp.

Se bloquea por NÚMERO, no por cuenta: un número con varios comercios comparte el
contador, y quien cuelga un comercio propio de un número ajeno no puede
resetearlo entrando con su clave.

Lo de «10 fallos en 24 horas anulan la clave» rige SÓLO para las claves viejas de 6
números del comercio (1 millón de combinaciones: 5 por cuarto de hora no alcanzan para
frenarlas). La clave nueva `PREFIJO-AZAR` (887 millones) ya queda cubierta por el bloqueo
de 5 fallos en 15 minutos, y anularla sería regalarle a cualquiera una forma de dejar sin
clave a un comerciante con 10 intentos. Una cuenta tiene clave vieja si guarda un hash con
`credenciales_version = 0`: toda clave que se genera desde la 0149 sube la versión. El
comprador (6 números siempre) conserva la anulación.
"""
from __future__ import annotations

import structlog
from fastapi import HTTPException

from app.core import clave as claves

logger = structlog.get_logger()

_COMERCIO = "comercio_usuarios"
_USUARIO = "usuarios"


def clave_vieja_de_6_numeros(cuenta: dict) -> bool:
    """¿Esta cuenta de comercio guarda una clave de 6 números (de antes de la 0149)?"""
    return bool(cuenta.get("clave_hash")) and int(cuenta.get("credenciales_version") or 0) == 0


def _se_anula_por_10_fallos(tabla: str, cuentas: list[dict] | None) -> bool:
    """El comprador siempre. El comercio, sólo si alguna cuenta del número tiene la clave
    vieja de 6 números o ya no tiene clave (anulada: seguir diciéndolo no daña a nadie y
    es lo que le explica al dueño por qué no entra). Un número sin cuentas se comporta
    como uno con clave nueva (lo normal de ahora en más): lo que se ve desde afuera es lo
    mismo que con una cuenta de clave nueva."""
    if tabla != _COMERCIO:
        return True
    return any(clave_vieja_de_6_numeros(c) or not c.get("clave_hash") for c in cuentas or [])


def abrir_intento(repo, tabla: str, numero: str, cuenta_ids: list[str], ip: str,
                  cuentas: list[dict] | None = None) -> dict:
    intento = repo.registrar_intento_clave(tabla, numero[:32], list(cuenta_ids), ip)
    if claves.bloqueado_por_ip(intento):
        repo.resolver_intento_clave(intento["id"], "bloqueado")
        logger.info("ingreso.bloqueado", motivo="ip", tabla=tabla, ip=ip)
        raise HTTPException(status_code=429, detail=claves.MENSAJE_BLOQUEADO)
    if claves.clave_ya_anulada(intento) and _se_anula_por_10_fallos(tabla, cuentas):
        repo.resolver_intento_clave(intento["id"], "bloqueado")
        logger.info("ingreso.bloqueado", motivo="clave_anulada", tabla=tabla, ip=ip)
        raise HTTPException(status_code=401, detail=claves.MENSAJE_ANULADA)
    if claves.bloqueado_15m(intento):
        repo.resolver_intento_clave(intento["id"], "bloqueado")
        logger.info("ingreso.bloqueado", motivo="15_minutos", tabla=tabla, ip=ip)
        raise HTTPException(status_code=429, detail=claves.MENSAJE_BLOQUEADO)
    return intento


def cerrar_ok(repo, intento: dict) -> None:
    """El ingreso fue correcto: este intento no cuenta. Los fallos de antes siguen."""
    repo.resolver_intento_clave(intento["id"], "ok")


def cerrar_fallo(repo, tabla: str, intento: dict, cuenta_ids: list[str], ip: str,
                 cuentas: list[dict] | None = None) -> None:
    """La clave no coincidió (el intento ya quedó como 'fallo'). Siempre levanta
    el 401; si era el décimo en 24 horas y la clave es de 6 números, la anula.
    `cuentas`: las filas de esas cuentas (para saber de qué clase es la clave)."""
    if claves.anula_la_clave(intento) and _se_anula_por_10_fallos(tabla, cuentas):
        if tabla == _COMERCIO:
            repo.anular_clave_comercio([c["id"] for c in cuentas or [] if clave_vieja_de_6_numeros(c)])
        else:
            for usuario_id in cuenta_ids:
                repo.anular_clave_usuario(usuario_id)
        logger.warning("ingreso.clave_anulada", tabla=tabla, cuentas=len(cuenta_ids), ip=ip)
        raise HTTPException(status_code=401, detail=claves.MENSAJE_ANULADA)
    raise HTTPException(status_code=401, detail=claves.MENSAJE_INCORRECTA)
