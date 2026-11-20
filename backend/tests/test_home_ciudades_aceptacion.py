"""QA de aceptación de «Home de las ciudades y Dax por ciudad» (docs/home-ciudades.md §8 y §9, criterios 6, 7 y 9).

Complementa test_asistente_sugerencias.py y test_clima_ciudades.py del dev con:
  - los bordes de las franjas a nivel de minuto (5:59/6:00/10:59/11:00/14:59/15:00/18:59/19:00/23:59/0:00), con hora
    naive (ya es de Bolivia) y con hora con zona (UTC) que se pasa a Bolivia (UTC-4);
  - Bermejo, las ciudades con guía y «sin ciudad» siguen con las sugerencias de frontera a CUALQUIER hora;
  - una batería de preguntas en una ciudad sin guía: ni las sugerencias ni los textos hablan del paso, la aduana,
    las chalanas ni se ofrecen pesos;
  - el endpoint /asistente/preguntar con una ciudad sin guía y con Bermejo;
  - el clima por ciudad: alineación con coordenadas ausentes en el medio, tolerancia a respuestas raras.

El hallazgo BUG-2 del QA (pesos en la cotización de una ciudad sin frontera) ya está corregido: sus tests corren normales.
"""
from datetime import datetime, timezone

import httpx
import pytest

from app.core.config import settings
from app.services import asistente, clima

TARIJA = {"slug": "tarija", "nombre": "Tarija", "guia_activa": False}
BERMEJO = {"slug": "bermejo", "nombre": "Bermejo", "guia_activa": True}
VILLAZON = {"slug": "villazon", "nombre": "Villazón", "guia_activa": True}

TABLA = {
    "desayuno": ["¿Dónde desayuno?", "Farmacia abierta cerca", "¿Qué visito hoy?"],
    "almuerzo": ["¿Dónde almuerzo?", "Busco zapatillas", "Cajero cerca"],
    "tarde": ["Busco zapatillas", "Necesito un servicio técnico", "¿Qué hago hoy?"],
    "noche": ["Boliches abiertos esta noche", "¿Dónde ceno?", "Hotel para esta noche"],
    "madrugada": ["Farmacia de turno", "Cajero cerca", "¿Dónde duermo?"],
}
FRONTERA = asistente.SUGERENCIAS_INICIALES

# (hora, minuto, franja) en hora de Bolivia
BORDES = [
    (0, 0, "madrugada"), (5, 59, "madrugada"), (6, 0, "desayuno"), (10, 59, "desayuno"), (11, 0, "almuerzo"),
    (14, 59, "almuerzo"), (15, 0, "tarde"), (18, 59, "tarde"), (19, 0, "noche"), (23, 59, "noche"),
]


@pytest.fixture(autouse=True)
def sin_modelo(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")


# ------------------------------------------------------------------ criterio 6: franjas a nivel de minuto
@pytest.mark.parametrize("h,m,franja", BORDES)
def test_bordes_de_franja_con_hora_de_bolivia_naive(repo, h, m, franja):
    r = asistente.responder(repo, "hola", ahora=datetime(2026, 11, 20, h, m), ciudad=TARIJA)
    assert r.sugerencias == TABLA[franja], f"{h}:{m:02d}"


@pytest.mark.parametrize("h,m,franja", BORDES)
def test_bordes_de_franja_con_hora_utc_se_pasa_a_bolivia(repo, h, m, franja):
    # Bolivia = UTC-4: el instante UTC es 4 horas después (con desborde de día incluido).
    utc = datetime(2026, 11, 20, h, m, tzinfo=timezone.utc) + (datetime(2026, 11, 20, 4) - datetime(2026, 11, 20, 0))
    r = asistente.responder(repo, "hola", ahora=utc, ciudad=TARIJA)
    assert r.sugerencias == TABLA[franja], f"{h}:{m:02d} Bolivia = {utc.isoformat()}"


@pytest.mark.parametrize("pregunta", ["hola", "gracias", "", "kjh asdf qwerty zzz"])
@pytest.mark.parametrize("h", range(24))
@pytest.mark.parametrize("ciudad", [BERMEJO, VILLAZON, None], ids=["bermejo", "con-guia", "sin-ciudad"])
def test_bermejo_y_las_ciudades_con_guia_siguen_con_las_de_frontera_a_cualquier_hora(repo, pregunta, h, ciudad):
    r = asistente.responder(repo, pregunta, ahora=datetime(2026, 11, 20, h, 30), ciudad=ciudad)
    assert r.sugerencias == FRONTERA, (pregunta, h, r.intent)


def test_la_lista_de_cada_franja_coincide_con_la_tabla_de_la_spec_y_no_trae_nada_de_frontera():
    for _desde, _hasta, lista in asistente.SUGERENCIAS_POR_FRANJA:
        assert 2 <= len(lista) <= 3
    assert [x[2] for x in asistente.SUGERENCIAS_POR_FRANJA] == [TABLA["madrugada"], TABLA["desayuno"], TABLA["almuerzo"], TABLA["tarde"], TABLA["noche"]]
    # Cubren 0..23 sin huecos ni solapes.
    horas = [h for desde, hasta, _ in asistente.SUGERENCIAS_POR_FRANJA for h in range(desde, hasta)]
    assert sorted(horas) == list(range(24))


# ------------------------------------------------------------------ criterio 6: nunca paso/aduana en una ciudad sin guía
PREGUNTAS_DE_FRONTERA = [
    "¿cómo está el paso?", "¿se puede cruzar hoy?", "qué puedo pasar por la aduana", "qué documentos necesito para cruzar",
    "chalanas", "¿cuánto cuesta el pasaje en chalana?", "información para visitantes", "qué información tenés",
    "estado de la frontera", "¿hay paso hoy?", "guía", "quiero hacer un encargo", "¿tienen guardería?",
]
PREGUNTAS_GENERICAS = [
    "hola", "gracias", "", "zapatillas", "baños", "cajero", "farmacia", "farmacia de turno", "qué hay abierto ahora",
    "dónde como", "hotel", "cómo publico mi negocio", "cuánto cuesta el plan", "kjh asdf qwerty zzz", "clima", "como llego",
]
PASO_ADUANA = ("paso", "aduana", "chalana", "frontera", "puente")


def _dicen_paso_o_aduana(texto: str) -> list[str]:
    # «paso» como palabra suelta (no «pasaje» ni «compás»); el resto por prefijo. Se ignora el eco de lo que escribió la
    # persona («No encontré «paso hoy»…») y las URLs: eso no es Dax ofreciendo el paso.
    import re
    t = re.sub(r"https?://\S+", " ", re.sub(r"«[^»]*»", " ", texto.lower()))
    return [p for p in PASO_ADUANA if re.search(rf"\b{p}", t)]


@pytest.mark.parametrize("pregunta", PREGUNTAS_DE_FRONTERA + PREGUNTAS_GENERICAS)
@pytest.mark.parametrize("h", [3, 8, 13, 17, 21])
def test_ciudad_sin_guia_ni_sugerencias_ni_textos_hablan_del_paso_ni_de_la_aduana(repo, pregunta, h):
    r = asistente.responder(repo, pregunta, ahora=datetime(2026, 11, 20, h, 0), ciudad=TARIJA)
    for s in r.sugerencias:
        assert not _dicen_paso_o_aduana(s), f"sugerencia «{s}» ({r.intent})"
    assert not _dicen_paso_o_aduana(r.texto), f"texto «{r.texto[:120]}» ({r.intent})"


def _con_cotizaciones(repo):
    repo.cotizaciones[0]["valor"] = 6.96   # dólar
    repo.cotizaciones[1]["valor"] = 7.20   # 1.000 ARS


# HALLAZGO (BUG-2): en una ciudad SIN frontera, «¿a cuánto está el dólar?» contesta con el peso argentino y sugiere
# «¿Cuánto son 10.000 pesos en bolivianos?». La spec (§8, «Backend») dice: «Nunca ofrece el paso, la aduana ni los pesos
# en una ciudad sin frontera». Corregido: la rama `cotizacion` de asistente.py mira `_con_guia()`.
@pytest.mark.parametrize("pregunta", ["a cuánto está el dólar", "cotización", "¿cuánto está el peso argentino?"])
def test_ciudad_sin_frontera_nunca_ofrece_pesos_en_la_cotizacion(repo, pregunta):
    _con_cotizaciones(repo)
    r = asistente.responder(repo, pregunta, ahora=datetime(2026, 11, 20, 20, 0), ciudad=TARIJA)
    assert r.intent == "cotizacion"
    for s in r.sugerencias:
        assert "peso" not in s.lower(), s
    assert "peso" not in r.texto.lower(), r.texto


def test_ciudad_sin_frontera_el_dolar_si_se_contesta(repo):
    """El dólar vale en todas las ciudades: lo que no tiene que salir es la moneda vecina (BUG-2 de arriba)."""
    _con_cotizaciones(repo)
    r = asistente.responder(repo, "a cuánto está el dólar", ahora=datetime(2026, 11, 20, 20, 0), ciudad=TARIJA)
    assert r.intent == "cotizacion" and "Dólar 6,96" in r.texto


# ------------------------------------------------------------------ la hora de la respuesta sale de la misma `ahora` que el resto
def test_las_sugerencias_usan_la_hora_pasada_y_no_se_filtran_entre_preguntas(repo):
    a = asistente.responder(repo, "hola", ahora=datetime(2026, 11, 20, 7, 0), ciudad=TARIJA)
    b = asistente.responder(repo, "hola", ahora=datetime(2026, 11, 20, 22, 0), ciudad=TARIJA)
    c = asistente.responder(repo, "hola", ahora=datetime(2026, 11, 20, 7, 0), ciudad=BERMEJO)
    assert (a.sugerencias, b.sugerencias, c.sugerencias) == (TABLA["desayuno"], TABLA["noche"], FRONTERA)
    # Después de responder, el contexto de la hora se limpia (la siguiente pregunta sin `ahora` usa el reloj real).
    assert asistente._AHORA.get() is None


def test_las_sugerencias_devueltas_no_comparten_la_lista_global(repo):
    r = asistente.responder(repo, "hola", ahora=datetime(2026, 11, 20, 7, 0), ciudad=TARIJA)
    r.sugerencias.append("x")
    assert "x" not in asistente.responder(repo, "hola", ahora=datetime(2026, 11, 20, 7, 0), ciudad=TARIJA).sugerencias
    rb = asistente.responder(repo, "hola", ahora=datetime(2026, 11, 20, 7, 0), ciudad=BERMEJO)
    rb.sugerencias.append("y")
    assert "y" not in asistente.SUGERENCIAS_INICIALES


# ------------------------------------------------------------------ endpoint
def test_endpoint_ciudad_sin_guia_devuelve_alguna_lista_de_franja(client, repo):
    r = client.post("/asistente/preguntar", json={"pregunta": "hola", "sesion": "sesion-qa-1", "ciudad": "tarija"}).json()
    assert r["sugerencias"] in list(TABLA.values())
    assert not any(_dicen_paso_o_aduana(s) for s in r["sugerencias"])


def test_endpoint_bermejo_con_guia_sigue_con_las_de_frontera(client, repo, monkeypatch):
    monkeypatch.setattr(repo, "get_ciudad", lambda slug: {"id": "c1", "slug": slug, "nombre": slug.title(), "guia_activa": True})
    r = client.post("/asistente/preguntar", json={"pregunta": "hola", "sesion": "sesion-qa-2", "ciudad": "bermejo"}).json()
    assert r["sugerencias"] == FRONTERA


def test_endpoint_sin_ciudad_es_bermejo(client, repo):
    r = client.post("/asistente/preguntar", json={"pregunta": "hola", "sesion": "sesion-qa-3"}).json()
    assert r["sugerencias"] == FRONTERA


def test_endpoint_ciudad_inexistente_cae_a_bermejo_sin_romper(client, repo, monkeypatch):
    monkeypatch.setattr(repo, "get_ciudad", lambda slug: None)
    r = client.post("/asistente/preguntar", json={"pregunta": "hola", "sesion": "sesion-qa-4", "ciudad": "atlantida"})
    assert r.status_code == 200 and r.json()["sugerencias"] == FRONTERA


# ------------------------------------------------------------------ criterio 7: clima por ciudad (backend)
def _item(temp, code=0):
    return {"current": {"temperature_2m": temp, "weather_code": code}}


def test_clima_alineacion_con_una_ciudad_sin_coordenadas_en_el_medio():
    """Si una ciudad no tiene lat/lng se excluye ANTES de pedir: el clima de una no se le asigna a otra."""
    ciudades = [
        {"id": "a", "lat": -22.7, "lng": -64.3}, {"id": "b", "lat": None, "lng": None}, {"id": "c", "lat": -21.5, "lng": -64.7},
    ]
    pedidos = []

    class _C:
        def __init__(self, *a, **k): ...
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url, *a, **k):
            pedidos.append(url)
            return httpx.Response(200, json=[_item(30.0), _item(15.0)])

    import asyncio
    orig = clima.httpx.AsyncClient
    clima.httpx.AsyncClient = _C
    try:
        out = asyncio.run(clima.fetch_clima_ciudades(ciudades))
    finally:
        clima.httpx.AsyncClient = orig
    assert out == {"a": {"temp_c": 30.0, "descripcion": "Despejado"}, "c": {"temp_c": 15.0, "descripcion": clima._desc(0)[0]}}
    assert len(pedidos) == 1 and "latitude=-22.7000,-21.5000" in pedidos[0] and "longitude=-64.3000,-64.7000" in pedidos[0]


def test_clima_cantidad_desalineada_no_asigna_nada():
    ciudades = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    assert clima.parsear_clima_ciudades(ciudades, [_item(1.0), _item(2.0)]) == {}
    assert clima.parsear_clima_ciudades(ciudades, [_item(1.0)] * 4) == {}


@pytest.mark.parametrize("payload", [None, "x", 42, [], {}, {"error": True, "reason": "boom"}, [None, None], [[], {}], [{"current": None}]])
def test_clima_respuestas_raras_no_levantan(payload):
    ciudades = [{"id": "a"}, {"id": "b"}]
    assert clima.parsear_clima_ciudades(ciudades, payload) == {}


def test_clima_temperatura_no_numerica_se_saltea_y_cero_es_dato_valido():
    ciudades = [{"id": "a"}, {"id": "b"}, {"id": "c"}, {"id": "d"}]
    out = clima.parsear_clima_ciudades(ciudades, [_item("calor"), _item(0), _item(True), _item(-4.5)])
    assert set(out) == {"b", "d"}
    assert out["b"]["temp_c"] == 0.0 and out["d"]["temp_c"] == -4.5


def test_clima_la_descripcion_no_lleva_emoji_ni_icono():
    out = clima.parsear_clima_ciudades([{"id": "a"}], [_item(20.0, 95)])
    assert set(out["a"]) == {"temp_c", "descripcion"}
    assert not any(ord(ch) > 0x2000 for ch in out["a"]["descripcion"]), out["a"]["descripcion"]
