"""Capa de proveedor intercambiable para OTP por WhatsApp (WAHA / Cloud API)."""
from app.core.config import settings
from app.services.whatsapp_client import (
    CloudAPIProvider, WAHAProvider, enviar_codigo_otp, get_whatsapp_provider,
)


def test_default_provider_es_waha():
    assert isinstance(get_whatsapp_provider(), WAHAProvider)


def test_selecciona_cloud_api_por_config(monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_provider", "cloud_api")
    assert isinstance(get_whatsapp_provider(), CloudAPIProvider)


def test_provider_desconocido_cae_a_waha(monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_provider", "algo-que-no-existe")
    assert isinstance(get_whatsapp_provider(), WAHAProvider)


def test_waha_sin_configurar_devuelve_false_sin_excepcion(monkeypatch):
    monkeypatch.setattr(settings, "waha_base_url", "")
    monkeypatch.setattr(settings, "waha_api_key", "")
    assert WAHAProvider().enviar_codigo_otp("59170000000", "123456", "login") is False


def test_cloud_api_sin_configurar_devuelve_false_sin_excepcion(monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_cloud_phone_id", "")
    monkeypatch.setattr(settings, "whatsapp_cloud_token", "")
    assert CloudAPIProvider().enviar_codigo_otp("59170000000", "123456", "login") is False


def test_enviar_codigo_otp_usa_el_proveedor_configurado(monkeypatch):
    llamadas = []
    monkeypatch.setattr(settings, "whatsapp_provider", "waha")

    class _FakeProvider:
        def enviar_codigo_otp(self, telefono, codigo, contexto):
            llamadas.append((telefono, codigo, contexto))
            return True

    import app.services.whatsapp_client as mod
    monkeypatch.setitem(mod._PROVIDERS, "waha", _FakeProvider)

    assert enviar_codigo_otp("59170000000", "654321", "recuperar_comercio") is True
    assert llamadas == [("59170000000", "654321", "recuperar_comercio")]
