"""Capa de proveedor intercambiable para OTP por WhatsApp (WAHA / Cloud API)."""
from app.core.config import settings
from app.services.whatsapp_client import (
    CloudAPIProvider, WAHAProvider, get_whatsapp_provider,
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


def test_enviar_codigo_otp_suelto_ya_no_existe():
    """El punto de entrada `enviar_codigo_otp` no lo llamaba nadie (el código
    del login viaja en la respuesta y lo confirma un mensaje ENTRANTE): se retiró
    en la limpieza de circuitos. Los proveedores quedan para la API oficial."""
    import app.services.whatsapp_client as mod
    assert not hasattr(mod, "enviar_codigo_otp")
