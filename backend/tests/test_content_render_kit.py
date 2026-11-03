"""El render con el motor `kit` (§16.4 y §16.5): la carpeta del job v2, el cliente HTTP del contenedor `reels`, el estado
`no_renderer` y la vuelta completa del worker con el contenedor simulado."""
import json
import json as jsonlib
import os
import re
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from PIL import Image

from app.core.config import settings
from app.services import content_render as cr, content_storage, content_video_texts as cvt
from tests.content_helpers import autorizar, banco, comercio, jpg, pieza

TOKEN = "token-de-prueba-123"
FACTS = {"pillar": "comercio_del_dia", "nombre": "Boutique Andina", "rubro": "Moda", "ciudad": "Bermejo",
         "slug": "boutique-andina", "hashtags_allowed": ["#URUKU", "#Bermejo", "#Tarija", "#Bolivia"], "allowed_numbers": []}
TEXTOS = {"kick": "NUEVA TEMPORADA", "title1": "Camperas que", "title2": "ya llegaron",
          "subtitle": "Eco cuero, doble faz y más modelos", "search_term": "camperas"}


@pytest.fixture(autouse=True)
def _motor_kit(monkeypatch):
    monkeypatch.setattr(settings, "content_render_engine", "kit")
    monkeypatch.setattr(settings, "renderer_token", TOKEN)
    monkeypatch.setattr(settings, "renderer_url", "http://buscadonde-reels:8090")
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(content_storage, "disco_pausado", lambda: False)


class Resp:
    def __init__(self, status=200, datos=None, texto=None):
        self.status_code = status
        self._datos = datos
        self._texto = texto

    def json(self):
        if self._texto is not None:
            raise ValueError("no es json")
        return self._datos


@pytest.fixture
def contenedor(monkeypatch):
    """El contenedor `reels` simulado: `/health` vivo y `POST /render` que deja video y portada en la carpeta del job."""
    est = {"posts": [], "gets": 0, "job": None, "fotos": [], "modos": None, "respuesta": None, "salud": True}

    def get(url, timeout=None):
        est["gets"] += 1
        if not est["salud"]:
            raise httpx.ConnectError("sin contenedor")
        return Resp(200, {"ok": True, "chromium": True, "ffmpeg": True, "busy": False})

    def post(url, json=None, headers=None, timeout=None):
        est["posts"].append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        carpeta = content_storage.carpeta_tmp(json["piece_id"])
        est["job"] = jsonlib.loads((carpeta / "job.json").read_text(encoding="utf-8"))
        est["fotos"] = sorted(p.name for p in carpeta.glob("s*.jpg"))
        est["modos"] = {"carpeta": oct(os.stat(carpeta).st_mode & 0o777), "job": oct(os.stat(carpeta / "job.json").st_mode & 0o777),
                        "foto": oct(os.stat(carpeta / "s0.jpg").st_mode & 0o777)}
        r = est["respuesta"] or Resp(200, {"ok": True, "duration_s": 14.0, "video_bytes": 200_000, "render_ms": 61000, "frames": 420})
        if r.status_code == 200 and r._datos and r._datos.get("ok"):
            (carpeta / "video.mp4").write_bytes(b"v" * 200_000)
            (carpeta / "cover.jpg").write_bytes(b"c" * 1000)
        return r
    monkeypatch.setattr(cr.httpx, "get", get)
    monkeypatch.setattr(cr.httpx, "post", post)
    cr.reiniciar_salud()
    return est


def _en_cola(repo, crepo, n=5, version=2, texts=True, **kw):
    comercio(repo, rubros={"nombre": "Moda", "slug": "moda"})
    autorizar(crepo, "com-1")
    fotos = banco(crepo, "com-1", n)
    extra = {"video_texts": cvt.armar_textos(TEXTOS, "comercio_del_dia", FACTS), "video_texts_engine": "human"} if texts else {}
    p = pieza(crepo, "com-1", status="queued", facts=FACTS, template_version=version, **extra, **kw)
    crepo.insert_sources([{"piece_id": p["id"], "position": i, "source_type": "asset", "source_id": a["id"],
                           "comercio_id": "com-1", "file_ref": a["file_path"], "chip_text": f"Frase de {i}" if i else None,
                           "focus_y": 0.3 if i == 1 else None} for i, a in enumerate(fotos)])
    return p, fotos


# ══════════════════════════════════════════════════════════════ el cliente HTTP

def _con_post(monkeypatch, respuesta=None, excepcion=None):
    visto = {}

    def post(url, json=None, headers=None, timeout=None):
        visto.update(url=url, json=json, headers=headers, timeout=timeout)
        if excepcion:
            raise excepcion
        return respuesta
    monkeypatch.setattr(cr.httpx, "post", post)
    return visto


def test_el_pedido_lleva_el_token_el_piece_id_y_el_plazo(monkeypatch):
    visto = _con_post(monkeypatch, Resp(200, {"ok": True, "duration_s": 14.0, "render_ms": 5}))
    monkeypatch.setattr(settings, "renderer_url", "http://reels:8090/")
    r = cr._pedir_render_kit("11111111-1111-1111-1111-111111111111")
    assert r["ok"] is True and r["duration_s"] == 14.0
    assert visto["url"] == "http://reels:8090/render" and visto["json"] == {"piece_id": "11111111-1111-1111-1111-111111111111"}
    assert visto["headers"] == {"Authorization": f"Bearer {TOKEN}"}
    assert visto["timeout"].read == settings.content_render_timeout_seg and visto["timeout"].connect == 10


def test_ok_false_del_contenedor_pasa_con_su_motivo_y_su_reintentable(monkeypatch):
    _con_post(monkeypatch, Resp(200, {"ok": False, "error": "Chromium se cerró", "retryable": True}))
    assert cr._pedir_render_kit("p") == {"ok": False, "error": "Chromium se cerró", "retryable": True}
    _con_post(monkeypatch, Resp(200, {"ok": False, "error": "Foto corrupta", "retryable": False}))
    assert cr._pedir_render_kit("p")["retryable"] is False
    _con_post(monkeypatch, Resp(200, {"ok": False}))
    r = cr._pedir_render_kit("p")
    assert r["ok"] is False and r["retryable"] is True and r["error"]


def test_409_ocupado_es_reintentable(monkeypatch):
    _con_post(monkeypatch, Resp(409, {"ok": False, "error": "Ocupado", "retryable": True}))
    r = cr._pedir_render_kit("p")
    assert r["ok"] is False and r["retryable"] is True and "ocupado" in r["error"]


def test_timeout_y_errores_de_red_son_reintentables(monkeypatch):
    _con_post(monkeypatch, excepcion=httpx.ReadTimeout("lento"))
    r = cr._pedir_render_kit("p")
    assert r == {"ok": False, "error": f"El render pasó de {settings.content_render_timeout_seg} s", "retryable": True}
    _con_post(monkeypatch, excepcion=httpx.ConnectError("no hay red"))
    r = cr._pedir_render_kit("p")
    assert r["retryable"] is True and "ConnectError" in r["error"]


def test_401_no_es_reintentable_y_el_token_no_se_filtra(monkeypatch, caplog):
    _con_post(monkeypatch, Resp(401, {"error": "no autorizado"}))
    r = cr._pedir_render_kit("p")
    assert r["ok"] is False and r["retryable"] is False and "RENDERER_TOKEN" in r["error"]
    assert TOKEN not in r["error"] and TOKEN not in caplog.text


def test_400_5xx_y_respuesta_ilegible(monkeypatch):
    _con_post(monkeypatch, Resp(400, {"error": "mal"}))
    assert cr._pedir_render_kit("p")["retryable"] is False
    _con_post(monkeypatch, Resp(502, {}))
    r = cr._pedir_render_kit("p")
    assert r["retryable"] is True and "502" in r["error"]
    _con_post(monkeypatch, Resp(200, texto="<html>"))
    assert cr._pedir_render_kit("p")["retryable"] is True
    _con_post(monkeypatch, Resp(200, ["no", "es", "un", "dict"]))
    assert cr._pedir_render_kit("p")["retryable"] is True


# ══════════════════════════════════════════════════════════════ estado del worker

def test_estado_no_renderer_sin_token_o_sin_health(monkeypatch, contenedor):
    monkeypatch.setattr(settings, "content_render_worker", True)
    monkeypatch.setattr(settings, "renderer_token", "")
    assert cr.estado_del_worker() == "no_renderer" and contenedor["gets"] == 0      # sin token ni pregunta
    monkeypatch.setattr(settings, "renderer_token", TOKEN)
    contenedor["salud"] = False
    cr.reiniciar_salud()
    assert cr.estado_del_worker() == "no_renderer"
    contenedor["salud"] = True
    cr.reiniciar_salud()
    assert cr.estado_del_worker() == "idle"
    monkeypatch.setattr(content_storage, "disco_pausado", lambda: True)
    assert cr.estado_del_worker() == "paused_disk"


def test_el_health_se_cachea_unos_segundos(monkeypatch, contenedor):
    monkeypatch.setattr(settings, "content_render_worker", True)
    for _ in range(5):
        assert cr.estado_del_worker() == "idle"
    assert contenedor["gets"] == 1
    cr._salud["hasta"] = 0.0                                                         # venció el caché
    cr.estado_del_worker()
    assert contenedor["gets"] == 2


def test_un_health_con_chromium_caido_cuenta_como_no_disponible(monkeypatch):
    monkeypatch.setattr(cr.httpx, "get", lambda url, timeout=None: Resp(200, {"ok": True, "chromium": False, "ffmpeg": True}))
    cr.reiniciar_salud()
    assert cr.renderer_vivo() is False
    monkeypatch.setattr(cr.httpx, "get", lambda url, timeout=None: Resp(500, {}))
    cr.reiniciar_salud()
    assert cr.renderer_vivo() is False


def test_con_pillow_el_estado_sigue_mirando_ffmpeg(monkeypatch):
    monkeypatch.setattr(settings, "content_render_worker", True)
    monkeypatch.setattr(settings, "content_render_engine", "pillow")
    monkeypatch.setattr(cr, "ffmpeg_disponible", lambda: False)
    assert cr.estado_del_worker() == "no_ffmpeg"


def test_sin_renderer_el_worker_no_toma_trabajos(repo, crepo, monkeypatch, contenedor):
    p, _ = _en_cola(repo, crepo)
    monkeypatch.setattr(settings, "renderer_token", "")
    assert cr.render_tick(crepo) is None
    monkeypatch.setattr(settings, "renderer_token", TOKEN)
    contenedor["salud"] = False
    cr.reiniciar_salud()
    assert cr.render_tick(crepo) is None
    assert crepo.pieces[p["id"]]["status"] == "queued" and contenedor["posts"] == []


# ══════════════════════════════════════════════════════════════ la carpeta del job (§16.4)

def test_el_job_json_es_el_del_contrato(repo, crepo, contenedor):
    p, fotos = _en_cola(repo, crepo, n=5)
    assert cr.render_tick(crepo) == {"piece_id": p["id"], "ok": True, "error": None}
    job = contenedor["job"]
    assert list(job) == ["version", "piece_id", "template", "format", "fps", "texts", "icons", "slides", "out_video", "out_cover"]
    assert (job["version"], job["template"], job["format"], job["fps"]) == (2, "t1", "9x16", 30)
    assert job["piece_id"] == p["id"] and job["out_video"] == "video.mp4" and job["out_cover"] == "cover.jpg"
    assert job["texts"] == {
        "kick": "NUEVA TEMPORADA", "title1": "Camperas que", "title2": "ya llegaron",
        "subtitle": "Eco cuero, doble faz y más modelos", "close_title1": "¿Dónde lo", "close_title2": "consigue?",
        "search_term": "camperas", "place_chip": "Boutique Andina · Bermejo",
        "close_line": "Consulte precio directo con el local", "url": "uruku.bo", "lema": "Si está en Bolivia, está en Uruku."}
    assert job["icons"] == ["pin", "whatsapp"]
    assert job["slides"] == [{"file": "s0.jpg", "chip": None, "focus_y": None},
                             {"file": "s1.jpg", "chip": "Frase de 1", "focus_y": 0.3},
                             {"file": "s2.jpg", "chip": "Frase de 2", "focus_y": None},
                             {"file": "s3.jpg", "chip": "Frase de 3", "focus_y": None},
                             {"file": "s4.jpg", "chip": "Frase de 4", "focus_y": None}]
    assert all(re.fullmatch(r"s\d{1,2}\.jpg", s["file"]) for s in job["slides"]) and contenedor["fotos"] == [s["file"] for s in job["slides"]]
    # el POST va con el piece_id y nada más
    assert contenedor["posts"][0]["json"] == {"piece_id": p["id"]} and contenedor["posts"][0]["url"].endswith(":8090/render")


def test_el_cierre_de_ofertas_sale_fijo_y_con_sus_iconos(repo, crepo, contenedor):
    from tests.test_content_revision_fixes import _compilado_armado
    p = _compilado_armado(repo, crepo, n=5, status="queued")
    facts = {**p["facts"], "items": [{"nombre": f"Local s{i}"} for i in range(5)]}
    crepo.pieces[p["id"]].update(template_version=2, facts=facts, video_texts=cvt.armar_textos(
        cvt.textos_fijos("ofertas", facts), "ofertas", facts))
    for i, f in enumerate(crepo.list_sources(p["id"])):
        f.update(chip_text=f"Local s{i}", file_ref=f"/fotos/x{i}.jpg")
    # las fotos de las ofertas: URLs públicas a archivos reales
    fotos_dir = Path(settings.fotos_dir)
    fotos_dir.mkdir(parents=True, exist_ok=True)
    for i, f in enumerate(crepo.list_sources(p["id"])):
        (fotos_dir / f"x{i}.jpg").write_bytes(jpg(1200, 1000, seed=i))
        f["file_ref"] = f"{settings.fotos_public_base_url.rstrip('/')}/x{i}.jpg"
    assert cr.render_tick(crepo)["ok"] is True
    job = contenedor["job"]
    assert job["icons"] == ["oferta", "pin"] and job["texts"]["close_title1"] == "¿Dónde las"
    assert job["texts"]["close_line"] == "Vea todas las ofertas en Uruku" and job["texts"]["place_chip"] is None
    assert [s["chip"] for s in job["slides"]] == [f"Local s{i}" for i in range(5)]


def test_los_textos_de_cierre_salen_siempre_de_la_base_aunque_el_guardado_diga_otra_cosa(repo, crepo, contenedor):
    p, _ = _en_cola(repo, crepo)
    crepo.pieces[p["id"]]["video_texts"] = {**crepo.pieces[p["id"]]["video_texts"], "close_line": "Precio Bs 5", "lema": "otro"}
    cr.render_tick(crepo)
    assert contenedor["job"]["texts"]["close_line"] == "Consulte precio directo con el local"
    assert contenedor["job"]["texts"]["lema"] == "Si está en Bolivia, está en Uruku."


def test_a_lo_sumo_6_fotos_y_cada_una_pasa_por_la_preparacion(repo, crepo, contenedor):
    p, _ = _en_cola(repo, crepo, n=8)
    cr.render_tick(crepo)
    assert len(contenedor["job"]["slides"]) == 6
    # las que no entraron no cuentan como usadas
    assert sum(a["use_count"] for a in crepo.assets.values()) == 6


def test_menos_de_4_fotos_que_se_puedan_preparar_falla_sin_reintento_y_sin_llamar(repo, crepo, contenedor):
    p, fotos = _en_cola(repo, crepo, n=5)
    for a in fotos[:2]:
        content_storage.borrar(a["file_path"])
    cr.render_tick(crepo)
    n = crepo.pieces[p["id"]]
    assert n["status"] == "failed" and n["render_error"] == "no_sources" and contenedor["posts"] == []
    assert not content_storage.carpeta_tmp(p["id"]).exists()


def test_una_foto_ilegible_se_saltea(repo, crepo, contenedor):
    p, fotos = _en_cola(repo, crepo, n=5)
    content_storage.safe_path(fotos[0]["file_path"]).write_bytes(b"no es una imagen")
    cr.render_tick(crepo)
    assert len(contenedor["job"]["slides"]) == 4 and contenedor["job"]["slides"][0]["file"] == "s0.jpg"


def test_la_foto_preparada_va_reorientada_a_1200_en_rgb_sin_exif(tmp_path):
    origen = tmp_path / "o.jpg"
    destino = tmp_path / "s0.jpg"
    exif = Image.Exif()
    exif[274] = 6                                   # Orientation: girar 90° (las fotos del celular)
    exif[271] = "CamaraSecreta"
    Image.open(BytesIO(jpg(2400, 1600, seed=3))).convert("L").save(origen, format="JPEG", exif=exif)
    assert cr._preparar_foto(origen, destino) is True
    with Image.open(destino) as im:
        assert im.format == "JPEG" and im.mode == "RGB"
        assert im.size == (800, 1200)               # 2400x1600 reorientada = 1600x2400 -> lado mayor 1200
        assert not im.getexif() and "exif" not in im.info
    chica = tmp_path / "c.jpg"
    Image.open(BytesIO(jpg(900, 700, seed=4))).save(chica, format="JPEG")
    assert cr._preparar_foto(chica, tmp_path / "s1.jpg")
    with Image.open(tmp_path / "s1.jpg") as im:
        assert im.size == (900, 700)                # nunca se agranda
    assert cr._preparar_foto(tmp_path / "no-existe.jpg", tmp_path / "s2.jpg") is False
    assert not (tmp_path / "s2.jpg").exists()


def test_el_n1_suave_se_aplica_a_la_foto_preparada(tmp_path):
    from app.services.content_render_job import n1_suave
    origen = tmp_path / "o.jpg"
    Image.new("RGB", (800, 600), (60, 70, 80)).save(origen, format="JPEG", quality=100)
    assert cr._preparar_foto(origen, tmp_path / "d.jpg")
    with Image.open(tmp_path / "d.jpg") as hecha, Image.open(origen) as vieja:
        esperada = n1_suave(vieja.convert("RGB"))
        assert abs(hecha.getpixel((400, 300))[0] - esperada.getpixel((400, 300))[0]) <= 6
        assert hecha.getpixel((400, 300)) != (60, 70, 80)                                  # el retoque cambió algo


@pytest.mark.skipif(os.name != "posix", reason="los modos de archivo de POSIX no aplican en Windows")
def test_la_carpeta_del_job_es_777_y_los_archivos_644(repo, crepo, contenedor, monkeypatch):
    """El contenedor corre como pwuser y el backend como root: sin 777 reels no puede escribir el mp4, y no se confía
    en el umask del proceso."""
    previo = os.umask(0o077)
    try:
        _en_cola(repo, crepo)
        cr.render_tick(crepo)
    finally:
        os.umask(previo)
    assert contenedor["modos"] == {"carpeta": "0o777", "job": "0o644", "foto": "0o644"}


def test_la_carpeta_del_job_se_prepara_con_modos_que_dejan_escribir_al_contenedor(repo, crepo):
    """Aunque no se pueda verificar el modo (Windows), la carpeta y los archivos existen donde el contenedor los espera."""
    p, _ = _en_cola(repo, crepo)
    ruta_job, job, usadas = cr._preparar_job(crepo, crepo.get_piece(p["id"]))
    carpeta = content_storage.carpeta_tmp(p["id"])
    assert ruta_job == carpeta / "job.json" and (carpeta / "s0.jpg").is_file() and len(usadas) == 5
    assert job["out_video"] == str(carpeta / "video.mp4") and job["out_cover"] == str(carpeta / "cover.jpg")
    # el job.json del disco lleva los nombres fijos, no las rutas absolutas
    assert json.loads(ruta_job.read_text(encoding="utf-8"))["out_video"] == "video.mp4"
    if os.name == "posix":
        assert oct(os.stat(carpeta).st_mode & 0o777) == "0o777" and oct(os.stat(ruta_job).st_mode & 0o777) == "0o644"


# ══════════════════════════════════════════════════════════════ la vuelta completa

def test_un_render_exitoso_deja_la_pieza_lista_para_revisar(repo, crepo, contenedor):
    p, fotos = _en_cola(repo, crepo)
    assert cr.render_tick(crepo)["ok"] is True
    n = crepo.pieces[p["id"]]
    assert n["status"] == "ready_for_review" and n["render_ms"] == 61000 and float(n["duration_s"]) == 14.0
    assert n["video_path"].endswith(f"{p['id']}/video.mp4") and content_storage.safe_path(n["video_path"]).stat().st_size == 200_000
    assert content_storage.safe_path(n["cover_path"]).is_file() and not content_storage.carpeta_tmp(p["id"]).exists()
    assert all(crepo.assets[a["id"]]["use_count"] == 1 for a in fotos)


@pytest.mark.parametrize("respuesta, reintentable", [
    (Resp(409, {"ok": False, "error": "Ocupado", "retryable": True}), True),
    (Resp(200, {"ok": False, "error": "Chromium murió", "retryable": True}), True),
    (Resp(502, {}), True),
])
def test_las_fallas_reintentables_vuelven_a_la_cola_con_espera_y_al_tercer_intento_fallan(repo, crepo, contenedor, respuesta, reintentable):
    p, _ = _en_cola(repo, crepo)
    contenedor["respuesta"] = respuesta
    ahora = datetime.now(timezone.utc)
    cr.render_tick(crepo, ahora)
    n = crepo.pieces[p["id"]]
    assert n["status"] == "queued" and n["render_attempts"] == 1
    assert datetime.fromisoformat(n["render_next_at"]) - ahora == timedelta(minutes=10)
    cr.render_tick(crepo, ahora + timedelta(minutes=11))
    cr.render_tick(crepo, ahora + timedelta(minutes=40))
    n = crepo.pieces[p["id"]]
    assert n["status"] == "failed" and n["render_attempts"] == 3 and len(contenedor["posts"]) == 3


def test_el_timeout_del_contenedor_es_reintentable(repo, crepo, contenedor, monkeypatch):
    p, _ = _en_cola(repo, crepo)

    def lento(url, json=None, headers=None, timeout=None):
        raise httpx.ReadTimeout("lento")
    monkeypatch.setattr(cr.httpx, "post", lento)
    cr.render_tick(crepo)
    n = crepo.pieces[p["id"]]
    assert n["status"] == "queued" and n["render_attempts"] == 1 and "pasó de" in n["render_error"]
    assert not content_storage.carpeta_tmp(p["id"]).exists()


def test_un_401_falla_la_pieza_de_una(repo, crepo, contenedor):
    p, _ = _en_cola(repo, crepo)
    contenedor["respuesta"] = Resp(401, {"error": "no"})
    cr.render_tick(crepo)
    n = crepo.pieces[p["id"]]
    assert n["status"] == "failed" and "RENDERER_TOKEN" in n["render_error"] and len(contenedor["posts"]) == 1


def test_una_pieza_v1_se_pasa_a_v2_con_sus_textos_antes_de_armarse(repo, crepo, contenedor):
    p, _ = _en_cola(repo, crepo, version=1, texts=False)
    cr.render_tick(crepo)
    n = crepo.pieces[p["id"]]
    assert n["status"] == "ready_for_review" and n["template_version"] == 2
    assert n["video_texts_engine"] == "template" and n["video_texts"]["title1"] == "Moda"
    assert contenedor["job"]["texts"]["kick"] == "EN BERMEJO" and contenedor["job"]["version"] == 2


def test_una_pieza_sin_autorizacion_no_llama_al_contenedor(repo, crepo, contenedor):
    p, _ = _en_cola(repo, crepo)
    autorizar(crepo, "com-1", granted=False)
    r = cr.render_tick(crepo)
    assert r["ok"] is False and crepo.pieces[p["id"]]["skip_reason"] == "consent_revoked" and contenedor["posts"] == []


def test_con_pillow_todo_sigue_como_antes(repo, crepo, contenedor, monkeypatch):
    p, _ = _en_cola(repo, crepo)
    monkeypatch.setattr(settings, "content_render_engine", "pillow")
    monkeypatch.setattr(cr, "ffmpeg_disponible", lambda: True)
    visto = {}

    def falso(ruta_job):
        visto["job"] = json.loads(Path(ruta_job).read_text(encoding="utf-8"))
        Path(visto["job"]["out_video"]).write_bytes(b"v" * 1000)
        Path(visto["job"]["out_cover"]).write_bytes(b"c")
        return {"ok": True, "duration_s": 15.0, "render_ms": 3}
    monkeypatch.setattr(cr, "_correr_subproceso", falso)
    cr.render_tick(crepo)
    assert contenedor["posts"] == [] and "slides" in visto["job"] and "path" in visto["job"]["slides"][0]
    assert visto["job"]["template_version"] == 2 and crepo.pieces[p["id"]]["status"] == "ready_for_review"
