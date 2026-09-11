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
