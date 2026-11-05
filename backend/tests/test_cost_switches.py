"""Interruptores de costo (§17.2): sin fila = apagado, el caché de 30 s, la API y, sobre todo, que APAGADO no se llame
a Gemini (ni para los textos de las redes ni para los del video ni desde el selector)."""
import pytest

from app.core import auth
from app.core.config import settings
from app.services import content_captions as cc, content_video_texts as cvt, cost_switches
from tests.content_helpers import gemini_on, h
from tests.test_content_video_texts import PIEZA, _fuentes

GEMINI = cost_switches.GEMINI_CONTENT


def token(*permisos):
    return h(auth.make_token("quien@uruku.bo", rol="x", roles=["x"], permisos=list(permisos)))


@pytest.fixture
def dueno():
    return token("equipo")


@pytest.fixture
def difusion():
    return token("difusion")


@pytest.fixture
def con_key(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "k")
    monkeypatch.setattr(settings, "gemini_model", "gemini-test")


def sin_llamadas(monkeypatch):
    """Cualquier llamada a Gemini (texto o visión) rompe el test."""
    def boom(*a, **k):
        pytest.fail("no tiene que llamar a Gemini")
    monkeypatch.setattr(cc, "_llamar_gemini", boom)
    monkeypatch.setattr(cvt, "_llamar_gemini", boom)
    monkeypatch.setattr("app.services.vision._post_con_reintentos", boom)


# ══════════════════════════════════════════════════════════════ el servicio

def test_sin_fila_esta_apagado_y_una_clave_desconocida_tambien(crepo):
    assert cost_switches.esta_prendido(crepo, GEMINI) is False
    assert cost_switches.esta_prendido(crepo, "otra") is False
    assert [i["enabled"] for i in cost_switches.listar(crepo)] == [False, False]   # gemini_content y gemini_phone_scan


def test_set_prende_y_apaga_y_guarda_quien(crepo):
    fila = cost_switches.set(crepo, GEMINI, True, "dueno@uruku.bo")
    assert fila["enabled"] is True and fila["updated_by"] == "dueno@uruku.bo"
    assert cost_switches.esta_prendido(crepo, GEMINI) is True
    cost_switches.set(crepo, GEMINI, False, "dueno@uruku.bo")
    assert cost_switches.esta_prendido(crepo, GEMINI) is False         # `set` limpia el caché: se ve al instante


def test_la_lectura_se_recuerda_30_segundos(crepo, monkeypatch):
    gemini_on(crepo)
    assert cost_switches.esta_prendido(crepo, GEMINI) is True
    crepo.cost_switches[GEMINI]["enabled"] = False                       # cambio por fuera, sin pasar por `set`
    assert cost_switches.esta_prendido(crepo, GEMINI) is True            # todavía el valor recordado
    t = cost_switches.time.monotonic()
    monkeypatch.setattr(cost_switches.time, "monotonic", lambda: t + cost_switches.CACHE_SEG + 1)
    assert cost_switches.esta_prendido(crepo, GEMINI) is False           # ya venció


def test_un_error_de_lectura_deja_apagado_y_no_se_recuerda(crepo, monkeypatch):
    gemini_on(crepo)
    cost_switches.reiniciar_cache()
    original = crepo.list_cost_switches
    monkeypatch.setattr(crepo, "list_cost_switches", lambda: (_ for _ in ()).throw(RuntimeError("base caída")))
    assert cost_switches.esta_prendido(crepo, GEMINI) is False
    monkeypatch.setattr(crepo, "list_cost_switches", original)
    assert cost_switches.esta_prendido(crepo, GEMINI) is True            # el error no quedó pegado


def test_el_catalogo_dice_que_hace_cuanto_cuesta_y_que_pasa_apagado():
    c = cost_switches.CATALOGO[GEMINI]
    assert c["label"] == "Textos con Gemini"
    assert c["cost"].startswith("Menos de US$ 0,01 por video") and "completás a mano en Revisión" in c["off_means"]
    assert set(c) == {"label", "what", "cost", "off_means"}


# ══════════════════════════════════════════════════════════════ apagado = cero llamadas a Gemini

def test_captions_apagado_no_llama_a_gemini_aunque_haya_key(crepo, con_key, monkeypatch):
    sin_llamadas(monkeypatch)
    facts = cc.build_facts_comercio({"nombre": "Vidriería Pacheco", "slug": "vidrieria-pacheco", "calle": "Calle Barrientos",
                                     "rubros": {"nombre": "Vidriería", "slug": "vidrios"},
                                     "ciudades": {"nombre": "Bermejo", "slug": "bermejo", "departamento": "Tarija"}})
    r = cc.generate_captions(facts, crepo=crepo)
    assert r["caption_engine"] == "template" and r["caption_checks"] == [] and "Vidriería Pacheco" in r["caption_tiktok"]


def test_captions_prendido_si_llama(crepo, con_key, monkeypatch):
    gemini_on(crepo)
    llamadas = []
    facts = cc.build_facts_comercio({"nombre": "Vidriería Pacheco", "slug": "vidrieria-pacheco",
                                     "rubros": {"nombre": "Vidriería", "slug": "vidrios"},
                                     "ciudades": {"nombre": "Bermejo", "slug": "bermejo", "departamento": "Tarija"}})
    ok = "Vidriería Pacheco, en Bermejo. Búsquela en uruku.bo y escríbale desde su ficha."
    monkeypatch.setattr(cc, "_llamar_gemini", lambda p: llamadas.append(p) or {
        "caption_tiktok": ok, "caption_ig": ok, "caption_channel": ok, "hashtags": ["#URUKU", "#Bermejo", "#Tarija", "#Bolivia"]})
    assert cc.generate_captions(facts, crepo=crepo)["caption_engine"] == "gemini:gemini-test" and len(llamadas) == 1


def test_proponer_apagado_no_llama_a_gemini_y_devuelve_textos_fijos_sin_marcas(crepo, con_key, monkeypatch):
    sin_llamadas(monkeypatch)
    r = cvt.proponer(PIEZA, _fuentes(crepo), crepo=crepo)
    assert r["engine"] == "template" and r["checks"] == [] and r["texts"]["title1"] == "Moda"
    assert [s["chip"] for s in r["slides"]] == [None] * 5 and all(s["flags"] == [] and s["focus_y"] is None for s in r["slides"])


def test_proponer_apagado_en_solo_fotos_tampoco_llama(crepo, con_key, monkeypatch):
    sin_llamadas(monkeypatch)
    r = cvt.proponer(PIEZA, _fuentes(crepo, n=2), solo_fotos=True, crepo=crepo)
    assert r["texts"] is None and r["engine"] is None and [s["flags"] for s in r["slides"]] == [[], []]


def test_proponer_prendido_si_llama(crepo, con_key, monkeypatch):
    gemini_on(crepo)
    llamadas = []
    buenos = {"kick": "NUEVA TEMPORADA", "title1": "Camperas que", "title2": "ya llegaron", "subtitle": None,
              "search_term": "camperas", "slides": [{"chip": None, "price_or_code_visible": False, "focus_y": 0.4}] * 5}
    monkeypatch.setattr(cvt, "_llamar_gemini", lambda partes: llamadas.append(partes) or buenos)
    r = cvt.proponer(PIEZA, _fuentes(crepo), crepo=crepo)
    assert r["engine"] == "gemini:gemini-test" and len(llamadas) == 1


def test_el_selector_apagado_no_llama_a_gemini_en_ninguna_pieza(repo, crepo, con_key, monkeypatch):
    from tests.test_content_selector import _comercios_con_oferta, plan, suscriptor
    sin_llamadas(monkeypatch)
    suscriptor(repo, crepo, "com-1", fotos=6)
    _comercios_con_oferta(repo, crepo, subs=4, otros=0)
    assert plan(repo, crepo)["created"] >= 2
    assert {p["caption_engine"] for p in crepo.pieces.values()} == {"template"}
    assert {p["video_texts_engine"] for p in crepo.pieces.values()} == {"template"}


def test_pedir_otra_propuesta_apagado_da_textos_fijos_sin_gemini(repo, crepo, client, con_key, monkeypatch):
    from tests.content_helpers import autorizar, banco, comercio, pieza
    sin_llamadas(monkeypatch)
    comercio(repo)
    autorizar(crepo, "com-1")
    fotos = banco(crepo, "com-1", 5)
    p = pieza(crepo, "com-1", status="ready_for_review", template_version=2)
    crepo.insert_sources([{"piece_id": p["id"], "position": i, "source_type": "asset", "source_id": a["id"],
                           "comercio_id": "com-1", "file_ref": a["file_path"]} for i, a in enumerate(fotos)])
    r = client.post(f"/admin/content/pieces/{p['id']}/video-texts/propose", headers=token("difusion"))
    assert r.status_code == 200 and r.json()["video_texts_engine"] == "template"


# ══════════════════════════════════════════════════════════════ la API

def test_lista_para_difusion_y_para_el_dueno_pero_no_para_otros(client, difusion, dueno):
    for cab in (difusion, dueno):
        r = client.get("/admin/cost-switches", headers=cab)
        assert r.status_code == 200
        item = r.json()["items"][0]
        assert set(item) == {"key", "label", "what", "cost", "off_means", "enabled", "updated_by", "updated_at"}
        assert item["key"] == GEMINI and item["enabled"] is False and item["updated_by"] is None
    assert client.get("/admin/cost-switches", headers=token("moderar")).status_code == 403
    assert client.get("/admin/cost-switches").status_code == 401


def test_solo_el_dueno_cambia_un_interruptor(client, difusion, dueno, crepo):
    cuerpo = {"enabled": True, "confirm_cost": True}
    assert client.put(f"/admin/cost-switches/{GEMINI}", headers=difusion, json=cuerpo).status_code == 403
    assert client.put(f"/admin/cost-switches/{GEMINI}", json=cuerpo).status_code == 401
    assert cost_switches.esta_prendido(crepo, GEMINI) is False
    r = client.put(f"/admin/cost-switches/{GEMINI}", headers=dueno, json=cuerpo)
    assert r.status_code == 200
    assert r.json()["enabled"] is True and r.json()["updated_by"] == "quien@uruku.bo" and r.json()["updated_at"]
    assert cost_switches.esta_prendido(crepo, GEMINI) is True
    assert client.get("/admin/cost-switches", headers=difusion).json()["items"][0]["enabled"] is True


def test_prender_exige_confirmar_el_costo(client, dueno, crepo):
    r = client.put(f"/admin/cost-switches/{GEMINI}", headers=dueno, json={"enabled": True})
    assert r.status_code == 400 and r.json()["detail"] == "Confirmá que sabés que tiene costo"
    r = client.put(f"/admin/cost-switches/{GEMINI}", headers=dueno, json={"enabled": True, "confirm_cost": False})
    assert r.status_code == 400 and cost_switches.esta_prendido(crepo, GEMINI) is False


@pytest.mark.parametrize("cuerpo", [{"enabled": False}, {"enabled": False, "confirm_cost": False},
                                    {"enabled": False, "confirm_cost": True}])
def test_apagar_no_pide_confirmacion(client, dueno, crepo, cuerpo):
    gemini_on(crepo)
    r = client.put(f"/admin/cost-switches/{GEMINI}", headers=dueno, json=cuerpo)
    assert r.status_code == 200 and r.json()["enabled"] is False and cost_switches.esta_prendido(crepo, GEMINI) is False


def test_clave_desconocida_es_404_y_no_escribe(client, dueno, crepo):
    r = client.put("/admin/cost-switches/elevenlabs", headers=dueno, json={"enabled": True, "confirm_cost": True})
    assert r.status_code == 404 and crepo.cost_switches == {}


def test_el_cambio_queda_en_el_log_con_actor_y_valor(client, dueno):
    import structlog
    with structlog.testing.capture_logs() as logs:
        client.put(f"/admin/cost-switches/{GEMINI}", headers=dueno, json={"enabled": True, "confirm_cost": True})
    ev = [l for l in logs if l["event"] == "cost_switch_changed"]
    assert ev and ev[0]["actor"] == "quien@uruku.bo" and ev[0]["enabled"] is True and ev[0]["key"] == GEMINI
