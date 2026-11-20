"""Las sugerencias iniciales de Dax por ciudad (docs/home-ciudades.md §8): las de frontera para las ciudades con
guía y las de la franja horaria (hora de Bolivia) para las demás, sin paso, aduana ni pesos."""
from datetime import datetime, timezone

import pytest

from app.services import asistente

FRONTERA = asistente.SUGERENCIAS_INICIALES
PROHIBIDAS = ("paso", "aduana", "peso", "dólar", "dolar", "frontera", "cambio")

TABLA = {
    "desayuno": ["¿Dónde desayuno?", "Farmacia abierta cerca", "¿Qué visito hoy?"],
    "almuerzo": ["¿Dónde almuerzo?", "Busco zapatillas", "Cajero cerca"],
    "tarde": ["Busco zapatillas", "Necesito un servicio técnico", "¿Qué hago hoy?"],
    "noche": ["Boliches abiertos esta noche", "¿Dónde ceno?", "Hotel para esta noche"],
    "madrugada": ["Farmacia de turno", "Cajero cerca", "¿Dónde duermo?"],
}


@pytest.mark.parametrize("hora,franja", [
    (6, "desayuno"), (8, "desayuno"), (10, "desayuno"),
    (11, "almuerzo"), (14, "almuerzo"),
    (15, "tarde"), (18, "tarde"),
    (19, "noche"), (23, "noche"),
    (0, "madrugada"), (3, "madrugada"), (5, "madrugada"),
])
def test_cada_hora_cae_en_su_franja_y_los_limites_son_cerrado_abierto(hora, franja):
    assert asistente.sugerencias_iniciales(False, hora) == TABLA[franja]


def test_las_cinco_franjas_cubren_las_24_horas_y_son_distintas():
    vistas = {tuple(asistente.sugerencias_iniciales(False, h)) for h in range(24)}
    assert vistas == {tuple(v) for v in TABLA.values()}


def test_con_guia_siempre_las_de_frontera_a_cualquier_hora():
    for h in range(24):
        assert asistente.sugerencias_iniciales(True, h) == FRONTERA


def test_sin_guia_nunca_ofrece_paso_aduana_ni_pesos():
    for h in range(24):
        for sug in asistente.sugerencias_iniciales(False, h):
            assert not any(p in sug.lower() for p in PROHIBIDAS), sug


def test_devuelve_una_lista_nueva():
    a = asistente.sugerencias_iniciales(True, 10)
    a.append("x")
    assert "x" not in asistente.SUGERENCIAS_INICIALES
    b = asistente.sugerencias_iniciales(False, 10)
    b.append("x")
    assert "x" not in asistente.sugerencias_iniciales(False, 10)


# ------------------------------------------------------------------ en las respuestas genéricas
@pytest.fixture
def sin_modelo(monkeypatch):
    monkeypatch.setattr(asistente.settings, "gemini_api_key", "")


GENERICAS = ["hola", "gracias", "", "kjh asdf qwerty zzz"]


@pytest.mark.parametrize("pregunta", GENERICAS)
def test_ciudad_sin_guia_recibe_las_de_la_franja(repo, sin_modelo, pregunta):
    tarija = {"slug": "tarija", "nombre": "Tarija", "guia_activa": False}
    r = asistente.responder(repo, pregunta, ahora=datetime(2026, 9, 15, 20, 0), ciudad=tarija)
    assert r.sugerencias == TABLA["noche"], (pregunta, r.intent)
    r = asistente.responder(repo, pregunta, ahora=datetime(2026, 9, 15, 7, 0), ciudad=tarija)
    assert r.sugerencias == TABLA["desayuno"]


@pytest.mark.parametrize("pregunta", GENERICAS)
def test_ciudad_con_guia_y_sin_ciudad_siguen_con_las_de_frontera(repo, sin_modelo, pregunta):
    villa = {"slug": "villazon", "nombre": "Villazón", "guia_activa": True}
    assert asistente.responder(repo, pregunta, ahora=datetime(2026, 9, 15, 20, 0), ciudad=villa).sugerencias == FRONTERA
    assert asistente.responder(repo, pregunta, ahora=datetime(2026, 9, 15, 20, 0)).sugerencias == FRONTERA


def test_la_guia_de_frontera_sigue_con_las_de_frontera(repo, sin_modelo):
    r = asistente.responder(repo, "¿qué información tenés?", ahora=datetime(2026, 9, 15, 20, 0))
    assert r.intent == "guia" and r.sugerencias == FRONTERA


def test_hora_con_zona_se_pasa_a_hora_de_bolivia(repo, sin_modelo):
    tarija = {"slug": "tarija", "nombre": "Tarija", "guia_activa": False}
    # 02:00 UTC = 22:00 en Bolivia (UTC-4): noche
    r = asistente.responder(repo, "hola", ahora=datetime(2026, 9, 16, 2, 0, tzinfo=timezone.utc), ciudad=tarija)
    assert r.sugerencias == TABLA["noche"]
