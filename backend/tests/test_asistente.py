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
    repo.cotizaciones[1]["valor"] = 7.2           # 1.000 ARS = 7,2 Bs
    r = asistente.responder(repo, "¿cuánto son 5.000 pesos en bolivianos?", ahora=MARTES_11)
    assert r.nivel == 0 and r.intent == "conversion"
    assert "Bs 36 " in r.texto and "/cambio" in r.texto
    # Sin decir a qué: pesos → bolivianos, bolivianos → pesos, dólares → bolivianos.
    assert "$ 27.777,78 pesos" in asistente.responder(repo, "200 bolivianos", ahora=MARTES_11).texto
    assert "Bs 1.120 bolivianos" in asistente.responder(repo, "100 dólares", ahora=MARTES_11).texto
    # "10 mil pesos" también.
    assert "Bs 72 " in asistente.responder(repo, "10 mil pesos a bolivianos", ahora=MARTES_11).texto
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
    assert "las abiertas ahora primero" in r.texto and "rubro=cambio&vista=mapa" in r.texto and "Hoy: Dólar 11,2 Bs" in r.texto
    assert [f["nombre"] for f in r.fuentes] == ["Cambios Frontera", "Cambio Central"]
    # Las que no tienen dirección se nombran igual (la ubicación la tiene el
    # mapa); se cuentan todas y se muestran las primeras cinco.
    for i in range(6):
        repo.comercios[f"cx{i}"] = {"id": f"cx{i}", "slug": f"casa-de-cambio-{i}", "nombre": "Casa de Cambio", "activo": True, "rubro_slug": "cambio"}
    r3 = asistente.responder(repo, "¿dónde cambio pesos?", ahora=MARTES_13)
    # Sin cifras para el comprador: cuántas hay lo ve el panel, no el chat.
    assert "Casas de cambio en Bermejo" in r3.texto and "Ver todas en el mapa" in r3.texto and len(r3.fuentes) == 5
    assert "8" not in r3.texto.split("\n")[0] and "Ver las 8" not in r3.texto
    # Sin casas cargadas, lo dice y queda anotado.
    repo.comercios.clear()
    r2 = asistente.responder(repo, "casa de cambio", ahora=MARTES_11)
    assert r2.intent == "casas_de_cambio" and r2.sin_respuesta


def test_las_preguntas_sobre_uruku_tienen_respuesta_fija(repo, sin_modelo):
    r = asistente.responder(repo, "¿cómo publico mi negocio?", ahora=MARTES_11)
    assert r.nivel == 0 and r.intent == "faq_registrar" and "/autoregistro" in r.texto
    r = asistente.responder(repo, "¿cobran comisión?", ahora=MARTES_11)
    assert r.intent == "faq_comision"
    # Los planes salen de la base, con el precio de hoy, no de un texto fijo.
    r = asistente.responder(repo, "¿cuánto cuestan los planes?", ahora=MARTES_11)
    assert r.intent == "faq_planes" and "Pro — Bs 400/mes" in r.texto and "/planes" in r.texto
    assert "Premium" not in r.texto


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


# ------------------------------------------------------------------ la guía

def test_como_esta_el_paso_sale_de_lo_cargado_en_contenido(repo, sin_modelo):
    repo.update_frontera_estado({"puente": "demoras", "chalanas": "suspendidas", "rio": "crecido", "nota": "Filas de dos horas por el feriado"})
    r = asistente.responder(repo, "¿cómo está el paso hoy?", ahora=MARTES_11)
    assert r.intent == "frontera_hoy" and r.nivel == 0
    assert "con demoras" in r.texto and "suspendidas" in r.texto and "crecido" in r.texto and "Filas de dos horas" in r.texto
    assert "/guia" in r.texto
    assert asistente.responder(repo, "se puede cruzar hoy?", ahora=MARTES_11).intent == "frontera_hoy"


def test_el_cambio_favorable_compara_con_los_ultimos_registros(repo, sin_modelo):
    for v in (6.4, 6.5, 6.4, 6.5):
        repo.cotizaciones_historial.append({"clave": "ars_bob", "valor": v, "registrado_en": "2026-09-10T00:00:00+00:00"})
    repo.cotizaciones_historial.append({"clave": "ars_bob", "valor": 6.9, "registrado_en": "2026-09-15T00:00:00+00:00"})
    repo.cotizaciones[1]["valor"] = 6.9
    r = asistente.responder(repo, "¿a cuánto está el peso argentino?", ahora=MARTES_11)
    assert r.intent == "cotizacion" and "favorable" in r.texto and "más bolivianos" in r.texto
    # Con menos de tres registros no se opina.
    repo.cotizaciones_historial.clear()
    repo.cotizaciones_historial.append({"clave": "ars_bob", "valor": 6.9, "registrado_en": "2026-09-15T00:00:00+00:00"})
    assert "favorable" not in asistente.responder(repo, "a cuánto está el peso argentino", ahora=MARTES_11).texto


def test_que_informacion_tenes_lista_la_guia(repo, sin_modelo):
    r = asistente.responder(repo, "¿qué información tenés para el que viene?", ahora=MARTES_11)
    assert r.intent == "guia" and "aduana" in r.texto and "/guia" in r.texto


def test_la_frontera_se_edita_desde_contenido(client, repo, sin_modelo):
    from app.core import auth as auth_mod
    tok = auth_mod.make_publicador_token("publicador@x.com")
    r = client.put("/contenido/frontera", json={"chalanas": "suspendidas", "nota": "río crecido"}, headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200 and r.json()["frontera"]["chalanas"] == "suspendidas"
    assert client.put("/contenido/frontera", json={"puente": "volando"}, headers={"Authorization": f"Bearer {tok}"}).status_code == 400
    assert client.put("/contenido/frontera", json={"puente": "cerrado"}).status_code in (401, 403)
    assert client.get("/contenido/frontera").json()["nota"] == "río crecido"


def test_donde_hay_un_bano_es_el_rubro_no_el_texto(repo, sin_modelo):
    """"baño" por texto trae la casa de sanitarios; el servicio se contesta con
    su rubro, que es lo mismo que abre el chip del home."""
    repo.comercios["san"] = {"id": "san", "slug": "sanitarios-lopez", "nombre": "Sanitarios López", "activo": True,
                             "rubro_slug": "ferreteria", "subcategoria": "artículos de baño"}
    repo.comercios["b1"] = {"id": "b1", "slug": "bano-publico-mercado", "nombre": "Baño público", "activo": True,
                            "rubro_slug": "banos", "direccion": "Mercado central"}
    r = asistente.responder(repo, "¿dónde hay un baño?", ahora=MARTES_11)
    assert r.nivel == 0 and r.intent == "buscar" and not r.sin_respuesta
    assert "Baños públicos en Bermejo" in r.texto and "Mercado central" in r.texto
    assert "Sanitarios López" not in r.texto and "rubro=banos&vista=mapa" in r.texto
    # Sin nada cargado, lo dice y queda anotado.
    r2 = asistente.responder(repo, "busco un cajero automático", ahora=MARTES_11)
    assert r2.sin_respuesta and "cajeros y bancos" in r2.texto


def test_una_pregunta_que_es_un_rubro_se_contesta_con_el_rubro(repo, sin_modelo):
    """"¿Dónde como?" no nombra ningún local ni dice "busco": es el rubro
    restaurantes. Y "wifi" sin nada cargado no pisa la nota de los chips."""
    repo.comercios["r1"] = {"id": "r1", "slug": "comedor-dona-rosa", "nombre": "Comedor Doña Rosa", "activo": True,
                            "rubro_slug": "restaurantes", "subcategoria": "comedor"}
    r = asistente.responder(repo, "¿dónde como?", ahora=MARTES_11)
    assert r.nivel == 0 and r.intent == "buscar" and "Comedor Doña Rosa" in r.texto and "rubro=restaurantes" in r.texto
    repo.saber_local["s-chip"] = {"id": "s-chip", "pregunta": "¿Qué chip compro?", "respuesta": "Entel o Tigo, en cualquier kiosco.",
                                  "etiquetas": ["chip", "wifi", "internet"], "activo": True}
    r2 = asistente.responder(repo, "¿hay wifi gratis?", ahora=MARTES_11)
    assert r2.intent == "saber_local" and "Entel" in r2.texto
    # Con un wifi cargado, gana el rubro.
    repo.comercios["w1"] = {"id": "w1", "slug": "zona-wifi-plaza", "nombre": "Zona wifi plaza", "activo": True, "rubro_slug": "wifi"}
    r3 = asistente.responder(repo, "¿hay wifi gratis?", ahora=MARTES_11)
    assert r3.intent == "buscar" and "Zona wifi plaza" in r3.texto


def test_la_policia_y_el_alquiler_son_rubros_que_se_ubican(repo, sin_modelo):
    repo.comercios["pol"] = {"id": "pol", "slug": "policia-bermejo", "nombre": "Policía Boliviana · Bermejo", "activo": True,
                             "rubro_slug": "emergencias", "direccion": "Av. Barrientos", "subcategoria": "otro"}
    r = asistente.responder(repo, "¿dónde está la policía?", ahora=MARTES_11)
    # Con una sola comisaría cargada la encuentra por el nombre (dirección y
    # cómo llegar); con varias, o preguntando "comisaría", va por el rubro.
    assert r.intent in ("buscar", "direccion") and "Policía Boliviana" in r.texto and "Barrientos" in r.texto
    r1 = asistente.responder(repo, "busco una comisaría", ahora=MARTES_11)
    assert r1.intent == "buscar" and "rubro=emergencias" in r1.texto and "otro" not in r1.texto
    repo.comercios["alq"] = {"id": "alq", "slug": "dpto-centro", "nombre": "Departamento centro", "activo": True,
                             "rubro_slug": "alquiler", "subcategoria": "departamento"}
    r2 = asistente.responder(repo, "busco un departamento en alquiler", ahora=MARTES_11)
    assert r2.intent == "buscar" and "Departamento centro" in r2.texto and "rubro=alquiler" in r2.texto


def test_las_chalanas_con_restricciones_y_su_horario(repo, sin_modelo, client, admin_token):
    """«limitadas» es el estado del medio, y el horario cargado sale en la
    respuesta; suspendidas, sin horario, porque no cruzan."""
    h = {"Authorization": f"Bearer {admin_token}"}
    r = client.put("/contenido/frontera", headers=h, json={"chalanas": "limitadas", "chalanas_horario": " 7:00 a 12:00 "})
    assert r.status_code == 200 and r.json()["frontera"]["chalanas_horario"] == "7:00 a 12:00"
    t = asistente.responder(repo, "¿cómo está el paso hoy?", ahora=MARTES_11).texto
    assert "cruzan con restricciones (7:00 a 12:00)" in t
    client.put("/contenido/frontera", headers=h, json={"chalanas": "suspendidas"})
    t2 = asistente.responder(repo, "¿cómo está el paso hoy?", ahora=MARTES_11).texto
    assert "suspendidas" in t2 and "7:00" not in t2
    assert client.put("/contenido/frontera", headers=h, json={"chalanas": "medio"}).status_code == 400


def test_en_otra_ciudad_no_hay_frontera_ni_saber_de_bermejo(client, repo, sin_modelo):
    """Yacuiba no es frontera (en el fake): el paso, la aduana y las chalanas
    no se contestan; la búsqueda se acota a la ciudad y los textos la nombran."""
    repo.comercios["f1"] = {"id": "f1", "slug": "farmacia-yacuiba", "nombre": "Farmacia Yacuiba", "activo": True,
                            "rubro_slug": "farmacia", "ciudad_slug": "yacuiba"}
    repo.comercios["f2"] = {"id": "f2", "slug": "farmacia-bermejo", "nombre": "Farmacia Bermejo", "activo": True,
                            "rubro_slug": "farmacia", "ciudad_slug": "bermejo"}
    repo.saber_local["s1"] = {"id": "s1", "pregunta": "¿Cómo está el paso?", "respuesta": "Por el puente, 24 h.",
                              "etiquetas": ["paso", "puente", "frontera"], "activo": True, "seccion": "frontera"}
    yac = {"slug": "yacuiba", "nombre": "Yacuiba"}
    r = client.post("/asistente/preguntar", json={"pregunta": "¿dónde hay una farmacia?", "sesion": "sesion-yac-1", "ciudad": "yacuiba"}).json()
    assert "Farmacia Yacuiba" in r["texto"] and "Farmacia Bermejo" not in r["texto"] and "en Yacuiba" in r["texto"]
    r2 = asistente.responder(repo, "¿cómo está el paso hoy?", ahora=MARTES_11, ciudad=yac)
    assert r2.intent != "frontera_hoy" and r2.intent != "saber_local"
    r3 = asistente.responder(repo, "¿qué es uruku?", ahora=MARTES_11, ciudad=yac)
    assert "Yacuiba" in r3.texto and "Bermejo" not in r3.texto
    # Sin ciudad, todo como siempre: Bermejo y su frontera.
    r4 = asistente.responder(repo, "¿cómo está el paso hoy?", ahora=MARTES_11)
    assert r4.intent == "frontera_hoy"
