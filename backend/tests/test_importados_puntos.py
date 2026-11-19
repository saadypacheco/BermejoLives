"""`GET /admin/importados/puntos`: los puntos de los importados de una ciudad para el mapa del panel."""
import pytest

from app.api import moderacion
from app.core import auth
from app.db.repository import COLUMNAS_PUNTOS_IMPORTADOS, SupabaseRepo, paginar_rango

URL = "/admin/importados/puntos"


def h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def datos():
    return h(auth.make_token("datos@uruku.bo", rol="x", roles=["x"], permisos=["datos"]))


def _imp(repo, id, **kw):
    fila = {"id": id, "fuente": "osm", "estado": "nuevo", "ciudad_id": "ciudad-scz", "nombre": f"N {id}",
            "rubro_slug": "restaurantes", "lat": -17.78, "lng": -63.18, "duplicado_de": None, **kw}
    repo.importados[id] = fila
    return fila


# ───────────────────────────── permiso y validación
def test_sin_token_no_entra(client):
    assert client.get(URL, params={"ciudad_id": "ciudad-scz"}).status_code in (401, 403)


def test_sin_permiso_datos_es_403(client):
    sin = h(auth.make_token("otro@uruku.bo", rol="x", roles=["x"], permisos=["pagos"]))
    assert client.get(URL, params={"ciudad_id": "ciudad-scz"}, headers=sin).status_code == 403


def test_ciudad_id_es_obligatorio(client, datos):
    assert client.get(URL, headers=datos).status_code == 422
    assert client.get(URL, params={"ciudad_id": ""}, headers=datos).status_code == 422


def test_estado_y_fuente_invalidos_son_422(client, datos):
    assert client.get(URL, params={"ciudad_id": "c", "estado": "borrado"}, headers=datos).status_code == 422
    assert client.get(URL, params={"ciudad_id": "c", "fuente": "x"}, headers=datos).status_code == 422


def test_no_choca_con_las_rutas_de_importado_id(client, datos):
    r = client.get(URL, params={"ciudad_id": "ciudad-scz"}, headers=datos)
    assert r.status_code == 200 and r.json() == {"items": [], "total": 0, "sin_punto": 0, "truncado": False}


# ───────────────────────────── filtros
def test_forma_del_item_y_redondeo_a_6_decimales(client, repo, datos):
    _imp(repo, "a", fuente="overture", lat=-17.78123456789, lng=-63.18987654321, ubicacion="aproximada",
         duplicado_de="com-1", telefono="no va", email="no@va")
    r = client.get(URL, params={"ciudad_id": "ciudad-scz"}, headers=datos)
    assert r.status_code == 200
    assert r.json() == {"items": [{"id": "a", "nombre": "N a", "fuente": "overture", "lat": -17.781235,
                                   "lng": -63.189877, "rubro_slug": "restaurantes", "repetido": True,
                                   "ubicacion": "aproximada"}],
                        "total": 1, "sin_punto": 0, "truncado": False}


def test_ubicacion_ausente_es_null_y_repetido_false(client, repo, datos):
    _imp(repo, "a")
    item = client.get(URL, params={"ciudad_id": "ciudad-scz"}, headers=datos).json()["items"][0]
    assert item["ubicacion"] is None and item["repetido"] is False


def test_filtra_por_ciudad_estado_fuente_y_rubro(client, repo, datos):
    _imp(repo, "ok")
    _imp(repo, "otra-ciudad", ciudad_id="ciudad-tarija")
    _imp(repo, "promovido", estado="promovido")
    _imp(repo, "tarjeta", fuente="tarjeta")
    _imp(repo, "otro-rubro", rubro_slug="farmacias")

    def ids(**p):
        r = client.get(URL, params={"ciudad_id": "ciudad-scz", **p}, headers=datos)
        assert r.status_code == 200, r.text
        return sorted(i["id"] for i in r.json()["items"])

    assert ids() == ["ok", "otro-rubro", "tarjeta"]                      # estado por defecto: nuevo
    assert ids(estado="promovido") == ["promovido"]
    assert ids(fuente="tarjeta") == ["tarjeta"]
    assert ids(rubro="farmacias") == ["otro-rubro"]
    assert ids(fuente="osm", rubro="restaurantes") == ["ok"]


def test_excluye_los_sin_punto_y_los_cuenta(client, repo, datos):
    _imp(repo, "con")
    _imp(repo, "sin-lat", lat=None)
    _imp(repo, "sin-lng", lng=None)
    _imp(repo, "sin-ambos", lat=None, lng=None)
    _imp(repo, "sin-punto-otra-ciudad", lat=None, ciudad_id="ciudad-tarija")
    _imp(repo, "sin-punto-otro-estado", lat=None, estado="descartado")
    j = client.get(URL, params={"ciudad_id": "ciudad-scz"}, headers=datos).json()
    assert [i["id"] for i in j["items"]] == ["con"]
    assert j["total"] == 1 and j["sin_punto"] == 3
    # `sin_punto` respeta los mismos filtros
    assert client.get(URL, params={"ciudad_id": "ciudad-scz", "rubro": "nada"}, headers=datos).json()["sin_punto"] == 0


def test_tope_y_truncado(client, repo, datos, monkeypatch):
    monkeypatch.setattr(moderacion, "TOPE_PUNTOS_MAPA", 3)
    for n in range(5):
        _imp(repo, f"i{n}")
    j = client.get(URL, params={"ciudad_id": "ciudad-scz"}, headers=datos).json()
    assert j["total"] == 3 and len(j["items"]) == 3 and j["truncado"] is True


def test_justo_en_el_tope_no_es_truncado(client, repo, datos, monkeypatch):
    monkeypatch.setattr(moderacion, "TOPE_PUNTOS_MAPA", 3)
    for n in range(3):
        _imp(repo, f"i{n}")
    j = client.get(URL, params={"ciudad_id": "ciudad-scz"}, headers=datos).json()
    assert j["total"] == 3 and j["truncado"] is False


# ───────────────────────────── paginación
def _pedidor(n_filas, pedidos):
    base = [{"id": f"{i:06d}"} for i in range(n_filas)]

    def pedir(inicio, fin):
        pedidos.append((inicio, fin))
        return base[inicio:fin + 1]
    return pedir


def test_paginar_rango_pide_de_a_1000_hasta_juntar_todo():
    pedidos = []
    filas = paginar_rango(_pedidor(2500, pedidos), 30_000)
    assert len(filas) == 2500 and [f["id"] for f in filas] == [f"{i:06d}" for i in range(2500)]
    assert pedidos == [(0, 999), (1000, 1999), (2000, 2999)]


def test_paginar_rango_corta_en_el_tope_sin_pasarse():
    pedidos = []
    filas = paginar_rango(_pedidor(5000, pedidos), 2500)
    assert len(filas) == 2500
    assert pedidos == [(0, 999), (1000, 1999), (2000, 2499)]


def test_paginar_rango_con_multiplo_exacto_pide_una_pagina_vacia_y_termina():
    pedidos = []
    assert len(paginar_rango(_pedidor(2000, pedidos), 30_000)) == 2000
    assert pedidos == [(0, 999), (1000, 1999), (2000, 2999)]


class _Q:
    """Cliente PostgREST falso: anota la cadena de llamadas y sirve filas según `.range()`."""
    def __init__(self, filas, anotadas):
        self.filas, self.anotadas, self._rango = filas, anotadas, None
        self.not_ = self

    def __getattr__(self, nombre):
        def llamada(*a, **kw):
            self.anotadas.append((nombre, a, kw))
            if nombre == "range":
                self._rango = a
            return self
        return llamada

    def execute(self):
        class R:
            pass
        r = R()
        r.data = self.filas[self._rango[0]:self._rango[1] + 1] if self._rango else []
        r.count = 7
        return r


class _Db:
    def __init__(self, filas):
        self.filas, self.anotadas = filas, []

    def table(self, nombre):
        self.anotadas.append(("table", (nombre,), {}))
        return _Q(self.filas, self.anotadas)


def _repo_real(filas):
    repo = SupabaseRepo.__new__(SupabaseRepo)
    repo._db = _Db(filas)
    return repo


def test_la_clase_real_pagina_y_pide_solo_las_columnas_del_mapa():
    repo = _repo_real([{"id": f"{i:06d}"} for i in range(2300)])
    filas = repo.puntos_importados("ciudad-scz", "nuevo", "osm", "farmacias", 30_000)
    assert len(filas) == 2300
    llamadas = repo._db.anotadas
    assert [a for n, a, _ in llamadas if n == "range"] == [(0, 999), (1000, 1999), (2000, 2999)]
    assert ("select", (COLUMNAS_PUNTOS_IMPORTADOS,), {}) in llamadas
    assert "*" not in COLUMNAS_PUNTOS_IMPORTADOS and "ubicacion" in COLUMNAS_PUNTOS_IMPORTADOS
    eqs = [a for n, a, _ in llamadas if n == "eq"]
    assert eqs.count(("ciudad_id", "ciudad-scz")) == 3
    assert ("rubro_slug", "farmacias") in eqs and ("fuente", "osm") in eqs
    assert [a for n, a, _ in llamadas if n == "order"][0] == ("id",)


def test_la_clase_real_cuenta_los_sin_punto_sin_traer_filas():
    repo = _repo_real([{"id": "x"}])
    assert repo.contar_importados_sin_punto("ciudad-scz", "nuevo", None, None) == 7
    llamadas = repo._db.anotadas
    assert ("select", ("id",), {"count": "exact"}) in llamadas
    assert ("or_", ("lat.is.null,lng.is.null",), {}) in llamadas
