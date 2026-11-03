"""Arma el video 9:16 de un job: Chromium fotografia cada cuadro y ffmpeg arma el mp4.

Metodo del kit (docs/contenido-redes-tecnico.md, 16.4): se carga la pagina de T1, se espera
a las fuentes y a las imagenes, se pausan todas las animaciones y por cada cuadro se
pone `currentTime` y se captura un JPEG q90 que va por stdin a ffmpeg.

Uso por linea de comandos (lo usa `server.py`, un proceso por render):

    python render.py <carpeta del job> [--deadline-seg N]

Imprime en stdout una sola linea JSON con el resultado.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

import reel_t1
from reel_t1 import ASSETS_DIR, COVER_T, FPS, HEIGHT, OUT_COVER, OUT_VIDEO, WIDTH, JobError

MIN_SECONDS, MAX_SECONDS = 12.0, 20.0
MIN_VIDEO_BYTES = 100 * 1024

FFMPEG_CMD = [
    "ffmpeg", "-y", "-loglevel", "error",
    "-f", "image2pipe", "-c:v", "mjpeg", "-r", str(FPS), "-i", "-",
    "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
    "-shortest",
    "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-b:a", "128k",
    "-movflags", "+faststart",
]


class RenderError(RuntimeError):
    """Fallo del render. `retryable` dice si vale la pena volver a intentar."""

    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


def log(event: str, **kw) -> None:
    print(json.dumps({"event": event, **kw}, ensure_ascii=False), file=sys.stderr, flush=True)


def chromium_path() -> str | None:
    """`CHROME_EXE` permite apuntar a un Chromium propio (PC sin la imagen de Playwright)."""
    return os.environ.get("CHROME_EXE") or None


def _make_route(allowed_files: set[Path], allowed_dirs: list[Path]):
    """Deja pasar solo `file://` dentro de la carpeta del job, de assets/ o la pagina misma."""

    def handler(route):
        url = route.request.url
        ok = False
        if url.startswith("file:"):
            try:
                path = Path(url2pathname(unquote(urlparse(url).path))).resolve()
                ok = path in allowed_files or any(path.is_relative_to(d) for d in allowed_dirs)
            except (OSError, ValueError):
                ok = False
        if ok:
            route.continue_()
        else:
            route.abort()
            log("render.request_bloqueada", url=url[:120])

    return handler


def prepare_page(page, page_file: Path, *, pause: bool = True) -> None:
    """Carga la pagina, espera fuentes e imagenes, ajusta titulos/tecleo y pausa las animaciones."""
    page.goto(page_file.as_uri())
    page.wait_for_load_state("load")
    page.evaluate(
        "Promise.all(['400 40px Poppins','500 40px Poppins','600 40px Poppins','700 40px Poppins']"
        ".map(f => document.fonts.load(f)))"
    )
    page.evaluate("document.fonts.ready")
    page.evaluate("Promise.all([...document.images].map(i => i.decode().catch(() => 0)))")
    page.evaluate(reel_t1.FIT_JS)
    if pause:
        page.evaluate("window.__a = document.getAnimations(); window.__a.forEach(a => a.pause())")


def _ffprobe(path: Path) -> dict:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)],
        capture_output=True, text=True, timeout=30,
    )
    if proc.returncode != 0:
        raise RenderError("ffprobe no pudo leer el video", retryable=False)
    return json.loads(proc.stdout)


def verify_video(path: Path) -> float:
    """ffprobe: 1080x1920, 12 a 20 s, con pista de audio y mas de 100 KB. Devuelve la duracion."""
    size = path.stat().st_size
    if size <= MIN_VIDEO_BYTES:
        raise RenderError(f"El video pesa {size} bytes: demasiado chico", retryable=False)
    info = _ffprobe(path)
    streams = info.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video is None or (video.get("width"), video.get("height")) != (WIDTH, HEIGHT):
        raise RenderError("El video no es de 1080x1920", retryable=False)
    if not any(s.get("codec_type") == "audio" for s in streams):
        raise RenderError("El video no tiene pista de audio", retryable=False)
    duration = float(info.get("format", {}).get("duration", 0))
    if not MIN_SECONDS <= duration <= MAX_SECONDS:
        raise RenderError(f"La duración del video ({duration:.1f} s) está fuera de 12–20 s", retryable=False)
    return duration


def _stop_ffmpeg(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    try:
        if proc.stdin:
            proc.stdin.close()
    except OSError:
        pass
    proc.kill()
    proc.wait(timeout=10)


def render_job(job_dir: Path, *, deadline: float | None = None) -> dict:
    """Renderiza el job. `deadline` es un instante de `time.monotonic()`.

    Devuelve el dict del 200 de la spec. Levanta JobError (el pedido es malo) o RenderError.
    """
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    t_start = time.monotonic()
    job_dir = Path(job_dir).resolve()
    job = reel_t1.load_job(job_dir)
    tl = reel_t1.timeline(len(job.slides))
    out_video, out_cover = job_dir / OUT_VIDEO, job_dir / OUT_COVER
    out_dir = out_video.parent
    if out_dir.is_symlink():
        raise JobError("out/ no puede ser un enlace")
    out_dir.mkdir(exist_ok=True)  # en producción la crea el backend (0700, del usuario del contenedor)
    for old in (out_video, out_cover):
        old.unlink(missing_ok=True)

    work = Path(tempfile.mkdtemp(prefix="reel-"))
    ffmpeg = None
    ffmpeg_err = tempfile.TemporaryFile()
    try:
        page_file = work / "reel.html"
        page_file.write_text(reel_t1.build_html(job), encoding="utf-8")
        frames, cover_index = tl.frames, round(COVER_T * FPS)

        def check_deadline():
            if deadline is not None and time.monotonic() > deadline:
                raise RenderError("Se venció el plazo del render", retryable=True)

        ffmpeg = subprocess.Popen(
            [*FFMPEG_CMD, str(out_video)], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=ffmpeg_err
        )
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=["--disable-dev-shm-usage"], executable_path=chromium_path())
            try:
                page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
                page.set_default_timeout(30_000)
                page.route(
                    "**/*",
                    _make_route({page_file.resolve()}, [job_dir, ASSETS_DIR.resolve()]),
                )
                prepare_page(page, page_file)
                set_time = "t => window.__a.forEach(a => { a.currentTime = t; })"

                page.evaluate(set_time, 0)
                page.screenshot(type="jpeg", quality=90)  # calentamiento: no se escribe

                t_frames = time.monotonic()
                for i in range(frames):
                    check_deadline()
                    page.evaluate(set_time, i * 1000 / FPS)
                    buf = page.screenshot(type="jpeg", quality=90)
                    try:
                        ffmpeg.stdin.write(buf)
                    except (BrokenPipeError, OSError) as exc:
                        raise RenderError("ffmpeg se cortó durante el render", retryable=True) from exc
                    if i == cover_index:
                        out_cover.write_bytes(buf)
                frames_ms = (time.monotonic() - t_frames) * 1000
            finally:
                browser.close()

        ffmpeg.stdin.close()
        try:
            code = ffmpeg.wait(timeout=60)
        except subprocess.TimeoutExpired as exc:
            raise RenderError("ffmpeg no terminó de armar el video", retryable=True) from exc
        if code != 0:
            ffmpeg_err.seek(0)
            tail = ffmpeg_err.read()[-300:].decode("utf-8", "replace").strip()
            raise RenderError(f"ffmpeg falló (código {code}): {tail}", retryable=True)

        duration = verify_video(out_video)
        if not out_cover.is_file() or out_cover.stat().st_size == 0:
            raise RenderError("No se generó la portada", retryable=True)
        render_ms = round((time.monotonic() - t_start) * 1000)
        log("render.ok", piece_id=job.piece_id, frames=frames, render_ms=render_ms, ms_por_cuadro=round(frames_ms / frames))
        return {
            "ok": True,
            "duration_s": round(duration, 1),
            "video_bytes": out_video.stat().st_size,
            "render_ms": render_ms,
            "frames": frames,
        }
    except PlaywrightError as exc:
        raise RenderError(f"Chromium falló: {str(exc).splitlines()[0][:200]}", retryable=True) from exc
    except BaseException:
        out_video.unlink(missing_ok=True)
        out_cover.unlink(missing_ok=True)
        raise
    finally:
        _stop_ffmpeg(ffmpeg)
        ffmpeg_err.close()
        shutil.rmtree(work, ignore_errors=True)


def result_for(exc: BaseException) -> dict:
    """Traduce una excepcion al dict `ok:false` del contrato."""
    if isinstance(exc, JobError):
        return {"ok": False, "error": str(exc), "retryable": False}
    if isinstance(exc, RenderError):
        return {"ok": False, "error": str(exc), "retryable": exc.retryable}
    return {"ok": False, "error": f"Error inesperado del render: {exc.__class__.__name__}", "retryable": True}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("job_dir")
    parser.add_argument("--deadline-seg", type=float, default=None)
    args = parser.parse_args(argv)
    deadline = time.monotonic() + args.deadline_seg if args.deadline_seg else None
    try:
        result = render_job(Path(args.job_dir), deadline=deadline)
    except BaseException as exc:  # noqa: BLE001 - el proceso siempre debe contestar una linea JSON
        log("render.error", error=repr(exc)[:300])
        result = result_for(exc)
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
