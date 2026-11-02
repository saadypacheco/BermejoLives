"""Lado PADRE del render de las piezas (docs/contenido-redes-tecnico.md §5.4).

`render_tick` hace UNA vuelta del loop de `main.py`: mira que se pueda renderizar (ffmpeg, disco),
recupera las piezas colgadas, toma la `queued` más vieja, arma el `job.json`, lanza el
subproceso (`content_render_job`, con `nice` e `ionice` donde existen), y según lo que
devuelva deja la pieza lista para revisar o la reintenta.

UNO A LA VEZ, EN DOS NIVELES
============================
- En este proceso: un candado en memoria (`_lock`).
- En la base: la toma es un UPDATE condicional (`... WHERE status = 'queued'`). Aunque alguien
  levante dos workers de uvicorn, no hay dos renders de la misma pieza.

LAS FALLAS
==========
Reintentable (timeout, ffmpeg que murió, memoria): `attempts + 1`; con menos de
`CONTENT_RENDER_MAX_ATTEMPTS`, vuelve a `queued` esperando 10 min × intento; si no, `failed`.
No reintentable (faltan fotos, fuente ausente): `failed` directo. Una pieza `failed` no
consume la cuota del suscriptor: el selector de la semana siguiente la vuelve a ofrecer.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import structlog

from app.core.config import settings
from app.services import content_storage

logger = structlog.get_logger()

_lock = threading.Lock()
_estado: dict = {"actual": None, "ultimo": None, "avisado_sin_ffmpeg": False, "avisado_dir": False,
                 "avisado_disco": False}

#: Mínimo de fotos que sirven para armar el video (las dos plantillas).
MIN_FOTOS = 4
#: Margen sobre el timeout antes de dar una pieza por colgada.
MARGEN_COLGADA_SEG = 120
#: Un video más pesado que esto se avisa en el log (no falla).
VIDEO_PESADO_BYTES = 15 * 1024 * 1024

_RAIZ_BACKEND = Path(__file__).resolve().parents[2]


def ffmpeg_disponible() -> bool:
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def estado_del_worker() -> str:
    """`disabled | unsafe_dir | no_ffmpeg | paused_disk | running | idle` (GET /admin/content/status)."""
    if not settings.content_render_worker:
        return "disabled"
    if not content_storage.dir_seguro():
        return "unsafe_dir"
    if not ffmpeg_disponible():
        return "no_ffmpeg"
    if _estado["actual"]:
        return "running"
    if content_storage.disco_pausado():
        return "paused_disk"
    return "idle"


def pieza_en_curso() -> str | None:
    return _estado["actual"]


def ultimo_render() -> dict | None:
    return _estado["ultimo"]


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# ───────────────────────────────────────────────────────────── el subproceso

def _matar(proc: subprocess.Popen) -> None:
    """Mata el subproceso y lo que lanzó (ffmpeg). En POSIX, el grupo entero."""
    try:
        if os.name == "posix":
            import signal

            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        else:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, timeout=15)
    except Exception:  # noqa: BLE001
        pass
    try:
        proc.kill()
    except Exception:  # noqa: BLE001
        pass


def comando_del_job(job_path: Path) -> list[str]:
    cmd = [sys.executable, "-m", "app.services.content_render_job", "--job", str(job_path)]
    prefijo: list[str] = []
    if os.name == "posix":
        if shutil.which("nice"):
            prefijo += ["nice", "-n", "19"]
        if shutil.which("ionice"):
            prefijo += ["ionice", "-c", "3"]
    return prefijo + cmd


def _correr_subproceso(job_path: Path) -> dict:
    """Corre el job y devuelve su JSON (`{ok, ...}`). Al vencer `CONTENT_RENDER_TIMEOUT_SEG` lo mata
    (el grupo entero) y devuelve una falla reintentable."""
    kwargs: dict = {}
    if os.name == "posix":
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(comando_del_job(job_path), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, cwd=str(_RAIZ_BACKEND), **kwargs)
    try:
        salida, err = proc.communicate(timeout=settings.content_render_timeout_seg)
    except subprocess.TimeoutExpired:
        _matar(proc)
        try:
            proc.communicate(timeout=10)
        except Exception:  # noqa: BLE001
            pass
        return {"ok": False, "error": f"El render pasó de {settings.content_render_timeout_seg} s", "retryable": True}
    lineas = [l for l in (salida or "").splitlines() if l.strip()]
    try:
        return json.loads(lineas[-1])
    except (IndexError, ValueError):
        return {"ok": False, "retryable": True,
                "error": f"El render terminó sin respuesta (código {proc.returncode}): {(err or '')[-200:]}"}


# ───────────────────────────────────────────────────────────── el trabajo

def _preparar_job(crepo, pieza: dict) -> tuple[Path, dict, list[dict]] | None:
    """Arma `tmp/<piece_id>/job.json`. None si no quedan fotos suficientes (el caller falla la pieza)."""
    fuentes = crepo.list_sources(pieza["id"])
    slides = []
    usadas = []
    for f in fuentes:
        ruta = content_storage.resolver_fuente(f.get("source_type"), f.get("file_ref"))
        if ruta is None:
            logger.info("content.fuente_no_existe", pieza=pieza["id"], tipo=f.get("source_type"))
            continue
        slides.append({"path": str(ruta), "caption_fact": f.get("caption_fact")})
        usadas.append(f)
    if len(slides) < MIN_FOTOS:
        return None
    tmp = content_storage.carpeta_tmp(pieza["id"])
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)
    job = {
        "piece_id": pieza["id"], "template": pieza.get("template"),
        "template_version": pieza.get("template_version") or 1,
        "facts": pieza.get("facts") or {}, "slides": slides,
        "out_video": str(tmp / "video.mp4"), "out_cover": str(tmp / "cover.jpg"),
        "width": 1080, "height": 1920, "fps": 30, "memory_mb": settings.content_render_memory_mb,
    }
    ruta_job = tmp / "job.json"
    ruta_job.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
    return ruta_job, job, usadas


def _registrar_falla(crepo, pieza: dict, error: str, retryable: bool, ahora: datetime) -> dict | None:
    """Deja la pieza en `queued` (con espera) o en `failed`, según los intentos que lleve."""
    intentos = int(pieza.get("render_attempts") or 0) + 1
    if retryable and intentos < settings.content_render_max_attempts:
        patch = {"status": "queued", "render_attempts": intentos, "render_error": error[:500],
                 "render_next_at": _iso(ahora + timedelta(minutes=10 * intentos)), "render_started_at": None}
    else:
        patch = {"status": "failed", "render_attempts": intentos, "render_error": error[:500],
                 "render_started_at": None}
    return crepo.update_piece(pieza["id"], patch, if_status="rendering")


def recuperar_colgadas(crepo, ahora: datetime | None = None) -> int:
    """Las `rendering` que llevan más que el timeout + 120 s volvieron a su suerte: cuentan como
    un intento fallido. Devuelve cuántas recuperó."""
    ahora = ahora or _ahora()
    corte = ahora - timedelta(seconds=settings.content_render_timeout_seg + MARGEN_COLGADA_SEG)
    n = 0
    for p in crepo.stuck_rendering(_iso(corte)):
        if _registrar_falla(crepo, p, "El render quedó colgado", True, ahora):
            n += 1
            logger.warning("content.render_colgada", pieza=p["id"])
    return n


def _mover_resultado(pieza: dict, job: dict, ahora: datetime) -> tuple[str, str, int]:
    """De `tmp/` a `renders/<aaaa-mm>/<piece_id>/`. Devuelve (video, portada, bytes)."""
    carpeta = content_storage.carpeta_de_render(pieza["id"], ahora)
    rel_video, rel_cover = f"{carpeta}/video.mp4", f"{carpeta}/cover.jpg"
    for rel, origen in ((rel_video, job["out_video"]), (rel_cover, job["out_cover"])):
        destino = content_storage.safe_path(rel)
        if destino is None:
            raise OSError("ruta de render fuera del directorio")
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(origen, destino)
    return rel_video, rel_cover, content_storage.safe_path(rel_video).stat().st_size


def render_tick(crepo, ahora: datetime | None = None) -> dict | None:
    """Una vuelta del loop. Devuelve un resumen de lo que hizo (o None si no había nada)."""
    if not _lock.acquire(blocking=False):
        return None
    try:
        return _tick(crepo, ahora or _ahora())
    finally:
        _lock.release()


def _tick(crepo, ahora: datetime) -> dict | None:
    if not content_storage.dir_seguro():
        if not _estado["avisado_dir"]:
            logger.error("content.dir_inseguro", detalle="CONTENT_DIR queda dentro de FOTOS_DIR (o al revés)")
            _estado["avisado_dir"] = True
        return None
    if not ffmpeg_disponible():
        if not _estado["avisado_sin_ffmpeg"]:
            logger.warning("content.render_no_disponible", detalle="ffmpeg/ffprobe no están en el PATH")
            _estado["avisado_sin_ffmpeg"] = True
        return None
    if content_storage.disco_pausado():
        if not _estado["avisado_disco"]:
            logger.warning("content.disk_low", libre=content_storage.libre_bytes())
            _estado["avisado_disco"] = True
        return None
    _estado["avisado_disco"] = False

    recuperar_colgadas(crepo, ahora)

    pieza = None
    for cand in crepo.list_queued_due(_iso(ahora), 5):
        pieza = crepo.update_piece(
            cand["id"], {"status": "rendering", "render_started_at": _iso(ahora)}, if_status="queued")
        if pieza:
            break
    if not pieza:
        return None

    _estado["actual"] = pieza["id"]
    inicio = time.monotonic()
    tmp = content_storage.carpeta_tmp(pieza["id"])
    try:
        preparado = _preparar_job(crepo, pieza)
        if preparado is None:
            crepo.update_piece(pieza["id"], {"status": "failed", "render_error": "no_sources",
                                             "render_started_at": None}, if_status="rendering")
            logger.warning("content.render_sin_fuentes", pieza=pieza["id"])
            resultado = {"ok": False, "error": "no_sources"}
        else:
            ruta_job, job, usadas = preparado
            r = _correr_subproceso(ruta_job)
            if r.get("ok"):
                rel_video, rel_cover, peso = _mover_resultado(pieza, job, ahora)
                previo = (pieza.get("video_path"), pieza.get("cover_path"))
                actualizada = crepo.update_piece(pieza["id"], {
                    "status": "ready_for_review", "video_path": rel_video, "cover_path": rel_cover,
                    "video_bytes": peso, "duration_s": r.get("duration_s"), "render_ms": r.get("render_ms"),
                    "render_error": None, "render_started_at": None, "files_purged_at": None,
                }, if_status="rendering")
                if actualizada is None:
                    # Mientras se armaba, alguien la saltó (autorización retirada): el archivo sobra.
                    content_storage.borrar(rel_video)
                    content_storage.borrar(rel_cover)
                else:
                    for viejo in previo:
                        if viejo and viejo not in (rel_video, rel_cover):
                            content_storage.borrar(viejo)
                    ids = [u["source_id"] for u in usadas if u.get("source_type") == "asset" and u.get("source_id")]
                    if ids:
                        crepo.bump_asset_use(ids, _iso(ahora))
                    if peso > VIDEO_PESADO_BYTES:
                        logger.warning("content.render_pesado", pieza=pieza["id"], bytes=peso)
                    logger.info("content.render_terminado", pieza=pieza["id"], render_ms=r.get("render_ms"),
                                duration_s=r.get("duration_s"), bytes=peso)
                resultado = {"ok": True, **r}
            else:
                error = str(r.get("error") or "Falló el render")
                _registrar_falla(crepo, pieza, error, bool(r.get("retryable", True)), ahora)
                logger.warning("content.render_fallo", pieza=pieza["id"], error=error[:200],
                               reintentable=bool(r.get("retryable", True)))
                resultado = r
    except Exception as exc:  # noqa: BLE001
        logger.warning("content.render_error", pieza=pieza["id"], error=str(exc)[:200], exc_info=True)
        try:
            _registrar_falla(crepo, pieza, f"{type(exc).__name__}: {exc}", True, ahora)
        except Exception:  # noqa: BLE001
            logger.warning("content.render_falla_sin_registrar", pieza=pieza["id"], exc_info=True)
        resultado = {"ok": False, "error": str(exc)}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        _estado["actual"] = None
    _estado["ultimo"] = {"piece_id": pieza["id"], "at": _iso(_ahora()),
                         "ms": resultado.get("render_ms") or round((time.monotonic() - inicio) * 1000),
                         "ok": bool(resultado.get("ok")), "error": resultado.get("error")}
    return {"piece_id": pieza["id"], "ok": bool(resultado.get("ok")), "error": resultado.get("error")}
