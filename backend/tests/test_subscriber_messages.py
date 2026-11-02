"""Las plantillas M1 a M6 y los textos de las tareas: funciones puras."""
import re

import pytest

from app.core.config import settings
from app.services import subscriber_messages as m
from app.services.content_captions import _EMOJI

CODIGO = "URUKU-K7M2"


@pytest.fixture(autouse=True)
def _sitio(monkeypatch):
    monkeypatch.setattr(settings, "sitio_url", "https://uruku.bo")


def todos(persona="Ana", firmante="Luis"):
    reporte = {"visits": 30, "whatsapp": 4, "terms": ["vidrios", "espejos"], "pieces_published": 1, "offers_approved": 2}
    pieza = {"redes": ["tiktok", "instagram"], "link_post": "https://www.tiktok.com/@u/video/1", "share_token": "T" * 22}
    comun = dict(persona_=persona, firmante_=firmante, comercio="Vidriería Pacheco", slug="vidrieria-pacheco",
                 paga_hasta="2026-11-12", reporte=reporte, pieza=pieza)
    return {k: m.mensaje_de_tarea(k, **comun) for k in
            ("welcome", "piece_delivery", "monthly_report", "photo_refresh", "renewal_before", "renewal_overdue", "week1_checkin")}


def test_las_seis_plantillas_existen_y_dicen_lo_que_dice_la_spec():
    t = todos()
    assert t["welcome"].startswith("Hola Ana, soy Luis de URUKU. Gracias por sumarte con Vidriería Pacheco.")
    assert t["welcome"].endswith("Tu ficha: https://uruku.bo/comercios/vidrieria-pacheco")
    assert "ya está el video de Vidriería Pacheco en TikTok y Instagram: https://www.tiktok.com/@u/video/1." in t["piece_delivery"]
    assert f"https://uruku.bo/pieza/{'T' * 22}" in t["piece_delivery"] and t["piece_delivery"].endswith("lo cambiamos.")
    assert "30 personas vieron tu ficha y 4 te escribieron por WhatsApp desde ahí." in t["monthly_report"]
    assert "«vidrios» y «espejos»" in t["monthly_report"] and "Tu plan se renueva el 12/11." in t["monthly_report"]
    assert t["photo_refresh"].startswith("Ana, ¿nos mandás 3 o 4 fotos de lo nuevo")
    assert t["renewal_before"] == ("Ana, tu plan de URUKU vence mañana, 12/11. ¿Seguimos? Podés pagar con el QR de "
                                   "https://uruku.bo/pagar y mandarnos el comprobante por acá. Cualquier duda, escribime.")
    assert t["renewal_overdue"].startswith("Ana, quedó pendiente el pago de URUKU de este mes.")
    assert t["week1_checkin"].startswith("Hola Ana, ¿cómo te fue esta primera semana con URUKU?")


def test_ninguna_plantilla_lleva_emoji_precio_ni_el_codigo_del_comercio():
    for kind, texto in todos().items():
        assert not _EMOJI.search(texto), kind
        assert not re.search(r"Bs\.?\s*\d|\$\s*\d|US\$", texto), kind
        assert CODIGO not in texto and "CONFIRMAR" not in texto, kind


def test_m5_y_m6_mandan_a_la_pagina_de_pago():
    t = todos()
    assert "https://uruku.bo/pagar" in t["renewal_before"] and "https://uruku.bo/pagar" in t["renewal_overdue"]


def test_persona_y_firmante_con_su_respaldo():
    assert m.persona("Doña Ana", "Vidriería") == "Doña Ana" and m.persona(None, "Vidriería") == "Vidriería"
    assert m.persona("  ", "Vidriería") == "Vidriería" and m.persona(None, None) == "hola"
    assert m.firmante("Luis") == "Luis" and m.firmante(None) == "el equipo" and m.firmante("  ") == "el equipo"
    t = todos(persona=m.persona(None, "Vidriería Pacheco"), firmante=m.firmante(None))
    assert t["welcome"].startswith("Hola Vidriería Pacheco, soy el equipo de URUKU.")


def test_reporte_sin_movimiento_usa_la_variante_con_ceros():
    texto = m.mensaje_de_tarea("monthly_report", persona_="Ana", firmante_="Luis", comercio="Kiosco Ana", paga_hasta="2026-11-12",
                               reporte={"visits": 0, "whatsapp": 0, "terms": ["x"], "pieces_published": 1, "offers_approved": 3})
    assert texto == ("Hola Ana, este mes la ficha de Kiosco Ana todavía tuvo poco movimiento; publicamos 1 videos tuyos y 3 ofertas. "
                     "Para el mes que viene te proponemos mandar fotos de lo nuevo al grupo. ¿Lo hacemos?")


def test_reporte_sin_palabras_saca_esa_frase_y_con_una_sola_la_adapta():
    base = dict(persona_="Ana", firmante_="Luis", comercio="K", paga_hasta="2026-11-12")
    sin = m.mensaje_de_tarea("monthly_report", reporte={"visits": 5, "whatsapp": 1, "terms": []}, **base)
    assert "Te encontraron" not in sin and "5 personas vieron tu ficha" in sin
    una = m.mensaje_de_tarea("monthly_report", reporte={"visits": 5, "whatsapp": 1, "terms": ["vidrios"]}, **base)
    assert "Te encontraron buscando «vidrios»." in una


def test_entrega_sin_link_de_post_y_sin_token():
    sin_link = m.mensaje_de_tarea("piece_delivery", persona_="Ana", firmante_="L", comercio="K",
                                  pieza={"redes": ["instagram"], "link_post": None, "share_token": "T" * 22})
    assert "ya está el video de K en Instagram. Acá lo podés bajar" in sin_link
    assert m.mensaje_de_tarea("piece_delivery", persona_="Ana", firmante_="L", comercio="K", pieza=None) is None


def test_las_tareas_sin_mensaje_y_las_etiquetas():
    for kind in ("profile_check", "first_offer", "photo_session", "first_piece", "churn_call"):
        assert m.mensaje_de_tarea(kind, persona_="A", firmante_="L", comercio="K") is None
    assert set(m.ETIQUETA_TAREA) == {"welcome", "profile_check", "first_offer", "photo_session", "first_piece", "week1_checkin",
                                     "piece_delivery", "photo_refresh", "monthly_report", "renewal_before", "renewal_overdue",
                                     "churn_call"}
    assert m.PLANTILLA_POR_TAREA == {"welcome": "M1", "piece_delivery": "M2", "monthly_report": "M3", "photo_refresh": "M4",
                                     "renewal_before": "M5", "renewal_overdue": "M6"}
    assert m.NECESITAN_RESULTADO == ("week1_checkin", "churn_call") and len(m.GUION_LLAMADA) == 3
    assert not any(_EMOJI.search(x) for x in m.ETIQUETA_TAREA.values())
