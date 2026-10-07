"""Lo que se vence, y los certificados que se miden en vivo.

La regla que separa las dos mitades: **si el sistema puede medirlo, no se
carga a mano.** Un dato cargado a mano que también se puede medir termina, algún
día, diciendo algo distinto de la realidad — y lo peor es que sigue diciéndolo
con confianza.

Por eso las fechas de dominios, VPS y chips viven en la tabla `vencimientos`
(nadie las puede averiguar desde acá) y las de los certificados TLS se preguntan
al servidor cada vez.
"""
from __future__ import annotations

import socket
import ssl
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import structlog

logger = structlog.get_logger()

# Bolivia está en UTC-4 todo el año (no tiene horario de verano).
#
# Comparar contra la fecha UTC parece inofensivo y no lo es: entre las 20:00 y
# la medianoche de Bermejo, en UTC ya es el día siguiente, y el panel diría que
# faltan 9 días cuando faltan 10. Peor: algo que vence hoy aparecería como
# vencido durante las últimas cuatro horas del día en que todavía se podía
# renovar.
#
# Las fechas las carga una persona parada en Bermejo pensando en el calendario
# de Bermejo. La cuenta tiene que hacerse en ese mismo calendario.
TZ_BOLIVIA = timezone(timedelta(hours=-4))


def hoy_local() -> "datetime.date":
    return datetime.now(TZ_BOLIVIA).date()

# Los dominios que sirven algo. Si uno deja de renovar, lo que se cae es lo que
# está entre paréntesis — por eso el nombre va junto y no sólo el host.
HOSTS_TLS = [
    ("uruku.bo", "el sitio"),
    ("api.uruku.bo", "el backend"),
    ("db.uruku.bo", "la base (PostgREST)"),
    ("tiles.uruku.bo", "el mapa"),
    ("waha.uruku.bo", "el panel de WhatsApp"),
]


def _dias_hasta(fecha: str | None) -> int | None:
    if not fecha:
        return None
    try:
        d = datetime.fromisoformat(str(fecha)[:10]).date()
    except ValueError:
        return None
    return (d - hoy_local()).days


def estado_de(dias: int | None, aviso: int) -> str:
    """`sin_fecha` NO es `ok`.

    Es la distinción que hace útil a este panel: una fila sin fecha no está
    tranquila, está sin vigilar. Mezclarla con las que están al día convierte el
    tablero en un semáforo que siempre da verde.
    """
    if dias is None:
        return "sin_fecha"
    if dias < 0:
        return "vencido"
    if dias <= 7:
        return "critico"
    if dias <= aviso:
        return "por_vencer"
    return "ok"


def con_estado(filas: list[dict]) -> list[dict]:
    salida = []
    for f in filas:
        dias = _dias_hasta(f.get("vence_el"))
        salida.append({**f, "dias": dias,
                       "estado": estado_de(dias, f.get("aviso_dias") or 30)})
    # Primero lo que arde; las sin fecha antes que las que están bien, porque
    # son trabajo pendiente y no calma.
    orden = {"vencido": 0, "critico": 1, "por_vencer": 2, "sin_fecha": 3, "ok": 4}
    salida.sort(key=lambda x: (orden.get(x["estado"], 9), x["dias"] if x["dias"] is not None else 9999))
    return salida


def vence_certificado(host: str, puerto: int = 443, timeout: float = 6.0) -> dict:
    """Cuándo vence el certificado TLS de un host. Nunca lanza.

    Los renueva Traefik solo, así que esto no es para renovarlos: es para
    enterarse cuando la renovación automática DEJÓ de funcionar. Ese fallo es
    silencioso por definición —todo anda hasta el día que vence— y el síntoma es
    el navegador diciendo que el sitio no es seguro, que es el peor momento para
    enterarse.
    """
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, puerto), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as tls:
                cert = tls.getpeercert()
        vence = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        # El certificado sí es un instante absoluto, no una fecha de
        # calendario: acá UTC es lo correcto.
        dias = (vence - datetime.now(timezone.utc)).days
        return {"host": host, "ok": True, "vence_el": vence.date().isoformat(), "dias": dias,
                # 30 días es el margen de Let's Encrypt: renueva a los 60 de 90.
                # Si quedan menos, la renovación automática no está funcionando.
                "estado": estado_de(dias, 30)}
    except ssl.SSLCertVerificationError as exc:
        # El certificado está, pero no se puede validar. Con uno VENCIDO
        # (verify_code 10) el saludo TLS falla justamente así, y como `sin_dato`
        # el tablero decía «al día» en el peor momento. Cualquier otra falla de
        # validación (el certificado por defecto de Traefik, otro nombre) es
        # igual de urgente: el visitante ve la pantalla roja del navegador.
        logger.warning("vencimientos.tls_invalido", host=host, codigo=exc.verify_code, error=str(exc)[:120])
        return {"host": host, "ok": False, "error": str(exc)[:120],
                "estado": "vencido" if exc.verify_code == 10 else "critico"}
    except Exception as exc:  # noqa: BLE001
        # No poder consultarlo NO es "está bien". Un host que no responde puede
        # ser un servicio caído, y eso también hay que verlo en el panel.
        logger.info("vencimientos.tls_fallo", host=host, error=str(exc))
        return {"host": host, "ok": False, "error": str(exc)[:120], "estado": "sin_dato"}


# ── El número del tablero ────────────────────────────────────────────────────
#: Los estados que cuentan como alerta (los mismos que suma /admin/vencimientos).
ESTADOS_ALERTA = {"vencido", "critico", "por_vencer"}

#: Cuánto se recuerda el resultado de medir los certificados. Cambian a lo sumo
#: una vez por día: medirlos en cada carga del tablero son cinco conexiones TLS
#: (con timeout) para enterarse siempre de lo mismo.
TTL_CERTIFICADOS_SEG = 600
_cache_certs: dict = {"hasta": 0.0, "alertas": 0}
_candado_certs = threading.Lock()
_medicion_certs = threading.Lock()


def limpiar_cache_certificados() -> None:
    with _candado_certs:
        _cache_certs.update(hasta=0.0, alertas=0)


def alertas_de_certificados(timeout: float = 3.0) -> int:
    """Cuántos certificados TLS están vencidos, críticos o por vencer. Nunca lanza.

    Las cinco consultas van en paralelo (peor caso: un `timeout`, no cinco) y el
    resultado se recuerda `TTL_CERTIFICADOS_SEG`. Un host que no responde es
    `sin_dato` y NO suma, igual que en /admin/vencimientos; uno que responde con
    un certificado que no valida (vencido, ajeno) SÍ suma."""
    with _candado_certs:
        if time.monotonic() < _cache_certs["hasta"]:
            return _cache_certs["alertas"]
    # Una sola medición a la vez: cuando vence el caché, los pedidos que llegan
    # juntos esperan a la que está en curso en vez de abrir cinco conexiones
    # TLS cada uno. El que entra después vuelve a mirar el caché.
    with _medicion_certs:
        with _candado_certs:
            if time.monotonic() < _cache_certs["hasta"]:
                return _cache_certs["alertas"]
        with ThreadPoolExecutor(max_workers=len(HOSTS_TLS)) as pool:
            certs = list(pool.map(lambda hq: vence_certificado(hq[0], timeout=timeout), HOSTS_TLS))
        n = sum(1 for c in certs if c.get("estado") in ESTADOS_ALERTA)
        with _candado_certs:
            _cache_certs.update(hasta=time.monotonic() + TTL_CERTIFICADOS_SEG, alertas=n)
        return n


def contar_alertas(filas: list[dict]) -> int:
    """Cuántas de las fechas cargadas a mano están vencidas, críticas o por vencer.
    Las `sin_fecha` NO cuentan (son trabajo pendiente, no urgencia)."""
    return sum(1 for i in con_estado(filas) if i["estado"] in ESTADOS_ALERTA)
