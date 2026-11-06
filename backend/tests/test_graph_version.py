"""Graph API: la versión es de configuración (GRAPH_API_VERSION), no está escrita a mano en el código.

La v20.0 se removió el 24/9/2026; el default es la v26.0 (changelog oficial de Meta). Ninguna URL de Graph puede
quedar escrita a mano: todas salen de `settings.graph_base()`.
"""
from __future__ import annotations

import re
from pathlib import Path

import httpx
import pytest

from app.core.config import Settings, settings
from app.services import difusion, mensajeria, wa_sesion
from app.services.whatsapp_client import CloudAPIProvider

APP = Path(__file__).resolve().parents[1] / "app"


class Resp:
    def __init__(self, status=200, cuerpo=None):
        self.status_code, self._c, self.text = status, cuerpo, str(cuerpo)

    def json(self):
        return self._c

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("x", request=None, response=self)


@pytest.fixture
def llamadas(monkeypatch):
    """httpx.post/get capturados: devuelve la lista de URLs pedidas."""
    urls: list[str] = []

    def _post(url, **kw):
        urls.append(url)
        return Resp(200, {"id": "ok"})

    def _get(url, **kw):
        urls.append(url)
        return Resp(200, {"url": None, "display_phone_number": "1"})

    monkeypatch.setattr(httpx, "post", _post)
    monkeypatch.setattr(httpx, "get", _get)
    monkeypatch.setattr(settings, "facebook_page_id", "111")
    monkeypatch.setattr(settings, "facebook_page_token", "tok")
    monkeypatch.setattr(settings, "instagram_user_id", "222")
    return urls


def test_el_default_es_la_v26_y_no_la_v20_vencida():
    assert Settings().graph_api_version == "v26.0"
    assert settings.graph_base() == "https://graph.facebook.com/v26.0"


def test_ninguna_url_de_graph_esta_escrita_a_mano():
    """Las URLs de Graph se arman SÓLO con `settings.graph_base()`: ni v20.0 ni ninguna versión fija en el código."""
    ofensores = []
    for f in APP.rglob("*.py"):
        for n, linea in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"graph\.facebook\.com/v?\d", linea):
                ofensores.append(f"{f.relative_to(APP)}:{n}: {linea.strip()}")
    assert not ofensores, ofensores


@pytest.mark.parametrize("malo", ["", "26.0", "v26", "v26.0/../x", "latest", "v2600.0"])
def test_una_version_invalida_no_arma_la_url(monkeypatch, malo):
    monkeypatch.setattr(settings, "graph_api_version", malo)
    with pytest.raises(ValueError):
        settings.graph_base()


def test_facebook_e_instagram_arman_las_urls_con_la_version_configurada(llamadas, monkeypatch):
    monkeypatch.setattr(settings, "graph_api_version", "v99.1")
    difusion._enviar_facebook("texto", "https://x/y.jpg")
    difusion._enviar_facebook("texto", None)
    difusion._enviar_instagram("texto", "https://x/y.jpg")
    assert llamadas == ["https://graph.facebook.com/v99.1/111/photos", "https://graph.facebook.com/v99.1/111/feed",
                        "https://graph.facebook.com/v99.1/222/media", "https://graph.facebook.com/v99.1/222/media_publish"]


def test_whatsapp_cloud_y_la_sesion_usan_la_misma_version(llamadas, monkeypatch):
    monkeypatch.setattr(settings, "graph_api_version", "v77.3")
    monkeypatch.setattr(settings, "whatsapp_cloud_phone_id", "999")
    monkeypatch.setattr(settings, "whatsapp_cloud_token", "t")
    mensajeria._cloud_texto("59170000009@c.us", "hola")
    mensajeria._cloud_imagen("59170000009@c.us", "https://x/y.jpg", "pie")
    CloudAPIProvider().enviar_codigo_otp("59170000009", "123456")
    wa_sesion.estado_cloud()
    mensajeria.descargar_media_cloud("media77")
    assert len(llamadas) == 5 and all(u.startswith("https://graph.facebook.com/v77.3/") for u in llamadas), llamadas
