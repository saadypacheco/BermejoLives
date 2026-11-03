"""Servidor HTTP del contenedor `reels` (docs/contenido-redes-tecnico.md, 16.4).

Solo stdlib. Sin puerto publicado ni Traefik: lo alcanza unicamente el backend por la
red interna `render`.

    POST /render   Authorization: Bearer <RENDERER_TOKEN>   {"piece_id": "<uuid>"}
    GET  /health   (sin token)

Un render a la vez (409 si hay otro en curso). Cada render corre en un proceso aparte
(`render.py`) para poder matarlo entero, con Chromium y ffmpeg, al vencer
RENDER_DEADLINE_SEG.
"""
from __future__ import annotations

import hmac
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import reel_t1
from reel_t1 import JobError

HERE = Path(__file__).resolve().parent
MAX_BODY = 1024
DEFAULT_DEADLINE_SEG = 280
HEALTH_CACHE_SEG = 60


def log(event: str, **kw) -> None:
    print(json.dumps({"event": event, **kw}, ensure_ascii=False), file=sys.stderr, flush=True)


def kill_tree(proc: subprocess.Popen) -> None:
    """Mata el proceso del render y todos sus hijos (Chromium, ffmpeg)."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, timeout=15)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        proc.kill()
    except OSError:
        pass


class Renderer:
    """Estado compartido del servidor: configuracion, candado de 'uno a la vez' y proceso actual."""

    def __init__(self, token: str, content_dir: Path, deadline_seg: float = DEFAULT_DEADLINE_SEG):
        self.token = token
        self.content_dir = Path(content_dir)
        self.deadline_seg = deadline_seg
        self.lock = threading.Lock()
        self.current: subprocess.Popen | None = None
        self._health: tuple[float, bool] | None = None

    # ---- auth ----
    def authorized(self, header: str | None) -> bool:
        if not self.token or not header or not header.startswith("Bearer "):
            return False
        return hmac.compare_digest(header[7:].encode("utf-8"), self.token.encode("utf-8"))

    # ---- health ----
    def chromium_ok(self) -> bool:
        now = time.monotonic()
        if self._health and now - self._health[0] < HEALTH_CACHE_SEG:
            return self._health[1]
        ok = False
        try:
            exe = os.environ.get("CHROME_EXE")
            if exe:
                ok = Path(exe).is_file()
            else:
                from playwright.sync_api import sync_playwright

                with sync_playwright() as pw:
                    ok = Path(pw.chromium.executable_path).is_file()
        except Exception:  # noqa: BLE001 - /health nunca debe romperse
            ok = False
        self._health = (now, ok)
        return ok

    def health(self) -> dict:
        return {
            "ok": True,
            "chromium": self.chromium_ok(),
            "ffmpeg": shutil.which("ffmpeg") is not None,
            "busy": self.lock.locked(),
        }

    # ---- render ----
    def job_dir(self, piece_id: str) -> Path:
        return self.content_dir / "tmp" / piece_id

    def run(self, piece_id: str) -> tuple[int, dict]:
        """Valida el job y lo renderiza. Quien llama ya tomo el candado."""
        started = time.monotonic()
        job_dir = self.job_dir(piece_id)
        try:
            reel_t1.load_job(job_dir)
        except JobError as exc:
            return 400, {"ok": False, "error": str(exc), "retryable": False}

        remaining = self.deadline_seg - (time.monotonic() - started)
        cmd = [sys.executable, str(HERE / "render.py"), str(job_dir), "--deadline-seg", str(max(1.0, remaining - 5))]
        kwargs = {"start_new_session": True} if os.name != "nt" else {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=None, text=True, encoding="utf-8", **kwargs)
        self.current = proc
        try:
            out, _ = proc.communicate(timeout=remaining)
        except subprocess.TimeoutExpired:
            kill_tree(proc)
            proc.communicate()
            for name in (reel_t1.OUT_VIDEO, reel_t1.OUT_COVER):
                (job_dir / name).unlink(missing_ok=True)
            log("render.plazo_vencido", piece_id=piece_id, deadline_seg=self.deadline_seg)
            return 200, {"ok": False, "error": "Se venció el plazo del render", "retryable": True}
        finally:
            self.current = None

        lines = [ln for ln in (out or "").splitlines() if ln.strip()]
        try:
            result = json.loads(lines[-1])
            if not isinstance(result, dict) or "ok" not in result:
                raise ValueError
        except (IndexError, ValueError):
            log("render.sin_resultado", piece_id=piece_id, returncode=proc.returncode)
            return 200, {"ok": False, "error": "El render terminó sin resultado", "retryable": True}
        return 200, result

    def shutdown_child(self) -> None:
        proc = self.current
        if proc is not None and proc.poll() is None:
            kill_tree(proc)


class Handler(BaseHTTPRequestHandler):
    server_version = "reels"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    @property
    def renderer(self) -> Renderer:
        return self.server.renderer  # type: ignore[attr-defined]

    def log_message(self, fmt, *args):  # nunca loguea cabeceras (el token viaja en Authorization)
        log("http", line=fmt % args)

    def _send(self, status: int, body: dict) -> None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/health":
            self._send(200, self.renderer.health())
        else:
            self._send(404, {"ok": False, "error": "No encontrado", "retryable": False})

    def do_POST(self):
        if self.path != "/render":
            self._send(404, {"ok": False, "error": "No encontrado", "retryable": False})
            return
        if not self.renderer.authorized(self.headers.get("Authorization")):
            self.close_connection = True
            self._send(401, {"ok": False, "error": "No autorizado", "retryable": False})
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            length = -1
        if not 0 < length <= MAX_BODY:
            self.close_connection = True
            self._send(400, {"ok": False, "error": "Cuerpo inválido", "retryable": False})
            return
        try:
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError
            piece_id = reel_t1.parse_piece_id(body.get("piece_id"))
        except (ValueError, JobError):
            self._send(400, {"ok": False, "error": "piece_id inválido: debe ser un UUID", "retryable": False})
            return

        if not self.renderer.lock.acquire(blocking=False):
            self._send(409, {"ok": False, "error": "Ocupado", "retryable": True})
            return
        try:
            status, result = self.renderer.run(piece_id)
        except Exception as exc:  # noqa: BLE001
            log("render.error_servidor", error=repr(exc)[:300])
            status, result = 200, {"ok": False, "error": "Error interno del armador", "retryable": True}
        finally:
            self.renderer.lock.release()
        self._send(status, result)


def make_server(host: str, port: int, renderer: Renderer) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    server.renderer = renderer  # type: ignore[attr-defined]
    return server


def main() -> None:
    token = os.environ.get("RENDERER_TOKEN", "")
    if not token:
        log("server.sin_token", aviso="RENDERER_TOKEN vacío: todo POST /render contestará 401")
    renderer = Renderer(
        token=token,
        content_dir=Path(os.environ.get("CONTENT_DIR", "/data/content")),
        deadline_seg=float(os.environ.get("RENDER_DEADLINE_SEG", DEFAULT_DEADLINE_SEG)),
    )
    server = make_server(os.environ.get("RENDERER_HOST", "0.0.0.0"), int(os.environ.get("RENDERER_PORT", "8090")), renderer)

    def stop(*_):
        renderer.shutdown_child()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    log("server.listo", port=server.server_address[1], deadline_seg=renderer.deadline_seg)
    server.serve_forever()


if __name__ == "__main__":
    main()
