"""IndexNow: avisa a Bing (y Yandex, Naver, Seznam, Yep) que una ficha cambió.

docs/visibilidad-buscadores-ia.md §3.12. Google NO participa del protocolo. Un 200
significa «recibido», no «indexado».

Sólo se avisan las fichas INDEXABLES (regla de §3.1, la misma de `frontend/lib/seo.ts`):
una ficha vacía sale con `noindex` y avisarla sería ruido. Nada de acá lanza hacia
afuera: es una cortesía al buscador, nunca puede romper el backend
(pattern-fire-and-forget-tracking).
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger()

#: IndexNow acepta hasta 10.000 URLs por pedido.
MAX_URLS_POR_PEDIDO = 10_000
#: Páginas que se suman una vez por día (su contenido cambia solo).
RUTAS_FIJAS = ("/", "/cambio", "/farmacias-de-turno")

_CLAVE_VALIDA = re.compile(r"^[A-Za-z0-9-]{8,128}$")


# ── reglas de §3.1 ───────────────────────────────────────────────────────────
def _vacio(v) -> bool:
    return not (v or "").strip()


def is_business_thin(c: dict) -> bool:
    """Ficha «fina»: sin rubro (o «otros») y sin nada de texto, o «a clasificar»."""
    sin_rubro = c.get("rubro_slug") in (None, "", "otros")
    sin_texto = all(_vacio(c.get(k)) for k in
                    ("subcategoria", "descripcion", "prod_obs_human", "prod_det_ia"))
    a_clasificar = bool(re.search(r"a clasificar", c.get("nombre") or "", re.I))
    return (sin_rubro and sin_texto) or a_clasificar


def is_business_indexable(c: dict) -> bool:
    return (bool(c.get("activo", True)) and not c.get("suspendido")
            and not is_business_thin(c))


# ── armado de URLs ───────────────────────────────────────────────────────────
def _sitio() -> str:
    return settings.sitio_url.rstrip("/")


def business_urls(comercios: list[dict]) -> list[str]:
    """URLs de las fichas indexables, sin repetir y en orden."""
    sitio = _sitio()
    vistas: dict[str, None] = {}
    for c in comercios:
        slug = (c.get("slug") or "").strip()
        if slug and is_business_indexable(c):
            vistas[f"{sitio}/comercios/{slug}"] = None
    return list(vistas)


def fixed_urls() -> list[str]:
    sitio = _sitio()
    return [sitio + r for r in RUTAS_FIJAS]


# ── habilitación ─────────────────────────────────────────────────────────────
def key_is_valid(key: str | None = None) -> bool:
    return bool(_CLAVE_VALIDA.match((key if key is not None else settings.indexnow_key) or ""))


def habilitado() -> bool:
    """Sólo en producción y sólo con una clave válida. Sin eso el loop no arranca."""
    return (settings.indexnow_worker
            and (settings.app_env or "").strip().lower() == "prod"
            and key_is_valid())


# ── envío ────────────────────────────────────────────────────────────────────
def submit(urls: list[str]) -> bool:
    """Manda las URLs a IndexNow. True si todos los pedidos fueron aceptados
    (200/202). NUNCA lanza: ante un error loguea `indexnow_failed` y devuelve False."""
    urls = list(dict.fromkeys(u for u in urls if u))
    if not urls:
        return True
    if not key_is_valid():
        logger.warning("indexnow_failed", motivo="sin_clave_valida", urls=len(urls))
        return False
    sitio = _sitio()
    host = urlsplit(sitio).netloc
    todo_ok = True
    for i in range(0, len(urls), MAX_URLS_POR_PEDIDO):
        lote = urls[i:i + MAX_URLS_POR_PEDIDO]
        cuerpo = {
            "host": host,
            "key": settings.indexnow_key,
            "keyLocation": f"{sitio}/{settings.indexnow_key}.txt",
            "urlList": lote,
        }
        try:
            r = httpx.post(settings.indexnow_endpoint, json=cuerpo, timeout=10.0,
                           headers={"Content-Type": "application/json; charset=utf-8"})
            if r.status_code in (200, 202):
                logger.info("indexnow_submitted", urls=len(lote), status=r.status_code,
                            ejemplo=lote[0])
            else:
                todo_ok = False
                logger.warning("indexnow_failed", status=r.status_code, urls=len(lote),
                               detalle=(r.text or "")[:200])
        except Exception as exc:  # noqa: BLE001
            todo_ok = False
            logger.warning("indexnow_failed", error=str(exc)[:200], urls=len(lote))
    return todo_ok


def _a_datetime(v) -> datetime | None:
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None


def run_once(repo, cursor: datetime, incluir_fijas: bool = False) -> tuple[datetime, int]:
    """Una vuelta: avisa las fichas cambiadas desde `cursor`. Devuelve
    `(cursor_nuevo, cantidad_enviada)`. Si el envío falla el cursor NO avanza (se
    reintenta en la vuelta siguiente; repetir es inocuo). Nunca lanza."""
    try:
        filas = repo.comercios_para_indexnow(cursor.isoformat())
    except Exception as exc:  # noqa: BLE001
        logger.warning("indexnow_failed", error=str(exc)[:200], etapa="leer_comercios")
        return cursor, 0
    urls = business_urls(filas)
    if incluir_fijas:
        urls += fixed_urls()
    if not urls:
        return _avanzar(cursor, filas), 0
    if not submit(urls):
        return cursor, 0
    return _avanzar(cursor, filas), len(urls)


def _avanzar(cursor: datetime, filas: list[dict]) -> datetime:
    """El cursor pasa al `updated_at` más nuevo visto (incluidas las fichas finas:
    no tiene que volver a mirarlas en cada vuelta)."""
    fechas = [d for d in (_a_datetime(f.get("updated_at")) for f in filas) if d]
    return max(fechas + [cursor])


def cursor_inicial() -> datetime:
    """Al arrancar: ahora - 1 h (repetir lo reciente es inocuo)."""
    return datetime.now(timezone.utc) - timedelta(hours=1)
