"""Pruebas con navegador: ajuste de títulos y tecleo (browser) y render de punta a punta (e2e).

Se saltean solas si no hay playwright, Chromium o ffmpeg.
"""
import http.client
import json
import subprocess
import threading
import uuid

import pytest

import reel_t1
import render
import server as srv
from conftest import TEXTS, foto_de_prueba, requiere_browser, requiere_ffmpeg


@requiere_browser
@pytest.mark.browser
def test_titulo_largo_baja_a_72px_y_el_tecleo_se_mide(make_job, tmp_path):
    from playwright.sync_api import sync_playwright

    texts = dict(TEXTS, title1="Zapatillas deportivas nuevas", title2="para toda la familia", search_term="zapatillas")
    _, _, job_dir = make_job(4, texts=texts)
    job = reel_t1.load_job(job_dir)
    page_file = tmp_path / "reel.html"
    page_file.write_text(reel_t1.build_html(job), encoding="utf-8")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--disable-dev-shm-usage"], executable_path=render.chromium_path())
        page = browser.new_page(viewport={"width": 1080, "height": 1920})
        render.prepare_page(page, page_file, pause=False)
        sizes = page.evaluate("[...document.querySelectorAll('.title')].map(t => t.querySelector('.tl1').style.fontSize)")
        tw = page.evaluate("document.querySelector('.typed').style.getPropertyValue('--tw')")
        browser.close()
    assert sizes[0] == "72px"  # el título del gancho no entra a 88 px
    assert sizes[1] == ""  # «¿Dónde lo» sí entra: se queda en 88 px
    assert tw.endswith("px") and int(tw[:-2]) > 100


@requiere_browser
@requiere_ffmpeg
@pytest.mark.e2e
def test_render_real_de_punta_a_punta_por_http(tmp_path):
    piece_id = str(uuid.uuid4())
    job_dir = tmp_path / "tmp" / piece_id
    job_dir.mkdir(parents=True)
    colores = ["0x2a7f62", "0x7f2a4d", "0x2a4d7f", "0x7f7f2a"]
    for i, color in enumerate(colores):
        foto_de_prueba(job_dir / f"s{i}.jpg", color)
    texts = dict(TEXTS, title1="Camperas ¿qué tal?", subtitle="Niños, jóvenes y más: ¡consulte!")
    data = {
        "version": 2, "piece_id": piece_id, "template": "t1", "format": "9x16", "fps": 30, "texts": texts,
        "icons": ["pin", "whatsapp"], "out_video": "video.mp4", "out_cover": "cover.jpg",
        "slides": [{"file": f"s{i}.jpg", "chip": "Eco cuero ñandú" if i % 2 == 0 else None, "focus_y": None} for i in range(4)],
    }
    (job_dir / "job.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    renderer = srv.Renderer(token="t", content_dir=tmp_path, deadline_seg=280)
    httpd = srv.make_server("127.0.0.1", 0, renderer)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=300)
        conn.request("POST", "/render", json.dumps({"piece_id": piece_id}), {"Authorization": "Bearer t"})
        resp = conn.getresponse()
        body = json.loads(resp.read())
    finally:
        httpd.shutdown()
        httpd.server_close()

    assert resp.status == 200, body
    assert body["ok"] is True, body
    assert body["frames"] == 420
    assert 13.5 <= body["duration_s"] <= 14.5
    video, cover = job_dir / "video.mp4", job_dir / "cover.jpg"
    assert body["video_bytes"] == video.stat().st_size > 100 * 1024
    assert cover.stat().st_size > 10 * 1024
    info = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", str(video)],
        capture_output=True, text=True, check=True).stdout)
    kinds = {s["codec_type"]: s for s in info["streams"]}
    assert (kinds["video"]["width"], kinds["video"]["height"]) == (1080, 1920)
    assert kinds["audio"]["codec_name"] == "aac"
    # el contenedor sólo escribe video.mp4 y cover.jpg en la carpeta del job
    assert sorted(p.name for p in job_dir.iterdir()) == ["cover.jpg", "job.json", "s0.jpg", "s1.jpg", "s2.jpg", "s3.jpg", "video.mp4"]
