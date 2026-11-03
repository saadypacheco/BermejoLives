"""Los textos del video v2 (§16.5 a §16.9): validador, textos fijos, Gemini con visión simulado, descarte de fotos
marcadas, y los endpoints PATCH / propose / approve."""
import json

import httpx
import pytest

from app.core import auth
from app.core.config import settings
from app.services import (content_captions as cc, content_selector as sel, content_storage,
                          content_video_texts as cvt)
from tests.content_helpers import autorizar, banco, comercio, gemini_on, h, pieza

BUENOS = {"kick": "NUEVA TEMPORADA", "title1": "Camperas que", "title2": "ya llegaron",
          "subtitle": "Eco cuero, doble faz y más modelos", "search_term": "camperas"}


@pytest.fixture
def ana():
    return h(auth.make_token("ana.perez@uruku.bo", rol="admin"))


def val(**kw):
    return cvt.validate_video_texts({**BUENOS, **kw}, None, "comercio_del_dia")


# ══════════════════════════════════════════════════════════════ el validador (§16.6)

def test_los_textos_buenos_no_tienen_objeciones():
    assert val() == []
    assert cvt.validate_video_texts(BUENOS, ["Eco cuero con cinturón", None, "Doble faz"], "comercio_del_dia") == []


@pytest.mark.parametrize("campo, valor, fragmento", [
    ("kick", "A" * 23, "pasa de 22"),
    ("title1", "", "es obligatorio"),
    ("title2", None, "es obligatorio"),
    ("title1", "uno dos tres cuatro cinco", "1 a 4 palabras"),
    ("title1", "Supercalifragilistico!", "pasa de 18"),
    ("subtitle", "x" * 43, "pasa de 42"),
    ("search_term", "", "es obligatorio"),
    ("search_term", "tres palabras sueltas", "1 o 2 palabras"),
    ("search_term", "camperasdemuchisimasmarcas", "pasa de 16"),
])
def test_largos_y_obligatorios(campo, valor, fragmento):
    assert any(fragmento in o for o in val(**{campo: valor})), val(**{campo: valor})


def test_los_limites_exactos_pasan():
    assert val(kick="A" * 22, title1="a b c d", title2="x" * 18, subtitle="y" * 42, search_term="dos palabras") == []


def test_el_chip_va_de_2_a_5_palabras_y_hasta_30_caracteres():
    ok = lambda c: cvt.validate_video_texts(None, [c], "comercio_del_dia")
    assert ok("Doble faz") == [] and ok("uno dos tres cuatro cinco") == [] and ok(None) == [] and ok("") == []
    assert any("2 a 5 palabras" in o for o in ok("Camperas"))
    assert any("2 a 5 palabras" in o for o in ok("uno dos tres cuatro cinco seis"))
    assert any("pasa de 30" in o for o in ok("a" * 15 + " " + "b" * 15))
    assert ok("Doble faz 1") and cvt.validate_video_texts(None, ["ok bien", "Camperas"], "comercio_del_dia")[0].startswith(
        "Frase de la foto 2")


@pytest.mark.parametrize("texto", [
    "Desde 20 modelos", "Precio Bs 80", "Solo $ 5", "Oferta US$ 9", "Hay 5 modelos",
])
def test_sin_digitos_ni_precios(texto):
    assert val(subtitle=texto)


def test_sin_emoji_url_arroba_dominio_ni_codigo():
    assert any("emoji" in o for o in val(subtitle="Con onda 🔥"))
    assert any("links" in o for o in val(subtitle="Entre a https://x.com"))
    assert any("links" in o for o in val(subtitle="Escriba a @uruku"))
    assert any("links" in o for o in val(subtitle="Visite uruku.bo"))
    assert any("código" in o for o in val(subtitle="Use URUKU-K7M2"))
    assert any("código" in o for o in val(subtitle="Escriba CONFIRMAR-123456"))
    assert any("código" in o for o in val(subtitle="Su clave BOUTIQUE-K7M2P9"))


@pytest.mark.parametrize("frase", ["el mejor precio", "envío gratis", "garantía total", "próximamente más", "más barato"])
def test_lo_que_no_se_promete(frase):
    assert any("promete algo que no se puede" in o for o in val(subtitle=frase)), frase


def test_cuero_solo_como_eco_cuero():
    assert any("eco cuero" in o for o in val(subtitle="Camperas de cuero"))
    assert any("eco cuero" in o for o in val(subtitle="Cuero y más"))
    assert val(subtitle="Camperas de eco cuero") == []
    assert val(subtitle="Eco Cuero con cinturón") == []
    assert val(subtitle="Camperas de eco-cuero") == []
    assert any("eco cuero" in o for o in val(subtitle="Eco y cuero"))             # «eco» no pegado a «cuero»
    assert any("eco cuero" in o for o in cvt.validate_video_texts(None, ["Campera de cuero"], "comercio_del_dia"))


@pytest.mark.parametrize("texto", ["Buscá su local", "Mirá las ofertas", "Si querés más", "Tenés que verlo", "Conocé Uruku",
                                   "Encontrá lo tuyo", "Vení hoy", "Escribile ahora", "Podés pedirlo", "vos elegís"])
def test_voseo_se_rechaza(texto):
    assert any("Use usted" in o for o in val(subtitle=texto)), texto


@pytest.mark.parametrize("texto", ["Tú eliges", "Busca tu estilo", "Si quieres más", "Tienes opciones", "Puedes pedir",
                                   "Para ti", "Te esperamos"])
def test_tuteo_se_rechaza(texto):
    assert any("Use usted" in o for o in val(subtitle=texto)), texto


@pytest.mark.parametrize("texto", ["Consulte precio directo", "Busque su estilo", "Escríbale al local", "Vea más modelos"])
def test_usted_pasa(texto):
    assert val(subtitle=texto) == []


def test_las_objeciones_se_nombran_por_campo_y_sin_repetir():
    obj = val(title1="Hay 5 vos", kick="x" * 30)
    assert any(o.startswith("Título, línea 1:") for o in obj) and any(o.startswith("Kick:") for o in obj)
    assert len(obj) == len(set(obj))


def test_en_ofertas_el_chip_es_el_nombre_del_comercio_y_no_se_valida():
    assert cvt.validate_video_texts(BUENOS, ["Tienda 24", "Bs"], "ofertas") == []
    assert cvt.validate_video_texts(BUENOS, ["Tienda 24"], "comercio_del_dia")


def test_normalizar_pone_kick_en_mayusculas_y_busqueda_en_minusculas():
    n = cvt.normalizar_textos({"kick": " nueva  temporada ", "title1": " A  b ", "subtitle": "  ", "search_term": " CAMPERAS "})
    assert n == {"kick": "NUEVA TEMPORADA", "title1": "A b", "title2": None, "subtitle": None, "search_term": "camperas"}


# ══════════════════════════════════════════════════════════════ textos fijos y cierre (§16.5, §16.7)

FACTS = {"pillar": "comercio_del_dia", "nombre": "Boutique Andina", "rubro": "Moda", "ciudad": "Bermejo",
         "slug": "boutique-andina"}
OFERTAS = {"pillar": "ofertas", "ciudad": "Bermejo", "items": [{"nombre": "A b"}]}


def test_textos_fijos_de_comercio_del_dia():
    t = cvt.textos_fijos("comercio_del_dia", FACTS)
    assert t == {"kick": "EN BERMEJO", "title1": "Moda", "title2": "en Bermejo", "subtitle": None, "search_term": "moda"}
    assert cvt.validate_video_texts(t, None, "comercio_del_dia") == []


def test_textos_fijos_con_rubro_largo_ciudad_larga_o_prohibida():
    t = cvt.textos_fijos("comercio_del_dia", {**FACTS, "rubro": "Ferretería y Construcción", "ciudad": "Santa Cruz de la Sierra"})
    assert t["title1"] == "Lo que busca" and t["title2"] == "está en Uruku" and t["kick"] is None       # 26 > 22
    assert t["search_term"] == "ferretería"
    t = cvt.textos_fijos("comercio_del_dia", {**FACTS, "rubro": "Envíos"})                              # frase prohibida
    assert t["title1"] == "Lo que busca" and t["search_term"] == "comercios"
    assert cvt.validate_video_texts(t, None, "comercio_del_dia") == []
    sin = cvt.textos_fijos("comercio_del_dia", {"nombre": "X"})
    assert sin["title1"] == "Lo que busca" and sin["kick"] is None and cvt.validate_video_texts(sin, None, "comercio_del_dia") == []


def test_textos_fijos_de_ofertas():
    t = cvt.textos_fijos("ofertas", OFERTAS)
    assert t == {"kick": "OFERTAS DE LA SEMANA", "title1": "Ofertas en", "title2": "Bermejo", "subtitle": None,
                 "search_term": "ofertas"}
    assert cvt.validate_video_texts(t, None, "ofertas") == []
    assert cvt.textos_fijos("ofertas", {"pillar": "ofertas", "ciudad": "Santa Cruz de la Sierra"})["title2"] == "su ciudad"


def test_textos_de_cierre_fijos():
    c = cvt.textos_de_cierre("comercio_del_dia", FACTS)
    assert c == {"close_title1": "¿Dónde lo", "close_title2": "consigue?", "place_chip": "Boutique Andina · Bermejo",
                 "close_line": "Consulte precio directo con el local"}
    largo = cvt.textos_de_cierre("comercio_del_dia", {**FACTS, "nombre": "Boutique Internacional Andina del Sur"})
    assert len(largo["place_chip"]) <= 34 and "·" not in largo["place_chip"] and largo["place_chip"].endswith("…")
    o = cvt.textos_de_cierre("ofertas", OFERTAS)
    assert o == {"close_title1": "¿Dónde las", "close_title2": "encuentra?", "place_chip": None,
                 "close_line": "Vea todas las ofertas en Uruku"}
    assert cvt.iconos_de("comercio_del_dia") == ["pin", "whatsapp"] and cvt.iconos_de("ofertas") == ["oferta", "pin"]


def test_armar_textos_trae_las_11_claves_del_contrato():
    t = cvt.armar_textos(BUENOS, "comercio_del_dia", FACTS)
    assert list(t) == ["kick", "title1", "title2", "subtitle", "close_title1", "close_title2", "search_term", "place_chip",
                       "close_line", "url", "lema"]
    assert t["url"] == "uruku.bo" and t["lema"] == "Si está en Bolivia, está en Uruku."


# ══════════════════════════════════════════════════════════════ Gemini con visión (simulado)

def _fuentes(crepo, cid="com-1", n=5, pilar_ofertas=False):
    fotos = banco(crepo, cid, n)
    return [{"source_type": "asset", "source_id": a["id"], "file_ref": a["file_path"], "comercio_id": cid,
             "caption_fact": f"Local {i}" if pilar_ofertas else None} for i, a in enumerate(fotos)]


NOMBRES = ("uno", "dos", "tres", "cuatro", "cinco", "seis", "siete")


def _slides(n, cambios=None):
    cambios = cambios or {}
    return [{"chip": f"Modelo {NOMBRES[i]}", "price_or_code_visible": False, "focus_y": 0.3, **cambios.get(i, {})}
            for i in range(n)]


def _gemini(monkeypatch, respuestas):
    llamadas = []

    def falso(partes):
        llamadas.append(partes)
        return respuestas.pop(0) if respuestas else None
    monkeypatch.setattr(cvt, "_llamar_gemini", falso)
    return llamadas


@pytest.fixture
def con_key(monkeypatch, crepo):
    """Clave de Gemini puesta Y el interruptor `gemini_content` prendido (por defecto está apagado, §17.2)."""
    gemini_on(crepo)
    monkeypatch.setattr(settings, "gemini_api_key", "k")
    monkeypatch.setattr(settings, "gemini_model", "gemini-test")


PIEZA = {"pillar": "comercio_del_dia", "facts": {**FACTS, "subcategoria": "Camperas"}}


def test_sin_key_salen_los_textos_fijos_y_no_llama_a_nadie(crepo, monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(cvt, "_llamar_gemini", lambda p: pytest.fail("no tiene que llamar"))
    r = cvt.proponer(PIEZA, _fuentes(crepo), crepo=crepo)
    assert r["engine"] == "template" and r["checks"] == [] and r["texts"]["title1"] == "Moda"
    assert [s["chip"] for s in r["slides"]] == [None] * 5 and all(s["flags"] == [] for s in r["slides"])


def test_gemini_valido_queda_como_gemini_y_manda_las_fotos_a_768(crepo, con_key, monkeypatch):
    llamadas = _gemini(monkeypatch, [{**BUENOS, "slides": _slides(5, {1: {"price_or_code_visible": True}})}])
    comercio_ficha = {"prod_obs_human": "camperas de eco cuero, jeans"}
    r = cvt.proponer(PIEZA, _fuentes(crepo), comercio_ficha, crepo=crepo)
    assert r["engine"] == "gemini:gemini-test" and r["checks"] == [] and r["texts"] == BUENOS
    assert r["slides"][1]["flags"] == ["price_or_code_visible"] and r["slides"][0]["flags"] == []
    assert r["slides"][0] == {"chip": "Modelo uno", "flags": [], "focus_y": 0.3}
    partes = llamadas[0]
    assert len([p for p in partes if "inline_data" in p]) == 5 and partes[0]["text"].startswith("Eres el redactor")
    assert "<datos>" in partes[0]["text"] and "camperas de eco cuero" in partes[0]["text"]
    assert "calle" not in partes[0]["text"].lower().split("<datos>")[1]              # sin datos de contacto


def test_las_fotos_se_mandan_reducidas(crepo, con_key, monkeypatch):
    import base64
    from io import BytesIO

    from PIL import Image
    llamadas = _gemini(monkeypatch, [{**BUENOS, "slides": _slides(5)}])
    cvt.proponer(PIEZA, _fuentes(crepo), crepo=crepo)
    imagen = next(p for p in llamadas[0] if "inline_data" in p)["inline_data"]
    with Image.open(BytesIO(base64.b64decode(imagen["data"]))) as im:
        assert max(im.size) <= 768 and imagen["mime_type"] == "image/jpeg"


def test_objetado_se_reintenta_una_vez_con_las_objeciones(crepo, con_key, monkeypatch):
    mala = {**BUENOS, "subtitle": "Buscá tu campera", "slides": _slides(5)}
    llamadas = _gemini(monkeypatch, [mala, {**BUENOS, "slides": _slides(5)}])
    r = cvt.proponer(PIEZA, _fuentes(crepo), crepo=crepo)
    assert r["engine"].startswith("gemini:") and len(llamadas) == 2
    assert "Use usted" in llamadas[1][0]["text"] and "objeciones" in llamadas[1][0]["text"]
    assert "objeciones" not in llamadas[0][0]["text"]


def test_objetado_dos_veces_cae_a_textos_fijos_pero_conserva_las_marcas(crepo, con_key, monkeypatch):
    mala = {**BUENOS, "title1": "Hay 5 modelos", "slides": _slides(5, {2: {"price_or_code_visible": True}})}
    llamadas = _gemini(monkeypatch, [mala, mala, {**BUENOS, "slides": _slides(5)}])
    r = cvt.proponer(PIEZA, _fuentes(crepo), crepo=crepo)
    assert r["engine"] == "template" and len(llamadas) == 2 and r["checks"] == []
    assert r["texts"]["title1"] == "Moda"
    assert [s["chip"] for s in r["slides"]] == [None] * 5                           # las frases de Gemini no se usan
    assert r["slides"][2]["flags"] == ["price_or_code_visible"]                     # la marca de precio sí: es prudente


def test_gemini_con_otra_cantidad_de_slides_se_objeta(crepo, con_key, monkeypatch):
    llamadas = _gemini(monkeypatch, [{**BUENOS, "slides": _slides(3)}, {**BUENOS, "slides": _slides(5)}])
    r = cvt.proponer(PIEZA, _fuentes(crepo), crepo=crepo)
    assert r["engine"].startswith("gemini:") and "exactamente 5" in llamadas[1][0]["text"]


@pytest.mark.parametrize("basura", [None, {}, {"slides": "no"}, {"title1": 5, "slides": [1, 2]}, {"title1": ["x"]}])
def test_gemini_que_devuelve_basura_cae_a_textos_fijos_sin_lanzar(crepo, con_key, monkeypatch, basura):
    _gemini(monkeypatch, [basura, basura])
    r = cvt.proponer(PIEZA, _fuentes(crepo), crepo=crepo)
    assert r["engine"] == "template" and len(r["slides"]) == 5 and r["checks"] == []


def test_error_http_de_gemini_cae_a_textos_fijos_sin_filtrar_la_key(crepo, monkeypatch, caplog):
    monkeypatch.setattr(settings, "gemini_api_key", "CLAVE-SECRETA")

    def roto(url, payload):
        raise httpx.ConnectError(f"fallo en {url}")
    monkeypatch.setattr("app.services.vision._post_con_reintentos", roto)
    r = cvt.proponer(PIEZA, _fuentes(crepo), crepo=crepo)
    assert r["engine"] == "template" and "CLAVE-SECRETA" not in caplog.text


def test_una_excepcion_inesperada_tampoco_frena(crepo, con_key, monkeypatch):
    def explota(partes):
        raise RuntimeError("boom")
    monkeypatch.setattr(cvt, "_llamar_gemini", explota)
    assert cvt.proponer(PIEZA, _fuentes(crepo), crepo=crepo)["engine"] == "template"


def test_foto_ilegible_no_se_manda_y_queda_sin_chip(crepo, con_key, monkeypatch):
    fuentes = _fuentes(crepo)
    content_storage.safe_path(fuentes[0]["file_ref"]).write_bytes(b"no es una imagen")
    llamadas = _gemini(monkeypatch, [{**BUENOS, "slides": _slides(4)}])
    r = cvt.proponer(PIEZA, fuentes, crepo=crepo)
    assert len([p for p in llamadas[0] if "inline_data" in p]) == 4
    assert r["engine"].startswith("gemini:") and r["slides"][0] == {"chip": None, "flags": [], "focus_y": None}
    assert r["slides"][1]["chip"] == "Modelo uno"                               # alineado con la foto que SÍ se mandó


def test_focus_y_se_acota_a_0_1_y_lo_invalido_es_none(crepo, con_key, monkeypatch):
    sl = _slides(5, {0: {"focus_y": 7}, 1: {"focus_y": -2}, 2: {"focus_y": "mucho"}, 3: {"focus_y": None}})
    _gemini(monkeypatch, [{**BUENOS, "slides": sl}])
    r = cvt.proponer(PIEZA, _fuentes(crepo), crepo=crepo)
    assert [s["focus_y"] for s in r["slides"]] == [1.0, 0.0, None, None, 0.3]


def test_en_ofertas_el_chip_es_el_nombre_del_comercio_aunque_gemini_diga_otra_cosa(crepo, con_key, monkeypatch):
    fuentes = _fuentes(crepo, n=4, pilar_ofertas=True)
    _gemini(monkeypatch, [{**BUENOS, "slides": _slides(4)}])
    r = cvt.proponer({"pillar": "ofertas", "facts": {"pillar": "ofertas", "ciudad": "Bermejo"}}, fuentes, crepo=crepo)
    assert [s["chip"] for s in r["slides"]] == ["Local 0", "Local 1", "Local 2", "Local 3"]
    assert r["engine"].startswith("gemini:")


def test_solo_fotos_no_toca_los_textos(crepo, con_key, monkeypatch):
    _gemini(monkeypatch, [{"slides": _slides(1, {0: {"price_or_code_visible": True}})}])
    r = cvt.proponer(PIEZA, _fuentes(crepo, n=1), solo_fotos=True, crepo=crepo)
    assert r["texts"] is None and r["engine"] is None and r["slides"][0]["flags"] == ["price_or_code_visible"]
    sin = cvt.proponer(PIEZA, _fuentes(crepo, n=1), solo_fotos=True, crepo=crepo)                # Gemini sin respuesta
    assert sin["texts"] is None and sin["slides"][0]["chip"] is None


# ══════════════════════════════════════════════════════════════ fotos marcadas

def test_las_marcadas_se_sacan_de_comercio_del_dia_si_quedan_4_sin_marca(caplog):
    fuentes = [{"source_type": "asset", "source_id": f"a{i}", "file_ref": f"r{i}"} for i in range(6)]
    prop = {"slides": [{"chip": None, "flags": ["price_or_code_visible"] if i in (1, 4) else [], "focus_y": None}
                       for i in range(6)]}
    quedan, n = cvt.aplicar_en_memoria(fuentes, prop, "comercio_del_dia")
    assert n == 2 and [f["source_id"] for f in quedan] == ["a0", "a2", "a3", "a5"]
    assert all(f["photo_flags"] == [] for f in quedan)


def test_si_quedan_menos_de_4_sin_marca_las_marcadas_se_quedan_con_la_marca():
    fuentes = [{"source_type": "asset", "source_id": f"a{i}", "file_ref": f"r{i}"} for i in range(5)]
    prop = {"slides": [{"chip": f"c{i}", "flags": ["price_or_code_visible"] if i in (0, 3) else [], "focus_y": 0.5}
                       for i in range(5)]}
    quedan, n = cvt.aplicar_en_memoria(fuentes, prop, "comercio_del_dia")
    assert n == 0 and len(quedan) == 5
    assert quedan[0]["photo_flags"] == ["price_or_code_visible"] and quedan[0]["chip_text"] == "c0"


def test_en_ofertas_las_marcadas_nunca_se_sacan():
    fuentes = [{"source_type": "offer", "source_id": f"o{i}", "file_ref": f"r{i}"} for i in range(8)]
    prop = {"slides": [{"chip": None, "flags": ["price_or_code_visible"] if i == 0 else [], "focus_y": None}
                       for i in range(8)]}
    quedan, n = cvt.aplicar_en_memoria(fuentes, prop, "ofertas")
    assert n == 0 and len(quedan) == 8 and quedan[0]["photo_flags"]


# ══════════════════════════════════════════════════════════════ el selector crea piezas v2

def _suscriptor(repo, crepo, cid="com-1", fotos=6):
    from tests.test_content_selector import suscriptor
    return suscriptor(repo, crepo, cid, fotos)


def test_el_selector_crea_la_pieza_v2_con_textos_fijos_sin_gemini(repo, crepo, monkeypatch):
    from tests.test_content_selector import plan
    monkeypatch.setattr(settings, "gemini_api_key", "")
    _suscriptor(repo, crepo)
    plan(repo, crepo)
    p = next(iter(crepo.pieces.values()))
    assert p["template_version"] == 2 and p["video_texts_engine"] == "template" and p["video_texts_checks"] == []
    assert p["video_texts"]["lema"] == "Si está en Bolivia, está en Uruku." and p["video_texts"]["title1"] == "Vidriería"
    assert p["photo_flags_ok"] is False
    assert len(crepo.list_sources(p["id"])) == 6                                    # tope de 6 fotos del video v2
    assert all(f["photo_flags"] == [] and f["chip_text"] is None for f in crepo.list_sources(p["id"]))


def test_el_selector_guarda_chips_marcas_y_saca_las_marcadas(repo, crepo, con_key, monkeypatch):
    from tests.test_content_selector import plan
    _suscriptor(repo, crepo)
    monkeypatch.setattr(cc, "_llamar_gemini", lambda prompt: None)
    sl = _slides(6, {2: {"price_or_code_visible": True}})
    _gemini(monkeypatch, [{**BUENOS, "slides": sl}])
    plan(repo, crepo)
    p = next(iter(crepo.pieces.values()))
    fuentes = crepo.list_sources(p["id"])
    assert p["video_texts_engine"] == "gemini:gemini-test" and p["video_texts"]["title1"] == "Camperas que"
    assert len(fuentes) == 5 and all(f["photo_flags"] == [] for f in fuentes)        # la marcada se sacó (quedaban 5 ≥ 4)
    assert fuentes[0]["chip_text"] == "Modelo uno" and fuentes[0]["focus_y"] == 0.3


def test_el_compilado_de_ofertas_no_lleva_precio_y_el_chip_es_el_nombre(repo, crepo, monkeypatch):
    from tests.test_content_selector import _comercios_con_oferta, _compilado, plan
    monkeypatch.setattr(settings, "gemini_api_key", "")
    _comercios_con_oferta(repo, crepo, subs=4, otros=4)
    plan(repo, crepo)
    p = _compilado(crepo)
    assert p["template_version"] == 2
    assert all("precio" not in i for i in p["facts"]["items"]) and "Bs" not in json.dumps(p["facts"])
    fuentes = crepo.list_sources(p["id"])
    assert [f["chip_text"] for f in fuentes] == [i["nombre"] for i in p["facts"]["items"]]
    assert all("·" not in (f["caption_fact"] or "") for f in fuentes)
    assert p["video_texts"]["close_title1"] == "¿Dónde las" and p["video_texts"]["place_chip"] is None
    assert not any(cc.tiene_voseo_o_tuteo(p[c]) for c in ("caption_tiktok", "caption_ig", "caption_channel"))


# ══════════════════════════════════════════════════════════════ reemplazar una foto: sólo la nueva

def _pieza_v2(repo, crepo, n=5, estado="ready_for_review", extra_bancos=0):
    comercio(repo)
    autorizar(crepo, "com-1")
    fotos = banco(crepo, "com-1", n + extra_bancos)
    facts = {**FACTS, "slug": "local-com-1", "nombre": "Local com-1",
             "hashtags_allowed": ["#URUKU", "#Bermejo", "#Tarija", "#Bolivia"], "allowed_numbers": []}
    p = pieza(crepo, "com-1", status=estado, facts=facts, template_version=2,
              video_texts=cvt.armar_textos(BUENOS, "comercio_del_dia", facts), video_texts_engine="gemini:x",
              video_path="renders/2026-11/x/video.mp4", cover_path="renders/2026-11/x/cover.jpg")
    crepo.insert_sources([{"piece_id": p["id"], "position": i, "source_type": "asset", "source_id": a["id"],
                           "comercio_id": "com-1", "file_ref": a["file_path"], "chip_text": f"Frase {NOMBRES[i]}"}
                          for i, a in enumerate(fotos[:n])])
    return p, fotos


def test_al_reemplazar_una_foto_solo_se_toca_el_chip_de_la_nueva(repo, crepo, con_key, monkeypatch):
    p, _ = _pieza_v2(repo, crepo, extra_bancos=1)
    antes = dict(crepo.pieces[p["id"]]["video_texts"])
    llamadas = _gemini(monkeypatch, [{"slides": [{"chip": "Foto de reemplazo", "price_or_code_visible": False,
                                                  "focus_y": 0.6}]}])
    sel.cambiar_fotos(crepo, crepo.pieces[p["id"]], [1])
    activas = crepo.list_sources(p["id"])
    assert len(llamadas) == 1 and len([x for x in llamadas[0] if "inline_data" in x]) == 1       # sólo la nueva
    assert [f["chip_text"] for f in activas] == ["Frase uno", "Frase tres", "Frase cuatro", "Frase cinco",
                                                 "Foto de reemplazo"]
    assert crepo.pieces[p["id"]]["video_texts"] == antes                                         # los textos no se tocan


def test_si_la_foto_nueva_viene_marcada_hay_que_volver_a_confirmar(repo, crepo, con_key, monkeypatch):
    p, _ = _pieza_v2(repo, crepo, n=4, extra_bancos=1)
    crepo.pieces[p["id"]]["photo_flags_ok"] = True
    _gemini(monkeypatch, [{"slides": [{"chip": None, "price_or_code_visible": True, "focus_y": 0.5}]}])
    sel.cambiar_fotos(crepo, crepo.pieces[p["id"]], [0])
    assert crepo.pieces[p["id"]]["photo_flags_ok"] is False                                      # quedaban < 4 sin marca
    assert any(f["photo_flags"] for f in crepo.list_sources(p["id"]))


def test_una_pieza_v1_no_pide_frases_al_reemplazar(repo, crepo, con_key, monkeypatch):
    p, _ = _pieza_v2(repo, crepo, extra_bancos=1)
    crepo.pieces[p["id"]]["template_version"] = 1
    monkeypatch.setattr(cvt, "_llamar_gemini", lambda partes: pytest.fail("no tiene que llamar"))
    sel.cambiar_fotos(crepo, crepo.pieces[p["id"]], [1])


# ══════════════════════════════════════════════════════════════ PATCH /video-texts

def _body(**kw):
    return {**BUENOS, "chips": [], **kw}


def _url(p, fin="video-texts"):
    return f"/admin/content/pieces/{p['id']}/{fin}"


@pytest.mark.parametrize("estado", ["ready_for_review", "failed"])
def test_patch_guarda_y_vuelve_a_encolar(client, repo, crepo, ana, estado):
    p, _ = _pieza_v2(repo, crepo, estado=estado)
    crepo.pieces[p["id"]].update(render_attempts=2, render_error="viejo")
    fuentes = crepo.list_sources(p["id"])
    r = client.patch(_url(p), headers=ana, json=_body(
        kick="otra cosa", title1="Nuevo título", chips=[{"source_id": fuentes[0]["id"], "text": "Frase nueva aquí"},
                                                       {"source_id": fuentes[1]["id"], "text": None}]))
    assert r.status_code == 200, r.text
    n = crepo.pieces[p["id"]]
    assert n["status"] == "queued" and n["render_attempts"] == 0 and n["render_error"] is None
    assert n["video_texts_engine"] == "human" and n["video_texts_checks"] == [] and n["template_version"] == 2
    assert n["video_texts"]["kick"] == "OTRA COSA" and n["video_texts"]["title1"] == "Nuevo título"
    assert n["video_texts"]["lema"].startswith("Si está en Bolivia")
    assert [f["chip_text"] for f in crepo.list_sources(p["id"])][:3] == ["Frase nueva aquí", None, "Frase tres"]
    cuerpo = r.json()
    assert cuerpo["status"] == "queued" and cuerpo["video_url"] is None and cuerpo["video_texts"]["kick"] == "OTRA COSA"


def test_patch_en_queued_solo_guarda(client, repo, crepo, ana):
    p, _ = _pieza_v2(repo, crepo, estado="queued")
    crepo.pieces[p["id"]]["render_next_at"] = "2099-01-01T00:00:00+00:00"
    assert client.patch(_url(p), headers=ana, json=_body(title1="Otro título")).status_code == 200
    n = crepo.pieces[p["id"]]
    assert n["status"] == "queued" and n["render_next_at"] == "2099-01-01T00:00:00+00:00" and n["video_texts"]["title1"] == "Otro título"


@pytest.mark.parametrize("estado", ["rendering", "approved", "published", "skipped"])
def test_patch_y_propose_en_otros_estados_son_409_sin_cambios(client, repo, crepo, ana, estado, monkeypatch):
    monkeypatch.setattr(cvt, "_llamar_gemini", lambda partes: pytest.fail("no tiene que llamar"))
    p, _ = _pieza_v2(repo, crepo, estado=estado)
    antes = json.dumps(crepo.pieces[p["id"]], sort_keys=True, default=str)
    assert client.patch(_url(p), headers=ana, json=_body(title1="Otro")).status_code == 409
    assert client.post(_url(p, "video-texts/propose"), headers=ana).status_code == 409
    assert json.dumps(crepo.pieces[p["id"]], sort_keys=True, default=str) == antes


def test_patch_valida_y_responde_400_con_la_objecion(client, repo, crepo, ana):
    p, _ = _pieza_v2(repo, crepo)
    r = client.patch(_url(p), headers=ana, json=_body(subtitle="Buscá tu campera"))
    assert r.status_code == 400 and "Subtítulo: Use usted, sin voseo ni tuteo" in r.json()["detail"]
    f0 = crepo.list_sources(p["id"])[0]
    r = client.patch(_url(p), headers=ana, json=_body(chips=[{"source_id": f0["id"], "text": "Cuesta 50 pesos"}]))
    assert r.status_code == 400 and "Frase de la foto 1" in r.json()["detail"]
    assert client.patch(_url(p), headers=ana, json=_body(title1="")).status_code == 400
    assert crepo.pieces[p["id"]]["status"] == "ready_for_review"                                # nada se guardó


def test_patch_con_un_source_id_que_no_es_de_la_pieza_es_400(client, repo, crepo, ana):
    p, _ = _pieza_v2(repo, crepo)
    r = client.patch(_url(p), headers=ana, json=_body(chips=[{"source_id": "no-existe", "text": "Dos palabras"}]))
    assert r.status_code == 400
    removida = crepo.list_sources(p["id"])[0]
    crepo.deactivate_source(p["id"], removida["position"])                                      # una fuente inactiva tampoco
    r = client.patch(_url(p), headers=ana, json=_body(chips=[{"source_id": removida["id"], "text": "Dos palabras"}]))
    assert r.status_code == 400


def test_patch_necesita_el_permiso_difusion_y_404_si_no_existe(client, repo, crepo, ana):
    p, _ = _pieza_v2(repo, crepo)
    sin = h(auth.make_token("mod@uruku.bo", rol="moderador"))
    assert client.patch(_url(p), headers=sin, json=_body()).status_code == 403
    assert client.post(_url(p, "video-texts/propose"), headers=sin).status_code == 403
    assert client.patch("/admin/content/pieces/no-existe/video-texts", headers=ana, json=_body()).status_code == 404


def test_patch_que_solo_cambia_photo_flags_ok_no_re_encola(client, repo, crepo, ana):
    p, _ = _pieza_v2(repo, crepo)
    fuentes = crepo.list_sources(p["id"])
    chips = [{"source_id": f["id"], "text": f["chip_text"]} for f in fuentes]
    r = client.patch(_url(p), headers=ana, json=_body(chips=chips, photo_flags_ok=True))
    assert r.status_code == 200
    n = crepo.pieces[p["id"]]
    assert n["photo_flags_ok"] is True and n["status"] == "ready_for_review" and n["video_path"]
    assert n["video_texts_engine"] == "gemini:x" and n["render_attempts"] == 0              # tampoco se marca como «escrito a mano»
    assert r.json()["video_url"]                                                              # el video sigue a la vista
    # sin chips en el cuerpo, con los mismos textos: lo mismo
    r = client.patch(_url(p), headers=ana, json=_body(photo_flags_ok=False))
    assert r.status_code == 200 and crepo.pieces[p["id"]]["photo_flags_ok"] is False and crepo.pieces[p["id"]]["status"] == "ready_for_review"
    # y si cambia un texto, sí se re-encola
    client.patch(_url(p), headers=ana, json=_body(title2="Otra cosa", photo_flags_ok=True))
    assert crepo.pieces[p["id"]]["status"] == "queued"


def test_en_ofertas_el_frontend_manda_chips_vacios_y_se_acepta(client, repo, crepo, ana):
    from tests.test_content_revision_fixes import _compilado_armado
    p = _compilado_armado(repo, crepo)
    crepo.pieces[p["id"]].update(template_version=2, video_texts=None)
    for f in crepo.list_sources(p["id"]):
        f["chip_text"] = f["caption_fact"].split(" · ")[0]
    r = client.patch(_url(p), headers=ana, json=_body(title2="Bermejo", search_term="ofertas"))
    assert r.status_code == 200, r.text
    n = crepo.pieces[p["id"]]
    assert n["status"] == "queued" and n["video_texts"]["close_title1"] == "¿Dónde las" and n["video_texts"]["place_chip"] is None
    assert [f["chip_text"] for f in crepo.list_sources(p["id"])][0] == "Local s0"
    # los chips que lleguen en ofertas se ignoran (el nombre sale del comercio)
    f0 = crepo.list_sources(p["id"])[0]
    crepo.pieces[p["id"]]["status"] = "ready_for_review"
    client.patch(_url(p), headers=ana, json=_body(title2="Bermejo", search_term="ofertas",
                                                  chips=[{"source_id": f0["id"], "text": "Otro nombre"}]))
    assert crepo.list_sources(p["id"])[0]["chip_text"] == "Local s0"


def test_patch_promueve_una_pieza_v1_a_v2(client, repo, crepo, ana):
    p, _ = _pieza_v2(repo, crepo)
    crepo.pieces[p["id"]].update(template_version=1, video_texts=None)
    assert client.patch(_url(p), headers=ana, json=_body()).status_code == 200
    assert crepo.pieces[p["id"]]["template_version"] == 2 and crepo.pieces[p["id"]]["video_texts"]["title1"] == "Camperas que"


# ══════════════════════════════════════════════════════════════ POST /video-texts/propose

@pytest.mark.parametrize("estado", ["ready_for_review", "failed", "queued"])
def test_propose_pide_a_gemini_guarda_y_re_encola(client, repo, crepo, ana, con_key, monkeypatch, estado):
    p, _ = _pieza_v2(repo, crepo, estado=estado)
    _gemini(monkeypatch, [{**BUENOS, "kick": "OTRO GANCHO", "slides": _slides(5)}])
    r = client.post(_url(p, "video-texts/propose"), headers=ana)
    assert r.status_code == 200, r.text
    n = crepo.pieces[p["id"]]
    assert n["video_texts_engine"] == "gemini:gemini-test" and n["video_texts"]["kick"] == "OTRO GANCHO"
    assert n["status"] == "queued" and n["video_texts_checks"] == []
    assert crepo.list_sources(p["id"])[0]["chip_text"] == "Modelo uno"
    assert r.json()["video_texts_engine"] == "gemini:gemini-test"


def test_propose_sin_gemini_deja_los_textos_fijos(client, repo, crepo, ana, monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    p, _ = _pieza_v2(repo, crepo)
    r = client.post(_url(p, "video-texts/propose"), headers=ana)
    assert r.status_code == 200 and crepo.pieces[p["id"]]["video_texts_engine"] == "template"
    assert crepo.pieces[p["id"]]["status"] == "queued"


def test_propose_saca_las_fotos_marcadas_si_quedan_4(client, repo, crepo, ana, con_key, monkeypatch):
    p, _ = _pieza_v2(repo, crepo, n=6)
    _gemini(monkeypatch, [{**BUENOS, "slides": _slides(6, {3: {"price_or_code_visible": True}})}])
    client.post(_url(p, "video-texts/propose"), headers=ana)
    assert len(crepo.list_sources(p["id"])) == 5 and not any(f["photo_flags"] for f in crepo.list_sources(p["id"]))


def test_propose_con_marcadas_que_no_se_pueden_sacar_pide_confirmar(client, repo, crepo, ana, con_key, monkeypatch):
    p, _ = _pieza_v2(repo, crepo, n=5)
    crepo.pieces[p["id"]]["photo_flags_ok"] = True
    _gemini(monkeypatch, [{**BUENOS, "slides": _slides(5, {0: {"price_or_code_visible": True}, 1: {"price_or_code_visible": True}})}])
    client.post(_url(p, "video-texts/propose"), headers=ana)
    assert len(crepo.list_sources(p["id"])) == 5 and crepo.pieces[p["id"]]["photo_flags_ok"] is False


# ══════════════════════════════════════════════════════════════ el contrato de la respuesta

def test_la_pieza_trae_los_campos_nuevos_y_el_id_de_cada_fuente(client, repo, crepo, ana):
    p, _ = _pieza_v2(repo, crepo)
    crepo.list_sources(p["id"])[0]["photo_flags"] = ["price_or_code_visible"]
    r = client.get(f"/admin/content/pieces/{p['id']}", headers=ana).json()
    for k in ("template_version", "video_texts", "video_texts_engine", "video_texts_checks", "photo_flags_ok"):
        assert k in r
    assert r["template_version"] == 2 and r["video_texts"]["title1"] == "Camperas que"
    ids = [f["id"] for f in crepo.list_sources(p["id"])]
    assert [s["id"] for s in r["sources"]] == ids
    assert set(r["sources"][0]) >= {"id", "position", "chip_text", "photo_flags", "focus_y", "thumb_url"}
    assert r["sources"][0]["photo_flags"] == ["price_or_code_visible"] and r["sources"][1]["chip_text"] == "Frase dos"


def test_una_pieza_v1_se_ve_con_video_texts_null(client, repo, crepo, ana):
    comercio(repo)
    p = pieza(crepo, "com-1", status="queued")
    r = client.get(f"/admin/content/pieces/{p['id']}", headers=ana).json()
    assert r["template_version"] == 1 and r["video_texts"] is None and r["video_texts_checks"] == [] and r["photo_flags_ok"] is False


# ══════════════════════════════════════════════════════════════ aprobar (§16.9)

def test_aprobar_se_bloquea_con_objeciones_en_los_textos_del_video(client, repo, crepo, ana):
    p, _ = _pieza_v2(repo, crepo)
    crepo.pieces[p["id"]]["video_texts_checks"] = ["Subtítulo: pasa de 42 caracteres"]
    r = client.post(f"/admin/content/pieces/{p['id']}/approve", headers=ana)
    assert r.status_code == 409 and r.json()["detail"] == "Revise los textos del video"
    assert crepo.pieces[p["id"]]["status"] == "ready_for_review"
    crepo.pieces[p["id"]]["video_texts_checks"] = []
    assert client.post(f"/admin/content/pieces/{p['id']}/approve", headers=ana).status_code == 200


def test_aprobar_se_bloquea_con_fotos_marcadas_hasta_confirmar(client, repo, crepo, ana):
    p, _ = _pieza_v2(repo, crepo)
    crepo.list_sources(p["id"])[2]["photo_flags"] = ["price_or_code_visible"]
    r = client.post(f"/admin/content/pieces/{p['id']}/approve", headers=ana)
    assert r.status_code == 409 and r.json()["detail"] == "Hay fotos marcadas: cámbielas o confirme que están bien"
    assert client.patch(_url(p), headers=ana, json=_body(photo_flags_ok=True,
                        chips=[{"source_id": f["id"], "text": f["chip_text"]} for f in crepo.list_sources(p["id"])])).status_code == 200
    assert client.post(f"/admin/content/pieces/{p['id']}/approve", headers=ana).status_code == 200


def test_aprobar_en_lote_rechaza_las_que_tienen_checks_o_marcas(client, repo, crepo, ana):
    malos, _ = _pieza_v2(repo, crepo)
    crepo.pieces[malos["id"]]["video_texts_checks"] = ["algo"]
    marcada = pieza(crepo, "com-1", status="ready_for_review", template_version=2, video_texts_checks=[],
                    dia=__import__("datetime").date.today() + __import__("datetime").timedelta(days=9))
    crepo.insert_sources([{"piece_id": marcada["id"], "position": 0, "source_type": "gallery", "source_id": "x",
                           "comercio_id": "com-1", "file_ref": "x", "photo_flags": ["price_or_code_visible"]}])
    r = client.post("/admin/content/pieces/approve-batch", headers=ana, json={"ids": [malos["id"], marcada["id"]]}).json()
    assert r["approved"] == [] and {x["motivo"] for x in r["refused"]} >= {"Revise los textos del video",
                                                                         "Hay fotos marcadas: cámbielas o confirme que están bien"}


def test_una_pieza_v1_se_aprueba_como_siempre(client, repo, crepo, ana):
    comercio(repo)
    autorizar(crepo, "com-1")
    p = pieza(crepo, "com-1")
    assert client.post(f"/admin/content/pieces/{p['id']}/approve", headers=ana).status_code == 200


def test_el_estado_del_worker_acepta_no_renderer_en_render_worker(client, repo, crepo, ana, monkeypatch):
    monkeypatch.setattr(settings, "content_render_worker", True)
    monkeypatch.setattr(settings, "content_render_engine", "kit")
    monkeypatch.setattr(settings, "renderer_token", "")
    r = client.get("/admin/content/status", headers=ana).json()
    assert r["render_worker"] == "no_renderer"
