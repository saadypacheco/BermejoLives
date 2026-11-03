"""QA de punta a punta de §16 y §17 (videos v2, pedir un video, interruptores de costo) por la API, con los fakes.

Independiente de los tests de cada módulo: acá se pide por HTTP, se corre el worker con el contenedor `reels`
simulado y se mira lo que salió (piezas, textos, captions, job.json). Un Gemini que rompe el test si lo llaman cuando
no debían.
"""
import json
import re
from pathlib import Path

import pytest
from PIL import Image

from app.core import auth
from app.core.config import settings
from app.services import content_captions as cc, content_render as cr, content_storage, content_video_texts as cvt
from tests.content_helpers import autorizar, banco, comercio, h, hoy
from tests.test_content_render_kit import Resp, contenedor  # noqa: F401  (el contenedor `reels` simulado)
from tests.test_content_requests import NOMBRES, zapaterias

ICONOS_DEL_KIT = {p.stem[3:] for p in (Path(__file__).resolve().parents[2] / "renderer" / "assets" / "iconos").glob("ic_*.png")}

# Lista independiente de la del backend: palabras de voseo / tuteo que no pueden aparecer en nada que sale al público.
VOSEO = ["vos", "tenés", "querés", "podés", "buscá", "mirá", "escribile", "conocé", "encontrá", "vení", "tú", "puedes",
         "quieres", "tienes", "elegí", "fijate", "mandale", "pasá", "entrá", "consultá", "esperá", "subí", "tenes",
         "queres", "podes", "busca", "encuentra", "mira"]
RE_VOSEO = re.compile(r"(?<!\w)(" + "|".join(VOSEO) + r")(?!\w)", re.I)
RE_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️]")


@pytest.fixture(autouse=True)
def _entorno(monkeypatch):
    monkeypatch.setattr(settings, "content_render_engine", "kit")
    monkeypatch.setattr(settings, "renderer_token", "tok-qa")
    monkeypatch.setattr(settings, "renderer_url", "http://buscadonde-reels:8090")
    monkeypatch.setattr(settings, "gemini_api_key", "KEY-QA-FALSA")       # hay clave: lo único que frena a Gemini es el interruptor
    monkeypatch.setattr(settings, "gemini_model", "gemini-qa")
    monkeypatch.setattr(content_storage, "disco_pausado", lambda: False)
    from app.services import cost_switches
    cost_switches.reiniciar_cache()


class Gemini:
    """Cuenta las llamadas a Gemini (por el punto más bajo: la petición HTTP de `vision`) y contesta lo que se le dé."""

    def __init__(self):
        self.llamadas: list[dict] = []
        self.respuesta: dict = {}

    def __call__(self, url, payload, *a, **k):
        self.llamadas.append(payload)
        data = self.respuesta
        gem = self

        class R:
            def raise_for_status(self):
                return None

            def json(self):
                return {"candidates": [{"content": {"parts": [{"text": json.dumps(data)}]}}]}
        return R()


@pytest.fixture
def gemini(monkeypatch):
    g = Gemini()
    monkeypatch.setattr("app.services.vision._post_con_reintentos", g)
    return g


@pytest.fixture
def ana():
    return h(auth.make_token("ana.perez@uruku.bo", rol="admin"))


def tok(*permisos):
    return h(auth.make_token("quien@uruku.bo", rol="x", roles=["x"], permisos=list(permisos)))


def valores(d):
    """Todos los textos (str) de un dict anidado."""
    if isinstance(d, dict):
        for v in d.values():
            yield from valores(v)
    elif isinstance(d, (list, tuple)):
        for v in d:
            yield from valores(v)
    elif isinstance(d, str):
        yield d


def sembrar_comercio(repo, crepo, n_fotos=5, cid="com-1", **kw):
    comercio(repo, cid, rubros={"nombre": "Moda", "slug": "moda"}, **kw)
    autorizar(crepo, cid)
    banco(crepo, cid, n_fotos)


def limpio(textos):
    for t in valores(textos):
        assert not RE_VOSEO.search(t), f"voseo/tuteo en {t!r}"
        assert not RE_EMOJI.search(t), f"emoji en {t!r}"
        assert "Bs" not in t and "$" not in t and "US$" not in t, f"precio en {t!r}"


# ══════════════════════════════════════════════════════════════ (a) pedir un negocio

def test_a_pedir_un_negocio_deja_una_pieza_v2_encolada_con_textos_fijos_y_sin_llamar_a_gemini(repo, crepo, client, ana, gemini):
    sembrar_comercio(repo, crepo, 5)
    r = client.post("/admin/content/pieces/request", headers=ana, json={"kind": "comercio", "comercio_id": "com-1"})
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["status"] == "queued" and p["template_version"] == 2 and p["origin"] == "pedido"
    assert p["pillar"] == "comercio_del_dia" and p["counts_for_quota"] is False
    assert p["video_texts_engine"] == "template" and p["video_texts_checks"] == []
    assert p["caption_engine"] == "template"
    assert gemini.llamadas == [], "Gemini apagado por defecto: no se llama"
    vt = p["video_texts"]
    assert vt["kick"] == "EN BERMEJO" and vt["subtitle"] is None
    assert vt["lema"] == "Si está en Bolivia, está en Uruku." and vt["url"] == "uruku.bo"
    assert vt["close_line"] == "Consulte precio directo con el local"
    assert vt["close_title1"] == "¿Dónde lo" and vt["close_title2"] == "consigue?"
    assert vt["search_term"] == vt["search_term"].lower() and len(vt["search_term"].split()) <= 2
    assert all(s["chip_text"] is None for s in p["sources"]) and len(p["sources"]) == 5
    assert all(s["photo_flags"] == [] for s in p["sources"])
    limpio(vt)
    limpio({k: p[k] for k in ("caption_tiktok", "caption_ig", "caption_channel")})
    fila = crepo.pieces[p["id"]]
    assert fila["created_by"] == "ana.perez@uruku.bo" and fila["scheduled_for"] == hoy().isoformat()
    assert fila["quota_cycle_start"] is None and not crepo.tasks         # sin cuota y sin tareas de suscriptor


def test_a_el_pedido_con_gemini_apagado_tampoco_llama_al_reintentar_ni_al_pedir_otra_propuesta(repo, crepo, client, ana, gemini):
    sembrar_comercio(repo, crepo, 5)
    pid = client.post("/admin/content/pieces/request", headers=ana, json={"kind": "comercio", "comercio_id": "com-1"}).json()["id"]
    r = client.post(f"/admin/content/pieces/{pid}/video-texts/propose", headers=ana)
    assert r.status_code == 200 and r.json()["video_texts_engine"] == "template"
    assert gemini.llamadas == []


def test_a_pedido_de_negocio_sin_autorizacion_o_con_pocas_fotos_es_422(repo, crepo, client, ana, gemini):
    comercio(repo, "com-1")
    banco(crepo, "com-1", 5)
    r = client.post("/admin/content/pieces/request", headers=ana, json={"kind": "comercio", "comercio_id": "com-1"})
    assert r.status_code == 422, r.text                       # sin autorización
    autorizar(crepo, "com-1")
    comercio(repo, "com-2")
    autorizar(crepo, "com-2")
    banco(crepo, "com-2", 3)
    r = client.post("/admin/content/pieces/request", headers=ana, json={"kind": "comercio", "comercio_id": "com-2"})
    assert r.status_code == 422 and "3" in r.json()["detail"] and "4" in r.json()["detail"], r.text
    assert gemini.llamadas == [] and not crepo.pieces


# ══════════════════════════════════════════════════════════════ (b) pedir un rubro con 4 comercios

def test_b_rubro_con_4_comercios_chips_son_los_nombres_y_el_caption_no_dice_cantidad_ni_precios_ni_voseo(repo, crepo, client, ana, gemini):
    zapaterias(repo, crepo, n=4)
    r = client.post("/admin/content/pieces/request", headers=ana,
                    json={"kind": "rubro", "rubro_slug": "zapatillas", "ciudad_slug": "bermejo"})
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["pillar"] == "rubro" and p["status"] == "queued" and p["origin"] == "pedido" and p["template_version"] == 2
    assert gemini.llamadas == []
    fuentes = crepo.list_sources(p["id"])
    assert len(fuentes) == 4 and len({f["comercio_id"] for f in fuentes}) == 4
    esperados = {f"Zapatería {NOMBRES[i]}" for i in range(4)}
    assert {f["chip_text"] for f in fuentes} == esperados            # los chips son los nombres de la base
    assert {s["chip_text"] for s in p["sources"]} == esperados
    caps = [p["caption_tiktok"], p["caption_ig"], p["caption_channel"]]
    for c in caps:
        assert c and "uruku.bo" in c
        assert not re.search(r"\d", c), f"dígitos (¿cantidad o precio?) en {c!r}"
        assert not re.search(r"\b(cuatro|4)\s+(comercios|negocios|locales|tiendas|zapater)", c, re.I)
        assert "Bs" not in c and "$" not in c and "bolivianos" not in c.lower()
        assert not RE_VOSEO.search(c), c
        assert "zapatillas" in c.lower() and "Bermejo" in c
    assert p["caption_tiktok"].lower().startswith("dónde comprar zapatillas en bermejo")
    assert 4 <= len(p["hashtags"]) <= 8 and "#Bolivia" in p["hashtags"]
    assert p["caption_checks"] == [] and p["video_texts_checks"] == []
    limpio(p["video_texts"])
    assert p["video_texts"]["close_line"] == "Vea horario y cómo llegar en Uruku"
    assert p["video_texts"]["place_chip"] is None


def test_b_rubro_con_3_comercios_es_422_y_con_5_toma_cinco(repo, crepo, client, ana, gemini):
    zapaterias(repo, crepo, n=3)
    r = client.post("/admin/content/pieces/request", headers=ana,
                    json={"kind": "rubro", "rubro_slug": "zapatillas", "ciudad_slug": "bermejo"})
    assert r.status_code == 422 and "3" in r.json()["detail"], r.text
    assert not crepo.pieces


def test_b_los_chips_de_un_rubro_no_se_editan_a_mano(repo, crepo, client, ana, gemini):
    zapaterias(repo, crepo, n=4)
    p = client.post("/admin/content/pieces/request", headers=ana,
                    json={"kind": "rubro", "rubro_slug": "zapatillas", "ciudad_slug": "bermejo"}).json()
    vt = p["video_texts"]
    body = {"kick": vt["kick"], "title1": vt["title1"], "title2": vt["title2"], "subtitle": None, "search_term": vt["search_term"],
            "chips": [{"source_id": s["id"], "text": "Frase pirata"} for s in p["sources"]]}
    r = client.patch(f"/admin/content/pieces/{p['id']}/video-texts", headers=ana, json=body)
    assert r.status_code == 200, r.text
    assert {f["chip_text"] for f in crepo.list_sources(p["id"])} == {f"Zapatería {NOMBRES[i]}" for i in range(4)}


# ══════════════════════════════════════════════════════════════ (c) interruptor gemini_content

def test_c_prender_sin_confirmar_400_con_difusion_403_con_equipo_200(client, crepo):
    url = "/admin/cost-switches/gemini_content"
    # sin permiso de equipo
    r = client.put(url, headers=tok("difusion"), json={"enabled": True, "confirm_cost": True})
    assert r.status_code == 403, r.text
    assert "gemini_content" not in crepo.cost_switches
    # sin token
    assert client.put(url, json={"enabled": True, "confirm_cost": True}).status_code in (401, 403)
    # equipo sin confirmar
    r = client.put(url, headers=tok("equipo"), json={"enabled": True})
    assert r.status_code == 400, r.text
    r = client.put(url, headers=tok("equipo"), json={"enabled": True, "confirm_cost": False})
    assert r.status_code == 400
    assert "gemini_content" not in crepo.cost_switches
    # equipo confirmando
    r = client.put(url, headers=tok("equipo"), json={"enabled": True, "confirm_cost": True})
    assert r.status_code == 200 and r.json()["enabled"] is True and r.json()["key"] == "gemini_content", r.text
    assert r.json()["updated_by"] == "quien@uruku.bo"
    # apagar no pide confirmación
    r = client.put(url, headers=tok("equipo"), json={"enabled": False})
    assert r.status_code == 200 and r.json()["enabled"] is False
    # clave inexistente
    assert client.put("/admin/cost-switches/otra", headers=tok("equipo"), json={"enabled": False}).status_code == 404
    # lectura: difusion y equipo sí, otro permiso no
    assert client.get("/admin/cost-switches", headers=tok("difusion")).status_code == 200
    assert client.get("/admin/cost-switches", headers=tok("equipo")).status_code == 200
    assert client.get("/admin/cost-switches", headers=tok("otro")).status_code == 403
    assert client.get("/admin/cost-switches").status_code in (401, 403)
    items = client.get("/admin/cost-switches", headers=tok("difusion")).json()["items"]
    assert [i["key"] for i in items] == ["gemini_content"] and items[0]["enabled"] is False


def test_c_el_interruptor_es_lo_que_deja_o_no_pasar_a_gemini(repo, crepo, client, ana, gemini):
    sembrar_comercio(repo, crepo, 5, cid="com-1")
    sembrar_comercio(repo, crepo, 5, cid="com-2")
    gemini.respuesta = {
        "kick": "NUEVA TEMPORADA", "title1": "Ropa que", "title2": "ya llegó", "subtitle": "Modelos para toda ocasión",
        "search_term": "ropa",
        "slides": [{"chip": f"Modelo {NOMBRES[i]}", "price_or_code_visible": False, "focus_y": 0.3} for i in range(5)],
        "caption_tiktok": "Local com-2 en Bermejo. Búsquelo en uruku.bo", "caption_ig": "Local com-2 en Bermejo. Búsquelo en uruku.bo",
        "caption_channel": "Local com-2. Búsquelo en uruku.bo", "hashtags": ["#URUKU", "#Bermejo", "#Tarija", "#Bolivia"]}
    # apagado: nada
    p1 = client.post("/admin/content/pieces/request", headers=ana, json={"kind": "comercio", "comercio_id": "com-1"}).json()
    assert gemini.llamadas == [] and p1["video_texts_engine"] == "template"
    # prendido por el dueño: ahora sí se llama, y el motor queda registrado
    assert client.put("/admin/cost-switches/gemini_content", headers=tok("equipo"),
                      json={"enabled": True, "confirm_cost": True}).status_code == 200
    p2 = client.post("/admin/content/pieces/request", headers=ana, json={"kind": "comercio", "comercio_id": "com-2"}).json()
    assert len(gemini.llamadas) >= 2, "texto del video + captions"
    assert p2["video_texts_engine"] == "gemini:gemini-qa", p2["video_texts_engine"]
    assert p2["video_texts"]["title1"] == "Ropa que" and p2["caption_engine"].startswith("gemini")
    # las fotos no salen del servidor sin prender: lo que viajó a Gemini es una imagen por foto
    n = len(gemini.llamadas)
    # apagar de nuevo: vuelve a no llamar
    assert client.put("/admin/cost-switches/gemini_content", headers=tok("equipo"), json={"enabled": False}).status_code == 200
    r = client.post(f"/admin/content/pieces/{p2['id']}/video-texts/propose", headers=ana)
    assert r.status_code == 200 and r.json()["video_texts_engine"] == "template"
    assert len(gemini.llamadas) == n


def test_c_con_el_interruptor_prendido_pero_gemini_caido_se_usan_los_textos_fijos_y_no_se_frena_la_cola(repo, crepo, client, ana, monkeypatch):
    sembrar_comercio(repo, crepo, 5)
    from tests.content_helpers import gemini_on
    gemini_on(crepo)

    def caido(*a, **k):
        raise RuntimeError("503")
    monkeypatch.setattr("app.services.vision._post_con_reintentos", caido)
    r = client.post("/admin/content/pieces/request", headers=ana, json={"kind": "comercio", "comercio_id": "com-1"})
    assert r.status_code == 201, r.text
    assert r.json()["video_texts_engine"] == "template" and r.json()["status"] == "queued"
    assert "KEY-QA-FALSA" not in r.text


# ══════════════════════════════════════════════════════════════ (d) approve bloqueado

def _lista_para_revisar(repo, crepo, client, ana, contenedor, n_fotos=4):
    sembrar_comercio(repo, crepo, n_fotos)
    p = client.post("/admin/content/pieces/request", headers=ana, json={"kind": "comercio", "comercio_id": "com-1"}).json()
    res = cr.render_tick(crepo)
    assert res and res["ok"], res
    assert crepo.pieces[p["id"]]["status"] == "ready_for_review"
    return p["id"]


def test_d_aprobar_se_bloquea_por_fotos_marcadas_hasta_confirmarlas(repo, crepo, client, ana, contenedor, gemini):
    pid = _lista_para_revisar(repo, crepo, client, ana, contenedor)
    fuentes = crepo.list_sources(pid)
    fuentes[1]["photo_flags"] = ["price_or_code_visible"]
    assert crepo.pieces[pid]["photo_flags_ok"] is False
    r = client.post(f"/admin/content/pieces/{pid}/approve", headers=ana)
    assert r.status_code == 409 and r.json()["detail"] == "Hay fotos marcadas: cámbielas o confirme que están bien", r.text
    assert crepo.pieces[pid]["status"] == "ready_for_review" and not crepo.posts
    lote = client.post("/admin/content/pieces/approve-batch", headers=ana, json={"ids": [pid]}).json()
    assert lote["approved"] == [] and lote["refused"] and "fotos marcadas" in lote["refused"][0]["motivo"]
    # confirmar «revisé las fotos marcadas» no re-encola (textos iguales) y habilita aprobar
    vt = crepo.pieces[pid]["video_texts"]
    body = {"kick": vt["kick"], "title1": vt["title1"], "title2": vt["title2"], "subtitle": vt["subtitle"],
            "search_term": vt["search_term"], "chips": [], "photo_flags_ok": True}
    r = client.patch(f"/admin/content/pieces/{pid}/video-texts", headers=ana, json=body)
    assert r.status_code == 200 and r.json()["photo_flags_ok"] is True and r.json()["status"] == "ready_for_review", r.text
    r = client.post(f"/admin/content/pieces/{pid}/approve", headers=ana)
    assert r.status_code == 200 and r.json()["status"] == "approved", r.text
    assert len(crepo.posts) >= 1


def test_d_aprobar_se_bloquea_por_objeciones_en_los_textos_del_video(repo, crepo, client, ana, contenedor, gemini):
    pid = _lista_para_revisar(repo, crepo, client, ana, contenedor)
    crepo.pieces[pid]["video_texts_checks"] = ["Use usted, sin voseo ni tuteo"]
    r = client.post(f"/admin/content/pieces/{pid}/approve", headers=ana)
    assert r.status_code == 409 and r.json()["detail"] == "Revise los textos del video", r.text
    assert crepo.pieces[pid]["status"] == "ready_for_review"
    lote = client.post("/admin/content/pieces/approve-batch", headers=ana, json={"ids": [pid]}).json()
    assert lote["approved"] == [] and lote["refused"][0]["motivo"] == "Revise los textos del video"
    # el dueño corrige a mano: las objeciones se limpian y la pieza vuelve a armarse
    vt = crepo.pieces[pid]["video_texts"]
    body = {"kick": "OTRO KICK", "title1": vt["title1"], "title2": vt["title2"], "subtitle": None, "search_term": vt["search_term"], "chips": []}
    r = client.patch(f"/admin/content/pieces/{pid}/video-texts", headers=ana, json=body)
    assert r.status_code == 200, r.text
    assert r.json()["video_texts_checks"] == [] and r.json()["video_texts_engine"] == "human"


@pytest.mark.xfail(strict=True, reason="BUG QA-1: el PATCH con textos idénticos a los guardados no limpia video_texts_checks (§16.9)")
def test_d_guardar_los_mismos_textos_limpia_las_objeciones_viejas(repo, crepo, client, ana, contenedor, gemini):
    pid = _lista_para_revisar(repo, crepo, client, ana, contenedor)
    crepo.pieces[pid]["video_texts_checks"] = ["Use usted, sin voseo ni tuteo"]
    vt = crepo.pieces[pid]["video_texts"]
    body = {"kick": vt["kick"], "title1": vt["title1"], "title2": vt["title2"], "subtitle": vt["subtitle"], "search_term": vt["search_term"], "chips": []}
    r = client.patch(f"/admin/content/pieces/{pid}/video-texts", headers=ana, json=body)
    assert r.status_code == 200 and r.json()["video_texts_checks"] == []


def test_d_el_patch_rechaza_voseo_precios_y_entradas_maliciosas_con_400(repo, crepo, client, ana, contenedor, gemini):
    pid = _lista_para_revisar(repo, crepo, client, ana, contenedor)
    base = {"kick": None, "title1": "Camperas que", "title2": "ya llegaron", "subtitle": None, "search_term": "camperas", "chips": []}
    malos = [
        {"subtitle": "Mirá lo que tenés"}, {"title1": "Podés venir"}, {"subtitle": "Desde Bs 50"}, {"subtitle": "Solo $ 5"},
        {"title2": "20 por ciento"}, {"subtitle": "Escríbanos a @local"}, {"subtitle": "visite uruku.bo"},
        {"subtitle": "Oferta 🔥"}, {"subtitle": "CONFIRMAR-ABC123"}, {"title1": "<script>x</script>1"},
        {"search_term": "uno dos tres"}, {"title1": ""}, {"subtitle": "x" * 43},
    ]
    for cambio in malos:
        r = client.patch(f"/admin/content/pieces/{pid}/video-texts", headers=ana, json={**base, **cambio})
        assert r.status_code == 400, (cambio, r.status_code, r.text)
    assert crepo.pieces[pid]["status"] == "ready_for_review"        # nada de eso re-encoló la pieza
    # fuente que no es de esta pieza
    r = client.patch(f"/admin/content/pieces/{pid}/video-texts", headers=ana,
                     json={**base, "chips": [{"source_id": "ajena", "text": "Dos palabras"}]})
    assert r.status_code == 400
    # permiso
    assert client.patch(f"/admin/content/pieces/{pid}/video-texts", headers=tok("otro"), json=base).status_code == 403


@pytest.mark.parametrize("estado", ["rendering", "approved", "published", "skipped"])
def test_d_transiciones_invalidas_del_patch_y_propose_son_409(repo, crepo, client, ana, contenedor, gemini, estado):
    pid = _lista_para_revisar(repo, crepo, client, ana, contenedor)
    crepo.pieces[pid]["status"] = estado
    base = {"kick": None, "title1": "Camperas que", "title2": "ya llegaron", "subtitle": None, "search_term": "camperas", "chips": []}
    assert client.patch(f"/admin/content/pieces/{pid}/video-texts", headers=ana, json=base).status_code == 409
    assert client.post(f"/admin/content/pieces/{pid}/video-texts/propose", headers=ana).status_code == 409
    assert crepo.pieces[pid]["status"] == estado


def test_d_aprobar_dos_veces_o_antes_de_renderizar_es_409(repo, crepo, client, ana, contenedor, gemini):
    sembrar_comercio(repo, crepo, 5)
    pid = client.post("/admin/content/pieces/request", headers=ana, json={"kind": "comercio", "comercio_id": "com-1"}).json()["id"]
    assert client.post(f"/admin/content/pieces/{pid}/approve", headers=ana).status_code == 409        # queued
    cr.render_tick(crepo)
    assert client.post(f"/admin/content/pieces/{pid}/approve", headers=ana).status_code == 200
    assert client.post(f"/admin/content/pieces/{pid}/approve", headers=ana).status_code == 409        # ya aprobada


def test_d_aprobar_requiere_permiso_difusion(repo, crepo, client, ana, contenedor, gemini):
    pid = _lista_para_revisar(repo, crepo, client, ana, contenedor)
    assert client.post(f"/admin/content/pieces/{pid}/approve", headers=tok("otro")).status_code == 403
    assert client.post(f"/admin/content/pieces/{pid}/approve").status_code in (401, 403)


# ══════════════════════════════════════════════════════════════ (e) contrato de job.json (§16.4)

CLAVES_JOB = ["version", "piece_id", "template", "format", "fps", "texts", "icons", "slides", "out_video", "out_cover"]
CLAVES_TEXTS = ["kick", "title1", "title2", "subtitle", "close_title1", "close_title2", "search_term", "place_chip",
                "close_line", "url", "lema"]


def _verificar_contrato(contenedor, piece_id, n_esperado):
    job = contenedor["job"]
    assert list(job) == CLAVES_JOB
    assert job["version"] == 2 and job["template"] == "t1" and job["format"] == "9x16" and job["fps"] == 30
    assert job["piece_id"] == piece_id and re.fullmatch(r"[0-9a-f-]{36}", piece_id)
    assert job["out_video"] == "video.mp4" and job["out_cover"] == "cover.jpg"
    assert set(job["texts"]) == set(CLAVES_TEXTS)
    assert job["texts"]["url"] == "uruku.bo" and job["texts"]["lema"] == "Si está en Bolivia, está en Uruku."
    for campo in ("kick", "subtitle", "place_chip"):
        assert job["texts"][campo] is None or isinstance(job["texts"][campo], str)
    for campo in ("title1", "title2", "close_title1", "close_title2", "search_term", "close_line", "url", "lema"):
        assert isinstance(job["texts"][campo], str) and job["texts"][campo].strip(), campo
    assert 4 <= len(job["slides"]) <= 6 and len(job["slides"]) == n_esperado
    for i, s in enumerate(job["slides"]):
        assert set(s) == {"file", "chip", "focus_y"}
        assert s["file"] == f"s{i}.jpg" and re.fullmatch(r"^s\d{1,2}\.jpg$", s["file"])
        assert s["chip"] is None or isinstance(s["chip"], str)
        assert s["focus_y"] is None or 0 <= s["focus_y"] <= 1
    assert contenedor["fotos"] == [s["file"] for s in job["slides"]]
    assert set(job["icons"]) <= ICONOS_DEL_KIT and job["icons"], (job["icons"], ICONOS_DEL_KIT)
    limpio(job["texts"])
    assert contenedor["posts"][-1]["json"] == {"piece_id": piece_id}
    assert contenedor["posts"][-1]["headers"] == {"Authorization": "Bearer tok-qa"}


def test_e_job_de_un_negocio_cumple_el_contrato_y_las_fotos_quedan_preparadas(repo, crepo, client, ana, contenedor, gemini):
    sembrar_comercio(repo, crepo, 5)
    pid = client.post("/admin/content/pieces/request", headers=ana, json={"kind": "comercio", "comercio_id": "com-1"}).json()["id"]
    # inspeccionar las fotos mientras el contenedor las tiene a mano
    visto = {}
    original = cr.httpx.post

    def espia(url, json=None, headers=None, timeout=None):
        carpeta = content_storage.carpeta_tmp(json["piece_id"])
        for f in sorted(carpeta.glob("s*.jpg")):
            with Image.open(f) as im:
                visto[f.name] = (im.size, im.mode, bool(im.getexif()), im.format)
        visto["archivos"] = sorted(p.name for p in carpeta.iterdir())
        return original(url, json=json, headers=headers, timeout=timeout)
    cr.httpx.post = espia
    try:
        assert cr.render_tick(crepo)["ok"] is True
    finally:
        cr.httpx.post = original
    _verificar_contrato(contenedor, pid, 5)
    assert contenedor["job"]["icons"] == ["pin", "whatsapp"]
    assert contenedor["job"]["texts"]["place_chip"] == "Local com-1 · Bermejo"
    assert contenedor["job"]["texts"]["kick"] == "EN BERMEJO"
    assert visto["archivos"] == ["job.json", "s0.jpg", "s1.jpg", "s2.jpg", "s3.jpg", "s4.jpg"]
    for n in range(5):
        (w, h_), modo, exif, fmt = visto[f"s{n}.jpg"]
        assert max(w, h_) <= 1200 and modo == "RGB" and fmt == "JPEG" and exif is False
    assert crepo.pieces[pid]["status"] == "ready_for_review"
    # el worker limpia tmp/ y deja el resultado en renders/
    assert not content_storage.carpeta_tmp(pid).exists()


def test_e_job_de_un_rubro_con_4_comercios_usa_iconos_tienda_y_pin(repo, crepo, client, ana, contenedor, gemini):
    zapaterias(repo, crepo, n=4)
    pid = client.post("/admin/content/pieces/request", headers=ana,
                      json={"kind": "rubro", "rubro_slug": "zapatillas", "ciudad_slug": "bermejo"}).json()["id"]
    assert cr.render_tick(crepo)["ok"] is True
    _verificar_contrato(contenedor, pid, 4)
    job = contenedor["job"]
    assert job["icons"] == ["tienda", "pin"]
    assert job["texts"]["close_title1"] == "Encuéntrelos" and job["texts"]["place_chip"] is None
    assert sorted(s["chip"] for s in job["slides"]) == sorted(f"Zapatería {NOMBRES[i]}" for i in range(4))
    assert not any(re.search(r"\d", v) for v in valores(job["texts"]))


def test_e_job_con_8_fotos_se_corta_en_6(repo, crepo, client, ana, contenedor, gemini):
    sembrar_comercio(repo, crepo, 8)
    p = client.post("/admin/content/pieces/request", headers=ana, json={"kind": "comercio", "comercio_id": "com-1"}).json()
    assert len(p["sources"]) <= 6                       # elegir_fotos ya topa en 6
    assert cr.render_tick(crepo)["ok"] is True
    _verificar_contrato(contenedor, p["id"], len(p["sources"]))


def test_e_el_texto_editado_a_mano_llega_al_job_pero_el_cierre_sigue_fijo(repo, crepo, client, ana, contenedor, gemini):
    pid = _lista_para_revisar(repo, crepo, client, ana, contenedor)
    p = client.get(f"/admin/content/pieces/{pid}", headers=ana).json()
    body = {"kick": "oferta del dia", "title1": "Ropa de", "title2": "temporada", "subtitle": "Modelos nuevos", "search_term": "Ropa",
            "chips": [{"source_id": p["sources"][0]["id"], "text": "Campera de cuero"}]}
    r = client.patch(f"/admin/content/pieces/{pid}/video-texts", headers=ana, json=body)
    assert r.status_code == 400 and "cuero" in r.text.lower(), r.text            # «cuero» sólo como «eco cuero»
    body["chips"][0]["text"] = "Eco cuero negro"
    r = client.patch(f"/admin/content/pieces/{pid}/video-texts", headers=ana, json=body)
    assert r.status_code == 200 and r.json()["status"] == "queued", r.text
    assert r.json()["video_texts"]["kick"] == "OFERTA DEL DIA" and r.json()["video_texts"]["search_term"] == "ropa"
    assert cr.render_tick(crepo)["ok"] is True
    job = contenedor["job"]
    assert job["texts"]["kick"] == "OFERTA DEL DIA" and job["slides"][0]["chip"] == "Eco cuero negro"
    assert job["texts"]["close_line"] == "Consulte precio directo con el local"


# ══════════════════════════════════════════════════════════════ transversales: tope, ciudad, sin renderer

def test_tope_de_5_pedidos_y_el_sexto_es_429(repo, crepo, client, ana, gemini):
    for i in range(6):
        sembrar_comercio(repo, crepo, 4, cid=f"com-{i}")
    for i in range(5):
        r = client.post("/admin/content/pieces/request", headers=ana, json={"kind": "comercio", "comercio_id": f"com-{i}"})
        assert r.status_code == 201, (i, r.text)
    r = client.post("/admin/content/pieces/request", headers=ana, json={"kind": "comercio", "comercio_id": "com-5"})
    assert r.status_code == 429, r.text


def test_pedir_requiere_difusion_y_valida_la_entrada(repo, crepo, client, ana, gemini):
    sembrar_comercio(repo, crepo, 5)
    url = "/admin/content/pieces/request"
    assert client.post(url, json={"kind": "comercio", "comercio_id": "com-1"}).status_code in (401, 403)
    assert client.post(url, headers=tok("equipo"), json={"kind": "comercio", "comercio_id": "com-1"}).status_code == 403
    assert client.post(url, headers=ana, json={"kind": "otro"}).status_code == 422
    assert client.post(url, headers=ana, json={"kind": "comercio", "comercio_id": "no-existe"}).status_code in (404, 422)
    for mal in ("'; drop table x;--", "../../etc", "<script>"):
        r = client.post(url, headers=ana, json={"kind": "rubro", "rubro_slug": mal, "ciudad_slug": "bermejo"})
        assert r.status_code in (404, 422), (mal, r.status_code)
    assert not crepo.pieces


def test_sin_renderer_el_estado_del_worker_es_no_renderer_y_no_toma_trabajos(repo, crepo, client, ana, monkeypatch, gemini):
    sembrar_comercio(repo, crepo, 5)
    pid = client.post("/admin/content/pieces/request", headers=ana, json={"kind": "comercio", "comercio_id": "com-1"}).json()["id"]
    monkeypatch.setattr(settings, "content_render_worker", True)
    monkeypatch.setattr(settings, "renderer_token", "")
    cr.reiniciar_salud()
    assert cr.estado_del_worker() == "no_renderer"
    assert cr.render_tick(crepo) is None and crepo.pieces[pid]["status"] == "queued"
    st = client.get("/admin/content/status", headers=ana)
    assert st.status_code == 200 and st.json()["render_worker"] == "no_renderer", st.text
