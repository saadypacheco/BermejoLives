"""Lado PADRE del render de las piezas (docs/contenido-redes-tecnico.md §5.4 y §16.5).

`render_tick` hace UNA vuelta del loop de `main.py`: mira que se pueda renderizar, recupera las piezas
colgadas, toma la `queued` más vieja, arma la carpeta del job y según lo que devuelva el motor deja la pieza
lista para revisar o la reintenta.

DOS MOTORES (`CONTENT_RENDER_ENGINE`)
=====================================
- `kit` (por defecto, §16): el contenedor `reels` (Chromium + ffmpeg) dibuja la plantilla v2 del kit. Acá se
  arma `tmp/<piece_id>/` con las fotos ya preparadas (`s0.jpg`, `s1.jpg`…) y el `job.json` de §16.4, y se le
  pide el render por HTTP (`POST /render`, con token). Sin `RENDERER_TOKEN`, o si `/health` no contesta, el
  worker no toma trabajos y `estado_del_worker` dice `no_renderer`.
- `pillow` (respaldo, y la PC sin Docker): el motor v1, un subproceso de este mismo backend
  (`content_render_job`, con `nice` e `ionice` donde existen).

UNO A LA VEZ, EN DOS NIVELES
============================
- En este proceso: un candado en memoria (`_lock`).
- En la base: la toma es un UPDATE condicional (`... WHERE status = 'queued'`). Aunque alguien
  levante dos workers de uvicorn, no hay dos renders de la misma pieza. (El contenedor además contesta 409
  si ya tiene uno en curso: es reintentable.)

LAS FALLAS
==========
Reintentable (timeout, red caída, contenedor ocupado, memoria): `attempts + 1`; con menos de
`CONTENT_RENDER_MAX_ATTEMPTS`, vuelve a `queued` esperando 10 min × intento; si no, `failed`.
No reintentable (faltan fotos, fuente ausente, token rechazado): `failed` directo. Una pieza `failed` no
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

import httpx
import structlog

from app.core.config import settings
from app.services import content_consent, content_storage, content_video_texts

logger = structlog.get_logger()

_lock = threading.Lock()
_estado: dict = {"actual": None, "ultimo": None, "avisado_sin_ffmpeg": False, "avisado_dir": False,
                 "avisado_disco": False, "avisado_sin_renderer": False}

#: Mínimo de fotos que sirven para armar el video (las dos plantillas).
MIN_FOTOS = 4
#: El video v2 lleva de 4 a 6 fotos (§16.4).
MAX_FOTOS_KIT = 6
#: Lado mayor de las fotos que se le pasan al contenedor (§16.4).
LADO_FOTO_KIT = 1200
#: Cuánto vale la respuesta de `/health` del contenedor antes de volver a preguntar, y cuánto se espera.
SALUD_CACHE_SEG = 10
SALUD_TIMEOUT_SEG = 3
_salud: dict = {"hasta": 0.0, "ok": False}
#: Margen sobre el timeout antes de dar una pieza por colgada.
MARGEN_COLGADA_SEG = 120
#: Un video más pesado que esto se avisa en el log (no falla).
VIDEO_PESADO_BYTES = 15 * 1024 * 1024

_RAIZ_BACKEND = Path(__file__).resolve().parents[2]


def ffmpeg_disponible() -> bool:
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def motor() -> str:
    """`kit` (el contenedor `reels`, por defecto) o `pillow` (el motor v1 de este backend)."""
    return "pillow" if (settings.content_render_engine or "").strip().lower() == "pillow" else "kit"


def reiniciar_salud() -> None:
    _salud.update({"hasta": 0.0, "ok": False})


def renderer_vivo() -> bool:
    """¿El contenedor `reels` contesta `GET /health`? La respuesta se cachea `SALUD_CACHE_SEG` segundos: el loop
    pregunta cada vuelta y el panel cada vez que se abre el estado; no hay que pegarle al contenedor cada vez."""
    ahora = time.monotonic()
    if ahora < _salud["hasta"]:
        return _salud["ok"]
    ok = False
    try:
        r = httpx.get(f"{settings.renderer_url.rstrip('/')}/health", timeout=SALUD_TIMEOUT_SEG)
        datos = r.json() if r.status_code == 200 else {}
        ok = bool(isinstance(datos, dict) and datos.get("ok") and datos.get("chromium") is not False
                  and datos.get("ffmpeg") is not False)
    except Exception:  # noqa: BLE001
        ok = False
    _salud.update({"hasta": ahora + SALUD_CACHE_SEG, "ok": ok})
    return ok


def renderer_disponible() -> bool:
    """Con `kit` hace falta el token y que el contenedor conteste."""
    return bool(settings.renderer_token) and renderer_vivo()


def estado_del_worker() -> str:
    """`disabled | unsafe_dir | no_renderer | no_ffmpeg | paused_disk | running | idle`
    (GET /admin/content/status). `no_renderer`: con el motor `kit`, falta `RENDERER_TOKEN` o `/health` del
    contenedor `reels` no contesta; `no_ffmpeg` es lo mismo para el motor `pillow`."""
    if not settings.content_render_worker:
        return "disabled"
    if not content_storage.dir_seguro():
        return "unsafe_dir"
    if motor() == "kit":
        if not renderer_disponible():
            return "no_renderer"
    elif not ffmpeg_disponible():
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


#: Lo ÚNICO que el subproceso hereda del entorno: dónde están los programas y el idioma. El render no necesita
#: ninguna clave (ni de la base ni de Gemini): lo que haya en el entorno del backend no tiene que viajar.
ENV_PERMITIDAS = ("PATH", "LANG", "LC_ALL", "PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "HOME", "TMPDIR", "TEMP", "TMP",
                  "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "LD_LIBRARY_PATH")


def entorno_del_subproceso() -> dict[str, str]:
    env = {k: os.environ[k] for k in ENV_PERMITIDAS if k in os.environ}
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _correr_subproceso(job_path: Path) -> dict:
    """Corre el job y devuelve su JSON (`{ok, ...}`). Al vencer `CONTENT_RENDER_TIMEOUT_SEG` lo mata
    (el grupo entero) y devuelve una falla reintentable."""
    kwargs: dict = {}
    if os.name == "posix":
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(comando_del_job(job_path), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, cwd=str(_RAIZ_BACKEND), env=entorno_del_subproceso(), **kwargs)
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


# ───────────────────────────────────────────────────────────── el contenedor `reels` (motor kit)

def _pedir_render_kit(piece_id: str) -> dict:
    """`POST /render` al contenedor `reels` (§16.4) y su respuesta como `{ok, ...}` o `{ok: False, error,
    retryable}`. El token viaja sólo en la cabecera y nunca se loguea.

    Reintentable: 409 (ya hay un render en curso), errores de red, timeout, 5xx y respuestas ilegibles.
    NO reintentable: 401 (el token no coincide: reintentar no lo arregla) y 400 (el pedido está mal)."""
    url = f"{settings.renderer_url.rstrip('/')}/render"
    plazo = settings.content_render_timeout_seg
    try:
        r = httpx.post(url, json={"piece_id": piece_id}, headers={"Authorization": f"Bearer {settings.renderer_token}"},
                       timeout=httpx.Timeout(plazo, connect=10))
    except httpx.TimeoutException:
        return {"ok": False, "error": f"El render pasó de {plazo} s", "retryable": True}
    except httpx.HTTPError as exc:
        return {"ok": False, "retryable": True,
                "error": f"No se pudo hablar con el armador de videos ({type(exc).__name__})"}
    if r.status_code == 409:
        return {"ok": False, "error": "El armador de videos está ocupado", "retryable": True}
    if r.status_code == 401:
        logger.error("content.renderer_token_rechazado")
        return {"ok": False, "retryable": False,
                "error": "El armador de videos rechazó el token: revise RENDERER_TOKEN en el backend y en renderer/.env"}
    if r.status_code == 400:
        return {"ok": False, "retryable": False, "error": "El armador de videos rechazó el pedido"}
    if r.status_code != 200:
        return {"ok": False, "retryable": True, "error": f"El armador de videos contestó {r.status_code}"}
    try:
        datos = r.json()
    except ValueError:
        datos = None
    if not isinstance(datos, dict) or "ok" not in datos:
        return {"ok": False, "retryable": True, "error": "El armador de videos contestó algo ilegible"}
    if datos.get("ok"):
        return datos
    return {"ok": False, "error": str(datos.get("error") or "Falló el render")[:500],
            "retryable": bool(datos.get("retryable", True))}


def _preparar_foto(origen: Path, destino: Path) -> bool:
    """Una foto lista para el contenedor (§16.4): reorientada, RGB, lado mayor 1200 px (sólo se reduce), retoque N1
    suave (el mismo del motor v1), JPEG q90 y SIN EXIF (Pillow no lo copia). False si no se pudo leer."""
    from PIL import Image, ImageOps

    from app.services.content_render_job import n1_suave

    try:
        with Image.open(origen) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            im.thumbnail((LADO_FOTO_KIT, LADO_FOTO_KIT), Image.LANCZOS)
            im = n1_suave(im)
            im.save(destino, format="JPEG", quality=90)
        os.chmod(destino, 0o644)
        return True
    except Exception:  # noqa: BLE001
        logger.warning("content.foto_no_se_pudo_preparar", ruta=str(origen)[-60:], exc_info=True)
        return False


# ───────────────────────────────────────────────────────────── el trabajo

class PiezaBloqueada(Exception):
    """La pieza no se puede armar: un comercio retiró la autorización o se dio de baja. `motivo` es el
    `skip_reason` con el que se saltea."""

    def __init__(self, motivo: str):
        super().__init__(motivo)
        self.motivo = motivo


def _fuentes_vigentes(crepo, pieza: dict) -> list[dict]:
    """Las fuentes de la pieza que todavía valen. Antes de dibujar nada se relee lo que pudo cambiar desde que se
    armó la pieza: la autorización y el estado de CADA comercio de las fuentes (si no valen, `PiezaBloqueada`) y cada
    foto del banco (una que se dio de baja o se marcó «no usar en redes» no entra al video)."""
    fuentes = crepo.list_sources(pieza["id"])
    motivo = content_consent.motivo_de_comercios(crepo, pieza, fuentes)
    if motivo:
        raise PiezaBloqueada(motivo)
    no_sirven = {id(f) for f in content_consent.fuentes_no_usables(crepo, fuentes)}
    for f in fuentes:
        if id(f) in no_sirven:
            logger.info("content.fuente_ya_no_sirve", pieza=pieza["id"], fuente=f.get("source_id"))
    return [f for f in fuentes if id(f) not in no_sirven]


def _asegurar_v2(crepo, pieza: dict) -> dict:
    """Una pieza v1 (o una v2 que quedó sin textos) que se arma con el motor `kit` primero recibe sus textos del
    video y pasa a v2 (§16.5). Devuelve la pieza actualizada."""
    if (pieza.get("template_version") or 1) >= 2 and pieza.get("video_texts"):
        return pieza
    nueva = content_video_texts.proponer_y_guardar(crepo, pieza, {"template_version": 2}, if_status="rendering")
    logger.info("content.pieza_pasada_a_v2", pieza=pieza["id"])
    return nueva or crepo.get_piece(pieza["id"]) or pieza


def _preparar_job(crepo, pieza: dict) -> tuple[Path, dict, list[dict]] | None:
    """Arma la carpeta del job: `tmp/<piece_id>/`. None si no quedan fotos suficientes (el caller falla la pieza).
    Devuelve (ruta del job.json, el job con las rutas de salida ABSOLUTAS, las fuentes que entraron)."""
    if motor() == "kit":
        return _preparar_job_kit(crepo, pieza)
    return _preparar_job_pillow(crepo, pieza)


def _preparar_job_kit(crepo, pieza: dict) -> tuple[Path, dict, list[dict]] | None:
    """El job v2 de §16.4: `job.json` + las fotos `s0.jpg`… ya preparadas. El contenedor sólo lee esa carpeta y
    sólo escribe `video.mp4` y `cover.jpg` ahí. Los textos del cierre salen siempre de la base (fijos)."""
    vigentes = _fuentes_vigentes(crepo, pieza)
    tmp = content_storage.carpeta_tmp(pieza["id"])
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)
    # El contenedor `reels` corre como usuario NO root (pwuser) y este backend como root: la carpeta del job
    # tiene que ser escribible por cualquiera (0o777, con chmod explícito: el umask del proceso no es de fiar) o
    # reels no puede dejar `video.mp4` ni `cover.jpg`. Las fotos y el job.json son 0o644 (legibles).
    try:
        os.chmod(tmp, 0o777)
    except OSError:
        pass
    slides, usadas = [], []
    for f in vigentes:
        if len(slides) >= MAX_FOTOS_KIT:
            break
        ruta = content_storage.resolver_fuente(f.get("source_type"), f.get("file_ref"))
        if ruta is None:
            logger.info("content.fuente_no_existe", pieza=pieza["id"], tipo=f.get("source_type"))
            continue
        destino = tmp / f"s{len(slides)}.jpg"
        if not _preparar_foto(ruta, destino):
            continue
        slides.append({"file": destino.name, "chip": f.get("chip_text"), "focus_y": f.get("focus_y")})
        usadas.append(f)
    if len(slides) < MIN_FOTOS:
        return None
    pilar = pieza.get("pillar") or "comercio_del_dia"
    job_json = {
        "version": 2, "piece_id": pieza["id"], "template": "t1", "format": "9x16", "fps": 30,
        "texts": content_video_texts.armar_textos(pieza.get("video_texts") or {}, pilar, pieza.get("facts") or {}),
        "icons": content_video_texts.iconos_de(pilar), "slides": slides,
        "out_video": "video.mp4", "out_cover": "cover.jpg",
    }
    ruta_job = tmp / "job.json"
    ruta_job.write_text(json.dumps(job_json, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(ruta_job, 0o644)
    except OSError:
        pass
    return ruta_job, {**job_json, "out_video": str(tmp / "video.mp4"), "out_cover": str(tmp / "cover.jpg")}, usadas


def _preparar_job_pillow(crepo, pieza: dict) -> tuple[Path, dict, list[dict]] | None:
    """El job del motor v1 (subproceso de este backend): `tmp/<piece_id>/job.json` con las rutas de las fotos."""
    slides = []
    usadas = []
    for f in _fuentes_vigentes(crepo, pieza):
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
    if motor() == "kit":
        if not renderer_disponible():
            if not _estado["avisado_sin_renderer"]:
                logger.warning("content.render_no_disponible", motor="kit",
                               detalle="falta RENDERER_TOKEN o el contenedor reels no contesta /health")
                _estado["avisado_sin_renderer"] = True
            return None
        _estado["avisado_sin_renderer"] = False
    elif not ffmpeg_disponible():
        if not _estado["avisado_sin_ffmpeg"]:
            logger.warning("content.render_no_disponible", motor="pillow", detalle="ffmpeg/ffprobe no están en el PATH")
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
        if motor() == "kit":
            pieza = _asegurar_v2(crepo, pieza)
        preparado = _preparar_job(crepo, pieza)
        if preparado is None:
            crepo.update_piece(pieza["id"], {"status": "failed", "render_error": "no_sources",
                                             "render_started_at": None}, if_status="rendering")
            logger.warning("content.render_sin_fuentes", pieza=pieza["id"])
            resultado = {"ok": False, "error": "no_sources"}
        else:
            ruta_job, job, usadas = preparado
            r = _pedir_render_kit(pieza["id"]) if motor() == "kit" else _correr_subproceso(ruta_job)
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
    except PiezaBloqueada as bloqueo:
        crepo.update_piece(pieza["id"], {"status": "skipped", "skip_reason": bloqueo.motivo, "skipped_by": "sistema",
                                         "skipped_at": _iso(_ahora()), "render_started_at": None},
                           if_status="rendering")
        logger.warning("content.render_pieza_bloqueada", pieza=pieza["id"], motivo=bloqueo.motivo)
        resultado = {"ok": False, "error": bloqueo.motivo}
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
