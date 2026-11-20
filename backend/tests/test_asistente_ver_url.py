"""Dax, tarjetas del panel: cada fuente de comercio lleva `foto` (miniatura de la portada, o la portada, o null) y la
respuesta lleva `ver_url` (relativa, con la ciudad) para el botón «Ver comercios ›». Los dos son opcionales y no
suman datos que `fuentes` no tuviera (nada de teléfonos ni código)."""
from datetime import datetime

import pytest

from app.core.config import settings
from app.services import asistente

MARTES_11 = datetime(2026, 9, 15, 11, 0)


@pytest.fixture(autouse=True)
def sin_modelo(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")


def _zapateria(repo, **extra):
    repo.comercios["com-zap"] = {
        "id": "com-zap", "slug": "zapateria-luz", "nombre": "Zapatería Luz", "activo": True, "subcategoria": "calzado",
        "direccion": "Mercado central", "whatsapp": "59170000001", "plan": "gratis", "codigo": "URUKU-1234",
        "prod_obs_human": "zapatillas, botas", **extra}


# ------------------------------------------------------------------ foto
def test_la_fuente_lleva_la_miniatura_si_la_hay():
    f = asistente._fuente({"nombre": "A", "slug": "a", "portada_thumb_url": "https://x/t.webp", "portada_url": "https://x/p.jpg"})
    assert f["foto"] == "https://x/t.webp"


def test_sin_miniatura_cae_a_la_portada_y_sin_ninguna_es_null():
    assert asistente._fuente({"nombre": "A", "slug": "a", "portada_url": "https://x/p.jpg"})["foto"] == "https://x/p.jpg"
    assert asistente._fuente({"nombre": "A", "slug": "a"})["foto"] is None
    assert asistente._fuente({"nombre": "A", "slug": "a", "portada_thumb_url": "", "portada_url": ""})["foto"] is None


def test_la_fuente_no_expone_telefono_ni_codigo():
    f = asistente._fuente({"nombre": "A", "slug": "a", "whatsapp": "59170000001", "telefono": "4111", "codigo": "URUKU-1234",
                           "portada_thumb_url": "https://x/t.webp"})
    assert set(f) == {"tipo", "nombre", "url", "detalle", "foto"}


def test_la_respuesta_trae_la_foto_del_comercio(repo):
    _zapateria(repo, portada_thumb_url="https://x/zap-t.webp")
    r = asistente.responder(repo, "¿Dónde consigo zapatillas?", ahora=MARTES_11)
    assert r.intent == "buscar" and r.fuentes[0]["foto"] == "https://x/zap-t.webp"
    assert "59170000001" not in str(r.fuentes) and "URUKU-1234" not in str(r.fuentes)


def test_comercio_sin_portada_foto_null(repo):
    _zapateria(repo)
    r = asistente.responder(repo, "¿Dónde consigo zapatillas?", ahora=MARTES_11)
    assert r.fuentes and r.fuentes[0]["foto"] is None


# ------------------------------------------------------------------ ver_url
def test_ver_url_por_palabras_con_la_ciudad(repo):
    _zapateria(repo)
    tarija = {"slug": "tarija", "nombre": "Tarija", "guia_activa": False}
    repo.comercios["com-zap"]["ciudad_slug"] = "tarija"
    r = asistente.responder(repo, "¿Dónde consigo zapatillas?", ahora=MARTES_11, ciudad=tarija)
    assert r.intent == "buscar" and r.ver_url.startswith("/buscar?q=") and "zapatillas" in r.ver_url
    assert r.ver_url.endswith("&ciudad=tarija")


def test_ver_url_sin_ciudad_no_lleva_ciudad(repo):
    _zapateria(repo)
    r = asistente.responder(repo, "¿Dónde consigo zapatillas?", ahora=MARTES_11)
    assert r.ver_url.startswith("/buscar?q=") and "ciudad=" not in r.ver_url


def test_ver_url_por_rubro_va_al_mapa(repo):
    repo.comercios["b1"] = {"id": "b1", "slug": "bano-publico-mercado", "nombre": "Baño público", "activo": True,
                            "rubro_slug": "banos", "direccion": "Mercado central", "ciudad_slug": "tarija"}
    r = asistente.responder(repo, "¿dónde hay un baño?", ahora=MARTES_11, ciudad={"slug": "tarija", "nombre": "Tarija"})
    assert r.intent == "buscar" and r.ver_url == "/buscar?rubro=banos&vista=mapa&ciudad=tarija"


def test_ver_url_en_casas_de_cambio_y_farmacia_de_turno(repo):
    repo.comercios["cc"] = {"id": "cc", "slug": "cambio-uno", "nombre": "Cambio Uno", "activo": True, "rubro_slug": "cambio"}
    r = asistente.responder(repo, "¿dónde cambio dólares?", ahora=MARTES_11)
    assert r.intent == "casas_de_cambio" and r.ver_url == "/buscar?rubro=cambio&vista=mapa"
    repo.comercios["fa"] = {"id": "fa", "slug": "farmacia-uno", "nombre": "Farmacia Uno", "activo": True, "rubro_slug": "farmacia"}
    r2 = asistente.responder(repo, "¿qué farmacia está de turno?", ahora=MARTES_11)
    assert r2.intent == "farmacia_turno" and r2.ver_url == "/buscar?rubro=farmacia&vista=mapa"


def test_sin_lista_de_comercios_no_hay_ver_url(repo):
    for pregunta in ("hola", "gracias", "", "¿qué es uruku?"):
        assert asistente.responder(repo, pregunta, ahora=MARTES_11).ver_url is None, pregunta
    r = asistente.responder(repo, "¿Dónde consigo zapatillas?", ahora=MARTES_11)  # sin resultados
    assert r.sin_respuesta and r.ver_url is None


def test_ver_url_escapa_lo_que_escribio_la_persona():
    assert asistente._ver_url(q="café & té") == "/buscar?q=caf%C3%A9+%26+t%C3%A9"
    assert asistente._ver_url(q="   ") is None and asistente._ver_url() is None


# ------------------------------------------------------------------ API
def test_el_endpoint_devuelve_foto_y_ver_url(client, repo):
    _zapateria(repo, portada_url="https://x/zap-p.jpg")
    r = client.post("/asistente/preguntar", json={"pregunta": "¿Dónde consigo zapatillas?", "sesion": "sesion-ver-1"}).json()
    assert r["ver_url"].startswith("/buscar?q=")
    assert r["fuentes"][0]["foto"] == "https://x/zap-p.jpg"
    # Una respuesta que no es lista de comercios: ver_url null (el campo existe, compatible hacia atrás).
    r2 = client.post("/asistente/preguntar", json={"pregunta": "hola", "sesion": "sesion-ver-1"}).json()
    assert "ver_url" in r2 and r2["ver_url"] is None
