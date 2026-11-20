"""Home de ciudades: arreglos de la revisión (docs/home-ciudades.md §8 y §9).

1. Las sugerencias de Dax salen sólo si la ciudad tiene el rubro (mismo mapa que el panel del sitio).
2. Sin frontera, la cotización es sólo el dólar (nada de pesos).
3. El «abierto ahora» lleva `&abierto=1` en `ver_url`.
4. El saludo es de Dax, por franja horaria en las ciudades sin guía.
5. El clima por ciudad: plazo total, números finitos y rango de temperatura.
6. La migración 0201: service_role sin DELETE ni TRUNCATE (y la comprobación lo verifica).
"""
import asyncio
import re
from datetime import datetime
from pathlib import Path

import httpx
import pytest

from app.core.config import settings
from app.db.repository import SupabaseRepo
from app.services import asistente, clima

RAIZ = Path(__file__).resolve().parents[2]
TARIJA = {"slug": "tarija", "nombre": "Tarija", "guia_activa": False}
BERMEJO = {"slug": "bermejo", "nombre": "Bermejo", "guia_activa": True}


@pytest.fixture(autouse=True)
def sin_modelo(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")


# ═════════════════════════════════════ 1. sugerencias según los rubros de la ciudad
def test_el_mapa_de_rubros_cubre_todas_las_sugerencias_de_las_franjas():
    textos = {t for _d, _h, lista in asistente.SUGERENCIAS_POR_FRANJA for t in lista}
    assert textos == set(asistente.RUBROS_DE_SUGERENCIA)


def test_el_mapa_de_rubros_es_el_mismo_que_el_del_frontend():
    """frontend/lib/home-ciudad-pure.ts (`SUGERENCIAS`): los dos tienen que decir lo mismo."""
    ruta = RAIZ / "frontend" / "lib" / "home-ciudad-pure.ts"
    if not ruta.exists():
        pytest.skip("el frontend no está en este checkout")
    ts = ruta.read_text(encoding="utf-8")
    bloque = ts[ts.index("const SUGERENCIAS"):ts.index("export function sugerenciasDeFranja")]
    pares = re.findall(r'\{\s*t:\s*"([^"]+)",\s*rubros:\s*\[([^\]]*)\]', bloque)
    assert pares
    for texto, rubros in pares:
        lista = tuple(r.strip().strip('"') if r.strip() != "RUBRO_PARA_VISITAR" else "para-visitar"
                      for r in rubros.split(",") if r.strip())
        assert asistente.RUBROS_DE_SUGERENCIA[texto] == lista, texto


def test_sin_rubros_conocidos_salen_todas():
    assert asistente.sugerencias_iniciales(False, 8, None) == ["¿Dónde desayuno?", "Farmacia abierta cerca", "¿Qué visito hoy?"]


def test_solo_salen_las_de_rubros_que_la_ciudad_tiene():
    assert asistente.sugerencias_iniciales(False, 8, {"farmacia", "para-visitar"}) == ["Farmacia abierta cerca", "¿Qué visito hoy?"]
    # cualquiera de los rubros de la sugerencia alcanza
    assert "¿Dónde desayuno?" in asistente.sugerencias_iniciales(False, 8, {"panaderia", "farmacia"})
    assert asistente.sugerencias_iniciales(False, 13, {"zapatillas", "cajeros"}) == ["Busco zapatillas", "Cajero cerca"]


def test_si_quedan_menos_de_dos_se_completa_con_las_que_valen_en_cualquier_ciudad():
    # una sola: se suma una de relleno (2 en total)
    assert asistente.sugerencias_iniciales(False, 8, {"farmacia"}) == ["Farmacia abierta cerca", "¿Qué hay abierto ahora?"]
    # ninguna: las dos de relleno, nunca una lista vacía
    assert asistente.sugerencias_iniciales(False, 8, set()) == asistente.SUGERENCIAS_RELLENO
    assert asistente.sugerencias_iniciales(False, 23, frozenset()) == asistente.SUGERENCIAS_RELLENO


def test_con_guia_no_se_filtra_por_rubro():
    assert asistente.sugerencias_iniciales(True, 8, set()) == asistente.SUGERENCIAS_INICIALES


def test_las_de_relleno_no_hablan_de_frontera():
    for s in asistente.SUGERENCIAS_RELLENO:
        assert not re.search(r"\b(paso|aduana|peso|dólar|frontera)", s.lower())


def test_el_saludo_de_una_ciudad_filtra_por_sus_rubros(repo):
    repo.rubros_de_ciudad["tarija"] = {"farmacia", "hospedaje"}
    r = asistente.responder(repo, "hola", ahora=datetime(2026, 11, 20, 20, 0), ciudad=TARIJA)
    assert r.sugerencias == ["Hotel para esta noche", "¿Qué hay abierto ahora?"]
    r = asistente.responder(repo, "gracias", ahora=datetime(2026, 11, 20, 3, 0), ciudad=TARIJA)
    assert r.sugerencias == ["Farmacia de turno", "¿Dónde duermo?"]


def test_si_la_lectura_de_rubros_falla_salen_todas_y_no_se_guarda_el_fallo(repo, monkeypatch):
    llamadas = []

    def roto(slug):
        llamadas.append(slug)
        raise RuntimeError("base caída")
    monkeypatch.setattr(repo, "list_rubros_de_ciudad", roto)
    r = asistente.responder(repo, "hola", ahora=datetime(2026, 11, 20, 8, 0), ciudad=TARIJA)
    assert r.sugerencias == ["¿Dónde desayuno?", "Farmacia abierta cerca", "¿Qué visito hoy?"]
    asistente.responder(repo, "hola", ahora=datetime(2026, 11, 20, 8, 0), ciudad=TARIJA)
    assert llamadas == ["tarija", "tarija"]  # el fallo no se cachea: la próxima vuelve a intentar


def test_los_rubros_se_cachean_y_el_cache_vence(repo, monkeypatch):
    llamadas = []
    original = repo.list_rubros_de_ciudad
    repo.rubros_de_ciudad["tarija"] = {"farmacia", "para-visitar"}

    def contado(slug):
        llamadas.append(slug)
        return original(slug)
    monkeypatch.setattr(repo, "list_rubros_de_ciudad", contado)
    reloj = {"t": 1000.0}
    monkeypatch.setattr(asistente.time, "monotonic", lambda: reloj["t"])
    for _ in range(3):
        asistente.responder(repo, "hola", ahora=datetime(2026, 11, 20, 8, 0), ciudad=TARIJA)
    assert llamadas == ["tarija"]
    reloj["t"] += asistente._RUBROS_TTL + 1
    repo.rubros_de_ciudad["tarija"] = {"farmacia"}
    r = asistente.responder(repo, "hola", ahora=datetime(2026, 11, 20, 8, 0), ciudad=TARIJA)
    assert llamadas == ["tarija", "tarija"]
    assert r.sugerencias == ["Farmacia abierta cerca", "¿Qué hay abierto ahora?"]


def test_bermejo_y_sin_ciudad_no_leen_los_rubros(repo, monkeypatch):
    def prohibido(slug):
        raise AssertionError("no hacía falta leer los rubros")
    monkeypatch.setattr(repo, "list_rubros_de_ciudad", prohibido)
    assert asistente.responder(repo, "hola", ahora=datetime(2026, 11, 20, 8, 0), ciudad=BERMEJO).sugerencias == asistente.SUGERENCIAS_INICIALES
    assert asistente.responder(repo, "hola", ahora=datetime(2026, 11, 20, 8, 0)).sugerencias == asistente.SUGERENCIAS_INICIALES


class _Rpc:
    def __init__(self, data=None, error=None):
        self.data, self.error, self.nombres = data, error, []

    def rpc(self, nombre, params):
        self.nombres.append(nombre)
        return self

    def execute(self):
        if self.error:
            raise self.error
        return type("R", (), {"data": self.data})()


def _repo_real(db):
    r = SupabaseRepo.__new__(SupabaseRepo)
    r._db = db
    return r


def test_repo_real_lee_los_rubros_de_la_ciudad_con_city_category_pages():
    db = _Rpc([
        {"city_slug": "tarija", "category_slug": "farmacia"}, {"city_slug": "tarija", "category_slug": "cajeros"},
        {"city_slug": "yacuiba", "category_slug": "hospedaje"},
    ])
    assert _repo_real(db).list_rubros_de_ciudad("tarija") == {"farmacia", "cajeros"}
    assert db.nombres == ["city_category_pages"]
    # una ciudad sin pares es un dato (vacío), no un "no se sabe"
    assert _repo_real(db).list_rubros_de_ciudad("potosi") == set()


def test_repo_real_si_falla_o_viene_vacio_devuelve_none():
    assert _repo_real(_Rpc(error=RuntimeError("caído"))).list_rubros_de_ciudad("tarija") is None
    assert _repo_real(_Rpc([])).list_rubros_de_ciudad("tarija") is None


# ═════════════════════════════════════ 2. cotización sin pesos fuera de la frontera
def _cotizaciones(repo, historial=True):
    repo.cotizaciones[:] = [
        {"clave": "usd_bob", "etiqueta": "Dólar", "valor": 6.96, "unidad": "Bs", "orden": 1},
        {"clave": "ars_bob", "etiqueta": "Peso argentino", "valor": 7.2, "unidad": "Bs", "detalle": "1.000 ARS", "orden": 2},
    ]
    if historial:
        for v in (7.0, 7.1, 7.0, 7.05):
            repo.cotizaciones_historial.append({"clave": "ars_bob", "valor": v, "registrado_en": "2026-01-01T00:00:00+00:00"})


@pytest.mark.parametrize("pregunta", ["a cuánto está el dólar", "cotización", "¿cuánto está el peso argentino?", "el blue"])
def test_sin_frontera_solo_el_dolar(repo, pregunta):
    _cotizaciones(repo)
    r = asistente.responder(repo, pregunta, ahora=datetime(2026, 11, 20, 20, 0), ciudad=TARIJA)
    assert r.intent == "cotizacion"
    assert "Dólar 6,96" in r.texto and "peso" not in r.texto.lower() and "ARS" not in r.texto and "argentin" not in r.texto.lower()
    assert r.sugerencias == ["¿Dónde cambio dólares?", "¿Qué hay abierto ahora?"]


def test_sin_frontera_ni_la_cotizacion_de_las_casas_de_cambio_trae_pesos(repo):
    _cotizaciones(repo)
    repo.comercios["cc"] = {"id": "cc", "slug": "cambio-uno", "nombre": "Cambio Uno", "activo": True, "rubro_slug": "cambio"}
    r = asistente.responder(repo, "¿dónde cambio dólares?", ahora=datetime(2026, 11, 20, 11, 0), ciudad=TARIJA)
    assert r.intent == "casas_de_cambio" and "Dólar 6,96" in r.texto and "peso argentino" not in r.texto.lower()


def test_bermejo_sigue_igual_con_pesos_y_su_sugerencia(repo):
    _cotizaciones(repo)
    for ciudad in (None, BERMEJO):
        r = asistente.responder(repo, "a cuánto está el dólar", ahora=datetime(2026, 11, 20, 20, 0), ciudad=ciudad)
        assert "Dólar 6,96" in r.texto and "Peso argentino 7,2 Bs (por 1.000 ARS)" in r.texto
        assert r.sugerencias == ["¿Cuánto son 10.000 pesos en bolivianos?", "¿Dónde cambio dólares?"]


# ═════════════════════════════════════ 3. «abierto ahora»: ver_url con abierto=1
def _abierto(repo, **extra):
    repo.comercios["far"] = {"id": "far", "slug": "farmacia-sol", "nombre": "Farmacia Sol", "activo": True,
                             "horario": "Lun-Dom 0:00-23:59", "rubro_slug": "farmacia", "subcategoria": "farmacia", **extra}


def test_abierto_ahora_lleva_abierto_1_con_palabras_y_con_ciudad(repo):
    _abierto(repo, ciudad_slug="tarija")
    r = asistente.responder(repo, "¿qué farmacia hay abierta?", ahora=datetime(2026, 11, 20, 11, 0), ciudad=TARIJA)
    assert r.intent == "abierto_ahora"
    assert r.ver_url == "/buscar?q=farmacia&abierto=1&ciudad=tarija"


def test_abierto_ahora_sin_palabras_y_sin_ciudad(repo):
    _abierto(repo)
    r = asistente.responder(repo, "¿qué hay abierto ahora?", ahora=datetime(2026, 11, 20, 11, 0))
    assert r.intent == "abierto_ahora" and r.ver_url == "/buscar?abierto=1"


def test_ver_url_abierto_no_cambia_las_demas():
    assert asistente._ver_url(q="zapatillas") == "/buscar?q=zapatillas"
    assert asistente._ver_url(rubro="banos") == "/buscar?rubro=banos&vista=mapa"
    assert asistente._ver_url() is None


# ═════════════════════════════════════ 4. el saludo es de Dax
@pytest.mark.parametrize("hora,saludo,cierre", [
    (0, "¡Buenas noches!", "¿Qué necesitás?"), (5, "¡Buenas noches!", "¿Qué necesitás?"),
    (6, "¡Buen día!", "¿Qué necesitás?"), (10, "¡Buen día!", "¿Qué necesitás?"),
    (11, "¡Hola!", "¿Qué necesitás?"), (18, "¡Hola!", "¿Qué necesitás?"),
    (19, "¡Buenas noches!", "¿Salís esta noche?"), (23, "¡Buenas noches!", "¿Salís esta noche?"),
])
def test_saludo_de_dax_por_franja_en_ciudades_sin_guia(repo, hora, saludo, cierre):
    r = asistente.responder(repo, "hola", ahora=datetime(2026, 11, 20, hora, 30), ciudad=TARIJA)
    assert r.intent == "saludo"
    assert r.texto == f"{saludo} Soy Dax y conozco Tarija. {cierre}"


@pytest.mark.parametrize("ciudad", [None, BERMEJO])
def test_saludo_de_bermejo_es_de_dax_y_mantiene_el_tono(repo, ciudad):
    r = asistente.responder(repo, "hola", ahora=datetime(2026, 11, 20, 9, 0), ciudad=ciudad)
    assert r.texto.startswith("¡Hola! Soy Dax. Preguntame dónde conseguir algo en Bermejo")
    assert "el dólar" in r.texto


@pytest.mark.parametrize("ciudad", [None, BERMEJO, TARIJA])
@pytest.mark.parametrize("hora", [3, 9, 15, 21])
def test_ninguna_respuesta_dice_la_ayuda_ni_asistente_ni_el_dax(repo, ciudad, hora):
    for pregunta in ("hola", "buenas noches", "gracias", "", "kjh asdf qwerty zzz"):
        t = asistente.responder(repo, pregunta, ahora=datetime(2026, 11, 20, hora, 0), ciudad=ciudad).texto.lower()
        assert "la ayuda" not in t and "asistente" not in t and "el dax" not in t, (pregunta, t)


# ═════════════════════════════════════ 5. clima: endurecimiento
def _item(temp, code=0):
    return {"current": {"temperature_2m": temp, "weather_code": code}}


@pytest.mark.parametrize("valor", [float("nan"), float("inf"), float("-inf")])
def test_numero_rechaza_nan_e_infinitos(valor):
    assert clima._numero(valor) is None
    assert clima._numero(12.5) == 12.5 and clima._numero(0) == 0.0 and clima._numero(True) is None


@pytest.mark.parametrize("temp", [-60.1, 60.1, 999, -999, 1e308])
def test_una_temperatura_absurda_se_ignora_y_el_resto_del_lote_sigue(temp):
    ciudades = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    out = clima.parsear_clima_ciudades(ciudades, [_item(20.0), _item(temp), _item(-4.0)])
    assert set(out) == {"a", "c"}


def test_los_limites_de_temperatura_son_validos():
    out = clima.parsear_clima_ciudades([{"id": "a"}, {"id": "b"}], [_item(-60), _item(60)])
    assert out["a"]["temp_c"] == -60.0 and out["b"]["temp_c"] == 60.0


def test_un_codigo_de_clima_infinito_no_rompe():
    out = clima.parsear_clima_ciudades([{"id": "a"}], [_item(20.0, float("inf"))])
    assert out == {"a": {"temp_c": 20.0, "descripcion": "—"}}


def test_coordenadas_fuera_de_rango_o_no_finitas_no_se_piden(monkeypatch):
    pedidos = []

    class _C:
        def __init__(self, *a, **k): ...
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url, *a, **k):
            pedidos.append(url)
            return httpx.Response(200, json=[_item(20.0)])
    monkeypatch.setattr(clima.httpx, "AsyncClient", _C)
    ciudades = [{"id": "a", "lat": -22.0, "lng": -64.0}, {"id": "b", "lat": 95.0, "lng": 0.0},
                {"id": "c", "lat": float("nan"), "lng": 1.0}, {"id": "d", "lat": 1.0, "lng": 200.0}]
    assert list(asyncio.run(clima.fetch_clima_ciudades(ciudades))) == ["a"]
    assert len(pedidos) == 1 and "latitude=-22.0000&" in pedidos[0]


def test_hay_un_plazo_total_y_un_timeout_de_httpx(monkeypatch):
    """Si la consulta se cuelga, `fetch_clima_ciudades` vuelve igual (con {}) al cumplirse el plazo total."""
    timeouts = []

    class _Colgado:
        def __init__(self, *a, **k):
            timeouts.append(k.get("timeout"))
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url, *a, **k):
            await asyncio.sleep(3600)
    monkeypatch.setattr(clima.httpx, "AsyncClient", _Colgado)
    monkeypatch.setattr(clima, "PLAZO_TOTAL_S", 0.05)
    assert asyncio.run(clima.fetch_clima_ciudades([{"id": "a", "lat": -22.0, "lng": -64.0}])) == {}
    t = timeouts[0]
    assert isinstance(t, httpx.Timeout) and t.connect == 5 and t.read == 10


def test_el_plazo_total_real_es_de_20_segundos():
    assert clima.PLAZO_TOTAL_S == 20


# ═════════════════════════════════════ 6. migración 0201
def _sql() -> str:
    return (RAIZ / "supabase" / "migrations" / "0201_clima_ciudades.sql").read_text(encoding="utf-8").replace("\r\n", "\n")


def _normal(sql: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"--[^\n]*", "", sql)).lower()


def test_migracion_le_saca_todo_a_service_role_y_le_da_solo_lo_que_usa():
    s = _normal(_sql())
    assert "revoke all on public.clima_ciudades from public, anon, authenticated, service_role;" in s
    # el revoke va ANTES de los grants (si no, los dejaría sin efecto)
    assert s.index("revoke all on public.clima_ciudades") < s.index("grant select, insert, update on public.clima_ciudades to service_role")
    assert "grant select, insert, update on public.clima_ciudades to service_role" in s


def test_la_comprobacion_verifica_delete_y_truncate_de_service_role():
    s = _normal(_sql())
    chk = s[s.index("do $chk$"):]
    assert "has_table_privilege('service_role', 'public.clima_ciudades', 'delete')" in chk
    assert "has_table_privilege('service_role', 'public.clima_ciudades', 'truncate')" in chk


def test_las_dos_copias_siguen_identicas():
    a = (RAIZ / "supabase" / "migrations" / "0201_clima_ciudades.sql").read_bytes().replace(b"\r\n", b"\n")
    b = (RAIZ / "selfhost" / "postgres-init" / "0201_clima_ciudades.sql").read_bytes().replace(b"\r\n", b"\n")
    assert a == b
