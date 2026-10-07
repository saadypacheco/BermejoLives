"""El tablero del panel: todos los números de Inicio en una sola respuesta
(docs/admin-rediseno.md §3-§5).

Los conteos de la base salen de UNA función SQL (`admin_resumen`, 0139): nunca
se bajan filas para contarlas en Python, porque PostgREST corta en 1000 sin
avisar. Esta capa suma lo que no está en la base (las consultas de Reservalo,
los certificados TLS y las fechas de vencimientos) y rellena los días vacíos de
la serie.

Una parte que falla viene en `null` y se loguea `admin.resumen_parcial`; el resto
sigue. Lo único que tumba la respuesta es no poder contar los comercios (sin
eso no hay tablero): `ResumenNoDisponible`.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from typing import Any, Callable

import structlog

from app.services import cargas, vencimientos

logger = structlog.get_logger()

DIAS_SERIE = 30

_CLAVES_COMERCIOS = ("total", "verificados", "sin_verificar", "sin_horario", "horario_estimado",
                     "sin_whatsapp", "sin_foto", "sin_rubro")
_CLAVES_POR_CIUDAD = ("total", "sin_verificar", "sin_horario")


class ResumenNoDisponible(Exception):
    """No se pudo contar lo esencial (los comercios): no hay tablero que mostrar."""


def _entero(valor: Any) -> int | None:
    """Un número de la base como int; None si es null o no se entiende (un número
    ilegible es «no sé», nunca un 0 inventado)."""
    if valor is None or isinstance(valor, bool):
        return None
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _parcial(parte: str, motivo: str) -> None:
    logger.warning("admin.resumen_parcial", parte=parte, motivo=motivo[:200])


def _comercios(raw: dict) -> dict:
    return {k: _entero(raw.get(k)) or 0 for k in _CLAVES_COMERCIOS}


def _por_ciudad(raw: list | None) -> list[dict]:
    salida = []
    for c in raw or []:
        if not isinstance(c, dict):
            continue
        salida.append({"slug": c.get("slug"), "nombre": c.get("nombre"),
                       **{k: _entero(c.get(k)) or 0 for k in _CLAVES_POR_CIUDAD}})
    return salida


def rellenar_serie(filas: list[dict], hoy: date, dias: int = DIAS_SERIE) -> list[dict]:
    """Un renglón por día, del más viejo a `hoy`: los días sin nada en 0.

    `filas` es lo que devuelve la base —sólo los días con algo—. Lo que caiga
    fuera de la ventana se descarta."""
    por_dia: dict[str, dict] = {}
    for f in filas or []:
        if isinstance(f, dict) and f.get("dia"):
            por_dia[str(f["dia"])[:10]] = f
    serie = []
    for atras in range(dias - 1, -1, -1):
        dia = (hoy - timedelta(days=atras)).isoformat()
        f = por_dia.get(dia) or {}
        serie.append({"dia": dia, "altas": _entero(f.get("altas")) or 0,
                      "visitas": _entero(f.get("visitas")) or 0,
                      "contactos": _entero(f.get("contactos")) or 0})
    return serie


def _intentar(parte: str, fn: Callable[[], Any], caidas: set[str]) -> Any:
    """Corre una parte; si falla devuelve None y lo deja dicho en el log."""
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 — una parte caída no tumba el tablero
        caidas.add(parte)
        _parcial(parte, f"{type(exc).__name__}: {exc}")
        return None


def _vencimientos(repo) -> int:
    """Lo que mostraría la pestaña Vencimientos como alertas: fechas cargadas +
    certificados medidos en vivo."""
    return vencimientos.contar_alertas(repo.list_vencimientos()) + vencimientos.alertas_de_certificados()


def _reclamos(raw_reclamos: int | None, consultas: int | None) -> int | None:
    """Reclamos + consultas de Reservalo. Si una de las dos no se pudo saber, el
    total no se sabe: un 3 que en realidad es 3 + «no sé cuántas» es un número
    que miente."""
    if raw_reclamos is None or consultas is None:
        return None
    return raw_reclamos + consultas


def armar_resumen(repo, reservalo, ciudad: str | None, hoy: date | None = None) -> dict:
    """La respuesta de `GET /admin/resumen`, con la forma de `ResumenAdmin`
    (frontend/lib/api.ts)."""
    ciudad = (ciudad or "").strip() or None
    hoy = hoy or cargas.hoy_bolivia()
    caidas: set[str] = set()   # partes que ya dejaron su `admin.resumen_parcial`

    # Las tres fuentes son independientes y dos tocan la red: en paralelo, el
    # tablero tarda lo que la más lenta y no la suma.
    with ThreadPoolExecutor(max_workers=3) as pool:
        f_sql = pool.submit(repo.resumen_admin, ciudad, hoy)
        f_venc = pool.submit(_intentar, "pendientes.vencimientos", lambda: _vencimientos(repo), caidas)
        f_res = pool.submit(_intentar, "pendientes.reclamos", reservalo.contar_consultas_pendientes, caidas)
        try:
            sql = f_sql.result()
        except Exception as exc:  # noqa: BLE001
            logger.error("admin.resumen_fallo", ciudad=ciudad, error=f"{type(exc).__name__}: {exc}"[:300])
            sql = None
        vencimientos_n = f_venc.result()
        consultas = f_res.result()

    if not isinstance(sql, dict) or not isinstance(sql.get("comercios"), dict) \
            or not isinstance(sql.get("por_ciudad"), list):
        if sql is not None:
            logger.error("admin.resumen_fallo", ciudad=ciudad, error="respuesta de la base sin comercios")
        raise ResumenNoDisponible()

    pend_raw = sql.get("pendientes") if isinstance(sql.get("pendientes"), dict) else {}
    act_raw = sql.get("actividad") if isinstance(sql.get("actividad"), dict) else {}

    pendientes = {
        "publicaciones": _entero(pend_raw.get("publicaciones")),
        "comercios_sin_verificar": _entero(pend_raw.get("comercios_sin_verificar")),
        "pagos": _entero(pend_raw.get("pagos")),
        "reclamos": _reclamos(_entero(pend_raw.get("reclamos")), consultas),
        "cambio_numero": _entero(pend_raw.get("cambio_numero")),
        "suscripciones": _entero(pend_raw.get("suscripciones")),
        "vencimientos": vencimientos_n,
        "recepcion_sin_comercio": _entero(pend_raw.get("recepcion_sin_comercio")),
    }

    serie_raw = act_raw.get("serie_30d")
    actividad = {
        "visitas_7d": _entero(act_raw.get("visitas_7d")),
        "contactos_7d": _entero(act_raw.get("contactos_7d")),
        "serie_30d": rellenar_serie(serie_raw, hoy) if isinstance(serie_raw, list) else None,
    }

    # Lo que quedó null y todavía no dejó rastro: la base no pudo calcularlo, o
    # (sólo los reclamos) Reservalo no contestó.
    for parte, valor in [*((f"pendientes.{k}", v) for k, v in pendientes.items()),
                         *((f"actividad.{k}", v) for k, v in actividad.items())]:
        if valor is None and parte not in caidas:
            motivo = ("Reservalo no contestó o la base no contó los reclamos"
                      if parte == "pendientes.reclamos"
                      else "la base no pudo calcularlo (ver el WARNING de Postgres)")
            _parcial(parte, motivo)

    return {
        "ciudad": ciudad,
        "comercios": _comercios(sql["comercios"]),
        "por_ciudad": _por_ciudad(sql["por_ciudad"]),
        "pendientes": pendientes,
        "actividad": actividad,
    }
