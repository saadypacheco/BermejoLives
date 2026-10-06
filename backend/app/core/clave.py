"""La clave secreta de 6 números (comerciante y comprador).

Se entra con celular + clave. El código `URUKU-XXXX` del comercio NO sirve de
clave: está impreso en el volante y se manda en el grupo. El mensaje de
WhatsApp (CONFIRMAR) queda para la primera vez y para «me olvidé la clave».

Reglas:
  - 6 dígitos al azar con `secrets` (nunca `random`).
  - Se guarda sólo el hash, el mismo que las contraseñas (`auth.hash_password`).
  - La clave NUNCA va a un log, a un evento de structlog ni a un WhatsApp: viaja
    una sola vez, en la respuesta HTTP que la genera.
  - Cada intento se registra en `clave_fallos` ANTES de verificar la clave (una
    función SQL lo inserta y cuenta bajo lock: atómico). El bloqueo se calcula,
    no se guarda: 5 fallos en 15 minutos bloquean; 10 en 24 horas anulan la
    clave; 20 por IP en una hora bloquean esa IP. Un ingreso correcto NO borra
    fallos: sólo una clave nueva obtenida por WhatsApp los deja obsoletos.
"""
from __future__ import annotations

import re
import secrets
import threading
import time
from collections import deque

from app.core import auth

LARGO = 6
MAX_FALLOS_15M = 5          # 5 fallos en 15 minutos bloquean el número
MAX_FALLOS_24H = 10         # 10 fallos en 24 horas anulan la clave
MAX_FALLOS_IP_1H = 20       # 20 fallos por IP en una hora bloquean esa IP

MENSAJE_INCORRECTA = "Celular o clave incorrectos"
MENSAJE_BLOQUEADO = "Demasiados intentos. Probá de nuevo en 15 minutos."
MENSAJE_ANULADA = "Por seguridad tu clave se anuló. Entrá con tu WhatsApp para recibir una nueva."

_RE_CLAVE = re.compile(r"^\d{6}$")


def generar_clave() -> str:
    """6 números al azar (con ceros a la izquierda: «004217» es válida)."""
    return f"{secrets.randbelow(10 ** LARGO):0{LARGO}d}"


def es_clave(valor: str | None) -> bool:
    return bool(valor) and bool(_RE_CLAVE.match(valor.strip()))


def hash_clave(clave: str) -> str:
    return auth.hash_password(clave.strip())


def clave_coincide(clave: str | None, hash_guardado: str | None) -> bool:
    """¿Esta clave es la que dejó ese hash? Falso si no hay hash o la clave no
    tiene la forma de una clave (así no se gasta PBKDF2 en basura)."""
    if not hash_guardado or not es_clave(clave):
        return False
    return auth.verify_password(clave.strip(), hash_guardado)


# Un hash cualquiera para gastar el mismo tiempo cuando no hay cuenta: si el
# ingreso con un número que no existe contestara al instante y el de uno que
# existe tardara los ~50 ms de PBKDF2, el tiempo delataría qué números tienen
# cuenta. Es el hash de una clave descartada, no protege nada.
_HASH_DE_RELLENO = auth.hash_password("000000", salt="00" * 16)


def gastar_tiempo(clave: str | None) -> None:
    auth.verify_password((clave or "").strip(), _HASH_DE_RELLENO)


def clave_distinta_de(hashes: list[str | None]) -> str:
    """Una clave nueva que NO coincide con ninguno de esos hashes.

    Es lo que permite que, en un número con varios comercios, la clave
    identifique cuál: al generarla se descartan las que ya usa otro comercio
    del mismo número (se verifica contra los hashes de esas cuentas)."""
    otros = [h for h in hashes if h]
    for _ in range(50):
        nueva = generar_clave()
        if not any(auth.verify_password(nueva, h) for h in otros):
            return nueva
    raise RuntimeError("no se pudo generar una clave distinta")  # prácticamente imposible


# ─────────────────────────────────────────────── intentos y bloqueo
# El conteo lo hace la base (`registrar_intento_clave`, 0137): devuelve cuántos
# fallos hay CONTANDO el intento que se acaba de registrar. «Antes de éste» es
# un fallo menos.
def _previos(intento: dict, clave: str) -> int:
    return max(int(intento.get(clave) or 0) - 1, 0)


def bloqueado_por_ip(intento: dict) -> bool:
    return _previos(intento, "fallos_ip_1h") >= MAX_FALLOS_IP_1H


def clave_ya_anulada(intento: dict) -> bool:
    return _previos(intento, "fallos_24h") >= MAX_FALLOS_24H


def bloqueado_15m(intento: dict) -> bool:
    return _previos(intento, "fallos_15m") >= MAX_FALLOS_15M


def anula_la_clave(intento: dict) -> bool:
    """Este fallo es el décimo en 24 horas: la clave se anula."""
    return int(intento.get("fallos_24h") or 0) >= MAX_FALLOS_24H


class VentanaPorClave:
    """Tope de N eventos por ventana para una clave (p. ej. un comercio), en
    memoria: sirve para frenar abusos baratos (pedir claves nuevas sin parar),
    no es un control de fuerza bruta. Con tope de claves para no crecer sin
    límite."""

    def __init__(self, maximo: int, ventana_seg: int, tope_claves: int = 10_000) -> None:
        self.maximo, self.ventana, self.tope = maximo, ventana_seg, tope_claves
        self._d: dict[str, deque] = {}
        self._lock = threading.Lock()

    def permitir(self, clave: str) -> bool:
        """Registra un evento y dice si entra en el tope."""
        ahora = time.time()
        with self._lock:
            dq = self._d.setdefault(clave, deque())
            while dq and ahora - dq[0] > self.ventana:
                dq.popleft()
            if len(dq) >= self.maximo:
                return False
            dq.append(ahora)
            if len(self._d) > self.tope:                       # limpia las ventanas vacías
                for k in [k for k, v in self._d.items() if not v or ahora - v[-1] > self.ventana]:
                    del self._d[k]
            return True

    def limpiar(self) -> None:
        with self._lock:
            self._d.clear()


# POST /comercio/clave: máximo 3 por hora por comercio.
pedidos_de_clave = VentanaPorClave(maximo=3, ventana_seg=3600)
