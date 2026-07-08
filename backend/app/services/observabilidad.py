"""Observabilidad propia: errores y performance de front/back, sin terceros.

Un insert que falla acá nunca debe tumbar el request que lo disparó — toda
falla queda silenciada (con un warning en structlog) y listo.
"""
import hashlib
import random
from datetime import datetime, timedelta, timezone

import structlog

from app.db.session import get_supabase

logger = structlog.get_logger()

_LIMPIEZA_PROBABILIDAD = 1 / 200  # 1 de cada ~200 inserts dispara limpieza de filas viejas
_RETENCION_DIAS = 30


def _fingerprint(origen: str, mensaje: str, ruta: str | None) -> str:
    base = f"{origen}|{mensaje}|{ruta or ''}"
    return hashlib.sha256(base.encode()).hexdigest()[:32]


def registrar_error(
    origen: str,
    mensaje: str,
    stack: str | None = None,
    ruta: str | None = None,
    status_code: int | None = None,
    contexto: dict | None = None,
) -> None:
    try:
        db = get_supabase()
        fp = _fingerprint(origen, mensaje, ruta)
        existente = db.table("error_logs").select("id, ocurrencias").eq("fingerprint", fp).limit(1).execute()
        if existente.data:
            row = existente.data[0]
            db.table("error_logs").update({
                "ocurrencias": row["ocurrencias"] + 1,
                "ultima_vez": datetime.now(timezone.utc).isoformat(),
                "resuelto": False,
            }).eq("id", row["id"]).execute()
        else:
            db.table("error_logs").insert({
                "fingerprint": fp,
                "origen": origen,
                "nivel": "error",
                "mensaje": mensaje[:2000],
                "stack": (stack or "")[:8000] or None,
                "ruta": ruta,
                "status_code": status_code,
                "contexto": contexto,
                "ocurrencias": 1,
            }).execute()
        _limpiar_si_toca(db)
    except Exception:
        logger.warning("observabilidad.registrar_error_fallo", mensaje=mensaje[:200])


def registrar_perf(origen: str, ruta: str, metrica: str, valor_ms: float, repetida: bool | None = None) -> None:
    try:
        db = get_supabase()
        db.table("perf_events").insert({
            "origen": origen,
            "ruta": ruta,
            "metrica": metrica,
            "valor_ms": valor_ms,
            "repetida": repetida,
        }).execute()
        _limpiar_si_toca(db)
    except Exception:
        logger.warning("observabilidad.registrar_perf_fallo", ruta=ruta, metrica=metrica)


def _limpiar_si_toca(db) -> None:
    if random.random() > _LIMPIEZA_PROBABILIDAD:
        return
    corte = (datetime.now(timezone.utc) - timedelta(days=_RETENCION_DIAS)).isoformat()
    db.table("perf_events").delete().lt("created_at", corte).execute()
    db.table("error_logs").delete().eq("resuelto", True).lt("ultima_vez", corte).execute()
