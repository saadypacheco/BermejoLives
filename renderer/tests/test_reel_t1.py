"""Armado del HTML de T1 y validación del job (sin navegador)."""
import copy
import json
import os
import re
import uuid
from pathlib import Path

import pytest

import reel_t1
from reel_t1 import JobError, build_html, load_job, timeline, validate_job

from conftest import TEXTS, job_data


def _job(make_job, n=4, **overrides):
    _, _, job_dir = make_job(n, **overrides)
    return load_job(job_dir)


# ---------------------------------------------------------------- HTML
def test_texto_con_script_y_comillas_queda_escapado(make_job):
    texts = dict(TEXTS, title1='<script>alert("x")</script>', title2="Tom & Jerry's", subtitle='"><img src=x onerror=1>')
    slides = [{"file": f"s{i}.jpg", "chip": '<b onclick="x">hola</b>', "focus_y": None} for i in range(4)]
    page = build_html(_job(make_job, texts=texts, slides=slides))
    assert "<script" not in page.lower()
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;" in page
    assert "Tom &amp; Jerry&#x27;s" in page
    assert "<img src=x" not in page
    assert "<b onclick" not in page
    assert "&lt;b onclick=&quot;x&quot;&gt;hola&lt;/b&gt;" in page


def test_texto_de_cierre_y_url_tambien_se_escapan(make_job):
    texts = dict(TEXTS, close_line="Vea <i>todo</i>", url="a&b.bo", lema="<u>x</u>", place_chip="<p>y</p>", search_term="<q>")
    page = build_html(_job(make_job, texts=texts))
    for crudo in ("<i>todo</i>", "<u>x</u>", "<p>y</p>", "<q>", "a&b.bo"):
        assert crudo not in page


def test_la_pagina_no_trae_script_y_si_la_csp(make_job):
    page = build_html(_job(make_job))
    assert "<script" not in page.lower()
    assert "Content-Security-Policy" in page
    assert "default-src &#x27;none&#x27;; img-src file:; style-src &#x27;unsafe-inline&#x27;; font-src file:" in page


def test_el_glow_no_usa_blur(make_job):
    page = build_html(_job(make_job))
    glow = re.search(r"\.glow\{[^}]*\}", page).group(0)
    assert "blur" not in glow
    assert "filter" not in glow
    assert "blur(24px)" not in page


def test_los_tiempos_son_los_de_la_spec():
    assert (timeline(4).close_at, timeline(4).total, timeline(4).frames) == (9.8, 14.0, 420)
    assert (timeline(6).close_at, timeline(6).total, timeline(6).frames) == (14.0, 18.2, 546)
    assert timeline(5).close_at == 11.9


@pytest.mark.parametrize("n", [4, 5, 6])
def test_carrusel_y_cierre_siguen_a_n(make_job, n):
    tl = timeline(n)
    page = build_html(_job(make_job, n))
    assert page.count('class="slide"') == n
    assert page.count("<b style=") == n  # indicador de N puntos
    for i in range(n):
        assert f"animation-delay:{1.5 + 2.1 * i:.2f}s" in page  # entrada de cada foto
    # la última foto sale justo antes del cierre; las demás 2,0 s después de entrar
    assert f"animation-delay:{1.5 + 2.1 * (n - 1):.2f}s,{tl.close_at - 0.2:.2f}s" in page
    assert f"animation-delay:{1.5:.2f}s,{3.5:.2f}s" in page
    # el título de cierre arranca en C y el logo/url/lema después
    assert f'class="tl1" style="animation-delay:{tl.close_at + .1:.2f}s"' in page
    assert f'<div class="url" style="top:1530px;animation-delay:{tl.close_at + 2.6:.2f}s">' in page
    assert f"{tl.close_at - 0.1:.2f}s linear both" in page  # escena de cierre


def test_el_tecleo_usa_steps_del_largo_del_termino(make_job):
    page = build_html(_job(make_job, texts=dict(TEXTS, search_term="camperas")))
    assert "steps(8)" in page
    assert 'class="tt">camperas</span>' in page
    page = build_html(_job(make_job, texts=dict(TEXTS, search_term="ropa")))
    assert "steps(4)" in page


def test_opcionales_null_no_se_dibujan(make_job):
    texts = dict(TEXTS, kick=None, subtitle=None, place_chip=None, close_line=None)
    slides = [{"file": f"s{i}.jpg", "chip": None, "focus_y": None} for i in range(4)]
    page = build_html(_job(make_job, texts=texts, slides=slides, icons=[]))
    assert 'class="kick"' not in page
    assert 'top:1730px' not in page  # subtítulo fijo
    assert 'class="whw"' not in page
    assert "<i></i>" not in page  # ni chips de foto ni chip de lugar
    assert 'class="coin"' not in page
    assert 'top:1060px' not in page  # close_line
    # lo obligatorio sigue
    assert "Camperas que" in page and "uruku.bo" in page and "Si está en Bolivia" in page


def test_opcionales_presentes_si_se_dibujan(make_job):
    page = build_html(_job(make_job))
    assert 'class="kick"' in page
    assert "Eco cuero, doble faz y más modelos" in page
    assert 'class="whw"' in page
    assert page.count('class="coin"') == 2
    assert page.count("<i></i>") == 4 + 1  # un chip por foto + el del lugar


def test_focus_y_por_defecto_y_explicito(make_job):
    slides = [{"file": "s0.jpg", "chip": None, "focus_y": None}] + [
        {"file": f"s{i}.jpg", "chip": None, "focus_y": 0.25} for i in range(1, 4)
    ]
    page = build_html(_job(make_job, slides=slides))
    assert "object-position:50% 40.0%" in page
    assert "object-position:50% 25.0%" in page


def test_la_linea_de_cierre_larga_se_parte_en_dos(make_job):
    page = build_html(_job(make_job))
    assert "Consulte precio<br>directo con el local" in page
    page = build_html(_job(make_job, texts=dict(TEXTS, close_line="Vea todas las ofertas en Uruku")))
    assert "<br>" in page


def test_las_rutas_del_html_son_file_dentro_del_job_o_assets(make_job):
    _, _, job_dir = make_job(4)
    page = build_html(load_job(job_dir))
    urls = re.findall(r'(?:src|url)[=(]"?(file:[^")]+)', page)
    assert urls
    for url in urls:
        path = Path(url.replace("file:///", "").replace("%20", " ")) if os.name == "nt" else Path(url[len("file://"):])
        assert path.is_relative_to(job_dir.resolve()) or path.is_relative_to(reel_t1.ASSETS_DIR.resolve()), url
    assert "http://" not in page and "https://" not in page


# ---------------------------------------------------------------- validación
def test_job_valido_carga(make_job):
    job = _job(make_job, 5)
    assert len(job.slides) == 5
    assert job.texts["kick"] == "NUEVA TEMPORADA"


@pytest.mark.parametrize(
    "malo",
    ["", "1234", "no-es-uuid", "../../etc/passwd", str(uuid.uuid4()) + "/x", None, 7, str(uuid.uuid4()).replace("-", "")],
)
def test_piece_id_invalido(malo):
    with pytest.raises(JobError):
        reel_t1.parse_piece_id(malo)


def test_piece_id_valido():
    pid = str(uuid.uuid4())
    assert reel_t1.parse_piece_id(pid) == pid


def test_piece_id_del_json_debe_coincidir_con_la_carpeta(make_job):
    _, _, job_dir = make_job(4)
    data = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
    data["piece_id"] = str(uuid.uuid4())
    with pytest.raises(JobError, match="no coincide"):
        validate_job(data, job_dir)


@pytest.mark.parametrize(
    "nombre",
    ["../s0.jpg", "/etc/passwd", "C:\\x\\s0.jpg", "s0.png", "s0.jpg.png", "S0.jpg", "s000.jpg", "s.jpg", "a/s0.jpg",
     "s0.jpg/../s1.jpg", "s0.jpg\n", " s0.jpg", "s0.JPG", "..", "", None, 5],
)
def test_nombre_de_foto_raro_se_rechaza(make_job, nombre):
    slides = [{"file": nombre, "chip": None, "focus_y": None}] + [
        {"file": f"s{i}.jpg", "chip": None, "focus_y": None} for i in range(1, 4)
    ]
    _, _, job_dir = make_job(4, slides=slides)
    with pytest.raises(JobError):
        load_job(job_dir)


@pytest.mark.parametrize("n", [0, 1, 3, 7])
def test_cantidad_de_fotos_fuera_de_4_a_6(make_job, n):
    _, _, job_dir = make_job(n)
    with pytest.raises(JobError, match="entre 4 y 6"):
        load_job(job_dir)


def test_foto_repetida_o_faltante(make_job):
    slides = [{"file": "s0.jpg", "chip": None, "focus_y": None}] * 4
    _, _, job_dir = make_job(4, slides=slides)
    with pytest.raises(JobError, match="repetido"):
        load_job(job_dir)
    _, _, job_dir = make_job(4)
    (job_dir / "s2.jpg").unlink()
    with pytest.raises(JobError, match="Falta la foto s2.jpg"):
        load_job(job_dir)


def test_foto_que_no_es_jpeg(make_job):
    _, _, job_dir = make_job(4)
    (job_dir / "s1.jpg").write_bytes(b"GIF89a....")
    with pytest.raises(JobError, match="no es un JPEG"):
        load_job(job_dir)


@pytest.mark.skipif(os.name == "nt", reason="los symlinks necesitan privilegios en Windows")
def test_foto_que_es_symlink_afuera_de_la_carpeta(make_job, tmp_path_factory):
    _, _, job_dir = make_job(4)
    afuera = tmp_path_factory.mktemp("afuera") / "secreto.jpg"
    afuera.write_bytes(b"\xff\xd8\xff" + b"x" * 50)
    (job_dir / "s0.jpg").unlink()
    (job_dir / "s0.jpg").symlink_to(afuera)
    with pytest.raises(JobError, match="fuera de la carpeta"):
        load_job(job_dir)


@pytest.mark.parametrize("campo,valor", [("out_video", "../video.mp4"), ("out_video", "otro.mp4"), ("out_video", "/tmp/x.mp4"),
                                         ("out_video", "video.mp4"), ("out_cover", "cover.jpg"),
                                         ("out_video", "out/../video.mp4"),
                                         ("out_cover", "cover.png"), ("out_cover", "../cover.jpg"), ("out_cover", None)])
def test_nombres_de_salida_fijos(make_job, campo, valor):
    _, _, job_dir = make_job(4, **{campo: valor})
    with pytest.raises(JobError, match="out_video y out_cover"):
        load_job(job_dir)


@pytest.mark.parametrize("icons", [["pin", "no_existe"], ["../pin"], ["pin", "pin"], "pin", [1], ["pin", "whatsapp", "oferta", "tienda"],
                                   ["ic_pin.png"]])
def test_iconos_fuera_de_la_lista(make_job, icons):
    _, _, job_dir = make_job(4, icons=icons)
    with pytest.raises(JobError):
        load_job(job_dir)


def test_iconos_conocidos_salen_de_assets():
    assert {"pin", "whatsapp", "oferta", "tienda", "comida"} <= reel_t1.KNOWN_ICONS


@pytest.mark.parametrize("campo", ["title1", "title2", "close_title1", "close_title2", "search_term", "url", "lema"])
def test_texto_obligatorio_faltante(make_job, campo):
    texts = dict(TEXTS)
    texts[campo] = None
    _, _, job_dir = make_job(4, texts=texts)
    with pytest.raises(JobError, match=campo):
        load_job(job_dir)


def test_textos_con_tipo_o_largo_invalido(make_job):
    for texts in (dict(TEXTS, title1=5), dict(TEXTS, title1="x" * 500), dict(TEXTS, kick=["a"])):
        _, _, job_dir = make_job(4, texts=texts)
        with pytest.raises(JobError):
            load_job(job_dir)


def test_caracteres_de_control_se_limpian(make_job):
    job = _job(make_job, texts=dict(TEXTS, title1="Camperas\x00\nque\t"))
    assert job.texts["title1"] == "Camperas  que"


@pytest.mark.parametrize("campo,valor", [("version", 1), ("template", "t2"), ("format", "16x9"), ("fps", 24), ("fps", True)])
def test_version_template_formato_fps(make_job, campo, valor):
    _, _, job_dir = make_job(4, **{campo: valor})
    with pytest.raises(JobError):
        load_job(job_dir)


@pytest.mark.parametrize("focus", [-0.1, 1.5, "0.3", True])
def test_focus_y_fuera_de_rango(make_job, focus):
    slides = [{"file": f"s{i}.jpg", "chip": None, "focus_y": focus if i == 0 else None} for i in range(4)]
    _, _, job_dir = make_job(4, slides=slides)
    with pytest.raises(JobError, match="focus_y"):
        load_job(job_dir)


def test_job_json_roto_o_ausente(make_job, tmp_path):
    _, _, job_dir = make_job(4)
    (job_dir / "job.json").write_text("{no es json", encoding="utf-8")
    with pytest.raises(JobError, match="no se puede leer"):
        load_job(job_dir)
    (job_dir / "job.json").unlink()
    with pytest.raises(JobError, match="No existe job.json"):
        load_job(job_dir)
    with pytest.raises(JobError, match="No existe la carpeta"):
        load_job(tmp_path / "nada")


def test_job_json_gigante(make_job):
    _, _, job_dir = make_job(4)
    (job_dir / "job.json").write_text(" " * (reel_t1.MAX_JOB_BYTES + 1), encoding="utf-8")
    with pytest.raises(JobError, match="demasiado grande"):
        load_job(job_dir)

def test_piece_id_con_salto_de_linea_final_no_pasa():
    with pytest.raises(JobError):
        reel_t1.parse_piece_id("12345678-1234-1234-1234-123456789abc\n")


def test_nombre_de_foto_con_salto_de_linea_final_no_pasa(make_job):
    _, _, job_dir = make_job(4, slides=[{"file": f"s{i}.jpg" + ("\n" if i == 0 else ""), "chip": None, "focus_y": 0.3}
                                       for i in range(4)])
    with pytest.raises(JobError, match="inválido"):
        load_job(job_dir)


def test_los_textos_se_normalizan_y_pierden_los_caracteres_invisibles(make_job):
    _, piece_id, job_dir = make_job(4)
    data = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
    data["texts"]["title1"] = "Cam\u200bperas\u202e \uff46\uff55\uff4c\uff4c"  # ancho cero, bidi y ancho completo
    data["slides"][0]["chip"] = "Ofer\u2060ta"
    (job_dir / "job.json").write_text(json.dumps(data), encoding="utf-8")
    job = load_job(job_dir)
    assert job.texts["title1"] == "Camperas full"
    assert job.slides[0].chip == "Oferta"


def test_un_texto_obligatorio_que_queda_vacio_tras_limpiar_se_rechaza(make_job):
    _, _, job_dir = make_job(4)
    data = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
    data["texts"]["title1"] = "\u200b\u200d"
    (job_dir / "job.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(JobError, match="Falta"):
        load_job(job_dir)
