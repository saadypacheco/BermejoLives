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
- Todos los topes de memoria son «si se llena, se cuenta de más» (nunca cero) salvo el buffer, que descarta.
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
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from typing import Any
from urllib.parse import urlsplit

import structlog

from app.core.ai_sources import classify_ai_source, summarize_ai_groups
from app.core.config import settings
from app.core.text import limpiar_ref

logger = structlog.get_logger()

# ── constantes ─────────────────────────────────────────────────────────────────────────────────
MAX_BODY_BYTES = 2048
MAX_BODY_CSP = 8192
MAX_CLAVES_LIMITE = 50_000          # claves de IP por ventana; lleno → se acepta y no se guarda
MAX_DEDUP = 200_000                 # entradas de deduplicación y de techos; lleno → se cuenta de más
MAX_BUFFER = 20_000                 # filas pendientes de volcar; llenas → se descartan y se avisa
LOTE_INSERT = 500                   # filas por pedido a PostgREST al volcar
VENTANA_VISTA_S = 30 * 60           # una vista de ficha por (sesión, comercio) cada 30 minutos
RETENCION_MESES = 13
HORA_PURGA_BOLIVIA = 4              # la purga corre a las 04:00 de Bolivia

#: Pedidos por minuto y por IP (una IP pública del CGNAT de una operadora junta a mucha gente).
LIMITES_POR_MINUTO = {"collect": 300, "lead": 120, "busqueda": 60, "csp": 30}

TECHO_VISTA_IP_DIA = 30             # vistas de ficha por IP y por comercio y por día
TECHO_CONTACTO_IP_DIA = 10          # de cada tipo de contacto, por IP y por comercio y por día

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
    """IP parseada: IPv4 tal cual, IPv6 agrupada por /64 (una conexión doméstica = un /64), IPv4 mapeada como
    IPv4. Si no parsea (header raro, `testclient`), la clave fija `invalid`."""
    try:
        addr = ipaddress.ip_address((ip or "").strip())
    except ValueError:
        return "invalid"
    if addr.version == 6:
        if addr.ipv4_mapped is not None:
            return str(addr.ipv4_mapped)
        return str(ipaddress.IPv6Network(f"{addr}/64", strict=False).network_address)
    return str(addr)


def _reloj() -> float:
    """El reloj monotónico de los límites y la deduplicación (los tests lo congelan para no cruzar una ventana)."""
    return time.monotonic()


class VentanaFija:
    """Límite por clave con VENTANA FIJA por minuto y memoria acotada: el dict se vacía al cambiar la ventana y
    tiene tope de claves. O(1) por pedido. `check` devuelve OK, LIMITED (429) o FULL (el dict está lleno: el
    pedido se acepta pero no se guarda)."""

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


class Medidor:
    """El estado en memoria de la medición: límites, deduplicación, techos por IP y buffer de filas.
    Todo con tope y detrás de un lock (los endpoints sincrónicos corren en hilos distintos)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.limitadores = {nombre: VentanaFija(n) for nombre, n in LIMITES_POR_MINUTO.items()}
        self._vistas: dict[tuple[str, str], float] = {}
        self._contactos: dict[tuple[str, str, str, str], str | None] = {}
        self._techos: dict[tuple[str, str, str], int] = {}
        self._dia: date | None = None
        self._sal = b""
        self._buffer: dict[str, list[dict]] = {"visitas": [], "site_events": [], "leads": []}
        self._ultimo_aviso_lleno = 0.0
        self.descartadas = 0

    # -- límites --------------------------------------------------------------------------
    def limitar(self, nombre: str, ip: str | None, ahora: float | None = None) -> str:
        with self._lock:
            return self.limitadores[nombre].check(clave_de_ip(ip), ahora)

    # -- el día (sal y contadores diarios) --------------------------------------------------
    def _rodar_dia(self, dia: date) -> None:
        if self._dia != dia:                      # día nuevo: sal nueva y contadores en cero
            self._dia, self._sal = dia, secrets.token_bytes(16)
            self._contactos, self._techos = {}, {}

    # -- deduplicación ----------------------------------------------------------------------
    def vista_repetida(self, sesion: str, comercio: str, ahora: float | None = None) -> bool:
        """True si esa sesión ya vio esa ficha hace menos de 30 minutos (un F5 no suma otra «persona»)."""
        ahora = _reloj() if ahora is None else ahora
        clave = (sesion, comercio)
        with self._lock:
            visto = self._vistas.get(clave)
            if visto is not None and ahora - visto < VENTANA_VISTA_S:
                return True
            if visto is None and len(self._vistas) >= MAX_DEDUP:
                self._podar_vistas(ahora)
            if visto is not None or len(self._vistas) < MAX_DEDUP:
                self._vistas[clave] = ahora
            return False                          # lleno: se cuenta de más

    def _podar_vistas(self, ahora: float) -> None:
        for k in [k for k, t in self._vistas.items() if ahora - t >= VENTANA_VISTA_S]:
            del self._vistas[k]

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
            if len(self._contactos) < MAX_DEDUP:
                self._contactos[(dia.isoformat(), sesion, comercio, clase)] = lead_id

    # -- techo por IP -----------------------------------------------------------------------
    def pasa_techo(self, dia: date, ip: str | None, comercio: str, clase: str, tope: int) -> bool:
        """True si esa IP todavía puede sumar `clase` sobre ese comercio hoy. La clave lleva un hash con la sal
        del día: la IP no se guarda y el hash de ayer no se relaciona con el de hoy."""
        with self._lock:
            self._rodar_dia(dia)
            h = hashlib.blake2b(self._sal + clave_de_ip(ip).encode(), digest_size=8).hexdigest()
            clave = (h, comercio, clase)
            n = self._techos.get(clave)
            if n is None:
                if len(self._techos) < MAX_DEDUP:
                    self._techos[clave] = 1
                return True                       # lleno: se cuenta de más
            if n >= tope:
                return False
            self._techos[clave] = n + 1
            return True

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
    return ruta[:200]


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
    - `{ok: False}`: `tipo` fuera de la lista, `comercio_id` que no es uuid, `detalle` fuera del conjunto cerrado o
      un error de la base. NADA se guarda (un tipo desconocido ya no se convierte en whatsapp).
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
    sesion_ok = limpiar_sesion(sesion, estricta=False)
    busqueda_ok = es_uuid(busqueda_id) if busqueda_id else None
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
_RE_MAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_RE_DIGITOS = re.compile(r"\d{6,}")


def enmascarar_busqueda(q: str | None) -> str:
    """El texto de una búsqueda sin datos personales: mails → `[mail]`, secuencias de 6 o más dígitos (teléfonos,
    documentos) → `#`. Tope de 100 caracteres. «71234567 zapatos» queda «# zapatos»."""
    texto = _RE_MAIL.sub("[mail]", q or "")
    texto = _RE_DIGITOS.sub("#", texto)
    return re.sub(r"\s+", " ", texto).strip()[:100]


# ── volcado y retención ────────────────────────────────────────────────────────────────────────
def volcar(repo) -> dict[str, int]:
    """Vuelca el buffer: un `insert` en lote por tabla (de a `LOTE_INSERT` filas). Si falla, se loguea
    `site_metrics_flush_failed` y se DESCARTA el lote (sin reintento infinito). Devuelve filas guardadas por tabla."""
    guardadas: dict[str, int] = {}
    for tabla, filas in medidor.tomar_buffer().items():
        if not filas:
            continue
        ok = 0
        for i in range(0, len(filas), LOTE_INSERT):
            parte = filas[i:i + LOTE_INSERT]
            try:
                repo.insert_site_rows(tabla, parte)
                ok += len(parte)
            except Exception as exc:  # noqa: BLE001
                logger.warning("site_metrics_flush_failed", tabla=tabla, filas=len(parte), error=str(exc)[:200])
        guardadas[tabla] = ok
    return guardadas


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

    `qr_aparte=True` (Mi comercio): un `?ref=` desconocido es `qr` con su clase (`volante`, `mesa`…).
    `False` (panel): es `other` con nombre `qr_<clase>`."""
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
        return ("qr", clase) if qr_aparte else ("other", f"qr_{clase}")
    return "direct", ""


def _contar(filas: list[tuple[tuple[str, str], int]], *, tope: int | None = None) -> list[dict]:
    c: Counter = Counter()
    for clave, n in filas:
        c[clave] += n
    salida = [{"kind": k, "name": nm, "n": n} for (k, nm), n in sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))]
    return salida[:tope] if tope else salida


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
            origenes.append((clasificar_llegada(r.get("origen") or None, r.get("referido") or None, qr_aparte=True), _entero(r.get("n"))))
    except Exception:  # noqa: BLE001
        logger.warning("comercio_origins_failed", exc_info=True)
    return {
        "por_tipo": por_tipo,
        "por_tipo_7d": por_tipo_7d,
        "como_llegar_30d": por_tipo.get("mapa", 0),
        "compartidos_30d": por_tipo.get("compartir", 0),
        "redes_30d": {k: _entero(v) for k, v in (cuentas.get("redes") or {}).items()},
        "origenes_30d": _contar(origenes),
    }


def configuracion_publica() -> dict:
    """`GET /public/measurement-config`. Umami no está en esta ronda: `umami` va siempre null (el contrato ya lo
    prevé para cuando se prenda)."""
    return {"internal": True, "umami": None}


# ── CSP ────────────────────────────────────────────────────────────────────────────────────────
def resumir_csp(raw: bytes) -> dict | None:
    """De un reporte de CSP (formato `report-uri` o Reporting API) saca sólo la directiva violada y el host
    bloqueado: sin IP, sin la URL de la página ni su query. None si no se entiende."""
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
    directiva = datos.get("effective-directive") or datos.get("effectiveDirective") or datos.get("violated-directive") \
        or datos.get("violatedDirective")
    bloqueado = datos.get("blocked-uri") or datos.get("blockedURL") or datos.get("blockedUri") or ""
    if not isinstance(directiva, str) or not isinstance(bloqueado, str):
        return None
    host = urlsplit(bloqueado).hostname if "://" in bloqueado else bloqueado.strip().lower()
    return {"directiva": directiva.split(" ", 1)[0][:60], "bloqueado": (host or "")[:120],
            "disposicion": str(datos.get("disposition") or "")[:20]}


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
