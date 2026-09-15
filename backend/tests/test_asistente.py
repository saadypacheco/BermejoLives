"""Uruku Ayuda: cada nivel contesta lo suyo, y lo que no sabe queda anotado.

Sin red: el modelo se reemplaza por una función. Lo que se prueba es la
escalera —qué se resuelve sin modelo, cuándo se lo llama, qué pasa cuando
dice que no sabe— y que todo lo que la gente pregunta queda en la base.
"""
from datetime import datetime

import pytest

from app.core.config import settings
from app.services import asistente, horario

MARTES_11 = datetime(2026, 9, 15, 11, 0)     # martes 11:00
MARTES_13 = datetime(2026, 9, 15, 13, 0)     # martes 13:00, siesta
SABADO_02 = datetime(2026, 9, 19, 2, 0)      # sábado 2 de la mañana


# ------------------------------------------------------------------ horario

def test_el_horario_partido_esta_cerrado_a_la_hora_de_la_siesta():
    h = "Lun-Sáb 8:00-12:00 y 14:30-20:00"
    assert horario.abierto_ahora(h, MARTES_11).estado == "abierto"
    assert horario.abierto_ahora(h, MARTES_13).estado == "cerrado"
    assert horario.etiqueta(horario.abierto_ahora(h, MARTES_13), MARTES_13) == "Cerrado · abre 14:30"


def test_el_boliche_que_cruza_la_medianoche_esta_abierto_a_las_dos():
    assert horario.abierto_ahora("Vie-Sáb 21:00-4:00", SABADO_02).estado == "abierto"
    assert horario.abierto_ahora("Vie-Sáb 21:00-4:00", MARTES_11).estado == "cerrado"


def test_un_horario_que_no_se_entiende_es_desconocido_no_cerrado():
    assert horario.abierto_ahora("consultar", MARTES_11).estado == "desconocido"
    assert horario.abierto_ahora("", MARTES_11).estado == "desconocido"
    assert horario.etiqueta(horario.abierto_ahora(None, MARTES_11), MARTES_11) is None


# ------------------------------------------------------------------ armado

def _rustico(repo, **extra):
    c = {"id": "com-rustico", "slug": "rustico", "nombre": "Rústico", "activo": True,
         "subcategoria": "restaurante", "direccion": "Calle Tarija 123", "horario": "Lun-Sáb 8:00-12:00 y 14:30-20:00",
         "whatsapp": "59170000001", "lat": -22.73, "lng": -64.33, "plan": "gratis",
         "prod_obs_human": "pizza, empanadas, milanesa", **extra}
    repo.comercios[c["id"]] = c
    return c


def _zapateria(repo):
    c = {"id": "com-zap", "slug": "zapateria-luz", "nombre": "Zapatería Luz", "activo": True,
         "subcategoria": "calzado", "direccion": "Mercado central", "horario": None,
         "whatsapp": None, "plan": "gratis", "prod_obs_human": "zapatillas, botas, chinelas"}
    repo.comercios[c["id"]] = c
    return c


@pytest.fixture
def sin_modelo(monkeypatch):
    """Sin GEMINI_API_KEY: el Nivel 1 no existe. Lo que no resuelve el 0 va al 3."""
    monkeypatch.setattr(settings, "gemini_api_key", "")


# ------------------------------------------------------------------ Nivel 0

def test_el_horario_de_un_local_nombrado_sale_sin_modelo(repo, sin_modelo):
    _rustico(repo)
    r = asistente.responder(repo, "¿A qué hora abre Rústico?", ahora=MARTES_13)
    assert r.nivel == 0 and r.intent == "horario"
    assert "Rústico" in r.texto and "cerrado" in r.texto.lower()
    assert r.fuentes[0]["url"].endswith("/comercios/rustico")


def test_la_direccion_y_el_whatsapp_tambien(repo, sin_modelo):
    _rustico(repo)
    d = asistente.responder(repo, "dónde queda rustico", ahora=MARTES_11)
    assert d.nivel == 0 and "Calle Tarija 123" in d.texto and "maps" in d.texto
    w = asistente.responder(repo, "whatsapp de rustico", ahora=MARTES_11)
    assert w.nivel == 0 and "wa.me/59170000001" in w.texto


def test_donde_consigo_algo_es_la_busqueda_del_sitio(repo, sin_modelo):
    _rustico(repo)
    _zapateria(repo)
    r = asistente.responder(repo, "¿Dónde consigo zapatillas?", ahora=MARTES_11)
    assert r.nivel == 0 and r.intent == "buscar"
    assert "Zapatería Luz" in r.texto and "Rústico" not in r.texto
    assert not r.sin_respuesta


def test_buscar_algo_que_no_hay_queda_anotado_como_sin_respuesta(repo, sin_modelo):
    _rustico(repo)
    r = asistente.responder(repo, "busco paracaídas", ahora=MARTES_11)
    assert r.nivel == 0 and r.sin_respuesta
    assert "paracaídas" in r.texto or "paracaidas" in r.texto


def test_que_hay_abierto_ahora_mira_los_horarios(repo, sin_modelo):
    _rustico(repo)
    _zapateria(repo)   # sin horario: no puede figurar abierto
    r = asistente.responder(repo, "¿qué hay abierto ahora?", ahora=MARTES_11)
    assert r.nivel == 0 and r.intent == "abierto_ahora"
    assert "Rústico" in r.texto and "Zapatería" not in r.texto
    r2 = asistente.responder(repo, "¿qué hay abierto ahora?", ahora=MARTES_13)
    assert "No encuentro" in r2.texto


def test_el_dolar_sale_de_las_cotizaciones(repo, sin_modelo):
    repo.cotizaciones[0]["valor"] = 11.2
    r = asistente.responder(repo, "¿a cuánto está el dólar?", ahora=MARTES_11)
    assert r.nivel == 0 and r.intent == "cotizacion" and "11,2 Bs" in r.texto
    assert "rubro=cambio&vista=mapa" in r.texto


def test_cuanto_son_tantos_pesos_es_una_conversion(repo, sin_modelo):
    repo.cotizaciones[0]["valor"] = 11.2          # 1 USD = 11,2 Bs
    repo.cotizaciones[1]["valor"] = 7.2           # 100 ARS = 7,2 Bs
    r = asistente.responder(repo, "¿cuánto son 5.000 pesos en bolivianos?", ahora=MARTES_11)
    assert r.nivel == 0 and r.intent == "conversion"
    assert "Bs 360" in r.texto and "/cambio" in r.texto
    # Sin decir a qué: pesos → bolivianos, bolivianos → pesos, dólares → bolivianos.
    assert "$ 2.777,78 pesos" in asistente.responder(repo, "200 bolivianos", ahora=MARTES_11).texto
    assert "Bs 1.120 bolivianos" in asistente.responder(repo, "100 dólares", ahora=MARTES_11).texto
    # "10 mil pesos" también.
    assert "Bs 720" in asistente.responder(repo, "10 mil pesos a bolivianos", ahora=MARTES_11).texto
    # Sin cotización cargada, lo dice y no inventa.
    repo.cotizaciones[1]["valor"] = 0
    r2 = asistente.responder(repo, "cuánto son 1000 pesos en bolivianos", ahora=MARTES_11)
    assert r2.sin_respuesta and "No tengo cargada" in r2.texto


def test_donde_cambio_dolares_es_un_lugar_no_un_numero(repo, sin_modelo):
    repo.cotizaciones[0]["valor"] = 11.2
    repo.comercios["cc1"] = {"id": "cc1", "slug": "cambios-frontera", "nombre": "Cambios Frontera", "activo": True,
                             "rubro_slug": "cambio", "direccion": "Av. del Puente 10", "horario": "Lun-Sáb 8:00-20:00"}
    repo.comercios["cc2"] = {"id": "cc2", "slug": "cambio-central", "nombre": "Cambio Central", "activo": True,
                             "rubro_slug": "cambio", "direccion": "Plaza principal", "horario": "Lun-Vie 9:00-12:00"}
    r = asistente.responder(repo, "¿Dónde cambio dólares?", ahora=MARTES_13)
    assert r.intent == "casas_de_cambio" and r.nivel == 0
    # Las dos casas, la abierta primero, el mapa, y la cotización al final.
    assert r.texto.index("Cambios Frontera") < r.texto.index("Cambio Central")
    assert "1 abiertas ahora" in r.texto and "rubro=cambio&vista=mapa" in r.texto and "Hoy: Dólar 11,2 Bs" in r.texto
    assert [f["nombre"] for f in r.fuentes] == ["Cambios Frontera", "Cambio Central"]
    # Las que no tienen dirección se nombran igual (la ubicación la tiene el
    # mapa); se cuentan todas y se muestran las primeras cinco.
    for i in range(6):
        repo.comercios[f"cx{i}"] = {"id": f"cx{i}", "slug": f"casa-de-cambio-{i}", "nombre": "Casa de Cambio", "activo": True, "rubro_slug": "cambio"}
    r3 = asistente.responder(repo, "¿dónde cambio pesos?", ahora=MARTES_13)
    assert "Hay 8 casas de cambio" in r3.texto and "Ver las 8 en el mapa" in r3.texto and len(r3.fuentes) == 5
    # Sin casas cargadas, lo dice y queda anotado.
    repo.comercios.clear()
    r2 = asistente.responder(repo, "casa de cambio", ahora=MARTES_11)
    assert r2.intent == "casas_de_cambio" and r2.sin_respuesta


def test_las_preguntas_sobre_uruku_tienen_respuesta_fija(repo, sin_modelo):
    r = asistente.responder(repo, "¿cómo publico mi negocio?", ahora=MARTES_11)
    assert r.nivel == 0 and r.intent == "faq_registrar" and "/autoregistro" in r.texto
    r = asistente.responder(repo, "¿cobran comisión?", ahora=MARTES_11)
    assert r.intent == "faq_comision"


def test_el_saber_local_se_encuentra_por_etiquetas(repo, sin_modelo):
    repo.upsert_saber_local({"pregunta": "¿Cómo cruzo a Argentina?", "respuesta": "Por el puente o en chalana.",
                             "etiquetas": ["argentina", "cruzar", "chalana"]})
    r = asistente.responder(repo, "quiero cruzar a argentina, cómo hago?", ahora=MARTES_11)
    assert r.nivel == 0 and r.intent == "saber_local" and "chalana" in r.texto


def test_el_saber_local_no_se_dispara_con_una_sola_palabra_suelta(repo, sin_modelo):
    repo.upsert_saber_local({"pregunta": "¿Dónde cambio dólares?", "respuesta": "En las casas de cambio.",
                             "etiquetas": ["dolar", "cambio"]})
    # "cambio de aceite" comparte "cambio" pero no es eso; sin modelo va al 3.
    r = asistente.responder(repo, "cambio de aceite para moto", ahora=MARTES_11)
    assert r.intent != "saber_local"


# ------------------------------------------------------------------ Nivel 1 y 3

def test_sin_modelo_lo_que_el_nivel_0_no_sabe_queda_anotado(repo, sin_modelo):
    r = asistente.responder(repo, "¿cuál es la historia del puente de Bermejo?", ahora=MARTES_11)
    assert r.nivel == 3 and r.sin_respuesta


def test_con_modelo_contesta_con_los_datos_de_la_base(repo, monkeypatch):
    _zapateria(repo)
    monkeypatch.setattr(settings, "gemini_api_key", "x")
    prompts = []

    def _gemini(prompt):
        prompts.append(prompt)
        return '{"respuesta": "Zapatería Luz, en el Mercado central, vende zapatillas.", "seguro": true, "sugerencias": ["Horario de Zapatería Luz"]}'
    monkeypatch.setattr(asistente, "_gemini", _gemini)
    r = asistente.responder(repo, "¿qué zapatillas me recomendás para caminar mucho?", ahora=MARTES_11)
    assert r.nivel == 1 and "Zapatería Luz" in r.texto and not r.sin_respuesta
    assert r.sugerencias == ["Horario de Zapatería Luz"]
    # El prompt lleva los datos y la regla, no el catálogo entero.
    assert "Zapatería Luz" in prompts[0] and "seguro" in prompts[0]


def test_si_el_modelo_dice_que_no_esta_seguro_se_anota_como_nivel_3(repo, monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "x")
    monkeypatch.setattr(asistente, "_gemini", lambda p: '{"respuesta": "No tengo ese dato.", "seguro": false, "sugerencias": []}')
    r = asistente.responder(repo, "¿a qué hora pasa el colectivo a Tarija?", ahora=MARTES_11)
    assert r.nivel == 3 and r.sin_respuesta and "No tengo ese dato" in r.texto


def test_si_el_modelo_falla_no_explota(repo, monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "x")
    monkeypatch.setattr(asistente, "_gemini", lambda p: None)
    r = asistente.responder(repo, "¿a qué hora pasa el colectivo a Tarija?", ahora=MARTES_11)
    assert r.nivel == 3 and r.sin_respuesta


# ------------------------------------------------------------------ el asistente de un comercio

def test_el_asistente_del_comercio_contesta_con_lo_suyo(repo, sin_modelo):
    c = _rustico(repo)
    repo.publicaciones.append({"id": "p1", "comercio_id": c["id"], "titulo": "Pizza grande", "precio": 45,
                               "moneda": "Bs", "estado": "aprobado", "tipo": "oferta", "activo": True})
    h = asistente.responder(repo, "están abiertos?", comercio=c, ahora=MARTES_11)
    assert h.nivel == 0 and "abierto" in h.texto.lower()
    o = asistente.responder(repo, "¿tienen alguna promo?", comercio=c, ahora=MARTES_11)
    assert o.nivel == 0 and "Pizza grande" in o.texto and "45" in o.texto


def test_lo_que_el_comercio_no_tiene_cargado_va_al_dueno(repo, sin_modelo):
    c = _rustico(repo)
    r = asistente.responder(repo, "¿hacen envíos a Aguas Blancas?", comercio=c, ahora=MARTES_11)
    assert r.nivel == 3 and r.sin_respuesta and "wa.me/59170000001" in r.texto


# ------------------------------------------------------------------ endpoints

def _pregunta(client, texto, sesion="sesion-abc", comercio_id=None):
    return client.post("/asistente/preguntar", json={"pregunta": texto, "sesion": sesion, "comercio_id": comercio_id})


def test_cada_pregunta_queda_en_la_base_con_su_nivel(client, repo, sin_modelo):
    _rustico(repo)
    r = _pregunta(client, "horario de rustico")
    assert r.status_code == 200, r.text
    assert r.json()["nivel"] == 0
    assert len(repo.conversaciones) == 1
    fila = repo.conversaciones[0]
    assert fila["pregunta"] == "horario de rustico" and fila["canal"] == "sitio" and fila["comercio_id"] is None


def test_el_pulgar_se_guarda(client, repo, sin_modelo):
    r = _pregunta(client, "hola")
    cid = r.json()["id"]
    assert client.post(f"/asistente/{cid}/util", json={"util": False}).status_code == 200
    assert repo.conversaciones[0]["util"] is False


def test_hay_un_tope_de_preguntas_por_sesion_y_dia(client, repo, sin_modelo, monkeypatch):
    monkeypatch.setattr(settings, "asistente_max_por_sesion_dia", 2)
    assert _pregunta(client, "hola").status_code == 200
    assert _pregunta(client, "hola").status_code == 200
    assert _pregunta(client, "hola").status_code == 429
    assert _pregunta(client, "hola", sesion="otra-sesion").status_code == 200


def test_apagado_contesta_503_y_no_gasta(client, repo, monkeypatch, sin_modelo):
    monkeypatch.setattr(settings, "asistente_activo", False)
    assert _pregunta(client, "hola").status_code == 503
    assert repo.conversaciones == []


def test_el_asistente_del_comercio_es_del_plan_empleado_digital(client, repo, sin_modelo):
    c = _rustico(repo, plan="gratis")
    assert _pregunta(client, "están abiertos?", comercio_id=c["id"]).status_code == 403
    c["plan"] = "empleado_ia"
    r = _pregunta(client, "están abiertos?", comercio_id=c["id"])
    assert r.status_code == 200 and repo.conversaciones[0]["canal"] == "ficha"
    assert _pregunta(client, "hola", comercio_id="no-existe").status_code == 404


def test_lo_sin_respuesta_se_contesta_en_el_admin_y_pasa_a_saber_local(client, repo, admin_token, sin_modelo):
    h = {"Authorization": f"Bearer {admin_token}"}
    _pregunta(client, "¿qué días hay feria en Bermejo?")
    pend = client.get("/admin/asistente/conversaciones", headers=h).json()["items"]
    assert len(pend) == 1 and pend[0]["sin_respuesta"]
    r = client.post(f"/admin/asistente/conversaciones/{pend[0]['id']}/responder", headers=h,
                    json={"respuesta": "La feria es los jueves y domingos en la avenida.", "etiquetas": ["feria", "Jueves"]})
    assert r.status_code == 200 and r.json()["saber"]["etiquetas"] == ["feria", "jueves"]
    # Ya no está pendiente, y la próxima vez la contesta el Nivel 0.
    assert client.get("/admin/asistente/conversaciones", headers=h).json()["items"] == []
    r2 = _pregunta(client, "¿qué días hay feria?").json()
    assert r2["nivel"] == 0 and "jueves" in r2["texto"]


def test_el_saber_local_se_edita_y_se_borra(client, repo, admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    r = client.post("/admin/asistente/saber", headers=h,
                    json={"pregunta": "¿Dónde está la terminal?", "respuesta": "En la avenida Petrolera.", "etiquetas": ["terminal", "buses"]})
    sid = r.json()["item"]["id"]
    r = client.post("/admin/asistente/saber", headers=h,
                    json={"id": sid, "pregunta": "¿Dónde está la terminal?", "respuesta": "Av. Petrolera, frente a la plaza.", "etiquetas": ["terminal"]})
    assert r.json()["item"]["respuesta"].startswith("Av. Petrolera")
    assert len(client.get("/admin/asistente/saber", headers=h).json()["items"]) == 1
    assert client.delete(f"/admin/asistente/saber/{sid}", headers=h).status_code == 200
    assert client.get("/admin/asistente/saber", headers=h).json()["items"] == []
    assert client.get("/admin/asistente/saber").status_code in (401, 403)


def test_el_dueno_ve_las_preguntas_de_sus_clientes(client, repo, sin_modelo):
    from tests.conftest import comercio_token
    c = _rustico(repo, plan="empleado_ia")
    _pregunta(client, "¿hacen envíos?", comercio_id=c["id"])
    r = client.get("/comercio/asistente/preguntas", headers={"Authorization": f"Bearer {comercio_token(c['id'])}"})
    assert r.status_code == 200 and r.json()["sin_respuesta"] == 1
    assert r.json()["items"][0]["pregunta"] == "¿hacen envíos?"
