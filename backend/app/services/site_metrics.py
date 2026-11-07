"""Medición propia del sitio: páginas vistas, eventos y contactos (docs/estadisticas-v2.md §4.2).

QUÉ GUARDA Y QUÉ NO
===================
Filas crudas SIN datos personales en `visitas`, `site_events` y `leads` (con `sesion`: un número al azar
que vive en la pestaña del navegador). Nunca una IP, un User-Agent, una cookie ni una URL con query. La IP
se usa sólo para los límites y los techos, en memoria, y como hash con una sal que cambia cada día (no se
guarda ni se loguea).

ASUME UN SOLO WORKER DE UVICORN
===============================
Los límites de pedidos, la deduplicación y el buffer viven en la memoria de ESTE proceso. Con más de un
worker cada uno contaría por su cuenta (se contaría de más y los límites valdrían N veces). Si algún día
se suben los workers, la deduplicación tiene que pasar a Postgres (AGENTS.md §7).

REGLAS (spec §4.2)
==================
- `POST /collect` contesta SIEMPRE 204 (también si descarta); 413 si el cuerpo pasa de 2 KB; 429 si la IP
  pasa el límite. Nunca 500: un error se loguea y se contesta 204.
- Se descarta sin decir por qué: User-Agent vacío o de bot, `Origin` que no es del sitio, `Sec-Fetch-Site:
  cross-site`, ruta interna, evento o `detail` fuera del catálogo, sesión mal formada.
- Los topes de memoria no se pueden apagar llenándolos: los límites por minuto, si se llenan, procesan el pedido
  sin anotar la clave («se cuenta de más»); la deduplicación y los techos por IP sacan lo MÁS VIEJO (LRU) para
  hacer lugar. Sólo el buffer descarta cuando se llena.
- `comercio_id` tiene que ser un comercio ACTIVO (se compara con un conjunto en memoria que se refresca cada ~5
  min) y `busqueda_id` uno que emitió este backend: la tabla `leads` tiene claves foráneas, y un solo id inventado
  haría fallar el insert en lote de las otras 499 filas.
- Las páginas vistas y los eventos van a un buffer que se vuelca en lote cada 5 s (y al apagar). Los
  contactos que devuelven `id` (whatsapp, telefono, reserva, mapa, email, web) se insertan síncronos.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import logging
import re
import secrets
import threading
import time
import uuid
from collections import Counter, OrderedDict
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from typing import Any
from urllib.parse import urlsplit

import structlog

from app.core.ai_sources import classify_ai_source, summarize_ai_groups
from app.core.config import settings
from app.core.ip import red_de_ip
from app.core.text import enmascarar_texto, limpiar_ref

logger = structlog.get_logger()

# ── constantes ─────────────────────────────────────────────────────────────────────────────────
MAX_BODY_BYTES = 2048
MAX_BODY_CSP = 8192
MAX_CLAVES_LIMITE = 50_000          # claves de IP por ventana; lleno → se procesa el pedido y no se guarda la clave
MAX_DEDUP = 200_000                 # entradas de deduplicación y de techos; lleno → sale la más vieja (LRU)
MAX_BUSQUEDAS_EMITIDAS = 50_000     # ids de búsqueda que emitió este backend (los que /lead acepta como `busqueda_id`)
TTL_BUSQUEDA_S = 6 * 3600           # un contacto puede atarse a una búsqueda de hasta 6 horas atrás
REFRESCO_COMERCIOS_S = 5 * 60       # cada cuánto se recarga el conjunto de comercios activos
RECARGA_MINIMA_S = 60               # un comercio desconocido fuerza una recarga, pero a lo sumo una por minuto
REINTENTO_COMERCIOS_S = 10          # si la carga falla, no se vuelve a intentar antes de esto
MAX_INTENTOS_AISLAR = 64            # pedidos de más a la base al aislar filas malas de un lote que falló
MAX_CLAVES_CSP = 200                # (directiva, host) distintos por minuto en el log de CSP; el resto es «otro»
PERIODO_LOG_CSP_S = 60
MAX_BUFFER = 20_000                 # filas pendientes de volcar; llenas → se descartan y se avisa
LOTE_INSERT = 500                   # filas por pedido a PostgREST al volcar
VENTANA_VISTA_S = 30 * 60           # una vista de ficha por (sesión, comercio) cada 30 minutos
RETENCION_MESES = 13
HORA_PURGA_BOLIVIA = 4              # la purga corre a las 04:00 de Bolivia

#: Pedidos por minuto y por IP (una IP pública del CGNAT de una operadora junta a mucha gente).
LIMITES_POR_MINUTO = {"collect": 300, "lead": 120, "busqueda": 60, "csp": 30}

TECHO_VISTA_IP_DIA = 30             # vistas de ficha por IP y por comercio y por día
TECHO_CONTACTO_IP_DIA = 10          # de cada tipo de contacto, por IP y por comercio y por día
TECHO_COMERCIOS_IP_DIA = 200        # comercios DISTINTOS que una misma IP puede tocar por día (el techo por comercio no alcanza
                                    # si el atacante reparte sus pedidos entre miles de comercios)

#: Rutas que NO se cuentan: el panel, la carga de campo y el editor del comercio son trabajo, no visitas.
#: El frontend tiene la misma lista (lib/medicion.ts): si se cambia una, se cambia la otra.
RUTAS_INTERNAS = ("/admin", "/contenido", "/publicar", "/campo", "/mi-comercio", "/api/")

TIPOS_LEAD = frozenset({"whatsapp", "telefono", "email", "web", "vista", "mapa", "reserva", "compartir", "red"})
#: Se insertan síncronos y devuelven `id` (el «¿te contestó?» lo necesita).
TIPOS_SINCRONOS = frozenset({"whatsapp", "telefono", "reserva", "mapa", "email", "web"})
#: Van al buffer (no devuelven id).
TIPOS_EN_LOTE = frozenset({"vista", "compartir", "red"})
#: Tipos de `leads` que NO son un contacto con el comercio (los usa el tablero y «Mi comercio»).
TIPOS_NO_CONTACTO = ("vista", "compartir", "red")
#: Los que cuentan para el embudo («escribió o llamó»).
TIPOS_CONTACTO_EMBUDO = ("whatsapp", "telefono", "reserva")

REDES = frozenset({"instagram", "facebook", "tiktok", "youtube"})
#: Las clases de `?ref=` que corresponden a un QR que imprimimos nosotros (migración 0114: `volante-<slug>`, `mesa-<slug>`,
#: `ficha-<slug>`). En «Mi comercio» un `?ref=` que no es de esta lista NO se muestra como QR (lo manda cualquiera).
CLASES_QR = frozenset({"volante", "mesa", "ficha"})
#: En «Mi comercio», un host de referido desconocido (spam de referrer) sólo se nombra si lo trajeron al menos tantas
#: sesiones distintas; el resto se junta en «Otros».
MIN_SESIONES_HOST_OTRO = 3
CANALES_COMPARTIR = frozenset({"native", "copy"})

#: Catálogo cerrado de eventos del sitio (spec §4.5): evento -> conjunto de `detail` válidos, o "uuid".
EVENTOS: dict[str, Any] = {
    "share": CANALES_COMPARTIR,
    "pwa_install": frozenset({"shown", "accepted", "dismissed", "installed", "ios_hint"}),
    "video_play": "uuid",
    "video_network_click": REDES,
    "uruku_whatsapp_click": frozenset({"canal", "comunidad", "contacto"}),
}

DISPOSITIVOS = frozenset({"mobile", "tablet", "desktop"})

# ── bots ───────────────────────────────────────────────────────────────────────────────────────
#: Lista corta de User-Agent de bots y clientes automáticos. NO incluye los navegadores dentro de las apps
#: (FBAV de Facebook, Instagram, TikTok): son personas. Un UA vacío cuenta como bot.
_BOT_RE = re.compile(
    r"bot|crawl|spider|slurp|facebookexternalhit|facebot|headless|lighthouse|pingdom|uptime|monitor|"
    r"preview|curl|wget|python-requests|python-httpx|aiohttp|go-http-client|java/|libwww|scrapy|"
    r"httpclient|node-fetch|axios|inspectiontool|ptst|gtmetrix",
    re.IGNORECASE)


def es_bot(user_agent: str | None) -> bool:
    """Sin User-Agent o con uno de la lista corta de bots. El UA nunca se guarda."""
    if not user_agent or not user_agent.strip():
        return True
    return _BOT_RE.search(user_agent) is not None


# ── origen del pedido ──────────────────────────────────────────────────────────────────────────
def normalizar_origen(url: str | None) -> str | None:
    """`scheme://host[:port]` en minúsculas y sin el puerto por defecto; None si no es una URL http(s) con host."""
    if not url:
        return None
    try:
        partes = urlsplit(url.strip())
        puerto = partes.port
    except ValueError:
        return None
    host = partes.hostname
    if partes.scheme not in ("http", "https") or not host:
        return None
    por_defecto = 443 if partes.scheme == "https" else 80
    return f"{partes.scheme}://{host}" + (f":{puerto}" if puerto and puerto != por_defecto else "")


@lru_cache(maxsize=8)
def _origenes_de(frontend_url: str, entorno: str) -> frozenset[str] | None:
    if (entorno or "").strip().lower() == "development":
        return None                              # en desarrollo vale cualquiera (igual que el CORS de main.py)
    salida: set[str] = set()
    for fe in (frontend_url or "").split(","):
        fe = fe.strip().rstrip("/")
        if not fe:
            continue
        for variante in (fe, fe.replace("https://www.", "https://") if "www." in fe else fe.replace("https://", "https://www.")):
            o = normalizar_origen(variante)
            if o:
                salida.add(o)
    return frozenset(salida)


def origenes_del_sitio() -> frozenset[str] | None:
    """Los orígenes del sitio (FRONTEND_URL, con y sin www). None = sin restricción (desarrollo)."""
    return _origenes_de(settings.frontend_url, settings.environment)


def hosts_propios() -> frozenset[str]:
    """Los hosts del sitio (sin www.): un referido con uno de ellos es navegación interna = directo."""
    hosts = set()
    for fe in (settings.frontend_url or "").split(","):
        h = urlsplit(fe.strip()).hostname
        if h:
            hosts.add(h.removeprefix("www."))
    return frozenset(hosts)


def origen_permitido(origin: str | None, sec_fetch_site: str | None) -> bool:
    """El pedido legítimo viene del propio sitio. Con `Sec-Fetch-Site: cross-site`, o con un `Origin` que no es
    del sitio, se descarta. Sin `Origin` (clientes viejos, tests) se acepta: los bots los filtra el User-Agent."""
    if sec_fetch_site and sec_fetch_site.strip().lower() == "cross-site":
        return False
    permitidos = origenes_del_sitio()
    if permitidos is None or origin is None:
        return True
    return normalizar_origen(origin) in permitidos


def pedido_permitido(user_agent: str | None, origin: str | None, sec_fetch_site: str | None) -> bool:
    """Ni bot ni de otro sitio. Es lo que filtra /collect, /visita, /lead y /busquedas/log."""
    return not es_bot(user_agent) and origen_permitido(origin, sec_fetch_site)


def pedido_de_request(request) -> bool:
    """`pedido_permitido` con las cabeceras de un `Request` de FastAPI."""
    h = request.headers
    return pedido_permitido(h.get("user-agent"), h.get("origin"), h.get("sec-fetch-site"))


# ── IP y límites ───────────────────────────────────────────────────────────────────────────────
def clave_de_ip(ip: str | None) -> str:
    """La red de la IP (core/ip.py): IPv4 tal cual, IPv6 agrupada por /56, IPv4 mapeada como IPv4. Si no parsea
    (header raro, `testclient`), la clave fija `invalid`."""
    return red_de_ip(ip)


def _reloj() -> float:
    """El reloj monotónico de los límites y la deduplicación (los tests lo congelan para no cruzar una ventana)."""
    return time.monotonic()


class VentanaFija:
    """Límite por clave con VENTANA FIJA por minuto y memoria acotada: el dict se vacía al cambiar la ventana y
    tiene tope de claves. O(1) por pedido. `check` devuelve OK, LIMITED (429) o FULL (el dict está lleno: la clave
    no se guarda y quien llama PROCESA el pedido igual: medir de más es mejor que no medir)."""

    OK, LIMITED, FULL = "ok", "limited", "full"

    def __init__(self, limite: int, ventana_s: float = 60.0, max_claves: int = MAX_CLAVES_LIMITE):
        self.limite, self.ventana_s, self.max_claves = limite, ventana_s, max_claves
        self._ventana = -1
        self._cuentas: dict[str, int] = {}

    def check(self, clave: str, ahora: float | None = None) -> str:
        ahora = _reloj() if ahora is None else ahora
        ventana = int(ahora // self.ventana_s)
        if ventana != self._ventana:
            self._ventana, self._cuentas = ventana, {}
        n = self._cuentas.get(clave)
        if n is None:
            if len(self._cuentas) >= self.max_claves:
                return self.FULL
            self._cuentas[clave] = 1
            return self.OK
        if n >= self.limite:
            return self.LIMITED
        self._cuentas[clave] = n + 1
        return self.OK


LIMITADO, LLENO, OK = VentanaFija.LIMITED, VentanaFija.FULL, VentanaFija.OK

_TZ_BOLIVIA = timezone(timedelta(hours=-4))        # Bolivia no tiene horario de verano


def ahora_bolivia() -> datetime:
    return datetime.now(_TZ_BOLIVIA)


def hoy_bolivia() -> date:
    return ahora_bolivia().date()


def ids_comercios_activos(repo) -> set[str]:
    """Los ids (uuid canónico) de los comercios activos. Si el repo tiene `ids_comercios_activos()` se usa; si no, se
    pagina `comercios` con el cliente de PostgREST que expone el repo (`_db`). Levanta si no hay de dónde sacarlos."""
    propio = getattr(repo, "ids_comercios_activos", None)
    if callable(propio):
        return {i for i in (es_uuid(x) for x in propio()) if i}
    db = getattr(repo, "_db", None)
    if db is None:
        raise RuntimeError("el repo no sabe listar los comercios activos")
    ids: set[str] = set()
    for pagina in range(200):                      # tope de seguridad: 200.000 comercios
        lote = (db.table("comercios").select("id").eq("activo", True).order("id")
                .range(pagina * 1000, pagina * 1000 + 999).execute().data) or []
        ids.update(i for i in (es_uuid(r.get("id")) for r in lote) if i)
        if len(lote) < 1000:
            break
    return ids


class Medidor:
    """El estado en memoria de la medición: límites, deduplicación, techos por IP y buffer de filas.
    Todo con tope y detrás de un lock (los endpoints sincrónicos corren en hilos distintos). Las estructuras con
    tope son `OrderedDict` que expiran por orden de inserción (amortizado O(1) por pedido): nada recorre el
    diccionario entero con el lock tomado."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.limitadores = {nombre: VentanaFija(n) for nombre, n in LIMITES_POR_MINUTO.items()}
        self._vistas: OrderedDict[tuple[str, str], float] = OrderedDict()
        self._contactos: OrderedDict[tuple[str, str, str, str], str | None] = OrderedDict()
        self._techos: OrderedDict[tuple[str, str, str], int] = OrderedDict()
        self._pares_ip_comercio: OrderedDict[tuple[str, str], None] = OrderedDict()   # (hash de IP, comercio) tocados hoy
        self._comercios_por_ip: dict[str, int] = {}                                    # hash de IP -> comercios distintos hoy
        self._dia: date | None = None
        self._sal = b""
        self._buffer: dict[str, list[dict]] = {"visitas": [], "site_events": [], "leads": []}
        self._ultimo_aviso_lleno = 0.0
        self.descartadas = 0
        # comercios activos (para no aceptar un `comercio_id` inventado) y búsquedas emitidas por este backend
        self._lock_comercios = threading.Lock()
        self._comercios_ok: frozenset[str] = frozenset()
        self._comercios_cargado: float | None = None
        self._comercios_intento: float | None = None
        self._busquedas: OrderedDict[str, float] = OrderedDict()
        # reportes de CSP agregados (se loguea una línea por minuto)
        self._csp: dict[tuple[str, str], list] = {}
        self._csp_desde = _reloj()

    # -- límites --------------------------------------------------------------------------
    def limitar(self, nombre: str, ip: str | None, ahora: float | None = None) -> str:
        with self._lock:
            return self.limitadores[nombre].check(clave_de_ip(ip), ahora)

    # -- el día (sal y contadores diarios) --------------------------------------------------
    def _rodar_dia(self, dia: date) -> None:
        if self._dia != dia:                      # día nuevo: sal nueva y contadores en cero
            self._dia, self._sal = dia, secrets.token_bytes(16)
            self._contactos, self._techos = OrderedDict(), OrderedDict()
            self._pares_ip_comercio, self._comercios_por_ip = OrderedDict(), {}

    # -- deduplicación ----------------------------------------------------------------------
    def vista_repetida(self, sesion: str, comercio: str, ahora: float | None = None) -> bool:
        """True si esa sesión ya vio esa ficha hace menos de 30 minutos (un F5 no suma otra «persona»).
        Las entradas están en orden de tiempo (cada vista nueva va al final): se vencen las del principio y, si el
        tope se pasa, sale la más vieja. Nunca se recorre todo con el lock tomado."""
        ahora = _reloj() if ahora is None else ahora
        clave = (sesion, comercio)
        with self._lock:
            visto = self._vistas.get(clave)
            if visto is not None and ahora - visto < VENTANA_VISTA_S:
                return True
            self._vistas[clave] = ahora
            self._vistas.move_to_end(clave)
            while self._vistas:
                _k, t = next(iter(self._vistas.items()))
                if len(self._vistas) > MAX_DEDUP or ahora - t >= VENTANA_VISTA_S:
                    self._vistas.popitem(last=False)
                else:
                    break
            return False

    def contacto_previo(self, dia: date, sesion: str, comercio: str, clase: str) -> tuple[bool, str | None]:
        """(¿ya hubo uno hoy?, id del primero). `clase` es el tipo (y el detalle, si lo lleva)."""
        with self._lock:
            self._rodar_dia(dia)
            clave = (dia.isoformat(), sesion, comercio, clase)
            if clave in self._contactos:
                return True, self._contactos[clave]
            return False, None

    def recordar_contacto(self, dia: date, sesion: str, comercio: str, clase: str, lead_id: str | None) -> None:
        with self._lock:
            self._rodar_dia(dia)
            clave = (dia.isoformat(), sesion, comercio, clase)
            self._contactos[clave] = lead_id
            self._contactos.move_to_end(clave)
            while len(self._contactos) > MAX_DEDUP:      # lleno: se olvida el más viejo, no el que llega
                self._contactos.popitem(last=False)

    # -- techo por IP -----------------------------------------------------------------------
    def pasa_techo(self, dia: date, ip: str | None, comercio: str, clase: str, tope: int) -> bool:
        """True si esa IP todavía puede sumar `clase` sobre ese comercio hoy. La clave lleva un hash con la sal
        del día: la IP no se guarda y el hash de ayer no se relaciona con el de hoy.

        Dos techos: `tope` por (IP, comercio, clase) y `TECHO_COMERCIOS_IP_DIA` comercios distintos por IP y por día.
        Si el diccionario se llena sale el registro más viejo (LRU): llenarlo ya no apaga el techo."""
        with self._lock:
            self._rodar_dia(dia)
            h = hashlib.blake2b(self._sal + clave_de_ip(ip).encode(), digest_size=8).hexdigest()
            par = (h, comercio)
            if par in self._pares_ip_comercio:
                self._pares_ip_comercio.move_to_end(par)
            else:
                if self._comercios_por_ip.get(h, 0) >= TECHO_COMERCIOS_IP_DIA:
                    return False
                self._pares_ip_comercio[par] = None
                self._comercios_por_ip[h] = self._comercios_por_ip.get(h, 0) + 1
                while len(self._pares_ip_comercio) > MAX_DEDUP:
                    (hv, _cv), _ = self._pares_ip_comercio.popitem(last=False)
                    quedan = self._comercios_por_ip.get(hv, 1) - 1
                    if quedan > 0:
                        self._comercios_por_ip[hv] = quedan
                    else:
                        self._comercios_por_ip.pop(hv, None)
            clave = (h, comercio, clase)
            n = self._techos.get(clave)
            if n is None:
                self._techos[clave] = 1
                while len(self._techos) > MAX_DEDUP:
                    self._techos.popitem(last=False)
                return True
            self._techos.move_to_end(clave)
            if n >= tope:
                return False
            self._techos[clave] = n + 1
            return True

    # -- comercios activos y búsquedas emitidas ---------------------------------------------
    def _refrescar_comercios(self, repo, ahora: float) -> None:
        with self._lock_comercios:
            if self._comercios_intento is not None and ahora - self._comercios_intento < REINTENTO_COMERCIOS_S:
                return                              # otro hilo acaba de recargar (o de intentarlo)
            self._comercios_intento = ahora
            try:
                nuevos = frozenset(ids_comercios_activos(repo))
            except Exception as exc:  # noqa: BLE001 — sin base se queda el conjunto anterior (o ninguno: todo se rechaza)
                logger.warning("comercios_activos_failed", error=str(exc)[:200])
                return
            self._comercios_ok, self._comercios_cargado = nuevos, ahora

    def comercio_activo(self, repo, cid: str) -> bool:
        """¿Es `cid` (uuid canónico) un comercio activo? Con un conjunto en memoria que se recarga cada 5 minutos; un
        id desconocido fuerza una recarga (por si es un comercio recién creado), a lo sumo una por minuto: así un
        atacante que prueba ids al azar no convierte esto en una consulta por pedido."""
        ahora = _reloj()
        cargado = self._comercios_cargado
        if cargado is None or ahora - cargado >= REFRESCO_COMERCIOS_S:
            self._refrescar_comercios(repo, ahora)
        if cid in self._comercios_ok:
            return True
        cargado = self._comercios_cargado
        if cargado is None or ahora - cargado >= RECARGA_MINIMA_S:
            self._refrescar_comercios(repo, ahora)
            return cid in self._comercios_ok
        return False

    def recordar_busqueda(self, busqueda_id: Any) -> None:
        """Anota un id de búsqueda que ACABA de emitir este backend: es el único que `/lead` acepta como `busqueda_id`."""
        clave = es_uuid(busqueda_id) or (str(busqueda_id) if busqueda_id else None)
        if not clave:
            return
        ahora = _reloj()
        with self._lock:
            self._busquedas[clave] = ahora
            self._busquedas.move_to_end(clave)
            while len(self._busquedas) > MAX_BUSQUEDAS_EMITIDAS or \
                    (self._busquedas and ahora - next(iter(self._busquedas.values())) >= TTL_BUSQUEDA_S):
                self._busquedas.popitem(last=False)

    def busqueda_emitida(self, busqueda_id: Any) -> str | None:
        """El id (canónico) si lo emitió este backend hace menos del TTL; None si no (el contacto se guarda sin él)."""
        clave = es_uuid(busqueda_id) or (str(busqueda_id).strip() if busqueda_id else None)
        if not clave:
            return None
        with self._lock:
            t = self._busquedas.get(clave)
            if t is None or _reloj() - t >= TTL_BUSQUEDA_S:
                return None
            return clave

    # -- reportes de CSP --------------------------------------------------------------------
    def anotar_csp(self, directiva: str, bloqueado: str, disposicion: str) -> None:
        clave = (directiva, bloqueado)
        with self._lock:
            if clave not in self._csp and len(self._csp) >= MAX_CLAVES_CSP:
                clave = ("otro", "otro")
            fila = self._csp.setdefault(clave, [0, disposicion])
            fila[0] += 1

    def tomar_csp_si_toca(self, forzar: bool = False) -> list[dict] | None:
        """Los reportes agregados desde la última vez, si pasó el período (1 minuto) o `forzar`; None si todavía no."""
        ahora = _reloj()
        with self._lock:
            if not self._csp:
                self._csp_desde = ahora
                return None
            if not forzar and ahora - self._csp_desde < PERIODO_LOG_CSP_S:
                return None
            filas = [{"directiva": d, "bloqueado": b, "disposicion": v[1], "n": v[0]}
                     for (d, b), v in sorted(self._csp.items(), key=lambda kv: -kv[1][0])]
            self._csp, self._csp_desde = {}, ahora
            return filas

    # -- buffer -----------------------------------------------------------------------------
    def encolar(self, tabla: str, fila: dict) -> bool:
        with self._lock:
            if sum(len(v) for v in self._buffer.values()) >= MAX_BUFFER:
                self.descartadas += 1
                ahora = _reloj()
                if ahora - self._ultimo_aviso_lleno > 60:     # un aviso por minuto, no uno por fila
                    self._ultimo_aviso_lleno = ahora
                    logger.warning("site_metrics_buffer_full", descartadas=self.descartadas)
                return False
            self._buffer[tabla].append(fila)
            return True

    def tomar_buffer(self) -> dict[str, list[dict]]:
        with self._lock:
            lote, self._buffer = self._buffer, {"visitas": [], "site_events": [], "leads": []}
            return lote

    def pendientes(self) -> int:
        with self._lock:
            return sum(len(v) for v in self._buffer.values())


medidor = Medidor()


def reiniciar() -> None:
    """Estado en blanco (tests)."""
    global medidor
    medidor = Medidor()


# ── validación de lo que llega ─────────────────────────────────────────────────────────────────
_SESION_RE = re.compile(r"^[A-Za-z0-9-]{6,40}$")
_SESION_LEAD_RE = re.compile(r"^[A-Za-z0-9-]{1,40}$")
_HOST_RE = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,118}[a-z0-9])?$")
_SLUG_RE = re.compile(r"[^a-z0-9-]")


def es_utf8(texto: str) -> bool:
    """False si el texto no se puede codificar en UTF-8 (un sustituto suelto U+D800 que el JSON deja pasar): Postgres lo
    rechaza, y una sola fila así haría fallar el insert en lote de todas las demás."""
    try:
        texto.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def es_uuid(valor: Any) -> str | None:
    """El uuid en su forma canónica, o None si no es uno."""
    try:
        return str(uuid.UUID(str(valor)))
    except (ValueError, AttributeError, TypeError):
        return None


def limpiar_sesion(valor: Any, *, estricta: bool = True) -> str | None:
    if not isinstance(valor, str):
        return None
    valor = valor.strip()
    return valor if (_SESION_RE if estricta else _SESION_LEAD_RE).match(valor) else None


def normalizar_ruta(raw: Any) -> str | None:
    """Sólo la ruta: sin query ni fragmento, con `/` inicial y 200 caracteres como máximo. None si no sirve."""
    if not isinstance(raw, str):
        return None
    ruta = raw.split("#", 1)[0].split("?", 1)[0].strip()
    if not ruta or not ruta.startswith("/") or any(ord(c) < 32 or ord(c) == 127 for c in ruta):
        return None
    ruta = ruta[:200]
    if not es_utf8(ruta):
        return None
    return ruta


def es_ruta_interna(ruta: str) -> bool:
    return ruta.lower().startswith(RUTAS_INTERNAS)


def normalizar_dominio(raw: Any) -> str | None:
    """El host del referido (sin esquema, ruta ni puerto, sin `www.`). Acepta `android-app://<paquete>/...`
    (devuelve el paquete). None si no es un host válido."""
    if not isinstance(raw, str):
        return None
    host = raw.strip().lower()
    if host.startswith("android-app://"):
        host = host[len("android-app://"):].split("/", 1)[0]
    else:
        host = re.sub(r"^[a-z][a-z0-9+.-]*://", "", host).split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
        host = host.rsplit("@", 1)[-1].split(":", 1)[0]
    host = host.rstrip(".").removeprefix("www.")
    if "." not in host or len(host) > 80 or not _HOST_RE.match(host):
        return None
    return host


def validar_evento(evento: Any, detalle: Any) -> str | None:
    """El `detail` normalizado si (evento, detalle) está en el catálogo cerrado; None si no."""
    if not isinstance(evento, str) or evento not in EVENTOS or not isinstance(detalle, str):
        return None
    detalle = detalle.strip().lower()
    regla = EVENTOS[evento]
    if regla == "uuid":
        return es_uuid(detalle)
    return detalle if detalle in regla else None


def limpiar_ciudad(valor: Any) -> str | None:
    if not isinstance(valor, str):
        return None
    return _SLUG_RE.sub("", valor.strip().lower())[:40] or None


# ── /collect ───────────────────────────────────────────────────────────────────────────────────
def procesar_collect(raw: bytes, *, hoy: date | None = None) -> str:
    """Valida el cuerpo de `/collect` y, si sirve, lo deja en el buffer. Devuelve qué pasó (`guardado`,
    `invalido`, `interna`, `lleno`) sólo para los tests y los logs: el endpoint contesta 204 igual. Nunca levanta."""
    try:
        datos = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, RecursionError):
        return "invalido"
    if not isinstance(datos, dict):
        return "invalido"
    tipo = datos.get("t")
    ruta = normalizar_ruta(datos.get("path"))
    sesion = limpiar_sesion(datos.get("session"))
    if tipo not in ("pv", "ev") or ruta is None or sesion is None:
        return "invalido"
    if es_ruta_interna(ruta):
        return "interna"
    dia = hoy or hoy_bolivia()
    ciudad = limpiar_ciudad(datos.get("city"))
    if tipo == "pv":
        referido = normalizar_dominio(datos.get("referrer"))
        if referido in hosts_propios():
            referido = None                       # navegación interna: no es un referido
        device = datos.get("device")
        fila = {
            "dia": dia.isoformat(),
            "ruta": ruta,
            "sesion": sesion,
            "origen": limpiar_ref(datos.get("ref")) if isinstance(datos.get("ref"), str) else None,
            "referido": referido,
            "ciudad_slug": ciudad,
            "primera": datos.get("first") is True,
            "device": device if device in DISPOSITIVOS else None,
            "standalone": datos.get("standalone") is True,
        }
        return "guardado" if medidor.encolar("visitas", fila) else "lleno"
    detalle = validar_evento(datos.get("event"), datos.get("detail"))
    if detalle is None:
        return "invalido"
    fila = {"day": dia.isoformat(), "event": datos["event"], "detail": detalle, "path": ruta,
            "session": sesion, "city_slug": ciudad}
    return "guardado" if medidor.encolar("site_events", fila) else "lleno"


def registrar_visita_vieja(*, ruta: str, sesion: str, origen: str | None, referido: str | None, ciudad: str | None,
                           primera: bool, device: str | None = None, standalone: bool = False) -> bool:
    """`POST /visita` (cliente viejo): mismo buffer que /collect. True si quedó en el buffer."""
    ruta_ok = normalizar_ruta(ruta)
    if ruta_ok is None or es_ruta_interna(ruta_ok):
        return False
    dominio = normalizar_dominio(referido)
    fila = {
        "dia": hoy_bolivia().isoformat(),
        "ruta": ruta_ok,
        "sesion": re.sub(r"[^a-zA-Z0-9-]", "", sesion)[:40],
        "origen": limpiar_ref(origen),
        "referido": None if dominio in hosts_propios() else dominio,
        "ciudad_slug": limpiar_ciudad(ciudad),
        "primera": bool(primera),
        "device": device if device in DISPOSITIVOS else None,
        "standalone": bool(standalone),
    }
    return medidor.encolar("visitas", fila)


# ── contactos (/lead) ──────────────────────────────────────────────────────────────────────────
def registrar_contacto(repo, *, ip: str | None, comercio_id: Any, tipo: Any, sesion: Any = None,
                       busqueda_id: Any = None, origen: Any = None, detalle: Any = None) -> dict:
    """`POST /lead`. Devuelve el cuerpo de la respuesta:
    - `{ok: False}`: `tipo` fuera de la lista, `comercio_id` que no es uuid o no es un comercio activo, `detalle`
      fuera del conjunto cerrado o un error de la base. NADA se guarda (un tipo desconocido ya no se convierte en
      whatsapp). Un `busqueda_id` que este backend no emitió no invalida el contacto: se guarda sin él.
    - `{ok: True, id: None}`: vista, compartir o red (van al buffer), o el techo por IP.
    - `{ok: True, id, token}`: contacto insertado; si la sesión ya lo había hecho hoy, el del primero con `repetido: True`.
    """
    from app.core import firmas

    if not isinstance(tipo, str) or tipo not in TIPOS_LEAD:
        return {"ok": False}
    cid = es_uuid(comercio_id)
    if cid is None:
        return {"ok": False}
    detalle_ok: str | None = None
    if tipo == "red":
        detalle_ok = detalle.strip().lower() if isinstance(detalle, str) and detalle.strip().lower() in REDES else None
        if detalle_ok is None:
            return {"ok": False}
    elif tipo == "compartir":
        detalle_ok = detalle.strip().lower() if isinstance(detalle, str) and detalle.strip().lower() in CANALES_COMPARTIR else None
        if detalle_ok is None:
            return {"ok": False}
    # Un comercio que no existe (o está dado de baja) no toca ningún mapa ni el buffer: la tabla `leads` tiene una
    # clave foránea y una sola fila inventada haría fallar el lote entero.
    if not medidor.comercio_activo(repo, cid):
        return {"ok": False}
    sesion_ok = limpiar_sesion(sesion, estricta=False)
    # Sólo un `busqueda_id` que emitió este backend (y todavía vigente); cualquier otro se guarda como NULL.
    busqueda_ok = medidor.busqueda_emitida(busqueda_id) if busqueda_id else None
    dia = hoy_bolivia()

    if tipo == "vista":
        if sesion_ok and medidor.vista_repetida(sesion_ok, cid):
            return {"ok": True, "id": None}
        if not medidor.pasa_techo(dia, ip, cid, "vista", TECHO_VISTA_IP_DIA):
            return {"ok": True, "id": None}
    else:
        clase = f"{tipo}:{detalle_ok}" if detalle_ok else tipo
        if sesion_ok:
            repetido, primero = medidor.contacto_previo(dia, sesion_ok, cid, clase)
            if repetido:
                cuerpo = {"ok": True, "id": primero, "repetido": True}
                if primero:
                    cuerpo["token"] = firmas.token_de_lead(str(primero), sesion_ok)
                return cuerpo
        if not medidor.pasa_techo(dia, ip, cid, clase, TECHO_CONTACTO_IP_DIA):
            return {"ok": True, "id": None}

    fila = {"comercio_id": cid, "tipo": tipo, "busqueda_id": busqueda_ok, "origen": limpiar_ref(origen) if isinstance(origen, str) else None,
            "sesion": sesion_ok, "detalle": detalle_ok}
    if tipo in TIPOS_EN_LOTE:
        if tipo != "vista" and sesion_ok:
            medidor.recordar_contacto(dia, sesion_ok, cid, f"{tipo}:{detalle_ok}", None)
        medidor.encolar("leads", fila)
        return {"ok": True, "id": None}

    try:
        creado = repo.insert_lead({k: v for k, v in fila.items() if v is not None}) or {}
    except Exception as exc:  # noqa: BLE001 — la base caída no puede dar un 500 en un click
        logger.warning("lead_insert_failed", tipo=tipo, error=str(exc)[:200])
        return {"ok": False}
    lead_id = creado.get("id")
    if not lead_id:
        return {"ok": False}
    if sesion_ok:
        medidor.recordar_contacto(dia, sesion_ok, cid, tipo, str(lead_id))
    return {"ok": True, "id": lead_id, "token": firmas.token_de_lead(str(lead_id), sesion_ok)}


# ── búsquedas ──────────────────────────────────────────────────────────────────────────────────
def enmascarar_busqueda(q: str | None) -> str:
    """El texto de una búsqueda sin datos personales: mails (y «(at)», «[at]») → `[mail]`, secuencias de 6 o más
    dígitos aunque vengan con espacios, puntos o guiones en el medio (teléfonos, documentos) → `#`. Tope de 100
    caracteres. «71234567 zapatos» queda «# zapatos»; «+591 712-34567 pan» queda «# pan». Lo mismo, en SQL, para las
    filas viejas: migración 0194."""
    return enmascarar_texto(q, marca_mail="[mail]", marca_digitos="#", largo=100)


# ── volcado y retención ────────────────────────────────────────────────────────────────────────
def _insertar_aislando(repo, tabla: str, filas: list[dict]) -> int:
    """Inserta el lote; si la base lo rechaza, lo PARTE A LA MITAD y reintenta cada mitad (recursivo) hasta aislar la
    fila (o las pocas filas) que lo rompe: así una fila mala no se lleva puestas las otras 499. Devuelve cuántas
    quedaron guardadas. Tiene un presupuesto de pedidos (`MAX_INTENTOS_AISLAR`): con la base caída no se hacen
    cientos de intentos, se descarta el resto."""
    presupuesto = [MAX_INTENTOS_AISLAR]

    def ir(parte: list[dict]) -> int:
        if presupuesto[0] <= 0:
            logger.warning("site_metrics_flush_failed", tabla=tabla, filas=len(parte), error="sin presupuesto de reintentos")
            return 0
        presupuesto[0] -= 1
        try:
            repo.insert_site_rows(tabla, parte)
            return len(parte)
        except Exception as exc:  # noqa: BLE001
            if len(parte) <= 1:
                logger.warning("site_metrics_flush_failed", tabla=tabla, filas=len(parte), error=str(exc)[:200])
                return 0
            medio = len(parte) // 2
            return ir(parte[:medio]) + ir(parte[medio:])

    return ir(filas)


def volcar(repo) -> dict[str, int]:
    """Vuelca el buffer: un `insert` en lote por tabla (de a `LOTE_INSERT` filas). Si un lote falla se parte a la mitad
    una y otra vez para aislar la fila mala (`_insertar_aislando`); la que no se puede guardar se loguea
    (`site_metrics_flush_failed`) y se DESCARTA, sin reintento infinito. Devuelve filas guardadas por tabla.
    También deja en el log, una vez por minuto, el resumen de los reportes de CSP."""
    guardadas: dict[str, int] = {}
    for tabla, filas in medidor.tomar_buffer().items():
        if not filas:
            continue
        ok = 0
        for i in range(0, len(filas), LOTE_INSERT):
            ok += _insertar_aislando(repo, tabla, filas[i:i + LOTE_INSERT])
        guardadas[tabla] = ok
    volcar_csp()
    return guardadas


def volcar_csp(forzar: bool = False) -> None:
    """Una línea de log por minuto con los reportes de CSP agregados por (directiva, host bloqueado)."""
    filas = medidor.tomar_csp_si_toca(forzar)
    if filas:
        logger.warning("csp_violations", total=sum(f["n"] for f in filas), distintas=len(filas), items=filas[:50])


def segundos_hasta_purga(ahora: datetime | None = None) -> float:
    """Segundos hasta las próximas 04:00 de Bolivia."""
    ahora = (ahora or datetime.now(timezone.utc)).astimezone(_TZ_BOLIVIA)
    proxima = ahora.replace(hour=HORA_PURGA_BOLIVIA, minute=0, second=0, microsecond=0)
    if proxima <= ahora:
        proxima += timedelta(days=1)
    return (proxima - ahora).total_seconds()


def purgar(repo, meses: int = RETENCION_MESES) -> int:
    """`rpc('purge_site_metrics', {p_months})`: el piso de 13 meses está también adentro de la función."""
    n = repo.purge_site_metrics(max(meses, RETENCION_MESES))
    logger.info("site_metrics_purged", filas=n, meses=meses)
    return n


# ── referidos canónicos (se aplican AL LEER: sirven también para el historial) ──────────────────
_GOOGLE_RE = re.compile(r"^(?:[a-z0-9-]+\.)*google\.(?:com|(?:com?\.)?[a-z]{2})$")     # google.com, google.com.bo, google.com.ar
_SEARCH: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("bing", ("bing.com",)), ("duckduckgo", ("duckduckgo.com",)),
    ("yahoo", ("yahoo.com", "yahoo.com.ar", "yahoo.co.jp")), ("ecosia", ("ecosia.org",)), ("brave", ("search.brave.com",)),
    ("yandex", ("yandex.com", "yandex.ru", "yandex.com.tr")), ("baidu", ("baidu.com",)), ("startpage", ("startpage.com",)),
    ("qwant", ("qwant.com",)), ("ask", ("ask.com",)),
)
_SOCIAL: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("facebook", ("facebook.com", "fb.com", "fb.me", "fb.watch")), ("instagram", ("instagram.com", "l.instagram.com")),
    ("x", ("x.com", "t.co", "twitter.com")), ("linkedin", ("linkedin.com", "lnkd.in")),
    ("youtube", ("youtube.com", "youtu.be")), ("tiktok", ("tiktok.com",)), ("reddit", ("reddit.com",)),
    ("pinterest", ("pinterest.com", "pinterest.com.ar", "pin.it")), ("telegram", ("t.me", "telegram.me", "telegram.org")),
    ("threads", ("threads.net", "threads.com")), ("messenger", ("messenger.com",)),
)
_WHATSAPP = (("whatsapp", ("whatsapp.com", "wa.me", "whatsapp.net")),)
#: Referidos de apps de Android (`android-app://<paquete>`): paquete -> (tipo, nombre canónico).
_APPS: dict[str, tuple[str, str]] = {
    "com.whatsapp": ("whatsapp", "whatsapp"), "com.whatsapp.w4b": ("whatsapp", "whatsapp"),
    "com.google.android.googlequicksearchbox": ("search", "google"),
    "com.google.android.gm": ("other", "gmail"),
    "com.facebook.katana": ("social", "facebook"), "com.facebook.lite": ("social", "facebook"),
    "com.facebook.orca": ("social", "messenger"), "com.facebook.mlite": ("social", "messenger"),
    "com.instagram.android": ("social", "instagram"),
    "com.zhiliaoapp.musically": ("social", "tiktok"), "com.ss.android.ugc.trill": ("social", "tiktok"),
    "org.telegram.messenger": ("social", "telegram"), "com.twitter.android": ("social", "x"),
}
#: `?ref=` / `utm_source` que son una red o un buscador y no un QR.
_ORIGEN_ALIAS: dict[str, tuple[str, str]] = {
    "fb": ("social", "facebook"), "facebook": ("social", "facebook"),
    "ig": ("social", "instagram"), "instagram": ("social", "instagram"),
    "tiktok": ("social", "tiktok"), "tt": ("social", "tiktok"), "youtube": ("social", "youtube"),
    "wa": ("whatsapp", "whatsapp"), "whatsapp": ("whatsapp", "whatsapp"),
    "google": ("search", "google"), "bing": ("search", "bing"),
}


def _es_dominio(dominio: str, bases: tuple[str, ...]) -> bool:
    return any(dominio == b or dominio.endswith("." + b) for b in bases)


def clasificar_referido(dominio: str | None, propios: frozenset[str] = frozenset()) -> tuple[str, str]:
    """`(tipo, nombre)` de un host de referido. Sin host (o uno propio) = `direct`. Para buscadores, redes y
    WhatsApp el nombre es el CANÓNICO (`google`, `facebook`, `whatsapp`…), nunca el subdominio; `other` guarda el host."""
    dominio = normalizar_dominio(dominio) or (dominio or "").strip().lower()      # las filas viejas guardan `android-app://…`
    if not dominio or dominio in propios:
        return "direct", ""
    app = _APPS.get(dominio)
    if app:
        return app
    if dominio == "mail.google.com":
        return "other", "gmail"
    if _GOOGLE_RE.match(dominio):
        return "search", "google"
    for tipo, tabla in (("whatsapp", _WHATSAPP), ("social", _SOCIAL), ("search", _SEARCH)):
        for nombre, bases in tabla:
            if _es_dominio(dominio, bases):
                return tipo, nombre
    return "other", dominio


def clasificar_llegada(origen: str | None, referido: str | None, *, qr_aparte: bool = False) -> tuple[str, str]:
    """`(tipo, nombre)` de cómo llegó alguien: `ai` (asistentes de IA, por origen o por referido), el referido
    canónico, o el `?ref=` (red conocida o, si no, el QR/enlace marcado). Sin nada = `direct`.

    `qr_aparte=True` (Mi comercio): un `?ref=` de un QR nuestro (`CLASES_QR`: volante, mesa, ficha) es `qr` con su clase;
    cualquier otro desconocido es `other`/`otros` (el `?ref=` lo puede escribir cualquiera).
    `False` (panel del admin): es `other` con nombre `qr_<clase>`, sea cual sea."""
    ia = classify_ai_source(origen, referido)
    if ia:
        return "ai", ia
    if referido:
        tipo, nombre = clasificar_referido(referido, hosts_propios())
        if tipo != "direct":
            return tipo, nombre
    if origen:
        clase = origen.split("-", 1)[0]
        alias = _ORIGEN_ALIAS.get(clase)
        if alias:
            return alias
        if qr_aparte:
            return ("qr", clase) if clase in CLASES_QR else ("other", "otros")
        return "other", f"qr_{clase}"
    return "direct", ""


def _contar(filas: list[tuple[tuple[str, str], int]], *, tope: int | None = None) -> list[dict]:
    c: Counter = Counter()
    for clave, n in filas:
        c[clave] += n
    salida = [{"kind": k, "name": nm, "n": n} for (k, nm), n in sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))]
    return salida[:tope] if tope else salida


def _juntar_hosts_raros(items: list[dict]) -> list[dict]:
    """Para «Mi comercio»: un host de referido desconocido (`other` con un punto en el nombre) con menos de
    `MIN_SESIONES_HOST_OTRO` sesiones se junta en «Otros». Así nadie puede usar la ficha de un comercio como cartel
    mandándole visitas con un `Referer` de su sitio (el dueño vería ese dominio en su pantalla)."""
    salida: list[dict] = []
    otros = 0
    for it in items:
        if it["kind"] == "other" and "." in it["name"] and it["n"] < MIN_SESIONES_HOST_OTRO:
            otros += it["n"]
        else:
            salida.append(it)
    if otros:
        previo = next((it for it in salida if it["kind"] == "other" and it["name"] == "otros"), None)
        if previo:
            previo["n"] += otros
        else:
            salida.append({"kind": "other", "name": "otros", "n": otros})
    return sorted(salida, key=lambda it: (-it["n"], it["kind"], it["name"]))


# ── resúmenes (los consume /admin/visitas y /comercio/metricas) ─────────────────────────────────
def _entero(v: Any) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def rango_de_dias(dias: int) -> tuple[date, date]:
    """(desde, hasta) inclusivos y en hora de Bolivia: `dias=1` es hoy, no hoy y ayer."""
    hasta = hoy_bolivia()
    return hasta - timedelta(days=max(0, dias - 1)), hasta


def resumen_del_sitio(repo, dias: int, ciudad: str | None = None) -> dict:
    """La respuesta de `GET /admin/visitas`: las claves de siempre (`dias, visitas, personas, por_dia, top_rutas,
    top_referidos, top_origenes, ai_sources, embudo`) más las nuevas (`referrers, devices, standalone_share, events,
    funnel, desde, hasta, umami_url, last_hit_at`)."""
    desde, hasta = rango_de_dias(dias)
    raw = repo.site_metrics_summary(desde.isoformat(), hasta.isoformat(), ciudad) or {}
    tot = raw.get("totals") or {}
    pageviews, sesiones, primeras = _entero(tot.get("pageviews")), _entero(tot.get("sessions")), _entero(tot.get("first_pages"))
    por_tipo = {k: _entero(v) for k, v in (raw.get("leads_by_type") or {}).items()}

    # De dónde llegaron (sólo las páginas que abrieron la sesión), con el nombre canónico.
    filas = [((r.get("referido") or None, r.get("origen") or None), _entero(r.get("n"))) for r in raw.get("referrers_raw") or []]
    contadas = sum(n for _c, n in filas)
    por_llegada = [(clasificar_llegada(o, rf), n) for (rf, o), n in filas]
    if primeras > contadas:                       # lo que no entró en el top 300 de la consulta
        por_llegada.append((("other", "otros"), primeras - contadas))
    # Los de origen y referido vacíos ya salen como `direct` de `clasificar_llegada`.
    referidos_crudos: Counter = Counter()
    for (rf, _o), n in filas:
        if rf:
            referidos_crudos[rf] += n

    funnel = raw.get("funnel") or {}
    try:
        ultimo = repo.last_visit_at()
    except Exception:  # noqa: BLE001 — el panel no se cae porque falle esta consulta
        logger.warning("last_visit_at_failed", exc_info=True)
        ultimo = None
    return {
        "dias": dias,
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "visitas": pageviews,
        "personas": sesiones,
        "por_dia": [{"dia": str(d.get("dia")), "visitas": _entero(d.get("visitas")), "personas": _entero(d.get("personas"))}
                    for d in raw.get("by_day") or []],
        "top_rutas": [{"ruta": r.get("ruta"), "n": _entero(r.get("n"))} for r in (raw.get("top_paths") or [])[:12]],
        "top_referidos": [{"referido": r, "n": n} for r, n in referidos_crudos.most_common(8)],
        "top_origenes": [{"origen": o.get("origen"), "n": _entero(o.get("n"))} for o in (raw.get("origins") or [])[:8]],
        "ai_sources": summarize_ai_groups(raw.get("ai_groups") or [], raw.get("ai_routes") or []),
        "embudo": {
            "visitas": pageviews,
            "personas": sesiones,
            "fichas_vistas": por_tipo.get("vista", 0),
            "contactos": sum(por_tipo.get(t, 0) for t in TIPOS_CONTACTO_EMBUDO),
            "mapa": por_tipo.get("mapa", 0),
        },
        "referrers": _contar(por_llegada),
        "devices": [{"device": d.get("device"), "n": _entero(d.get("n"))} for d in raw.get("devices") or []],
        "standalone_share": float(raw.get("standalone_share") or 0),
        "events": [{"event": e.get("event"), "detail": e.get("detail") or "", "n": _entero(e.get("n"))} for e in raw.get("events") or []],
        "funnel": {
            "sessions": _entero(funnel.get("sessions")),
            "sessions_with_ficha": _entero(funnel.get("sessions_with_ficha")),
            "sessions_with_contact": _entero(funnel.get("sessions_with_contact")),
        },
        "umami_url": None,                        # Umami no está en esta ronda
        "last_hit_at": ultimo,
    }


def metricas_de_comercio(repo, comercio_id: str, dias: int = 30) -> dict:
    """Lo que `GET /comercio/metricas` suma a lo de siempre. SIEMPRE de ese comercio (nunca los de otros ni
    posiciones en un ranking). Ya llegan deduplicados."""
    cuentas = repo.comercio_lead_counts(comercio_id, dias) or {}
    por_tipo = {k: _entero(v) for k, v in (cuentas.get("por_tipo") or {}).items()}
    por_tipo_7d = {k: _entero(v) for k, v in (cuentas.get("por_tipo_7d") or {}).items()}
    desde = hoy_bolivia() - timedelta(days=dias)
    origenes: list[tuple[tuple[str, str], int]] = []
    try:
        for r in repo.comercio_origins(comercio_id, desde.isoformat()) or []:
            # `sesiones` (0194) son las sesiones DISTINTAS; sin él (RPC vieja) se usa `n`, que son primeras páginas.
            personas = _entero(r.get("sesiones") if r.get("sesiones") is not None else r.get("n"))
            origenes.append((clasificar_llegada(r.get("origen") or None, r.get("referido") or None, qr_aparte=True), personas))
    except Exception:  # noqa: BLE001
        logger.warning("comercio_origins_failed", exc_info=True)
    return {
        "por_tipo": por_tipo,
        "por_tipo_7d": por_tipo_7d,
        "como_llegar_30d": por_tipo.get("mapa", 0),
        "compartidos_30d": por_tipo.get("compartir", 0),
        "redes_30d": {k: _entero(v) for k, v in (cuentas.get("redes") or {}).items()},
        "origenes_30d": _juntar_hosts_raros(_contar(origenes)),
    }


def configuracion_publica() -> dict:
    """`GET /public/measurement-config`. Umami no está en esta ronda: `umami` va siempre null (el contrato ya lo
    prevé para cuando se prenda)."""
    return {"internal": True, "umami": None}


# ── CSP ────────────────────────────────────────────────────────────────────────────────────────
_DIRECTIVA_CSP_RE = re.compile(r"^[a-z-]{1,40}$")
_HOST_CSP_RE = re.compile(r"^[a-z0-9.-]{1,120}$")
_PALABRAS_CSP = frozenset({"inline", "eval", "data", "blob", "wasm-eval", "about", "self"})
_DISPOSICIONES_CSP = frozenset({"enforce", "report"})


def _directiva_csp(valor: str) -> str:
    d = valor.strip().split(" ", 1)[0].lower()
    return d if _DIRECTIVA_CSP_RE.match(d) else "otro"


def _bloqueado_csp(valor: str) -> str:
    """Un host (`[a-z0-9.-]`) o una de las palabras conocidas (inline, eval, data, blob…); todo lo demás es «otro».
    El reporte lo manda cualquiera: nada de lo que traiga llega crudo al log."""
    v = valor.strip().lower()[:300]
    if v in _PALABRAS_CSP:
        return v
    esquema = v.split(":", 1)[0]
    if ":" in v and esquema in _PALABRAS_CSP:        # «data:image/png;base64,…», «blob:https://…»
        return esquema
    if "://" in v:
        try:
            host = urlsplit(v).hostname or ""
        except ValueError:
            return "otro"
        return host if _HOST_CSP_RE.match(host) else "otro"
    return v if _HOST_CSP_RE.match(v) else "otro"


def resumir_csp(raw: bytes) -> dict | None:
    """De un reporte de CSP (formato `report-uri` o Reporting API) saca sólo la directiva violada y el host
    bloqueado: sin IP, sin la URL de la página ni su query. None si no se entiende. Lista blanca estricta (el
    endpoint es público: sin ella, un salto de línea en el reporte falsificaba líneas del log): directiva `[a-z-]{1,40}`,
    host `[a-z0-9.-]` o una palabra conocida, disposición `enforce`/`report`; lo demás es «otro»."""
    try:
        datos = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, RecursionError):
        return None
    if isinstance(datos, list):
        datos = next((d.get("body") for d in datos if isinstance(d, dict) and isinstance(d.get("body"), dict)), None)
    elif isinstance(datos, dict):
        datos = datos.get("csp-report") if isinstance(datos.get("csp-report"), dict) else datos.get("body", datos)
    if not isinstance(datos, dict):
        return None
    directiva = datos.get("effective-directive") or datos.get("effectiveDirective") or datos.get("violated-directive")         or datos.get("violatedDirective")
    bloqueado = datos.get("blocked-uri") or datos.get("blockedURL") or datos.get("blockedUri") or ""
    if not isinstance(directiva, str) or not isinstance(bloqueado, str):
        return None
    disposicion = datos.get("disposition")
    disposicion = disposicion.strip().lower() if isinstance(disposicion, str) else ""
    return {"directiva": _directiva_csp(directiva), "bloqueado": _bloqueado_csp(bloqueado),
            "disposicion": disposicion if disposicion in _DISPOSICIONES_CSP else "otro"}


def registrar_csp(resumen: dict) -> None:
    """Suma un reporte (ya saneado por `resumir_csp`) al conteo por (directiva, host); el log sale una vez por minuto."""
    medidor.anotar_csp(resumen["directiva"], resumen["bloqueado"], resumen["disposicion"])
    volcar_csp()


# ── access log ─────────────────────────────────────────────────────────────────────────────────
RUTAS_SIN_ACCESS_LOG = ("/collect", "/visita", "/lead", "/busquedas/log", "/csp-report")


_RE_SIN_ACCESS_LOG = re.compile(r"(?:^|\s)(?:%s)(?:[/?\s\"]|$)" % "|".join(re.escape(p) for p in RUTAS_SIN_ACCESS_LOG))


class FiltroAccessLog(logging.Filter):
    """Saca del access log de uvicorn las líneas de los endpoints de medición: de ahí no tiene que quedar
    ninguna huella de quién visitó qué."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            # uvicorn: args = (cliente, método, ruta con query, versión, estado)
            texto = str(record.args[2]) if isinstance(record.args, tuple) and len(record.args) >= 3 else record.getMessage()
        except Exception:  # noqa: BLE001
            return True
        return not _RE_SIN_ACCESS_LOG.search(texto)


def instalar_filtro_access_log() -> None:
    """Idempotente. No se suma `--proxy-headers`: la IP del visitante no tiene que llegar al log."""
    log = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, FiltroAccessLog) for f in log.filters):
        log.addFilter(FiltroAccessLog())
