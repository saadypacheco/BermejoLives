"""Clima por ciudad (docs/home-ciudades.md §9): el parseo de open-meteo con varias coordenadas, el guardado y
el salteo de lo que falla (con el repo falso y sin red), el loop y la migración 0201 (estática)."""
import asyncio
import re
from pathlib import Path

import httpx
import pytest

from app import main
from app.services import clima

RAIZ = Path(__file__).resolve().parents[2]
NOMBRE = "0201_clima_ciudades.sql"

CIUDADES = [
    {"id": "ciu-1", "slug": "bermejo", "lat": -22.7361, "lng": -64.3433},
    {"id": "ciu-sc", "slug": "santa-cruz", "lat": -17.7833, "lng": -63.1821},
    {"id": "ciu-tj", "slug": "tarija", "lat": -21.5355, "lng": -64.7296},
]


def _item(temp, code):
    return {"latitude": 0, "longitude": 0, "current": {"time": "2026-11-20T10:00", "temperature_2m": temp, "weather_code": code}}


class _FakeClient:
    """Reemplaza httpx.AsyncClient: guarda la URL pedida y contesta lo que se le diga."""
    pedidos: list[str] = []
    respuesta: httpx.Response | Exception = httpx.Response(200, json=[])

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, *a, **k):
        _FakeClient.pedidos.append(url)
        if isinstance(_FakeClient.respuesta, Exception):
            raise _FakeClient.respuesta
        return _FakeClient.respuesta


@pytest.fixture
def http(monkeypatch):
    _FakeClient.pedidos = []
    _FakeClient.respuesta = httpx.Response(200, json=[])
    monkeypatch.setattr(clima.httpx, "AsyncClient", _FakeClient)
    return _FakeClient


# ------------------------------------------------------------------ parseo
def test_parseo_lista_de_varias_ciudades_en_orden():
    out = clima.parsear_clima_ciudades(CIUDADES, [_item(31.5, 0), _item(27.0, 3), _item(18.2, 61)])
    assert out == {
        "ciu-1": {"temp_c": 31.5, "descripcion": "Despejado"},
        "ciu-sc": {"temp_c": 27.0, "descripcion": "Nublado"},
        "ciu-tj": {"temp_c": 18.2, "descripcion": "Lluvia"},
    }


def test_parseo_objeto_unico_cuando_hay_una_sola_ciudad():
    out = clima.parsear_clima_ciudades(CIUDADES[:1], _item(20, 95))
    assert out == {"ciu-1": {"temp_c": 20.0, "descripcion": "Tormenta"}}


def test_la_descripcion_no_lleva_emoji():
    for code in (0, 1, 3, 45, 61, 71, 95, 999):
        d = clima.parsear_clima_ciudades(CIUDADES[:1], _item(10, code))["ciu-1"]["descripcion"]
        assert all(ord(ch) < 0x2190 for ch in d), d  # letras (con tildes) y el guion: ningún emoji


def test_parseo_saltea_la_ciudad_sin_temperatura_o_sin_current():
    payload = [_item(31.5, 0), {"latitude": 1, "longitude": 1}, _item(None, 3)]
    assert clima.parsear_clima_ciudades(CIUDADES, payload) == {"ciu-1": {"temp_c": 31.5, "descripcion": "Despejado"}}


def test_parseo_con_codigo_desconocido_o_ausente_no_rompe():
    item = {"current": {"temperature_2m": 12.0}}
    assert clima.parsear_clima_ciudades(CIUDADES[:1], item) == {"ciu-1": {"temp_c": 12.0, "descripcion": "—"}}


def test_parseo_de_respuesta_rara_devuelve_vacio():
    assert clima.parsear_clima_ciudades(CIUDADES, {"error": True, "reason": "x"}) == {}
    assert clima.parsear_clima_ciudades(CIUDADES, "basura") == {}
    assert clima.parsear_clima_ciudades(CIUDADES, None) == {}
    # cantidad que no coincide: no se adivina de quién es cada dato
    assert clima.parsear_clima_ciudades(CIUDADES, [_item(1, 0)]) == {}


# ------------------------------------------------------------------ fetch (HTTP simulado)
def test_fetch_hace_una_sola_llamada_con_todas_las_coordenadas(http):
    http.respuesta = httpx.Response(200, json=[_item(31.5, 0), _item(27.0, 3), _item(18.2, 61)])
    out = asyncio.run(clima.fetch_clima_ciudades(CIUDADES))
    assert len(http.pedidos) == 1
    url = http.pedidos[0]
    assert "api.open-meteo.com" in url
    assert "latitude=-22.7361,-17.7833,-21.5355" in url
    assert "longitude=-64.3433,-63.1821,-64.7296" in url
    assert set(out) == {"ciu-1", "ciu-sc", "ciu-tj"}


def test_fetch_ignora_ciudades_sin_coordenadas(http):
    http.respuesta = httpx.Response(200, json=[_item(31.5, 0)])
    sin = [{"id": "x", "slug": "x", "lat": None, "lng": None}] + CIUDADES[:1]
    out = asyncio.run(clima.fetch_clima_ciudades(sin))
    assert list(out) == ["ciu-1"]
    assert asyncio.run(clima.fetch_clima_ciudades([{"id": "x", "lat": None, "lng": 1}])) == {}
    assert len(http.pedidos) == 1  # la segunda no llamó a nadie


@pytest.mark.parametrize("respuesta", [
    httpx.Response(500, json={"error": True}),
    httpx.Response(200, content=b"no es json"),
    httpx.TimeoutException("timeout"),
    RuntimeError("se cayó la red"),
])
def test_fetch_nunca_levanta(http, respuesta):
    http.respuesta = respuesta
    assert asyncio.run(clima.fetch_clima_ciudades(CIUDADES)) == {}


# ------------------------------------------------------------------ guardado con el repo falso
def test_actualizar_guarda_una_fila_por_ciudad(http, repo):
    repo.ciudades_con_coordenadas = CIUDADES
    http.respuesta = httpx.Response(200, json=[_item(31.5, 0), _item(27.0, 3), _item(18.2, 61)])
    assert asyncio.run(clima.actualizar_clima_ciudades(repo)) == 3
    assert repo.clima_ciudades["ciu-tj"]["temp_c"] == 18.2
    assert repo.clima_ciudades["ciu-tj"]["descripcion"] == "Lluvia"
    assert repo.clima["temp_c"] is None  # la tabla `clima` de Bermejo no se toca acá


def test_una_ciudad_que_falla_se_saltea_y_conserva_el_dato_anterior(http, repo):
    repo.ciudades_con_coordenadas = CIUDADES
    repo.clima_ciudades["ciu-sc"] = {"ciudad_id": "ciu-sc", "temp_c": 99.0, "descripcion": "Anterior"}
    http.respuesta = httpx.Response(200, json=[_item(31.5, 0), {"current": {}}, _item(18.2, 61)])
    assert asyncio.run(clima.actualizar_clima_ciudades(repo)) == 2
    assert repo.clima_ciudades["ciu-sc"] == {"ciudad_id": "ciu-sc", "temp_c": 99.0, "descripcion": "Anterior"}
    assert repo.clima_ciudades["ciu-1"]["temp_c"] == 31.5


def test_si_open_meteo_falla_no_se_pisa_nada(http, repo):
    repo.ciudades_con_coordenadas = CIUDADES
    repo.clima_ciudades["ciu-1"] = {"ciudad_id": "ciu-1", "temp_c": 5.0, "descripcion": "Anterior"}
    http.respuesta = httpx.TimeoutException("timeout")
    assert asyncio.run(clima.actualizar_clima_ciudades(repo)) == 0
    assert repo.clima_ciudades == {"ciu-1": {"ciudad_id": "ciu-1", "temp_c": 5.0, "descripcion": "Anterior"}}


def test_un_error_al_guardar_una_ciudad_no_frena_a_las_otras(http, repo, monkeypatch):
    repo.ciudades_con_coordenadas = CIUDADES
    http.respuesta = httpx.Response(200, json=[_item(31.5, 0), _item(27.0, 3), _item(18.2, 61)])
    original = repo.upsert_clima_ciudad

    def roto(ciudad_id, temp_c, descripcion):
        if ciudad_id == "ciu-sc":
            raise RuntimeError("falló la base")
        return original(ciudad_id, temp_c, descripcion)
    monkeypatch.setattr(repo, "upsert_clima_ciudad", roto)
    assert asyncio.run(clima.actualizar_clima_ciudades(repo)) == 2
    assert set(repo.clima_ciudades) == {"ciu-1", "ciu-tj"}


def test_si_falla_leer_las_ciudades_no_levanta(repo, monkeypatch):
    def roto():
        raise RuntimeError("base caída")
    monkeypatch.setattr(repo, "list_ciudades_con_coordenadas", roto)
    assert asyncio.run(clima.actualizar_clima_ciudades(repo)) == 0


def test_sin_ciudades_no_llama_a_open_meteo(http, repo):
    repo.ciudades_con_coordenadas = []
    assert asyncio.run(clima.actualizar_clima_ciudades(repo)) == 0
    assert http.pedidos == []


# ------------------------------------------------------------------ el loop
def test_el_loop_actualiza_bermejo_y_las_ciudades_y_no_se_cae(http, repo, monkeypatch):
    repo.ciudades_con_coordenadas = CIUDADES[:1]
    http.respuesta = httpx.Response(200, json=_item(30.0, 0))
    monkeypatch.setattr(main, "get_repo", lambda: repo)

    async def bermejo():
        return {"temp_c": 33.0, "descripcion": "Despejado", "icono": "☀️", "fuente": "open-meteo"}
    monkeypatch.setattr(main, "fetch_clima_bermejo", bermejo)

    async def dormir(seg):
        raise asyncio.CancelledError()
    monkeypatch.setattr(main.asyncio, "sleep", dormir)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(main._clima_loop())
    assert repo.clima["temp_c"] == 33.0                       # Bermejo, como siempre
    assert repo.clima_ciudades["ciu-1"]["temp_c"] == 30.0      # y la tabla nueva


def test_el_loop_sigue_aunque_falle_el_clima_de_las_ciudades(repo, monkeypatch):
    monkeypatch.setattr(main, "get_repo", lambda: repo)

    async def bermejo():
        return {"temp_c": 33.0, "descripcion": "Despejado", "icono": "☀️", "fuente": "open-meteo"}

    async def roto(_repo):
        raise RuntimeError("explotó")
    monkeypatch.setattr(main, "fetch_clima_bermejo", bermejo)
    monkeypatch.setattr(main, "actualizar_clima_ciudades", roto)

    async def dormir(seg):
        raise asyncio.CancelledError()
    monkeypatch.setattr(main.asyncio, "sleep", dormir)
    with pytest.raises(asyncio.CancelledError):  # llegó al sleep: la excepción se tragó
        asyncio.run(main._clima_loop())
    assert repo.clima["temp_c"] == 33.0


# ------------------------------------------------------------------ migración 0201 (estática)
def _sql(carpeta: str) -> str:
    return (RAIZ / carpeta / NOMBRE).read_text(encoding="utf-8").replace("\r\n", "\n")


def _normal(sql: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"--[^\n]*", "", sql)).lower()


def test_migracion_identica_en_las_dos_carpetas_y_numero_unico():
    assert _sql("supabase/migrations") == _sql("selfhost/postgres-init")
    for carpeta in ("supabase/migrations", "selfhost/postgres-init"):
        assert sorted(p.name for p in (RAIZ / carpeta).glob("0201_*.sql")) == [NOMBRE]


def test_migracion_tabla_rls_y_grants():
    s = _normal(_sql("supabase/migrations"))
    assert "create table if not exists public.clima_ciudades" in s
    assert "ciudad_id uuid primary key references public.ciudades(id)" in s
    assert "temp_c numeric" in s and "descripcion text" in s
    assert "actualizado_en timestamptz not null default now()" in s
    assert "alter table public.clima_ciudades enable row level security" in s
    assert "drop policy if exists" in s and "create policy" in s and "for select to anon, authenticated" in s
    assert "grant select on public.clima_ciudades to anon, authenticated" in s
    assert "grant select, insert, update on public.clima_ciudades to service_role" in s
    assert "notify pgrst, 'reload schema'" in s


def test_migracion_no_da_escritura_a_anon_ni_delete_a_nadie():
    s = _normal(_sql("supabase/migrations"))
    grants = re.findall(r"grant ([a-z, ]+) on public\.clima_ciudades to ([a-z_, ]+);", s)
    assert grants
    for privilegios, roles in grants:
        if "anon" in roles or "authenticated" in roles:
            assert privilegios.strip() == "select", (privilegios, roles)
        assert "delete" not in privilegios and "all" not in privilegios.split(", "), (privilegios, roles)
