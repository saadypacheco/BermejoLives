"""El render: composición de los cuadros, el lado padre con el subproceso simulado y un render real con ffmpeg."""
import json
import shutil
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from PIL import Image

from app.core.config import settings
from app.services import content_render as cr, content_render_job as job, content_storage
from tests.content_helpers import banco, comercio, jpg, pieza

HAY_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
FACTS = {"pillar": "comercio_del_dia", "nombre": "Vidriería Pacheco", "rubro": "Vidriería", "calle": "Calle Barrientos",
         "ciudad": "Bermejo", "slug": "vidrieria-pacheco"}


def _foto(w=1600, h=1200, seed=1):
    return Image.open(__import__("io").BytesIO(jpg(w, h, seed))).convert("RGB")


def dentro(caja, zona=job.SAFE):
    x0, y0, x1, y1 = caja
    return zona[0] <= x0 and x1 <= zona[2] and zona[1] <= y0 and y1 <= zona[3]


# ── composición (sin ffmpeg) ─────────────────────────────────────────────────

def test_la_tapa_dibuja_los_datos_dentro_de_la_zona_segura():
    lz = job.tramo_tapa(FACTS, _foto())
    assert lz.img.size == (job.BASE_W, job.BASE_H)
    textos = [t for t, _ in lz.cajas]
    assert textos == ["Vidriería Pacheco", "Vidriería", "Calle Barrientos, Bermejo"]
    assert all(dentro(c) for _, c in lz.cajas), lz.cajas


def test_un_nombre_larguisimo_se_achica_y_sigue_dentro_de_dos_lineas():
    px, lineas = job.ajustar_nombre("Supermercado Internacional Hermanos Rodríguez y Asociados Sociedad Limitada")
    assert len(lineas) <= 2 and px < 96
    f = dict(FACTS, nombre="Supermercado Internacional Hermanos Rodríguez y Asociados Sociedad Limitada de Bermejo")
    assert all(dentro(c) for _, c in job.tramo_tapa(f, _foto()).cajas)
    assert job.ajustar_nombre("Kiosco Ana")[0] == 96


def test_el_cierre_invita_a_buscar_el_comercio_y_el_de_ofertas_a_ver_todas():
    assert [t for t, _ in job.tramo_cierre(FACTS).cajas] == ['Buscá "Vidriería', 'Pacheco" en uruku.bo'] or \
        "uruku.bo" in " ".join(t for t, _ in job.tramo_cierre(FACTS).cajas)
    of = job.tramo_cierre({"pillar": "ofertas", "ciudad": "Bermejo"})
    assert "ofertas" in " ".join(t for t, _ in of.cajas) and all(dentro(c) for _, c in of.cajas)
    assert all(dentro(c) for _, c in job.tramo_cierre(FACTS).cajas)


def test_la_tapa_de_ofertas_dice_la_ciudad():
    lz = job.tramo_tapa({"pillar": "ofertas", "ciudad": "Bermejo"}, _foto())
    assert "Bermejo" in " ".join(t for t, _ in lz.cajas)


def test_la_banda_de_la_oferta_va_fuera_de_la_foto_y_el_texto_dentro_de_la_zona_segura():
    banda = {"nombre": "Calzados Luz", "precio": "Bs 180", "titulo_corto": "Zapatillas deportivas"}
    for w, h in ((1600, 1200), (1200, 1600), (1000, 1000)):
        lz, caja = job.tramo_foto(_foto(w, h), banda)
        b0, b1 = job.OFERTA_BANDA
        assert caja[3] <= b0 <= b1 and caja[1] >= job.OFERTA_FOTO_Y[0] - 1                      # la foto no se tapa
        assert [t for t, _ in lz.cajas] == ["Calzados Luz", "Bs 180", "Zapatillas deportivas"]
        assert all(dentro(c) and c[1] >= b0 for _, c in lz.cajas), lz.cajas
        # el píxel del medio de la banda es verde de marca
        x, y = lz.p(540), lz.p(b0 + 5)
        assert lz.img.getpixel((x, y)) == job.VERDE


def test_la_foto_se_ve_entera_en_1080_de_ancho_o_hasta_1500_de_alto():
    _, caja = job.tramo_foto(_foto(1600, 1200))
    assert round(caja[2] - caja[0]) == 1080
    _, caja = job.tramo_foto(_foto(1200, 2400))
    assert round(caja[3] - caja[1]) == 1500 and round(caja[2] - caja[0]) == 750


def test_los_emojis_no_se_dibujan():
    assert job.sin_emojis("Pizzería 🍕 Luigi ✨") == "Pizzería Luigi"
    lz = job.tramo_tapa(dict(FACTS, nombre="Café 🔥 Sol"), _foto())
    assert lz.cajas[0][0] == "Café Sol"


def _slides(tmp_path, n, w=1600, h=1200):
    rutas = []
    for i in range(n):
        p = tmp_path / f"f{i}.jpg"
        p.write_bytes(jpg(w, h, seed=i))
        rutas.append({"path": str(p), "caption_fact": None})
    return rutas


def test_los_tramos_duran_2_mas_2_5_por_foto_mas_3(tmp_path):
    for n, total in ((4, 15.0), (5, 17.5), (7, 22.5)):
        tramos = job.armar_tramos(FACTS, _slides(tmp_path, n))
        assert len(tramos) == n + 2 and job.duracion_total(tramos) == total
    assert len(job.armar_tramos(FACTS, _slides(tmp_path, 9))) == 7 + 2          # tope de 7 fotos


def test_menos_de_4_fotos_no_se_renderiza_y_no_es_reintentable(tmp_path):
    with pytest.raises(job.RenderError) as e:
        job.armar_tramos(FACTS, _slides(tmp_path, 3))
    assert e.value.retryable is False
    with pytest.raises(job.RenderError):
        job.armar_tramos(dict(FACTS, pillar="inventada"), _slides(tmp_path, 4))


def test_cada_cuadro_es_de_1080x1920_y_el_fundido_mezcla(tmp_path):
    tramos = job.armar_tramos(FACTS, _slides(tmp_path, 4))
    assert job.cuadro_en(tramos, 0).size == (1080, 1920) == job.cuadro_en(tramos, 14.99).size
    en_el_borde = job.cuadro_en(tramos, 2.0)                    # unión tapa → foto 1: mitad y mitad
    a, b = tramos[0].cuadro(2.0), tramos[1].cuadro(0.0)
    assert en_el_borde.getpixel((540, 960)) != a.getpixel((540, 960)) or en_el_borde.getpixel((540, 960)) != b.getpixel((540, 960))
    sin_fundido = job.cuadro_en(tramos, 1.5)
    assert sin_fundido.getpixel((100, 100)) == tramos[0].cuadro(1.5).getpixel((100, 100))


def test_el_zoom_va_de_1_a_1_06_sin_saltos(tmp_path):
    tr = job.armar_tramos(FACTS, _slides(tmp_path, 4))[1]
    assert (tr.z0, tr.z1) == (1.0, 1.06)
    assert job.armar_tramos(FACTS, _slides(tmp_path, 4))[2].z0 == 1.06                # el siguiente se aleja
    assert tr.cuadro(0).size == tr.cuadro(1.25).size == tr.cuadro(2.5).size == (1080, 1920)


def test_sin_la_fuente_el_render_falla_sin_reintento(monkeypatch, tmp_path):
    monkeypatch.setattr(job, "ASSETS", tmp_path)
    job._fuentes.clear()
    try:
        with pytest.raises(job.RenderError) as e:
            job.fuente("bold", 40)
        assert e.value.retryable is False
    finally:
        job._fuentes.clear()


def test_el_comando_de_ffmpeg_codifica_h264_con_audio_mudo_y_faststart(tmp_path):
    cmd = job.comando_ffmpeg(tmp_path / "v.mp4")
    for parte in ("rawvideo", "rgb24", "1080x1920", "libx264", "anullsrc=r=48000:cl=stereo", "aac", "+faststart", "yuv420p"):
        assert any(parte in x for x in cmd), parte


# ── el lado padre, con el subproceso simulado ────────────────────────────────

@pytest.fixture
def listo(monkeypatch):
    """El render 'disponible' (hay ffmpeg y disco) y el subproceso falso, que escribe los archivos y contesta."""
    monkeypatch.setattr(cr, "ffmpeg_disponible", lambda: True)
    monkeypatch.setattr(content_storage, "disco_pausado", lambda: False)
    estado = {"respuesta": None, "veces": 0}

    def falso(ruta_job):
        estado["veces"] += 1
        datos = json.loads(Path(ruta_job).read_text(encoding="utf-8"))
        estado["job"] = datos
        r = estado["respuesta"] or {"ok": True, "duration_s": 17.5, "video_bytes": 200_000, "render_ms": 42}
        if r.get("ok"):
            Path(datos["out_video"]).write_bytes(b"v" * 200_000)
            Path(datos["out_cover"]).write_bytes(b"c" * 1000)
        if estado.get("antes_de_responder"):
            estado["antes_de_responder"]()
        return r
    monkeypatch.setattr(cr, "_correr_subproceso", falso)
    return estado


def _en_cola(repo, crepo, n=5, **kw):
    comercio(repo)
    fotos = banco(crepo, "com-1", n)
    p = pieza(crepo, "com-1", status="queued", **kw)
    crepo.insert_sources([{"piece_id": p["id"], "position": i, "source_type": "asset", "source_id": a["id"],
                           "comercio_id": "com-1", "file_ref": a["file_path"]} for i, a in enumerate(fotos)])
    return p, fotos


def test_un_render_exitoso_deja_la_pieza_lista_para_revisar(repo, crepo, listo):
    p, fotos = _en_cola(repo, crepo)
    r = cr.render_tick(crepo)
    assert r == {"piece_id": p["id"], "ok": True, "error": None}
    n = crepo.pieces[p["id"]]
    assert n["status"] == "ready_for_review" and n["render_ms"] == 42 and float(n["duration_s"]) == 17.5
    assert n["video_path"].startswith("renders/") and n["video_path"].endswith(f"{p['id']}/video.mp4")
    assert content_storage.safe_path(n["video_path"]).stat().st_size == 200_000
    assert content_storage.safe_path(n["cover_path"]).is_file()
    assert not content_storage.carpeta_tmp(p["id"]).exists()                    # el tmp se borra siempre
    assert all(crepo.assets[a["id"]]["use_count"] == 1 and crepo.assets[a["id"]]["last_used_at"] for a in fotos)
    assert cr.ultimo_render()["ok"] and cr.pieza_en_curso() is None
    assert [s["path"].endswith(".jpg") for s in listo["job"]["slides"]] == [True] * 5
    assert listo["job"]["facts"]["nombre"] == "Local com-1" and listo["job"]["template"] == "comercio_del_dia"


def test_sin_piezas_en_cola_no_hace_nada(repo, crepo, listo):
    assert cr.render_tick(crepo) is None and listo["veces"] == 0


def test_toma_la_mas_vieja_por_fecha_y_respeta_la_espera(repo, crepo, listo):
    p1, _ = _en_cola(repo, crepo, dia=datetime.now().date() + timedelta(days=5))
    p2 = pieza(crepo, "com-1", dia=datetime.now().date() + timedelta(days=2), status="queued")
    crepo.insert_sources([{"piece_id": p2["id"], "position": i, "source_type": "asset", "source_id": s["source_id"],
                           "comercio_id": "com-1", "file_ref": s["file_ref"]} for i, s in enumerate(crepo.list_sources(p1["id"]))])
    crepo.pieces[p2["id"]]["render_next_at"] = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    assert cr.render_tick(crepo)["piece_id"] == p1["id"]                          # la otra todavía espera
    crepo.pieces[p2["id"]]["render_next_at"] = datetime.now(timezone.utc).isoformat()
    assert cr.render_tick(crepo)["piece_id"] == p2["id"]


def test_timeout_reintenta_con_espera_y_al_tercer_intento_falla(repo, crepo, listo):
    p, _ = _en_cola(repo, crepo)
    listo["respuesta"] = {"ok": False, "error": "El render pasó de 300 s", "retryable": True}
    ahora = datetime.now(timezone.utc)
    cr.render_tick(crepo, ahora)
    n = crepo.pieces[p["id"]]
    assert n["status"] == "queued" and n["render_attempts"] == 1 and n["render_error"] == "El render pasó de 300 s"
    assert datetime.fromisoformat(n["render_next_at"]) - ahora == timedelta(minutes=10)
    assert cr.render_tick(crepo, ahora + timedelta(minutes=1)) is None                  # todavía espera
    cr.render_tick(crepo, ahora + timedelta(minutes=11))
    n = crepo.pieces[p["id"]]
    assert n["render_attempts"] == 2 and datetime.fromisoformat(n["render_next_at"]) - (ahora + timedelta(minutes=11)) == timedelta(minutes=20)
    cr.render_tick(crepo, ahora + timedelta(minutes=40))
    n = crepo.pieces[p["id"]]
    assert n["status"] == "failed" and n["render_attempts"] == 3 and listo["veces"] == 3
    assert cr.render_tick(crepo, ahora + timedelta(hours=2)) is None                    # failed no se vuelve a tomar
    assert not cr.pieza_en_curso() and not content_storage.carpeta_tmp(p["id"]).exists()


def test_una_falla_no_reintentable_es_failed_de_una(repo, crepo, listo):
    p, _ = _en_cola(repo, crepo)
    listo["respuesta"] = {"ok": False, "error": "Falta la fuente", "retryable": False}
    cr.render_tick(crepo)
    n = crepo.pieces[p["id"]]
    assert n["status"] == "failed" and n["render_error"] == "Falta la fuente" and listo["veces"] == 1


def test_con_menos_de_4_fotos_en_el_disco_falla_sin_reintento_y_sin_correr_nada(repo, crepo, listo):
    p, fotos = _en_cola(repo, crepo, n=5)
    for a in fotos[:2]:
        content_storage.borrar(a["file_path"])
    cr.render_tick(crepo)
    n = crepo.pieces[p["id"]]
    assert n["status"] == "failed" and n["render_error"] == "no_sources" and listo["veces"] == 0


def test_una_excepcion_del_subproceso_se_trata_como_reintentable(repo, crepo, listo, monkeypatch):
    p, _ = _en_cola(repo, crepo)
    monkeypatch.setattr(cr, "_correr_subproceso", lambda r: (_ for _ in ()).throw(OSError("no se pudo lanzar")))
    cr.render_tick(crepo)
    n = crepo.pieces[p["id"]]
    assert n["status"] == "queued" and n["render_attempts"] == 1 and "OSError" in n["render_error"]


def test_una_colgada_vuelve_a_la_cola_con_un_intento_mas(repo, crepo, listo):
    p, _ = _en_cola(repo, crepo)
    ahora = datetime.now(timezone.utc)
    crepo.update_piece(p["id"], {"status": "rendering", "render_started_at": (ahora - timedelta(seconds=300 + 121)).isoformat()})
    assert cr.recuperar_colgadas(crepo, ahora) == 1
    n = crepo.pieces[p["id"]]
    assert n["status"] == "queued" and n["render_attempts"] == 1
    crepo.update_piece(p["id"], {"status": "rendering", "render_started_at": (ahora - timedelta(seconds=100)).isoformat()})
    assert cr.recuperar_colgadas(crepo, ahora) == 0                               # todavía está dentro del tiempo


def test_la_toma_es_condicional_dos_workers_no_renderizan_lo_mismo(repo, crepo, listo):
    p, _ = _en_cola(repo, crepo)
    primero = crepo.update_piece(p["id"], {"status": "rendering"}, if_status="queued")
    segundo = crepo.update_piece(p["id"], {"status": "rendering"}, if_status="queued")
    assert primero and segundo is None
    crepo.update_piece(p["id"], {"status": "queued"})
    # y el candado en memoria: con el candado tomado la vuelta no corre
    assert cr._lock.acquire(blocking=False)
    try:
        assert cr.render_tick(crepo) is None and listo["veces"] == 0
    finally:
        cr._lock.release()


def test_si_la_saltan_mientras_se_arma_el_video_nuevo_se_descarta(repo, crepo, listo):
    p, _ = _en_cola(repo, crepo)
    listo["antes_de_responder"] = lambda: crepo.update_piece(p["id"], {"status": "skipped", "skip_reason": "consent_revoked"})
    cr.render_tick(crepo)
    assert crepo.pieces[p["id"]]["status"] == "skipped"
    assert not list((Path(settings.content_dir) / "renders").rglob("*.mp4"))        # no queda el archivo


def test_al_rearmar_se_borra_el_render_anterior(repo, crepo, listo):
    p, _ = _en_cola(repo, crepo)
    cr.render_tick(crepo)
    viejo = crepo.pieces[p["id"]]["video_path"]
    crepo.update_piece(p["id"], {"status": "queued", "render_next_at": datetime.now(timezone.utc).isoformat()})
    # otro mes: otra carpeta, así que el nombre difiere y el viejo se borra
    crepo.pieces[p["id"]]["video_path"] = "renders/2020-01/x/video.mp4"
    crepo.pieces[p["id"]]["cover_path"] = "renders/2020-01/x/cover.jpg"
    content_storage.guardar("renders/2020-01/x/video.mp4", b"viejo")
    cr.render_tick(crepo)
    assert not content_storage.esta_en_disco("renders/2020-01/x/video.mp4")
    assert content_storage.esta_en_disco(crepo.pieces[p["id"]]["video_path"]) and viejo


def test_el_estado_del_worker(repo, crepo, listo, monkeypatch):
    assert cr.estado_del_worker() == "disabled"
    monkeypatch.setattr(settings, "content_render_worker", True)
    assert cr.estado_del_worker() == "idle"
    monkeypatch.setattr(cr, "ffmpeg_disponible", lambda: False)
    assert cr.estado_del_worker() == "no_ffmpeg"
    monkeypatch.setattr(cr, "ffmpeg_disponible", lambda: True)
    monkeypatch.setattr(content_storage, "disco_pausado", lambda: True)
    assert cr.estado_del_worker() == "paused_disk"
    monkeypatch.setattr(content_storage, "dir_seguro", lambda: False)
    assert cr.estado_del_worker() == "unsafe_dir"


def test_sin_ffmpeg_o_con_poco_disco_o_dir_inseguro_no_toma_trabajos(repo, crepo, listo, monkeypatch):
    p, _ = _en_cola(repo, crepo)
    monkeypatch.setattr(cr, "ffmpeg_disponible", lambda: False)
    assert cr.render_tick(crepo) is None
    monkeypatch.setattr(cr, "ffmpeg_disponible", lambda: True)
    monkeypatch.setattr(content_storage, "disco_pausado", lambda: True)
    assert cr.render_tick(crepo) is None
    monkeypatch.setattr(content_storage, "disco_pausado", lambda: False)
    monkeypatch.setattr(content_storage, "dir_seguro", lambda: False)
    assert cr.render_tick(crepo) is None
    assert crepo.pieces[p["id"]]["status"] == "queued" and listo["veces"] == 0


def test_el_comando_del_job_usa_nice_ionice_en_posix(monkeypatch, tmp_path):
    monkeypatch.setattr(cr.os, "name", "posix")
    monkeypatch.setattr(cr.shutil, "which", lambda x: f"/usr/bin/{x}")
    cmd = cr.comando_del_job(tmp_path / "job.json")
    assert cmd[:6] == ["nice", "-n", "19", "ionice", "-c", "3"] and cmd[-4:-1] == ["-m", "app.services.content_render_job", "--job"]
    monkeypatch.setattr(cr.os, "name", "nt")
    assert cr.comando_del_job(tmp_path / "job.json")[1:3] == ["-m", "app.services.content_render_job"]


def test_el_subproceso_vencido_se_mata_y_es_reintentable(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "content_render_timeout_seg", 1)
    colgado = tmp_path / "colgado.py"
    colgado.write_text("import time\ntime.sleep(60)\n")
    monkeypatch.setattr(cr, "comando_del_job", lambda ruta: [cr.sys.executable, str(colgado)])
    inicio = time.monotonic()
    r = cr._correr_subproceso(tmp_path / "job.json")
    assert r["ok"] is False and r["retryable"] is True and "pasó de 1 s" in r["error"]
    assert time.monotonic() - inicio < 20


def test_un_subproceso_que_no_contesta_json_es_reintentable(monkeypatch, tmp_path):
    muda = tmp_path / "muda.py"
    muda.write_text("print('basura')\n")
    monkeypatch.setattr(cr, "comando_del_job", lambda ruta: [cr.sys.executable, str(muda)])
    r = cr._correr_subproceso(tmp_path / "job.json")
    assert r["ok"] is False and r["retryable"] is True


# ── render REAL con ffmpeg ───────────────────────────────────────────────────

def _ffprobe(ruta):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height",
                        "-show_entries", "format=duration", "-of", "json", str(ruta)], capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


@pytest.mark.skipif(not HAY_FFMPEG, reason="ffmpeg/ffprobe no están instalados")
def test_render_real_de_4_fotos_da_un_mp4_9_16_de_15_a_25_segundos(repo, crepo, monkeypatch):
    """La pieza completa por el camino real: el padre arma el job, lanza `python -m content_render_job`, el hijo
    dibuja con Pillow y codifica con ffmpeg, y el padre deja el video en `renders/`. Mide el tiempo."""
    monkeypatch.setattr(settings, "content_render_timeout_seg", 300)
    p, _ = _en_cola(repo, crepo, n=4)
    inicio = time.monotonic()
    r = cr.render_tick(crepo)
    segundos = time.monotonic() - inicio
    print(f"\nRENDER REAL (4 fotos): {segundos:.1f} s")
    assert r and r["ok"], r
    n = crepo.pieces[p["id"]]
    assert n["status"] == "ready_for_review", n.get("render_error")
    video, portada = content_storage.safe_path(n["video_path"]), content_storage.safe_path(n["cover_path"])
    datos = _ffprobe(video)
    v = next(s for s in datos["streams"] if s["codec_type"] == "video")
    assert (v["width"], v["height"], v["codec_name"]) == (1080, 1920, "h264")
    assert any(s["codec_type"] == "audio" and s["codec_name"] == "aac" for s in datos["streams"])
    assert 14.5 <= float(datos["format"]["duration"]) <= 25.5 and float(n["duration_s"]) == 15.0
    assert video.stat().st_size > 100 * 1024 and n["video_bytes"] == video.stat().st_size
    with Image.open(portada) as im:
        assert im.format == "JPEG" and im.size == (1080, 1920)
    assert segundos < 180                                                            # el presupuesto de la spec
    assert not content_storage.carpeta_tmp(p["id"]).exists()
