"""La clave de Mi comercio mandada por WhatsApp.

Un comerciante que ve una clave nueva y la manda "para probar" por el chat o por el
grupo la deja escrita en la bandeja (`wa_inbox`), en los logs del bridge y en el
teléfono de todos los que están en el grupo. Una clave que se vio así ya no es
secreta.

Qué hace la ingesta (`services/ingest.handle_message`), ANTES de guardar nada:

  1. Busca en el texto algo con forma de clave (`RE_FORMA_DE_CLAVE`: prefijo + 6 del
     azar, o 6 números de la clave vieja).
  2. Si el número que escribe tiene cuentas de comercio con clave, compara cada
     candidato contra sus hashes (PBKDF2: por eso se acota cuántos se prueban).
  3. Si coincide: NO se publica nada, el mensaje se guarda en `wa_inbox` con la clave
     tapada (`[clave]`) tanto en `body` como en el crudo, la clave se anula (sube
     `credenciales_version`: también se cierran las sesiones abiertas con ella), queda
     un evento en `comercio_eventos` y el motivo se ve en la bandeja del admin.

La clave nunca va a un log: ni la del mensaje ni su hash.
"""
from __future__ import annotations

import re
from typing import Any

import structlog

from app.core import clave_comercio
from app.services.cuentas import cuentas_de_numero

logger = structlog.get_logger()

MOTIVO = "El comerciante mandó su clave por WhatsApp: se anuló"
TAPADO = "[clave]"
#: Cuántos candidatos se prueban por mensaje. Cada comparación es un PBKDF2 (~50 ms) por
#: cuenta: un mensaje cualquiera tiene palabras que "tienen forma" de clave.
MAX_CANDIDATOS = 5

# Todos los candidatos, también los que se pisan: «precio BOUTIQUE-K7M2P9» tiene uno que
# empieza en «precio» y otro en «BOUTIQUE», y un `finditer` común se quedaría con el primero.
# Es la forma de clave de `RE_FORMA_DE_CLAVE`, con hasta 3 separadores entre el prefijo y el
# azar: quien la copia a mano escribe «Boutique - K7M2P9» y eso también es la clave.
_RE_FORMA_SOLAPADA = re.compile(
    r"(?=(\b[A-Z0-9]{1,8}[\s\-_‐-―−]{0,3}[2-9A-HJKMNP-Z]{6}\b))", re.IGNORECASE)
# La clave vieja del comercio: 6 números sueltos.
_RE_SEIS_NUMEROS = re.compile(r"(?<![0-9])[0-9]{6}(?![0-9])")


def candidatos(texto: str | None) -> list[str]:
    """Los tramos del texto que podrían ser una clave, tal como están escritos, los más
    parecidos a una clave primero (con dígitos y con guion), sin repetir y acotados."""
    if not texto:
        return []
    crudos = [m.group(1) for m in _RE_FORMA_SOLAPADA.finditer(texto)]
    crudos += _RE_SEIS_NUMEROS.findall(texto)
    vistos: dict[str, str] = {}
    for crudo in crudos:
        norm = clave_comercio.normalizar(crudo)
        if clave_comercio.es_clave(norm) and norm not in vistos:
            vistos[norm] = crudo

    def parecido(item: tuple[str, str]) -> tuple[int, int, int]:
        norm, crudo = item
        # Más probable primero: con separador, con dígitos en el azar, más largo.
        return (-int(bool(re.search(r"[\s\-_]", crudo))), -int(any(c.isdigit() for c in norm[-6:])), -len(norm))

    ordenados = sorted(vistos.items(), key=parecido)
    return [crudo for _norm, crudo in ordenados][:MAX_CANDIDATOS]


def enmascarar(valor: Any, secretos: list[str]) -> Any:
    """Copia de `valor` (texto, lista o dict, a cualquier profundidad) con cada secreto
    reemplazado por `[clave]`, sin distinguir mayúsculas."""
    if not secretos:
        return valor
    patrones = [re.compile(re.escape(s), re.IGNORECASE) for s in sorted(set(secretos), key=len, reverse=True)]

    def tapar(x: Any) -> Any:
        if isinstance(x, str):
            for patron in patrones:
                x = patron.sub(TAPADO, x)
            return x
        if isinstance(x, list):
            return [tapar(i) for i in x]
        if isinstance(x, dict):
            return {k: tapar(v) for k, v in x.items()}
        return x

    return tapar(valor)


def detectar(repo, numero: str | None, texto: str | None) -> dict | None:
    """¿Ese texto trae la clave de alguna cuenta del número que lo escribió?

    Devuelve `{"cuentas": [cuenta, ...], "secretos": [tramo, ...]}` (las cuentas cuya
    clave coincidió y los tramos del texto que la contenían) o None."""
    cands = candidatos(texto)
    if not cands:
        return None
    cuentas = [c for c in cuentas_de_numero(repo, numero) if c.get("clave_hash")]
    if not cuentas:
        return None
    coinciden: list[dict] = []
    secretos: list[str] = []
    for crudo in cands:
        for cuenta in cuentas:
            if clave_comercio.clave_coincide(crudo, cuenta["clave_hash"]):
                if cuenta not in coinciden:
                    coinciden.append(cuenta)
                if crudo not in secretos:
                    secretos.append(crudo)
    if not coinciden:
        return None
    return {"cuentas": coinciden, "secretos": secretos}


def anular(repo, cuentas: list[dict]) -> None:
    """Anula la clave de esas cuentas (y cierra sus sesiones) y deja el evento. Si no
    puede anular, lanza: seguir con la clave a la vista sería peor que fallar."""
    repo.anular_clave_comercio([c["id"] for c in cuentas])
    for cuenta in cuentas:
        try:
            repo.registrar_evento_comercio(cuenta["comercio_id"], "clave_anulada_por_whatsapp", "sistema")
        except Exception:  # noqa: BLE001 - la clave ya está anulada: lo importante está hecho
            logger.error("clave_filtrada.evento_fallo", comercio_id=cuenta["comercio_id"], exc_info=True)
