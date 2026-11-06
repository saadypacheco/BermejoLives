"""Medición v2 (docs/estadisticas-v2.md §4.2 y §4.6): `/collect`, los alias endurecidos, límites, bots, deduplicación,
orígenes canónicos, enmascarado de búsquedas, volcado, retención y los resúmenes del panel y de «Mi comercio».

Criterios de aceptación que cubre este archivo: CA-2, CA-8, CA-9, CA-10, CA-14, CA-15 y CA-16, más la parte de
backend de CA-1, CA-6 y CA-13. CA-3, CA-11 y CA-12 (permisos y retención en Postgres) están en
`test_site_metrics_migration.py`; CA-4 (privacidad) en `test_site_metrics_privacy.py`.
"""
import json
import logging

import pytest
from structlog.testing import capture_logs

from app.core import auth
from app.core.config import settings
from app.services import site_metrics
from app.services.site_metrics import Medidor, VentanaFija

C1 = "00000000-0000-4000-8000-0000000000c1"
C2 = "00000000-0000-4000-8000-0000000000c2"
SES = "sesion-abcdef12"

UA_NAVEGADOR = "Mozilla/5.0 (Linux; Android 13; SM-A346M) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36"
UA_INSTAGRAM = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/21A329 Instagram 300.0.0.29.110"
UA_FACEBOOK = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36 [FB_IAB/FB4A;FBAV/440.0.0.30.113;]"
UA_TIKTOK = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36 musical_ly_32.5.0 BytedanceWebview/d8a21c6"


@pytest.fixture(autouse=True)
def _reloj_quieto(monkeypatch):
    """Los límites son de ventana fija por minuto: sin congelar el reloj, una tanda de 300 pedidos que cruza el
    minuto se parte en dos ventanas y el test se vuelve intermitente."""
    monkeypatch.setattr(site_metrics, "_reloj", lambda: 1_000_000.0)


@pytest.fixture
def cliente(client):
    """El cliente de siempre, sin volcar el buffer solo: cada test decide cuándo se vuelca."""
    client.auto_volcar = False
    return client


def _collect(client, cuerpo, ua=UA_NAVEGADOR, **cabeceras):
    texto = cuerpo if isinstance(cuerpo, (str, bytes)) else json.dumps(cuerpo)
    h = {"content-type": "text/plain;charset=UTF-8", "user-agent": ua, **cabeceras}
    return client.post("/collect", content=texto, headers=h)


def _pv(**extra):
    return {"t": "pv", "path": "/buscar", "session": SES, "device": "mobile", "standalone": False, "first": True, **extra}


def _volcar(repo):
    return site_metrics.volcar(repo)


# ═════════════════════════════════════ /collect: lo que se guarda
def test_collect_guarda_una_pagina_vista_y_contesta_204(cliente, repo):
    r = _collect(cliente, _pv(ref="Volante-Rustico", referrer="https://l.facebook.com/l.php?u=1", city="Bermejo"))
    assert r.status_code == 204 and r.content == b""
    assert site_metrics.medidor.pendientes() == 1 and repo.visitas == []           # va al buffer, no a la base
    assert _volcar(repo) == {"visitas": 1}
    v = repo.visitas[0]
    assert v["ruta"] == "/buscar" and v["sesion"] == SES and v["device"] == "mobile" and v["standalone"] is False
    assert v["primera"] is True and v["origen"] == "volante-rustico" and v["referido"] == "l.facebook.com"
    assert v["ciudad_slug"] == "bermejo" and v["dia"]


def test_la_ruta_se_guarda_sin_query_ni_hash(cliente, repo):
    _collect(cliente, _pv(path="/buscar?q=zapatillas&x=1#arriba"))
    _volcar(repo)
    assert repo.visitas[0]["ruta"] == "/buscar"


def test_el_referido_del_propio_sitio_no_cuenta_como_referido(cliente, repo, monkeypatch):
    monkeypatch.setattr(settings, "frontend_url", "https://uruku.bo")
    _collect(cliente, _pv(referrer="https://www.uruku.bo/buscar"))
    _volcar(repo)
    assert repo.visitas[0]["referido"] is None


def test_device_desconocido_se_guarda_sin_device(cliente, repo):
    _collect(cliente, _pv(device="smart-fridge"))
    _volcar(repo)
    assert repo.visitas[0]["device"] is None


def test_un_evento_del_catalogo_va_a_site_events(cliente, repo):
    uid = "6f1e0a52-8c3a-4a2f-9a55-0d6f3c5b7a10"
    for ev, det in [("share", "native"), ("pwa_install", "ios_hint"), ("video_play", uid),
                    ("video_network_click", "tiktok"), ("uruku_whatsapp_click", "canal")]:
        assert _collect(cliente, {"t": "ev", "path": "/", "session": SES, "event": ev, "detail": det}).status_code == 204
    _volcar(repo)
    assert [(e["event"], e["detail"]) for e in repo.site_events] == [
        ("share", "native"), ("pwa_install", "ios_hint"), ("video_play", uid),
        ("video_network_click", "tiktok"), ("uruku_whatsapp_click", "canal")]
    assert repo.visitas == []


@pytest.mark.parametrize("cuerpo", [
    {"t": "ev", "path": "/", "session": SES, "event": "inventado", "detail": "x"},
    {"t": "ev", "path": "/", "session": SES, "event": "share", "detail": "carrier-pigeon"},
    {"t": "ev", "path": "/", "session": SES, "event": "share"},                            # sin detail
    {"t": "ev", "path": "/", "session": SES, "event": "video_play", "detail": "no-es-uuid"},
    {"t": "ev", "path": "/", "session": SES, "event": "video_network_click", "detail": "myspace"},
    {"t": "otro", "path": "/", "session": SES},
    {"t": "pv", "path": "sin-barra", "session": SES},
    {"t": "pv", "path": "/", "session": "corta"},                                           # sesión mal formada
    {"t": "pv", "path": "/", "session": "con espacios y símbolos!!"},
    {"t": "pv", "path": "/", "session": SES * 5},
    {"t": "pv", "session": SES},
    ["no", "es", "un", "objeto"],
])
def test_lo_que_esta_fuera_del_catalogo_se_descarta_con_204(cliente, repo, cuerpo):
    assert _collect(cliente, cuerpo).status_code == 204
    _volcar(repo)
    assert repo.visitas == [] and repo.site_events == []


def test_un_cuerpo_que_no_es_json_contesta_204_y_no_guarda(cliente, repo):
    assert _collect(cliente, "esto no es json {").status_code == 204
    assert _collect(cliente, b"\xff\xfe\x00").status_code == 204
    _volcar(repo)
    assert repo.visitas == []


@pytest.mark.parametrize("ruta", ["/admin", "/admin/visitas", "/contenido/x", "/publicar", "/campo", "/mi-comercio",
                                  "/mi-comercio/perfil", "/api/health", "/ADMIN"])
def test_las_rutas_internas_no_se_miden(cliente, repo, ruta):
    assert _collect(cliente, _pv(path=ruta)).status_code == 204
    _volcar(repo)
    assert repo.visitas == []


# ═════════════════════════════════════ CA-8: bots
@pytest.mark.parametrize("ua", [
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
    "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/120.0.0.0 Safari/537.36",
    "curl/8.4.0", "curl", "", "   ", "Mozilla/5.0 (X11; Linux x86_64) Chrome-Lighthouse",
    "python-requests/2.31.0", "Pingdom.com_bot_version_1.4",
])
def test_CA8_los_bots_dan_204_y_no_guardan_nada(cliente, repo, ua):
    assert _collect(cliente, _pv(), ua=ua).status_code == 204
    assert cliente.post("/visita", json={"ruta": "/", "sesion": SES}, headers={"user-agent": ua}).json()["contada"] is False
    assert site_metrics.medidor.pendientes() == 0
    _volcar(repo)
    assert repo.visitas == []


@pytest.mark.parametrize("ua", [UA_NAVEGADOR, UA_INSTAGRAM, UA_FACEBOOK, UA_TIKTOK])
def test_CA8_los_navegadores_dentro_de_las_apps_si_se_cuentan(cliente, repo, ua):
    assert _collect(cliente, _pv(), ua=ua).status_code == 204
    _volcar(repo)
    assert len(repo.visitas) == 1


def test_un_bot_no_guarda_contactos_ni_busquedas(cliente, repo):
    h = {"user-agent": "Googlebot/2.1"}
    assert cliente.post("/lead", json={"comercio_id": C1, "tipo": "whatsapp"}, headers=h).json() == {"ok": True, "id": None}
    assert cliente.post("/busquedas/log", json={"query": "pan", "resultados": 1}, headers=h).json() == {"ok": True}
    assert repo.leads == [] and repo.busquedas == []


# ═════════════════════════════════════ Origin y Sec-Fetch-Site
def test_un_pedido_de_otro_sitio_se_descarta(cliente, repo, monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "frontend_url", "https://uruku.bo")
    for cab in ({"origin": "https://evil.example"}, {"origin": "null"}, {"sec-fetch-site": "cross-site"},
                {"origin": "https://uruku.bo", "sec-fetch-site": "cross-site"}):
        assert _collect(cliente, _pv(), **cab).status_code == 204
    _volcar(repo)
    assert repo.visitas == []
    for cab in ({"origin": "https://uruku.bo"}, {"origin": "https://www.uruku.bo"}, {}, {"sec-fetch-site": "same-site"}):
        assert _collect(cliente, _pv(), **cab).status_code == 204
    _volcar(repo)
    assert len(repo.visitas) == 4


def test_los_alias_tambien_miran_el_origin(cliente, repo, monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "frontend_url", "https://uruku.bo")
    h = {"origin": "https://evil.example", "user-agent": UA_NAVEGADOR}
    assert cliente.post("/lead", json={"comercio_id": C1, "tipo": "whatsapp"}, headers=h).json() == {"ok": True, "id": None}
    assert cliente.post("/visita", json={"ruta": "/", "sesion": SES}, headers=h).json()["contada"] is False
    assert cliente.post("/busquedas/log", json={"query": "pan"}, headers=h).json() == {"ok": True}
    _volcar(repo)
    assert repo.leads == [] and repo.visitas == [] and repo.busquedas == []


# ═════════════════════════════════════ CA-9: límites, tamaño, nunca 500
def test_CA9_el_pedido_301_de_una_ip_a_collect_da_429(cliente):
    estados = [_collect(cliente, _pv()).status_code for _ in range(301)]
    assert estados[:300] == [204] * 300 and estados[300] == 429


def test_CA9_el_pedido_121_a_lead_da_429(cliente, repo):
    estados = [cliente.post("/lead", json={"comercio_id": C1, "tipo": "vista", "sesion": f"sesion-{i:06d}"}).status_code
               for i in range(121)]
    assert estados[:120] == [200] * 120 and estados[120] == 429


def test_el_pedido_61_a_busquedas_log_da_429(cliente):
    estados = [cliente.post("/busquedas/log", json={"query": f"pan {i}"}).status_code for i in range(61)]
    assert estados[:60] == [200] * 60 and estados[60] == 429


def test_cada_ip_tiene_su_propio_limite(cliente):
    h1, h2 = {"x-forwarded-for": "1.1.1.1"}, {"x-forwarded-for": "2.2.2.2"}
    for _ in range(300):
        _collect(cliente, _pv(), **h1)
    assert _collect(cliente, _pv(), **h1).status_code == 429
    assert _collect(cliente, _pv(), **h2).status_code == 204


def test_las_ipv6_de_un_mismo_64_comparten_el_limite():
    assert site_metrics.clave_de_ip("2800:cb0:1:2::1") == site_metrics.clave_de_ip("2800:cb0:1:2:ffff::9")
    assert site_metrics.clave_de_ip("2800:cb0:1:3::1") != site_metrics.clave_de_ip("2800:cb0:1:2::1")
    assert site_metrics.clave_de_ip("::ffff:1.2.3.4") == "1.2.3.4"
    assert site_metrics.clave_de_ip("basura") == "invalid"


def test_ventana_fija_con_tope_de_claves():
    v = VentanaFija(limite=2, max_claves=2)
    assert [v.check("a", 0.0), v.check("a", 1.0), v.check("a", 2.0)] == ["ok", "ok", "limited"]
    assert v.check("b", 3.0) == "ok"
    assert v.check("c", 4.0) == "full"                   # lleno: se acepta pero no se guarda
    assert v.check("a", 61.0) == "ok"                    # ventana nueva: todo vuelve a cero


def test_CA9_un_cuerpo_de_3_kb_da_413_y_uno_de_2_kb_pasa(cliente, repo):
    grande = json.dumps(_pv(path="/" + "a" * 3000))
    assert len(grande) > 3000
    assert _collect(cliente, grande).status_code == 413
    assert _collect(cliente, json.dumps(_pv(path="/" + "a" * 150))).status_code == 204
    # chunked / sin Content-Length: igual se corta
    def trozos():
        yield b'{"t":"pv","path":"/' + b"a" * 1500
        yield b"b" * 1500 + b'","session":"sesion-abcdef12"}'
    r = cliente.post("/collect", content=trozos(), headers={"user-agent": UA_NAVEGADOR, "content-type": "text/plain"})
    assert r.status_code == 413


def test_CA9_nunca_500_con_la_base_caida(cliente, repo):
    repo.insert_site_rows_falla = True
    assert _collect(cliente, _pv()).status_code == 204
    with capture_logs() as logs:
        guardadas = _volcar(repo)
    assert guardadas == {"visitas": 0}
    assert any(l["event"] == "site_metrics_flush_failed" and l["tabla"] == "visitas" for l in logs)
    assert site_metrics.medidor.pendientes() == 0        # el lote se descartó: sin reintento infinito


def test_CA9_un_contacto_con_la_base_caida_da_ok_false_no_500(cliente, repo, monkeypatch):
    def falla(_fila):
        raise RuntimeError("db caída")
    monkeypatch.setattr(repo, "insert_lead", falla)
    r = cliente.post("/lead", json={"comercio_id": C1, "tipo": "whatsapp", "sesion": SES})
    assert r.status_code == 200 and r.json() == {"ok": False}


def test_una_falla_inesperada_en_collect_igual_da_204(cliente, monkeypatch):
    def rompe(_raw):
        raise RuntimeError("bug")
    monkeypatch.setattr(site_metrics, "procesar_collect", rompe)
    with capture_logs() as logs:
        assert _collect(cliente, _pv()).status_code == 204
    assert any(l["event"] == "collect_failed" for l in logs)


# ═════════════════════════════════════ CA-10: orígenes canónicos
@pytest.mark.parametrize("referido, esperado", [
    ("android-app://com.whatsapp/", ("whatsapp", "whatsapp")),
    ("com.whatsapp", ("whatsapp", "whatsapp")),
    ("l.facebook.com", ("social", "facebook")),
    ("m.facebook.com", ("social", "facebook")),
    ("lm.facebook.com", ("social", "facebook")),
    ("android-app://com.facebook.lite/", ("social", "facebook")),
    ("com.facebook.lite", ("social", "facebook")),
    ("google.com.bo", ("search", "google")),
    ("google.com.ar", ("search", "google")),
    ("www.google.com", ("search", "google")),
    ("com.zhiliaoapp.musically", ("social", "tiktok")),
    ("vm.tiktok.com", ("social", "tiktok")),
    ("l.instagram.com", ("social", "instagram")),
    ("bing.com", ("search", "bing")),
    ("wa.me", ("whatsapp", "whatsapp")),
    ("un-blog.example.com", ("other", "un-blog.example.com")),
    (None, ("direct", "")),
    ("", ("direct", "")),
])
def test_CA10_los_referidos_se_canonicalizan(referido, esperado):
    assert site_metrics.clasificar_llegada(None, referido) == esperado


def test_CA10_chatgpt_es_ia_y_el_origen_manda_sobre_el_referido():
    assert site_metrics.clasificar_llegada(None, "chatgpt.com") == ("ai", "chatgpt")
    assert site_metrics.clasificar_llegada("chatgpt.com", "google.com") == ("ai", "chatgpt")
    assert site_metrics.clasificar_llegada("perplexity.ai", None) == ("ai", "perplexity")


def test_el_ref_de_un_qr_se_distingue_segun_el_panel_o_mi_comercio():
    assert site_metrics.clasificar_llegada("volante-rustico", None) == ("other", "qr_volante")
    assert site_metrics.clasificar_llegada("volante-rustico", None, qr_aparte=True) == ("qr", "volante")
    assert site_metrics.clasificar_llegada("mesa-sol", "google.com", qr_aparte=True) == ("search", "google")
    assert site_metrics.clasificar_llegada("fb", None) == ("social", "facebook")
    assert site_metrics.clasificar_llegada("ig-bio", None) == ("social", "instagram")


# ═════════════════════════════════════ CA-14: /visita (cliente viejo)
def test_CA14_un_cliente_viejo_que_manda_visita_con_json_sigue_contando(cliente, repo):
    r = cliente.post("/visita", json={"ruta": "/ofertas", "sesion": "sesion-vieja1", "origen": "VOLANTE-x",
                                      "referido": "google.com", "ciudad": "bermejo", "primera": True})
    assert r.status_code == 200 and r.json() == {"ok": True, "contada": True}
    _volcar(repo)
    v = repo.visitas[0]
    assert v["ruta"] == "/ofertas" and v["origen"] == "volante-x" and v["referido"] == "google.com"
    assert v["ciudad_slug"] == "bermejo" and v["primera"] is True and v["standalone"] is False and v["device"] is None


def test_visita_vieja_con_ruta_interna_no_cuenta(cliente, repo):
    r = cliente.post("/visita", json={"ruta": "/mi-comercio", "sesion": SES})
    assert r.json() == {"ok": True, "contada": False}
    _volcar(repo)
    assert repo.visitas == []


def test_visita_vieja_respeta_el_limite_de_collect(cliente):
    for _ in range(300):
        cliente.post("/visita", json={"ruta": "/", "sesion": SES})
    assert cliente.post("/visita", json={"ruta": "/", "sesion": SES}).status_code == 429
    assert _collect(cliente, _pv()).status_code == 429          # comparten el mismo contador


# ═════════════════════════════════════ CA-15: /lead blindado
@pytest.mark.parametrize("cuerpo", [
    {"comercio_id": C1, "tipo": "cualquiera"},
    {"comercio_id": C1, "tipo": "<b>x</b>"},
    {"comercio_id": C1, "tipo": ""},
    {"comercio_id": "no-es-uuid", "tipo": "whatsapp"},
    {"comercio_id": "1; drop table leads", "tipo": "whatsapp"},
    {"comercio_id": C1, "tipo": "red"},                                   # red sin detalle
    {"comercio_id": C1, "tipo": "red", "detalle": "myspace"},
    {"comercio_id": C1, "tipo": "compartir", "detalle": "paloma"},
    {"comercio_id": C1, "tipo": "compartir"},
])
def test_CA15_lo_que_no_es_valido_no_se_guarda_ni_se_convierte_en_whatsapp(cliente, repo, cuerpo):
    r = cliente.post("/lead", json=cuerpo)
    assert r.status_code == 200 and r.json() == {"ok": False}
    _volcar(repo)
    assert repo.leads == []


def test_lead_devuelve_id_y_token_de_siempre(cliente, repo):
    r = cliente.post("/lead", json={"comercio_id": C1, "tipo": "whatsapp", "sesion": SES, "origen": "Mesa-Sol",
                                    "busqueda_id": "no-es-uuid"}).json()
    assert r["ok"] is True and r["id"] and r["token"]
    assert repo.leads[0]["origen"] == "mesa-sol" and repo.leads[0]["sesion"] == SES
    assert "busqueda_id" not in repo.leads[0]                              # un id inválido se descarta sin perder el contacto
    sin_sesion = cliente.post("/lead", json={"comercio_id": C2, "tipo": "telefono"}).json()
    assert sin_sesion["id"] and sin_sesion["token"]


def test_compartir_y_red_van_al_buffer_con_su_detalle(cliente, repo):
    for cuerpo in ({"comercio_id": C1, "tipo": "compartir", "detalle": "native", "sesion": SES},
                   {"comercio_id": C1, "tipo": "red", "detalle": "Instagram", "sesion": SES},
                   {"comercio_id": C1, "tipo": "red", "detalle": "facebook", "sesion": SES}):
        assert cliente.post("/lead", json=cuerpo).json() == {"ok": True, "id": None}
    assert repo.leads == []
    _volcar(repo)
    assert [(l["tipo"], l["detalle"]) for l in repo.leads] == [("compartir", "native"), ("red", "instagram"), ("red", "facebook")]


def test_la_vista_va_al_buffer_y_el_contacto_se_inserta_en_el_momento(cliente, repo):
    assert cliente.post("/lead", json={"comercio_id": C1, "tipo": "vista", "sesion": SES}).json() == {"ok": True, "id": None}
    assert cliente.post("/lead", json={"comercio_id": C1, "tipo": "whatsapp", "sesion": SES}).json()["id"]
    assert [l["tipo"] for l in repo.leads] == ["whatsapp"]
    _volcar(repo)
    assert sorted(l["tipo"] for l in repo.leads) == ["vista", "whatsapp"]


# ═════════════════════════════════════ CA-2: deduplicación
def test_CA2_un_f5_en_la_ficha_dentro_de_30_minutos_no_suma_vista(cliente, repo):
    for _ in range(3):
        cliente.post("/lead", json={"comercio_id": C1, "tipo": "vista", "sesion": SES})
    cliente.post("/lead", json={"comercio_id": C2, "tipo": "vista", "sesion": SES})          # otra ficha: sí
    cliente.post("/lead", json={"comercio_id": C1, "tipo": "vista", "sesion": "sesion-otra01"})  # otra sesión: sí
    _volcar(repo)
    assert sorted((l["comercio_id"], l["sesion"]) for l in repo.leads) == sorted(
        [(C1, SES), (C2, SES), (C1, "sesion-otra01")])


def test_CA2_la_vista_vuelve_a_contar_a_los_30_minutos():
    m = Medidor()
    assert m.vista_repetida("s", "c", ahora=0.0) is False
    assert m.vista_repetida("s", "c", ahora=1799.0) is True
    assert m.vista_repetida("s", "c", ahora=1801.0) is False


def test_CA2_dos_toques_a_whatsapp_el_mismo_dia_suman_un_contacto_con_el_mismo_id(cliente, repo):
    a = cliente.post("/lead", json={"comercio_id": C1, "tipo": "whatsapp", "sesion": SES}).json()
    b = cliente.post("/lead", json={"comercio_id": C1, "tipo": "whatsapp", "sesion": SES}).json()
    assert b["id"] == a["id"] and b["repetido"] is True and b["token"] == a["token"] and "repetido" not in a
    assert len(repo.leads) == 1
    # otro tipo o otro comercio en la misma sesión: contactos distintos
    c = cliente.post("/lead", json={"comercio_id": C1, "tipo": "telefono", "sesion": SES}).json()
    d = cliente.post("/lead", json={"comercio_id": C2, "tipo": "whatsapp", "sesion": SES}).json()
    assert len({a["id"], c["id"], d["id"]}) == 3 and len(repo.leads) == 3


def test_CA2_el_te_contesto_se_pregunta_una_sola_vez(cliente, repo):
    from datetime import datetime, timedelta, timezone
    repo.seed_comercio(id=C1, slug="uno", nombre="Uno", whatsapp="591700001")
    a = cliente.post("/lead", json={"comercio_id": C1, "tipo": "whatsapp", "sesion": SES}).json()
    b = cliente.post("/lead", json={"comercio_id": C1, "tipo": "whatsapp", "sesion": SES}).json()
    assert a["id"] == b["id"] and len(repo.leads) == 1
    repo.leads[0]["created_at"] = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()   # pasaron los 2 minutos
    # el token del segundo toque es el del primero: sirve para votar sobre ese único contacto, una sola vez
    voto = {"respondio": False, "sesion": SES}
    assert cliente.post(f"/lead/{b['id']}/respondio", json={**voto, "token": b["token"]}).json()["contacto_no"] == 1
    assert cliente.post(f"/lead/{a['id']}/respondio", json={**voto, "token": a["token"]}).json() == {"ok": True, "ya": True}


def test_el_contacto_sin_sesion_no_se_deduplica_pero_el_techo_de_la_ip_si_corta(cliente, repo):
    ids = [cliente.post("/lead", json={"comercio_id": C1, "tipo": "whatsapp"}).json()["id"] for _ in range(12)]
    assert sum(1 for i in ids if i) == 10                                       # 10 de cada contacto por comercio y por día
    assert len(repo.leads) == 10
    # otro tipo de contacto y otro comercio tienen su propio techo
    assert cliente.post("/lead", json={"comercio_id": C1, "tipo": "telefono"}).json()["id"]
    assert cliente.post("/lead", json={"comercio_id": C2, "tipo": "whatsapp"}).json()["id"]


def test_el_techo_de_vistas_por_ip_y_comercio_es_30(cliente, repo):
    for i in range(35):
        cliente.post("/lead", json={"comercio_id": C1, "tipo": "vista", "sesion": f"sesion-{i:06d}"})
    _volcar(repo)
    assert len(repo.leads) == 30


def test_los_topes_en_memoria_se_llenan_sin_romper(monkeypatch):
    monkeypatch.setattr(site_metrics, "MAX_DEDUP", 3)
    m = Medidor()
    for i in range(10):
        m.vista_repetida(f"s{i}", "c", ahora=0.0)
    assert len(m._vistas) <= 3
    assert m.vista_repetida("nueva", "c", ahora=0.0) is False                    # lleno: se cuenta de más, no de menos


def test_la_sal_del_dia_cambia_y_la_ip_no_se_guarda():
    from datetime import date
    m = Medidor()
    assert m.pasa_techo(date(2026, 11, 6), "203.0.113.9", "c", "vista", 1) is True
    sal = m._sal
    assert m.pasa_techo(date(2026, 11, 6), "203.0.113.9", "c", "vista", 1) is False
    assert not any("203.0.113.9" in str(k) for k in m._techos)
    assert m.pasa_techo(date(2026, 11, 7), "203.0.113.9", "c", "vista", 1) is True   # día nuevo: contadores en cero
    assert m._sal != sal


# ═════════════════════════════════════ CA-16: búsquedas
def test_CA16_una_busqueda_con_un_telefono_queda_enmascarada(cliente, repo):
    r = cliente.post("/busquedas/log", json={"query": "71234567 zapatos", "resultados": 2})
    assert r.json()["busqueda_id"]
    assert repo.busquedas[-1]["query"] == "# zapatos"


@pytest.mark.parametrize("crudo, esperado", [
    ("71234567 zapatos", "# zapatos"),
    ("zapatos 5917 1234567", "zapatos 5917 #"),
    ("escribime a juan.perez@gmail.com por favor", "escribime a [mail] por favor"),
    ("talle 38", "talle 38"),
    ("12345", "12345"),
    ("123456", "#"),
    ("  mucho    espacio  ", "mucho espacio"),
    ("a" * 150, "a" * 100),
])
def test_enmascarar_busqueda(crudo, esperado):
    assert site_metrics.enmascarar_busqueda(crudo) == esperado


def test_una_busqueda_que_es_solo_un_telefono_no_se_guarda(cliente, repo):
    assert cliente.post("/busquedas/log", json={"query": "71234567"}).json() == {"ok": True}
    assert cliente.post("/busquedas/log", json={"query": "a@b.co"}).json() == {"ok": True}
    assert repo.busquedas == []


def test_la_busqueda_descarta_comercios_que_no_son_uuid(cliente, repo):
    r = cliente.post("/busquedas/log", json={"query": "pan", "resultados": 2, "comercios": [C1, "no-es-uuid", C2]})
    assert r.json()["busqueda_id"]
    assert [bc["comercio_id"] for bc in repo.busqueda_comercios] == [C1, C2]


def test_la_base_caida_no_rompe_el_buscador(cliente, repo, monkeypatch):
    def falla(*_a, **_k):
        raise RuntimeError("db")
    monkeypatch.setattr(repo, "insert_busqueda", falla)
    r = cliente.post("/busquedas/log", json={"query": "pan"})
    assert r.status_code == 200 and r.json() == {"ok": True}


# ═════════════════════════════════════ /lead/{id}/respondio: límite propio
def test_el_te_contesto_se_limita_a_30_por_minuto_por_ip(cliente):
    estados = [cliente.post("/lead/no-existe/respondio", json={"respondio": True}).status_code for _ in range(31)]
    assert estados[:30] == [404] * 30 and estados[30] == 429


# ═════════════════════════════════════ GET /public/measurement-config
def test_la_config_publica_de_medicion(client):
    r = client.get("/public/measurement-config")
    assert r.status_code == 200
    assert r.json() == {"internal": True, "umami": None}
    assert r.headers["cache-control"] == "public, max-age=300"


# ═════════════════════════════════════ POST /csp-report
def test_csp_report_loguea_la_directiva_y_el_host_sin_ip(cliente):
    cuerpo = {"csp-report": {"document-uri": "https://uruku.bo/buscar?q=secreto", "violated-directive": "script-src-elem",
                             "effective-directive": "script-src-elem", "blocked-uri": "https://cdn.ajeno.example/x.js?token=1",
                             "disposition": "report"}}
    with capture_logs() as logs:
        r = cliente.post("/csp-report", content=json.dumps(cuerpo), headers={"content-type": "application/csp-report",
                                                                              "x-forwarded-for": "198.51.100.23"})
    assert r.status_code == 204
    ev = [l for l in logs if l["event"] == "csp_violation"]
    assert len(ev) == 1 and ev[0]["directiva"] == "script-src-elem" and ev[0]["bloqueado"] == "cdn.ajeno.example"
    volcado = json.dumps(ev, default=str)
    assert "198.51.100.23" not in volcado and "secreto" not in volcado and "token" not in volcado


def test_csp_report_formato_reporting_api_y_basura(cliente):
    nuevo = [{"type": "csp-violation", "body": {"effectiveDirective": "img-src", "blockedURL": "inline"}}]
    with capture_logs() as logs:
        assert cliente.post("/csp-report", content=json.dumps(nuevo)).status_code == 204
        assert cliente.post("/csp-report", content="basura{").status_code == 204
    assert [(l["directiva"], l["bloqueado"]) for l in logs if l["event"] == "csp_violation"] == [("img-src", "inline")]


def test_csp_report_limite_413_y_apagado(cliente, monkeypatch):
    assert cliente.post("/csp-report", content="x" * 9000).status_code == 413
    estados = [cliente.post("/csp-report", content="{}").status_code for _ in range(31)]
    assert estados[-1] == 429
    site_metrics.reiniciar()
    monkeypatch.setattr(settings, "csp_report_enabled", False)
    assert [cliente.post("/csp-report", content="{}").status_code for _ in range(40)] == [204] * 40


# ═════════════════════════════════════ /admin/visitas
def _admin():
    return {"Authorization": f"Bearer {auth.make_token('admin@bermejolive.com', rol='admin')}"}


def _sembrar_panel(client, repo):
    repo.seed_comercio(id=C1, slug="rustico", nombre="Rústico", whatsapp="591700001")
    client.auto_volcar = False
    visitas = [
        ("sesion-aaaaaa", "/", {"referrer": "https://l.facebook.com/", "device": "mobile"}),
        ("sesion-aaaaaa", "/comercios/rustico", {"first": False}),
        ("sesion-bbbbbb", "/comercios/rustico", {"referrer": "android-app://com.whatsapp/", "device": "mobile", "standalone": True}),
        ("sesion-cccccc", "/", {"referrer": "https://www.google.com.bo/", "device": "desktop"}),
        ("sesion-dddddd", "/", {"ref": "volante-rustico", "device": "mobile"}),
        ("sesion-eeeeee", "/", {"referrer": "https://chatgpt.com/", "device": "tablet"}),
    ]
    for ses, ruta, extra in visitas:
        _collect(client, {**_pv(path=ruta, session=ses), **extra})
    _collect(client, {"t": "ev", "path": "/", "session": "sesion-aaaaaa", "event": "share", "detail": "copy"})
    client.post("/lead", json={"comercio_id": C1, "tipo": "whatsapp", "sesion": "sesion-aaaaaa"})
    client.post("/lead", json={"comercio_id": C1, "tipo": "vista", "sesion": "sesion-aaaaaa"})
    _volcar(repo)


def test_admin_visitas_exige_permiso_y_no_se_cachea(client, repo):
    assert client.get("/admin/visitas").status_code == 401
    r = client.get("/admin/visitas", headers=_admin())
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"


def test_admin_visitas_trae_las_claves_de_siempre_y_las_nuevas(client, repo):
    _sembrar_panel(client, repo)
    d = client.get("/admin/visitas?dias=7", headers=_admin()).json()
    for clave in ("dias", "visitas", "personas", "por_dia", "top_rutas", "top_referidos", "top_origenes", "ai_sources", "embudo",
                  "referrers", "devices", "standalone_share", "events", "funnel", "umami_url", "last_hit_at", "desde", "hasta"):
        assert clave in d, clave
    assert d["dias"] == 7 and len(d["por_dia"]) == 7 and d["umami_url"] is None
    assert d["visitas"] == 6 and d["personas"] == 5
    assert d["embudo"] == {"visitas": 6, "personas": 5, "fichas_vistas": 1, "contactos": 1, "mapa": 0}
    assert {(x["kind"], x["name"]): x["n"] for x in d["referrers"]} == {
        ("social", "facebook"): 1, ("whatsapp", "whatsapp"): 1, ("search", "google"): 1,
        ("other", "qr_volante"): 1, ("ai", "chatgpt"): 1}
    assert {x["device"]: x["n"] for x in d["devices"]} == {"mobile": 3, "desktop": 1, "tablet": 1}
    assert d["standalone_share"] == 0.2
    assert d["events"] == [{"event": "share", "detail": "copy", "n": 1}]
    assert d["funnel"] == {"sessions": 5, "sessions_with_ficha": 2, "sessions_with_contact": 1}
    assert d["last_hit_at"]
    assert [x["source"] for x in d["ai_sources"]] == ["chatgpt"]


def test_admin_visitas_filtra_por_ciudad(client, repo):
    client.auto_volcar = False
    _collect(client, _pv(city="bermejo"))
    _collect(client, _pv(session="sesion-zzzzzz", city="tarija"))
    _volcar(repo)
    assert client.get("/admin/visitas?ciudad=bermejo", headers=_admin()).json()["visitas"] == 1
    assert client.get("/admin/visitas", headers=_admin()).json()["visitas"] == 2


def test_admin_visitas_valida_los_dias(client):
    assert client.get("/admin/visitas?dias=0", headers=_admin()).status_code == 422
    assert client.get("/admin/visitas?dias=181", headers=_admin()).status_code == 422


# ═════════════════════════════════════ /comercio/metricas
def _com_headers(cid):
    from tests.conftest import comercio_token
    return {"Authorization": f"Bearer {comercio_token(comercio_id=cid)}"}


def test_metricas_del_comercio_suma_lo_nuevo_y_ya_viene_deduplicado(client, repo):
    repo.seed_comercio(id=C1, slug="rustico", nombre="Rústico", whatsapp="591700001")
    repo.seed_comercio(id=C2, slug="otro", nombre="Otro", whatsapp="591700002")
    client.auto_volcar = False
    for _ in range(3):                                                          # F5: una sola vista
        client.post("/lead", json={"comercio_id": C1, "tipo": "vista", "sesion": SES})
    for _ in range(2):                                                          # doble toque: un solo contacto
        client.post("/lead", json={"comercio_id": C1, "tipo": "whatsapp", "sesion": SES})
    client.post("/lead", json={"comercio_id": C1, "tipo": "mapa", "sesion": SES})
    client.post("/lead", json={"comercio_id": C1, "tipo": "compartir", "detalle": "copy", "sesion": SES})
    client.post("/lead", json={"comercio_id": C1, "tipo": "red", "detalle": "instagram", "sesion": SES})
    client.post("/lead", json={"comercio_id": C1, "tipo": "red", "detalle": "tiktok", "sesion": SES})
    for i in range(5):                                                          # el otro comercio: no aparece
        client.post("/lead", json={"comercio_id": C2, "tipo": "whatsapp", "sesion": f"sesion-x{i:05d}"})
    _collect(client, _pv(path="/comercios/rustico", ref="mesa-rustico", session="sesion-q00001"))
    _collect(client, _pv(path="/comercios/rustico", referrer="https://www.google.com/", session="sesion-q00002"))
    _collect(client, _pv(path="/comercios/otro", referrer="https://www.google.com/", session="sesion-q00003"))
    _volcar(repo)
    d = client.get("/comercio/metricas", headers=_com_headers(C1)).json()
    assert d["visitas_30d"] == 1 and d["visitas_7d"] == 1
    assert d["contactos_30d"] == 2 and d["contactos_7d"] == 2                  # whatsapp + mapa (compartir y red no son contactos)
    assert d["contactos_por_tipo"] == {"vista": 1, "whatsapp": 1, "mapa": 1}
    assert d["como_llegar_30d"] == 1 and d["compartidos_30d"] == 1
    assert d["redes_30d"] == {"instagram": 1, "tiktok": 1}
    assert {(o["kind"], o["name"]): o["n"] for o in d["origenes_30d"]} == {("qr", "mesa"): 1, ("search", "google"): 1}
    assert "terminos_busqueda" in d and "publicaciones_total" in d


# ═════════════════════════════════════ el buffer
def test_el_buffer_lleno_descarta_y_avisa(monkeypatch):
    monkeypatch.setattr(site_metrics, "MAX_BUFFER", 2)
    m = Medidor()
    with capture_logs() as logs:
        resultados = [m.encolar("visitas", {"n": i}) for i in range(4)]
    assert resultados == [True, True, False, False]
    assert m.pendientes() == 2 and m.descartadas == 2
    assert sum(1 for l in logs if l["event"] == "site_metrics_buffer_full") == 1      # un aviso, no uno por fila


def test_volcar_inserta_en_lote_por_tabla(cliente, repo, monkeypatch):
    monkeypatch.setattr(site_metrics, "LOTE_INSERT", 2)
    for i in range(5):
        _collect(cliente, _pv(session=f"sesion-{i:06d}"))
    _collect(cliente, {"t": "ev", "path": "/", "session": SES, "event": "share", "detail": "copy"})
    assert _volcar(repo) == {"visitas": 5, "site_events": 1}
    assert repo.lotes_volcados == [("visitas", 2), ("visitas", 2), ("visitas", 1), ("site_events", 1)]
    assert _volcar(repo) == {}                                                       # nada pendiente: no toca la base


def test_las_filas_del_buffer_llevan_siempre_las_mismas_claves(cliente):
    """PostgREST rellena con NULL lo que falta en un insert en lote: las filas tienen que ser uniformes."""
    _collect(cliente, _pv())
    _collect(cliente, _pv(ref="mesa-x", referrer="google.com", city="bermejo", session="sesion-uuuuuu"))
    cliente.post("/lead", json={"comercio_id": C1, "tipo": "vista", "sesion": SES})
    cliente.post("/lead", json={"comercio_id": C1, "tipo": "red", "detalle": "tiktok"})
    lote = site_metrics.medidor.tomar_buffer()
    assert len({tuple(sorted(f)) for f in lote["visitas"]}) == 1
    assert len({tuple(sorted(f)) for f in lote["leads"]}) == 1


# ═════════════════════════════════════ retención
def test_la_purga_pide_siempre_13_meses_o_mas(repo):
    pedidos = []
    original = repo.purge_site_metrics
    repo.purge_site_metrics = lambda m: (pedidos.append(m), original(m))[1]
    site_metrics.purgar(repo, 1)
    site_metrics.purgar(repo)
    assert pedidos == [13, 13]


def test_el_fake_de_la_purga_respeta_el_piso(repo):
    with pytest.raises(RuntimeError):
        repo.purge_site_metrics(12)
    repo.visitas.append({"id": "v1", "dia": "2020-01-01", "ruta": "/", "sesion": "s"})
    repo.visitas.append({"id": "v2", "dia": "2999-01-01", "ruta": "/", "sesion": "s"})
    assert repo.purge_site_metrics(13) == 1 and [v["id"] for v in repo.visitas] == ["v2"]


def test_las_04_de_bolivia_son_las_08_utc():
    from datetime import datetime, timezone
    # 03:00 en Bolivia (07:00 UTC) -> falta 1 hora
    assert site_metrics.segundos_hasta_purga(datetime(2026, 11, 6, 7, 0, tzinfo=timezone.utc)) == 3600
    # 04:00 justo -> mañana
    assert site_metrics.segundos_hasta_purga(datetime(2026, 11, 6, 8, 0, tzinfo=timezone.utc)) == 86400
    assert site_metrics.segundos_hasta_purga(datetime(2026, 11, 6, 20, 0, tzinfo=timezone.utc)) == 12 * 3600


def test_los_loops_estan_en_el_lifespan_y_se_apagan_con_el_flag():
    import inspect
    from app import main
    fuente = inspect.getsource(main.lifespan)
    assert "_site_metrics_flush_loop" in fuente and "_site_metrics_retention_loop" in fuente
    assert "settings.site_metrics_worker" in fuente
    assert settings.site_metrics_worker is False                                      # el conftest lo apaga en tests
    assert "site_metrics.volcar" in fuente                                            # y vuelca al apagar


# ═════════════════════════════════════ access log
def _registro(ruta):
    return logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
                             ("10.0.0.1:1234", "POST", ruta, "1.1", 204), None)


@pytest.mark.parametrize("ruta", ["/collect", "/visita", "/lead", "/lead/abc/respondio", "/busquedas/log", "/csp-report",
                                  "/collect?x=1"])
def test_el_access_log_no_registra_los_endpoints_de_medicion(ruta):
    assert site_metrics.FiltroAccessLog().filter(_registro(ruta)) is False


@pytest.mark.parametrize("ruta", ["/health", "/comercios", "/leaderboard", "/admin/visitas", "/collector"])
def test_el_access_log_sigue_registrando_lo_demas(ruta):
    assert site_metrics.FiltroAccessLog().filter(_registro(ruta)) is True


def test_el_filtro_queda_instalado_en_uvicorn_access_una_sola_vez():
    site_metrics.instalar_filtro_access_log()
    site_metrics.instalar_filtro_access_log()
    filtros = [f for f in logging.getLogger("uvicorn.access").filters if isinstance(f, site_metrics.FiltroAccessLog)]
    assert len(filtros) == 1


# ═════════════════════════════════════ el navegador ya no escribe directo y no queda `insert_visita`
def test_el_backend_no_tiene_caminos_de_insert_sueltos():
    from pathlib import Path
    fuente = (Path(__file__).resolve().parents[1] / "app").rglob("*.py")
    for ruta in fuente:
        texto = ruta.read_text(encoding="utf-8")
        assert "insert_visita" not in texto, ruta
        assert 'table("visitas").insert' not in texto.replace(" ", ""), ruta


def test_el_loop_de_volcado_vuelca_lo_pendiente_cada_5_segundos(repo, monkeypatch):
    import asyncio
    from app import main
    monkeypatch.setattr(main, "get_repo", lambda: repo)
    site_metrics.medidor.encolar("visitas", {"dia": "2026-11-06", "ruta": "/", "sesion": SES, "origen": None, "referido": None,
                                             "ciudad_slug": None, "primera": True, "device": None, "standalone": False})
    pausas = []

    async def dormir(seg):
        pausas.append(seg)
        if len(pausas) > 1:
            raise asyncio.CancelledError

    monkeypatch.setattr(main.asyncio, "sleep", dormir)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(main._site_metrics_flush_loop())
    assert pausas == [5, 5] and len(repo.visitas) == 1


def test_el_loop_de_retencion_purga_con_13_meses(repo, monkeypatch):
    import asyncio
    from app import main
    monkeypatch.setattr(main, "get_repo", lambda: repo)
    pedidos = []
    monkeypatch.setattr(repo, "purge_site_metrics", lambda m: pedidos.append(m) or 0)
    pausas = []

    async def dormir(seg):
        pausas.append(seg)
        if len(pausas) > 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(main.asyncio, "sleep", dormir)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(main._site_metrics_retention_loop())
    assert pedidos == [13] and 0 < pausas[0] <= 86400 and pausas[1] == 60


def test_el_lifespan_vuelca_lo_que_quedo_en_el_buffer_al_apagar(repo, monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    monkeypatch.setattr(settings, "site_metrics_worker", True)
    monkeypatch.setattr(main, "get_repo", lambda: repo)
    with TestClient(main.app) as c:
        assert _collect(c, _pv()).status_code == 204
        assert site_metrics.medidor.pendientes() == 1 and repo.visitas == []
    assert len(repo.visitas) == 1 and site_metrics.medidor.pendientes() == 0


# ═════════════════════════════════════ el repo de verdad, con una base de mentira
class _Resp:
    def __init__(self, data=None):
        self.data = data


class _DbDeMentira:
    def __init__(self, rpc_data=None):
        self.llamadas, self._rpc_data = [], rpc_data

    def table(self, nombre):
        db = self

        class T:
            def insert(self, filas, **kw):
                db.llamadas.append(("insert", nombre, len(filas), kw))
                return self

            def select(self, *a, **k): return self
            def order(self, *a, **k): return self
            def limit(self, *a, **k): return self

            def execute(self):
                return _Resp([{"created_at": "2026-11-06T12:00:00+00:00"}])
        return T()

    def rpc(self, nombre, params):
        self.llamadas.append(("rpc", nombre, params))
        db = self

        class R:
            def execute(self):
                return _Resp(db._rpc_data)
        return R()


def test_el_repo_real_inserta_en_lote_sin_pedir_las_filas_de_vuelta():
    from app.db.repository import SupabaseRepo
    db = _DbDeMentira()
    r = SupabaseRepo(db)
    r.insert_site_rows("visitas", [{"a": 1}, {"a": 2}])
    r.insert_site_rows("site_events", [])
    assert db.llamadas == [("insert", "visitas", 2, {"returning": "minimal"})]
    with pytest.raises(ValueError):
        r.insert_site_rows("comercios", [{"a": 1}])


def test_el_repo_real_llama_a_las_rpc_con_los_nombres_de_la_0193():
    from app.db.repository import SupabaseRepo
    db = _DbDeMentira(rpc_data={"ok": 1})
    r = SupabaseRepo(db)
    assert r.site_metrics_summary("2026-11-01", "2026-11-06", "bermejo") == {"ok": 1}
    r.site_metrics_summary("2026-11-01", "2026-11-06")
    r.comercio_origins(C1, "2026-10-07")
    r.comercio_lead_counts(C1, 30)
    db._rpc_data = 3
    assert r.purge_site_metrics(13) == 3
    assert db.llamadas == [
        ("rpc", "site_metrics_summary", {"p_from": "2026-11-01", "p_to": "2026-11-06", "p_city": "bermejo"}),
        ("rpc", "site_metrics_summary", {"p_from": "2026-11-01", "p_to": "2026-11-06", "p_city": None}),
        ("rpc", "comercio_origins", {"p_comercio": C1, "p_from": "2026-10-07"}),
        ("rpc", "comercio_lead_counts", {"p_comercio": C1, "p_days": 30}),
        ("rpc", "purge_site_metrics", {"p_months": 13}),
    ]
    assert r.last_visit_at() == "2026-11-06T12:00:00+00:00"
