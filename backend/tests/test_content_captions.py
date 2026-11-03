"""Textos de las piezas: hechos, validador determinista, Gemini simulado y plantilla fija."""
import re

import httpx
import pytest

from app.core.config import settings
from app.services import content_captions as cc

COMERCIO = {"nombre": "Vidriería Pacheco", "slug": "vidrieria-pacheco", "calle": "Calle Barrientos",
            "horario": "Lunes a sábado de 8 a 19", "subcategoria": "Vidrios y espejos",
            "monedas_aceptadas": ["BOB", "ARS"],
            "rubros": {"nombre": "🪟 Vidriería", "slug": "vidrios"},
            "ciudades": {"nombre": "Bermejo", "slug": "bermejo", "departamento": "Tarija"}}


@pytest.fixture
def facts():
    return cc.build_facts_comercio(COMERCIO)


OK = "Vidriería Pacheco, en calle Barrientos de Bermejo. Búsquela en uruku.bo y escríbale directo desde su ficha."
TAGS = ["#URUKU", "#Bermejo", "#Tarija", "#Bolivia"]


def test_los_hechos_salen_de_la_base_sin_emojis_y_con_los_numeros_permitidos(facts):
    assert facts["nombre"] == "Vidriería Pacheco" and facts["rubro"] == "Vidriería"       # sin el emoji del rubro
    assert facts["monedas"] == ["bolivianos", "pesos"] and facts["slug"] == "vidrieria-pacheco"
    assert facts["allowed_numbers"] == ["19", "8"] or set(facts["allowed_numbers"]) == {"8", "19"}
    assert facts["hashtags_allowed"][:3] == ["#URUKU", "#Bermejo", "#Tarija"] and "#Vidrieria" in facts["hashtags_allowed"]
    assert "codigo" not in facts


def test_los_campos_vacios_no_se_mandan():
    f = cc.build_facts_comercio({"nombre": "Kiosco Ana", "slug": "kiosco-ana", "ciudades": {"nombre": "Bermejo", "departamento": "Tarija"}})
    assert "horario_texto" not in f and "calle" not in f and "monedas" not in f


def test_el_texto_correcto_no_tiene_objeciones(facts):
    for red in ("tiktok", "instagram", "channel"):
        assert cc.validate_caption(OK, facts, red) == []


@pytest.mark.parametrize("texto, objecion", [
    ("Vidriería Pacheco 😀 en uruku.bo", "Tiene un emoji"),
    ("Vidriería Pacheco abre de 9 a 19", "El número 9 no está en los datos"),
    ("Vidriería Pacheco, URUKU-K7M2, en uruku.bo", "Tiene el código del comercio"),
    ("Vidriería Pacheco. Escribí CONFIRMAR-123456", "Tiene un texto de ingreso"),
    ("Vidriería Pacheco. Tu clave: BOUTIQUE-K7M2P9", "Tiene un texto de ingreso"),
    ("Vidriería Pacheco, uno de los 500 comercios de URUKU", "Cuenta comercios"),
    ("Vidriería Pacheco vende a Bs 500", "Tiene un precio"),
    ("Vidriería Pacheco, desde 500 bolivianos", "Tiene un precio"),
    ("Vidriería Pacheco, vidrios a $ 99", "Tiene un precio"),
    ("Vidriería Pacheco, espejos a US$ 5", "Tiene un precio"),
    ("Vidriería Pacheco. Si necesitás un vidrio, buscala en uruku.bo", "Use usted, sin voseo ni tuteo"),
    ("Vidriería Pacheco. Mirá su ficha en uruku.bo", "Use usted, sin voseo ni tuteo"),
    ("Vidriería Pacheco. Si quieres un espejo, busca tu vidriería en uruku.bo", "Use usted, sin voseo ni tuteo"),
    ("Vidriería Pacheco. Escribile desde su ficha en uruku.bo", "Use usted, sin voseo ni tuteo"),
    ("Vidriería Pacheco es la mejor de Bermejo", "Promete algo que no se puede (la mejor)"),
    ("Vidriería Pacheco con envío a todo el país", "Promete algo que no se puede (envío)"),
    ("Vidriería Pacheco con GARANTÍA", "Promete algo que no se puede (garantía)"),
    ("Vidriería Pacheco, próximamente más", "Promete algo que no se puede (próximamente)"),
    ("Te traemos clientes. Vidriería Pacheco", "Promete algo que no se puede (te traemos clientes)"),
    ("Mirá la vidriería de Bermejo en uruku.bo", "Falta el nombre del comercio"),
    ("Vidriería Pacheco #Fierro", "Hashtag fuera de la lista"),
])
def test_cada_regla_del_validador(facts, texto, objecion):
    assert objecion in cc.validate_caption(texto, facts, "tiktok")


def test_los_largos_por_red(facts):
    largo = "Vidriería Pacheco " + "a" * 600
    assert "Pasa de 300 caracteres" in cc.validate_caption(largo[:301], facts, "tiktok")
    assert "Pasa de 600 caracteres" in cc.validate_caption(largo[:601], facts, "instagram")
    assert "Pasa de 400 caracteres" in cc.validate_caption(largo[:401], facts, "channel")
    assert not any("Pasa de" in o for o in cc.validate_caption(largo[:300], facts, "tiktok"))


def test_numeros_equivalentes_valen_lo_mismo():
    assert cc.norm_numero("1.200") == cc.norm_numero("1200") == cc.norm_numero("1200,00") == "1200"
    assert cc.norm_numero("12,50") == "12.5"
    # Un número que SÍ está en los hechos (el horario) vale con cualquier formato; un monto nunca es válido (§16.5).
    f = cc.build_facts_comercio({**COMERCIO, "horario": "Lunes a sábado de 1.200 a 1900"})
    assert cc.validate_caption("Vidriería Pacheco abre de 1200 a 1.900 en uruku.bo", f, "tiktok") == []
    assert "Tiene un precio" in cc.validate_caption("Vidriería Pacheco, espejos a $ 1200", f, "tiktok")


def test_los_hechos_de_ofertas_no_llevan_precio_ni_lo_dejan_pasar():
    """Los items viejos que traían `precio` lo pierden al armar los hechos, y `allowed_numbers` no lo incluye."""
    f = cc.build_facts_ofertas({"nombre": "Bermejo", "departamento": "Tarija"},
                               [{"nombre": "Bazar Mía", "precio": "Bs 1.200", "titulo_corto": "Ollas"}] * 4)
    assert all("precio" not in i for i in f["items"]) and f["allowed_numbers"] == []
    assert "1200" not in str(f) and "Bs" not in str(f)
    obj = cc.validate_caption("Ofertas en Bermejo: ollas a Bs 1200 en uruku.bo", f, "tiktok")
    assert "Tiene un precio" in obj and "El número 1200 no está en los datos" in obj
    assert cc.validate_caption("Ofertas en Bermejo. Consulte precio directo con el local en uruku.bo", f, "tiktok") == []


def test_un_nombre_comun_no_se_confunde_con_una_clave():
    f = cc.build_facts_comercio({**COMERCIO, "nombre": "Ferretería El Puente"})
    assert cc.validate_caption("Ferretería El Puente, en calle Tarija. Escríbale desde su ficha en uruku.bo.", f, "instagram") == []


def test_el_nombre_se_compara_sin_tildes_ni_mayusculas(facts):
    assert cc.validate_caption("VIDRIERIA PACHECO en uruku.bo", facts, "tiktok") == []


def test_hashtags_solo_de_la_lista_y_entre_4_y_8(facts):
    assert {"#Bolivia", "#ComerciosLocales"} <= set(facts["hashtags_allowed"]) and len(facts["hashtags_allowed"]) <= 8
    assert cc.validate_hashtags(TAGS, facts) == []
    assert cc.validate_hashtags(TAGS + ["#ComerciosLocales", "#Vidrieria"], facts) == []
    assert cc.validate_hashtags(["#URUKU", "#Bermejo", "#Tarija"], facts)              # 3: pocos
    assert cc.validate_hashtags(TAGS + ["#Otro"], facts)                               # fuera de la lista
    assert cc.validate_hashtags(facts["hashtags_allowed"] * 2, facts)                  # más de 8
    assert cc.validate_caption("Vidriería Pacheco #URUKU", facts, "channel") == ["Hashtag fuera de la lista"]
    assert cc.validate_caption("Vidriería Pacheco #URUKU", facts, "tiktok") == []


def test_validate_piece_antepone_la_red_y_puede_ignorar_numeros(facts):
    obj = cc.validate_piece(facts, "Vidriería Pacheco abre a las 5", OK, OK, TAGS)
    assert obj == ["TikTok: El número 5 no está en los datos"]
    assert cc.validate_piece(facts, "Vidriería Pacheco abre a las 5", OK, OK, TAGS, ignorar_numeros=True) == []


# ── plantilla fija ───────────────────────────────────────────────────────────

def test_la_plantilla_fija_siempre_sale_en_verde(facts):
    t = cc.template_captions(facts)
    assert t["caption_tiktok"] == "Vidriería Pacheco · Vidriería · Calle Barrientos, Bermejo. Búsquelo en uruku.bo"
    assert cc.validate_piece(facts, t["caption_tiktok"], t["caption_ig"], t["caption_channel"], t["hashtags"]) == []
    # los tres fijos + #Bolivia + #ComerciosLocales + el primero del rubro (§16.5): 6, dentro de 4 a 8
    assert t["hashtags"] == ["#URUKU", "#Bermejo", "#Tarija", "#Bolivia", "#ComerciosLocales", "#Vidrieria"]


def test_la_plantilla_sin_tramos_vacios_y_con_nombre_largo():
    f = cc.build_facts_comercio({"nombre": "N" * 400, "slug": "n", "ciudades": {"nombre": "Bermejo", "departamento": "Tarija"}})
    t = cc.template_captions(f)
    assert len(t["caption_tiktok"]) <= 300 and len(t["caption_channel"]) <= 400
    f2 = cc.build_facts_comercio({"nombre": "Kiosco Ana", "slug": "k", "ciudades": {"nombre": "Bermejo", "departamento": "Tarija"}})
    assert cc.template_captions(f2)["caption_tiktok"] == "Kiosco Ana · Bermejo. Búsquelo en uruku.bo"
    t2 = cc.template_captions(f2)
    assert cc.validate_hashtags(t2["hashtags"], f2) == [] and 4 <= len(t2["hashtags"]) <= 8


def test_la_plantilla_de_ofertas_nunca_cuenta_comercios():
    f = cc.build_facts_ofertas({"nombre": "Bermejo", "departamento": "Tarija"},
                               [{"nombre": f"C{i}", "precio": "Bs 10", "titulo_corto": ""} for i in range(5)])
    t = cc.template_captions(f)
    assert t["caption_tiktok"] == "Ofertas de la semana en Bermejo. Consulte precio directo con el local y vea todas en uruku.bo"
    assert cc.validate_piece(f, t["caption_tiktok"], t["caption_ig"], t["caption_channel"], t["hashtags"]) == []
    assert "Cuenta comercios" not in cc.validate_caption(t["caption_tiktok"], f, "tiktok")


# ── Gemini simulado ──────────────────────────────────────────────────────────

def _gemini(monkeypatch, respuestas):
    llamadas = []

    def falso(prompt):
        llamadas.append(prompt)
        return respuestas.pop(0) if respuestas else None
    monkeypatch.setattr(cc, "_llamar_gemini", falso)
    return llamadas


BUENA = {"caption_tiktok": OK, "caption_ig": OK, "caption_channel": OK, "hashtags": TAGS}
MALA = {**BUENA, "caption_tiktok": "Vidriería Pacheco 🔥 la mejor, con envío"}


def test_gemini_valido_queda_como_gemini(facts, monkeypatch):
    monkeypatch.setattr(settings, "gemini_model", "gemini-test")
    _gemini(monkeypatch, [BUENA])
    r = cc.generate_captions(facts)
    assert r["caption_engine"] == "gemini:gemini-test" and r["caption_checks"] == [] and r["caption_tiktok"] == OK


def test_gemini_objetado_se_reintenta_una_vez_con_las_objeciones(facts, monkeypatch):
    llamadas = _gemini(monkeypatch, [MALA, BUENA])
    r = cc.generate_captions(facts)
    assert r["caption_engine"].startswith("gemini:") and len(llamadas) == 2
    assert "Tiene un emoji" in llamadas[1] and "corrígelas" in llamadas[1] and "corrígelas" not in llamadas[0]


def test_gemini_invalido_dos_veces_cae_a_la_plantilla(facts, monkeypatch):
    llamadas = _gemini(monkeypatch, [MALA, MALA, BUENA])
    r = cc.generate_captions(facts)
    assert r["caption_engine"] == "template" and len(llamadas) == 2 and r["caption_checks"] == []


def test_sin_key_es_plantilla_y_no_llama_a_nadie(facts, monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr("app.services.vision._post_con_reintentos", lambda *a, **k: pytest.fail("no tiene que llamar"))
    assert cc.generate_captions(facts)["caption_engine"] == "template"


def test_error_http_de_gemini_cae_a_la_plantilla_sin_filtrar_la_key(facts, monkeypatch, caplog):
    monkeypatch.setattr(settings, "gemini_api_key", "CLAVE-SECRETA")

    def roto(url, payload):
        raise httpx.ConnectError(f"fallo en {url}")
    monkeypatch.setattr("app.services.vision._post_con_reintentos", roto)
    r = cc.generate_captions(facts)
    assert r["caption_engine"] == "template"
    assert "CLAVE-SECRETA" not in caplog.text


def test_gemini_manda_solo_hechos_y_pide_json(facts, monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "k")
    visto = {}

    class R:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"candidates": [{"content": {"parts": [{"text": '```json\n' + __import__("json").dumps(BUENA) + '\n```'}]}}]}

    def post(url, payload):
        visto.update(payload=payload, url=url)
        return R()
    monkeypatch.setattr("app.services.vision._post_con_reintentos", post)
    r = cc.generate_captions(facts)
    assert r["caption_engine"].startswith("gemini:")
    assert visto["payload"]["generationConfig"]["responseMimeType"] == "application/json"
    prompt = visto["payload"]["contents"][0]["parts"][0]["text"]
    assert "Vidriería Pacheco" in prompt and "allowed_numbers" not in prompt and "Anthropic" not in prompt
    assert prompt.count("\n- ") >= 6


def test_respuesta_que_no_es_json_no_lanza(facts, monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "k")

    class R:
        def raise_for_status(self): pass
        def json(self): return {"candidates": [{"content": {"parts": [{"text": "no soy json"}]}}]}
    monkeypatch.setattr("app.services.vision._post_con_reintentos", lambda u, p: R())
    assert cc.generate_captions(facts)["caption_engine"] == "template"


# ── texto por red ────────────────────────────────────────────────────────────

def test_texto_por_red_y_ref_tag(facts, monkeypatch):
    monkeypatch.setattr(settings, "sitio_url", "https://uruku.bo")
    pieza = {"facts": facts, "caption_tiktok": "TT", "caption_ig": "IG", "caption_channel": "CH", "hashtags": ["#URUKU", "#Bermejo"]}
    assert cc.ref_tag("tiktok", facts, "1104") == "tt-vidrieria-pacheco-1104"
    assert cc.ref_tag("wa_channel", facts, "1104") == "canal-vidrieria-pacheco-1104"
    assert cc.caption_text(pieza, "tiktok", "r") == "TT\n\n#URUKU #Bermejo"
    assert cc.caption_text(pieza, "instagram", "r") == "IG\n\n#URUKU #Bermejo"
    assert cc.caption_text(pieza, "facebook", "fb-x") == "IG\n\nhttps://uruku.bo/comercios/vidrieria-pacheco?ref=fb-x\n\n#URUKU #Bermejo"
    assert cc.caption_text(pieza, "wa_channel", "canal-x") == "CH\n\nhttps://uruku.bo/comercios/vidrieria-pacheco?ref=canal-x"
    of = cc.build_facts_ofertas({"nombre": "Bermejo", "departamento": "Tarija"}, [])
    assert cc.ref_tag("facebook", of, "1105") == "fb-ofertas-1105"
    assert cc.link_de(of, "fb-ofertas-1105") == "https://uruku.bo/ofertas?ref=fb-ofertas-1105"
    assert len(cc.ref_tag("tiktok", {**facts, "slug": "s" * 100}, "1104")) == 64


# ── tono: español neutro, sin voseo ni tuteo (§16.1 y §16.6) ─────────────────

@pytest.mark.parametrize("texto", [
    "vos tenés razón", "Buscá el local", "Mirá la ficha", "Conocé el local", "Encontrá lo que busca", "Vení a verlo",
    "Si querés, podés escribir", "Escribile por WhatsApp", "Buscalo en la web", "Mandale un mensaje", "Consultalo hoy",
    "Tú puedes buscarlo", "Si tienes dudas", "Tu comercio en Uruku", "Para ti", "Te ayudamos a buscar", "Si quieres comprar",
    "Búscalo en uruku.bo", "Escríbele desde su ficha",
])
def test_el_voseo_y_el_tuteo_se_detectan(texto):
    assert cc.tiene_voseo_o_tuteo(texto), texto


@pytest.mark.parametrize("texto", [
    "Busque su local en uruku.bo", "Consulte precio directo con el local", "Escríbale desde su ficha",
    "Vea cómo llegar", "Búsquela en uruku.bo", "Conozca el local", "Si necesita un vidrio", "¿Dónde lo consigue? En Uruku",
    "El que busca, encuentra", "Un café con estilo", "Ropa de hombre y de mujer", "Atiende de lunes a sábado",
])
def test_el_usted_no_se_objeta(texto):
    assert not cc.tiene_voseo_o_tuteo(texto), texto


def test_un_comercio_llamado_tu_casa_no_es_tuteo():
    f = cc.build_facts_comercio({**COMERCIO, "nombre": "Tu Casa Muebles"})
    assert cc.validate_caption("Tu Casa Muebles, en calle Barrientos de Bermejo. Búsquelo en uruku.bo", f, "tiktok") == []
    assert "Use usted, sin voseo ni tuteo" in cc.validate_caption("Tu Casa Muebles. Buscá tu mueble en uruku.bo", f, "tiktok")


def test_los_ejemplos_del_prompt_y_la_plantilla_estan_en_neutro_y_en_verde(facts):
    assert not any(cc.tiene_voseo_o_tuteo(e) for e in cc.EJEMPLOS) and len(cc.EJEMPLOS) == 6
    assert not any(re.search(r"\bBs\b|\$|\d{3}", e) for e in cc.EJEMPLOS)            # ni un precio
    t = cc.template_captions(facts)
    assert not cc.tiene_voseo_o_tuteo(t["caption_tiktok"], [facts["nombre"]])
    prompt = cc.construir_prompt(facts)
    assert "NEUTRO" in prompt and "usted" in prompt and "NUNCA escribas un precio" in prompt
    assert "búsquela en uruku.bo" in prompt and "Buscalo" not in prompt


def test_gemini_que_tutea_o_da_un_precio_se_objeta_y_cae_a_la_plantilla(facts, monkeypatch):
    tutea = {**BUENA, "caption_tiktok": "Vidriería Pacheco. Busca tu vidrio en uruku.bo"}
    con_precio = {**BUENA, "caption_ig": "Vidriería Pacheco, espejos desde Bs 80 en uruku.bo"}
    llamadas = _gemini(monkeypatch, [tutea, con_precio])
    r = cc.generate_captions(facts)
    assert r["caption_engine"] == "template" and len(llamadas) == 2
    assert "Use usted, sin voseo ni tuteo" in llamadas[1] or "Tiene un precio" in llamadas[1]
    assert not cc.tiene_voseo_o_tuteo(r["caption_tiktok"], [facts["nombre"]]) and r["caption_checks"] == []
