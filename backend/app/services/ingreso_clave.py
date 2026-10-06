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
"""
from __future__ import annotations

import structlog
from fastapi import HTTPException

from app.core import clave as claves

logger = structlog.get_logger()

_COMERCIO = "comercio_usuarios"
_USUARIO = "usuarios"


def abrir_intento(repo, tabla: str, numero: str, cuenta_ids: list[str], ip: str) -> dict:
    intento = repo.registrar_intento_clave(tabla, numero[:32], list(cuenta_ids), ip)
    if claves.bloqueado_por_ip(intento):
        repo.resolver_intento_clave(intento["id"], "bloqueado")
        logger.info("ingreso.bloqueado", motivo="ip", tabla=tabla, ip=ip)
        raise HTTPException(status_code=429, detail=claves.MENSAJE_BLOQUEADO)
    if claves.clave_ya_anulada(intento):
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


def cerrar_fallo(repo, tabla: str, intento: dict, cuenta_ids: list[str], ip: str) -> None:
    """La clave no coincidió (el intento ya quedó como 'fallo'). Siempre levanta
    el 401; si era el décimo en 24 horas, anula la clave de esas cuentas."""
    if claves.anula_la_clave(intento):
        if tabla == _COMERCIO:
            repo.anular_clave_comercio(list(cuenta_ids))
        else:
            for usuario_id in cuenta_ids:
                repo.anular_clave_usuario(usuario_id)
        logger.warning("ingreso.clave_anulada", tabla=tabla, cuentas=len(cuenta_ids), ip=ip)
        raise HTTPException(status_code=401, detail=claves.MENSAJE_ANULADA)
    raise HTTPException(status_code=401, detail=claves.MENSAJE_INCORRECTA)
