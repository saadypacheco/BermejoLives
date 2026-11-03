"""Utilidades compartidas de los tests del renderer."""
import json
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

TEXTS = {
    "kick": "NUEVA TEMPORADA",
    "title1": "Camperas que",
    "title2": "ya llegaron",
    "subtitle": "Eco cuero, doble faz y más modelos",
    "close_title1": "¿Dónde lo",
    "close_title2": "consigue?",
    "search_term": "camperas",
    "place_chip": "Boutique Andina · Bermejo",
    "close_line": "Consulte precio directo con el local",
    "url": "uruku.bo",
    "lema": "Si está en Bolivia, está en Uruku.",
}


def job_data(piece_id: str, n: int = 4, **overrides) -> dict:
    data = {
        "version": 2,
        "piece_id": piece_id,
        "template": "t1",
        "format": "9x16",
        "fps": 30,
        "texts": dict(TEXTS),
        "icons": ["pin", "whatsapp"],
        "slides": [{"file": f"s{i}.jpg", "chip": f"Foto número {i}", "focus_y": 0.3} for i in range(n)],
        "out_video": "video.mp4",
        "out_cover": "cover.jpg",
    }
    data.update(overrides)
    return data


JPEG_MINIMO = b"\xff\xd8\xff\xe0" + b"\x00" * 64  # sólo para validar; no es una imagen real


@pytest.fixture
def make_job(tmp_path):
    """Crea <tmp>/tmp/<uuid>/ con job.json y fotos mínimas. Devuelve (content_dir, piece_id, job_dir)."""

    def _make(n: int = 4, write_photos: bool = True, **overrides):
        piece_id = str(uuid.uuid4())
        job_dir = tmp_path / "tmp" / piece_id
        job_dir.mkdir(parents=True)
        data = job_data(piece_id, n, **overrides)
        (job_dir / "job.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        if write_photos:
            for slide in data["slides"]:
                name = slide.get("file") if isinstance(slide, dict) else None
                if isinstance(name, str) and re.fullmatch(r"s\d{1,2}\.jpg", name):
                    (job_dir / name).write_bytes(JPEG_MINIMO)
        return tmp_path, piece_id, job_dir

    return _make


def chromium_disponible() -> bool:
    """True si hay playwright y un Chromium que se pueda lanzar."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    exe = os.environ.get("CHROME_EXE")
    if exe:
        return Path(exe).is_file()
    try:
        with sync_playwright() as pw:
            return Path(pw.chromium.executable_path).is_file()
    except Exception:
        return False


requiere_browser = pytest.mark.skipif(not chromium_disponible(), reason="no hay playwright/Chromium")
requiere_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="no hay ffmpeg/ffprobe"
)


def foto_de_prueba(path: Path, color: str = "0x2a7f62") -> None:
    """JPEG real de 800x1000 hecho con ffmpeg (el contenedor no trae PIL)."""
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c={color}:s=800x1000", "-frames:v", "1", str(path)],
        check=True,
    )
