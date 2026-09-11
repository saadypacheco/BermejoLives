"""Que se sepa cuando la sesión de WhatsApp está caída.

Estuvo caída tres días sin que nadie lo supiera: el sitio andaba, el panel
andaba, y no entraba una sola oferta. Lo que se prueba acá es que eso ya no
pueda pasar en silencio.
"""
import httpx
import pytest

from app.core.config import settings
from app.services import wa_sesion


def _h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def waha(monkeypatch):
    """WAHA de mentira: contesta lo que le digan los tests."""
    monkeypatch.setattr(settings, "waha_base_url", "http://waha:3000")
    monkeypatch.setattr(settings, "waha_api_key", "k")
    estado = {"respuesta": None, "status_code": 200, "explota": False}

    class _R:
        def __init__(self):
            self.status_code = estado["status_code"]

        def json(self):
            return estado["respuesta"]

        def raise_for_status(self):
            if self.status_code >= 400:
                raise httpx.HTTPStatusError("x", request=None, response=None)

    def _get(url, **kw):
        if estado["explota"]:
            raise httpx.ConnectError("sin red")
        return _R()

    monkeypatch.setattr(httpx, "get", _get)
    return estado


def test_working_es_ok(waha):
    waha["respuesta"] = {"name": "default", "status": "WORKING",
                         "me": {"id": "59164610187@c.us", "pushName": "URUKU"}}
    e = wa_sesion.estado()
    assert e["ok"] is True
    assert e["numero"] == "59164610187"
    assert e["nombre"] == "URUKU"


def test_cualquier_otro_estado_no_es_ok(waha):
    """FAILED, STARTING, SCAN_QR_CODE… todos significan lo mismo para las
    ofertas: no entra ninguna."""
    for st in ("FAILED", "STARTING", "SCAN_QR_CODE", "STOPPED"):
        waha["respuesta"] = {"status": st, "me": {"id": "59164610187@c.us"}}
        assert wa_sesion.estado()["ok"] is False, st


def test_waha_caido_tambien_es_un_estado(waha):
    """Que WAHA no conteste es peor que una sesión caída, y tiene que verse
    distinto: uno se arregla en la tablet, el otro en el servidor."""
    waha["explota"] = True
    e = wa_sesion.estado()
    assert e["ok"] is False
    assert e["alcanzable"] is False
    assert e["estado"] == "WAHA_NO_RESPONDE"


def test_sesion_borrada(waha):
    waha["status_code"] = 404
    assert wa_sesion.estado()["estado"] == "NO_EXISTE"


def test_sin_configurar_no_lanza(monkeypatch):
    monkeypatch.setattr(settings, "waha_base_url", "")
    e = wa_sesion.estado()
    assert e["ok"] is False and e["estado"] == "SIN_CONFIGURAR"


def test_vigilar_grita_cuando_no_esta_working(waha, monkeypatch):
    """`error`, no `warning`: es lo único que, sin romper nada más, hace que se
    pierdan ofertas."""
    gritos = []
    monkeypatch.setattr(wa_sesion.logger, "error", lambda *a, **k: gritos.append(k))
    waha["respuesta"] = {"status": "FAILED", "me": {}}
    wa_sesion.vigilar()
    assert gritos and gritos[0]["estado"] == "FAILED"


def test_vigilar_calla_cuando_esta_bien(waha, monkeypatch):
    gritos = []
    monkeypatch.setattr(wa_sesion.logger, "error", lambda *a, **k: gritos.append(k))
    waha["respuesta"] = {"status": "WORKING", "me": {"id": "1@c.us"}}
    wa_sesion.vigilar()
    assert gritos == []


def test_el_panel_muestra_la_sesion(client, admin_token, waha):
    """Es lo primero que tiene que ver quien abra la pestaña."""
    waha["respuesta"] = {"status": "FAILED", "me": {"id": "59164610187@c.us"}}
    r = client.get("/admin/whatsapp/entrantes", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["sesion"]["ok"] is False
    assert r.json()["sesion"]["estado"] == "FAILED"


# ═════════════════════════════════════════ el Plan B, verificable desde acá

def test_cloud_sin_configurar(monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_cloud_phone_id", "")
    monkeypatch.setattr(settings, "whatsapp_cloud_token", "")
    e = wa_sesion.estado_cloud()
    assert e["configurado"] is False and e["ok"] is False


def test_cloud_token_valido(waha, monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_cloud_phone_id", "111")
    monkeypatch.setattr(settings, "whatsapp_cloud_token", "tok")
    waha["respuesta"] = {"display_phone_number": "+591 67991916",
                         "verified_name": "URUKU", "quality_rating": "GREEN"}
    e = wa_sesion.estado_cloud()
    assert e["ok"] is True
    assert e["nombre"] == "URUKU" and e["calidad"] == "GREEN"


def test_cloud_token_vencido_tiene_nombre_propio(waha, monkeypatch):
    """Es el caso más común y se arregla rehaciendo el token, no mirando la
    red: tiene que verse distinto de "Meta no responde"."""
    monkeypatch.setattr(settings, "whatsapp_cloud_phone_id", "111")
    monkeypatch.setattr(settings, "whatsapp_cloud_token", "tok")
    waha["status_code"] = 400
    waha["respuesta"] = {"error": {"code": 190, "message": "token expired"}}
    assert wa_sesion.estado_cloud()["estado"] == "TOKEN_INVALIDO"


def test_cloud_activo_refleja_el_interruptor(monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_provider", "cloud_api")
    assert wa_sesion.estado_cloud()["activo"] is True
    monkeypatch.setattr(settings, "whatsapp_provider", "waha")
    assert wa_sesion.estado_cloud()["activo"] is False


def test_la_bandeja_dice_por_donde_entro_el_ultimo(client, repo, admin_token, waha, monkeypatch):
    """La única prueba de que el Plan B RECIBE: un mensaje al número de Meta
    que aparece como "cloud", con hora."""
    waha["respuesta"] = {"status": "WORKING", "me": {"id": "1@c.us"}}
    repo.insert_wa_inbox({"wa_message_id": "w1", "wa_jid": "1@c.us", "raw": {},
                          "via": "cloud", "created_at": "2026-09-11T12:00:00Z"})
    r = client.get("/admin/whatsapp/entrantes", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["cloud"]["ultimo_entrante"] == "2026-09-11T12:00:00Z"


def test_un_mensaje_de_meta_queda_marcado_como_cloud(client, repo, monkeypatch):
    import hashlib, hmac, json

    monkeypatch.setattr(settings, "meta_app_secret", "s")
    evento = {"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {
        "messages": [{"from": "59170000001", "id": "wamid.x", "timestamp": "1",
                      "type": "text", "text": {"body": "hola"}}]}}]}]}
    cuerpo = json.dumps(evento).encode()
    firma = "sha256=" + hmac.new(b"s", cuerpo, hashlib.sha256).hexdigest()
    client.post("/ingest/webhook", content=cuerpo,
                headers={"Content-Type": "application/json", "X-Hub-Signature-256": firma})
    fila = next(f for f in repo.wa_inbox.values() if f["wa_message_id"] == "wamid.x")
    assert fila["via"] == "cloud"


def test_la_prueba_de_salida_solo_a_numeros_propios(client, admin_token, monkeypatch):
    """Una prueba que le llega a un comerciante es un mensaje raro de un
    número que no conoce."""
    monkeypatch.setattr(settings, "wa_numeros_propios", "59175314737")
    from app.core import config as cfg
    cfg._numeros_propios.cache_clear()
    r = client.post("/admin/whatsapp/cloud/prueba", json={"numero": "59170000009"},
                    headers=_h(admin_token))
    assert r.status_code == 400
    assert "URUKU" in r.json()["detail"]


def test_la_prueba_de_salida_va_por_meta_aunque_el_interruptor_este_en_waha(
    client, admin_token, monkeypatch,
):
    """Es una prueba, no un cambio de proveedor. Y no pasa por la llave de
    sólo lectura, que es sobre WAHA."""
    from app.services import mensajeria

    monkeypatch.setattr(settings, "wa_numeros_propios", "59175314737")
    from app.core import config as cfg
    cfg._numeros_propios.cache_clear()
    monkeypatch.setattr(settings, "whatsapp_provider", "waha")
    monkeypatch.setattr(settings, "wa_solo_lectura", True)
    enviados = []
    monkeypatch.setattr(mensajeria, "_cloud_texto", lambda a, t: enviados.append(a) or True)

    r = client.post("/admin/whatsapp/cloud/prueba", json={"numero": "59175314737"},
                    headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert enviados == ["59175314737"]
