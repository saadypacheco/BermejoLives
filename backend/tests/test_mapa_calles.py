"""Mapa de calles recorridas (docs/mapa-calles.md): cobertura, estado, marcas, importación y permisos.

No sale a la red: Overpass se reemplaza por un cliente falso (`app.dependency_overrides`) y el
cliente HTTP real (`descargar_vias`) se prueba con `httpx.post` simulado.
"""
import math
import random
import time
from pathlib import Path

import httpx
import pytest

from app.core import auth
from app.db.repository import SupabaseRepo
from app.main import app
from app.services import calles_mapa
from tests.pg_0149 import pg0149  # noqa: F401

RAIZ = Path(__file__).resolve().parents[2]
BERMEJO = "ciu-1"
SANTA_CRUZ = "ciu-santa-cruz"

LAT0, LNG0 = -22.7361, -64.3433
M_LAT = 1 / 110_540                                        # grados por metro hacia el norte
M_LNG = 1 / (111_320 * math.cos(math.radians(LAT0)))       # grados por metro hacia el este


def _h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _cache_limpia():
    calles_mapa.limpiar_cache()
    yield
    calles_mapa.limpiar_cache()
    app.dependency_overrides.pop(calles_mapa.get_overpass, None)


@pytest.fixture
def admin():
    return auth.make_token("admin@uruku.bo", rol="admin")


@pytest.fixture
def agente():
    return auth.make_agente_token("ana.perez@uruku.bo", ciudad_slug="bermejo")


@pytest.fixture
def agente_sc():
    return auth.make_agente_token("luis@uruku.bo", ciudad_slug="santa-cruz")


def _linea(norte_m=0.0, este_m=0.0, largo=300.0, puntos=4):
    """Una calle recta de sur a norte que arranca `norte_m`/`este_m` metros al N/E del origen."""
    return [[round(LAT0 + (norte_m + largo * i / (puntos - 1)) * M_LAT, 5),
             round(LNG0 + este_m * M_LNG, 5)] for i in range(puntos)]


def _tramo(repo, nombre="Calle Uno", geom=None, ciudad=BERMEJO, way=None, tipo="residential"):
    geom = geom or _linea()
    fila = {"ciudad_id": ciudad, "osm_way_id": way or (len(repo.calles_tramos) + 1000), "nombre": nombre,
            "tipo": tipo, "geom": geom, "longitud_m": int(round(calles_mapa.largo_m(geom))), "activo": True}
    repo.upsert_calles_tramos([fila])
    return next(t["id"] for t in repo.calles_tramos.values()
                if t["ciudad_id"] == ciudad and t["osm_way_id"] == fila["osm_way_id"])


def _comercio(repo, norte_m, este_m=10.0, ciudad=BERMEJO, **extra):
    fila = {"nombre": f"Local {len(repo.comercios)}", "activo": True, "ciudad_id": ciudad,
            "lat": LAT0 + norte_m * M_LAT, "lng": LNG0 + este_m * M_LNG,
            "created_at": "2026-10-01T10:00:00+00:00", "cargado_por": "otro@uruku.bo", **extra}
    return repo.crear_comercio(fila)["id"]


def _a_lo_largo(repo, desde, hasta, cada=20.0, este_m=10.0, **extra):
    n = desde
    while n <= hasta:
        _comercio(repo, n, este_m, **extra)
        n += cada


def _mapa_admin(client, admin, ciudad="bermejo"):
    r = client.get(f"/admin/calles/mapa?ciudad={ciudad}", headers=_h(admin))
    assert r.status_code == 200, r.text
    return r.json()


def _por_id(mapa):
    return {t["id"]: t for t in mapa["tramos"]}


# ══════════════════════════════════════════════ cobertura y estado

def test_tramo_con_comercios_a_lo_largo_es_recorrida(client, repo, admin):
    t = _tramo(repo)
    _a_lo_largo(repo, 0, 300)
    tr = _por_id(_mapa_admin(client, admin))[t]
    assert tr["cobertura"] == 100.0
    assert tr["estado"] == "recorrida"
    assert tr["comercios"] == 16
    assert tr["marca"] is None


def test_tramo_parcial(client, repo, admin):
    t = _tramo(repo, geom=_linea(largo=600))
    _comercio(repo, 100)                  # cada comercio cubre ~66 m de 600 (11 %): dos separados = ~22 %
    _comercio(repo, 400)
    tr = _por_id(_mapa_admin(client, admin))[t]
    assert 15 <= tr["cobertura"] < 60, tr["cobertura"]
    assert tr["estado"] == "parcial"
    assert tr["comercios"] == 2


def test_tramo_sin_comercios_es_pendiente(client, repo, admin):
    t = _tramo(repo)
    tr = _por_id(_mapa_admin(client, admin))[t]
    assert (tr["cobertura"], tr["comercios"], tr["estado"], tr["ultimo"]) == (0.0, 0, "pendiente", None)


def test_un_solo_comercio_en_una_calle_larga_sigue_pendiente(client, repo, admin):
    t = _tramo(repo, geom=_linea(largo=600))
    _comercio(repo, 300)
    tr = _por_id(_mapa_admin(client, admin))[t]
    assert tr["cobertura"] < 15
    assert tr["estado"] == "pendiente"
    assert tr["comercios"] == 1


@pytest.mark.parametrize("cobertura,esperado", [
    (100, "recorrida"), (60, "recorrida"), (59.96, "parcial"), (15, "parcial"), (14.99, "pendiente"), (0, "pendiente"),
])
def test_umbrales_del_estado_automatico(cobertura, esperado):
    assert calles_mapa.estado_de(cobertura, None) == esperado


@pytest.mark.parametrize("estado", ["recorrida", "sin_comercios", "pendiente"])
def test_la_marca_manual_gana_sobre_el_automatico(estado):
    assert calles_mapa.estado_de(100, {"estado": estado}) == estado
    assert calles_mapa.estado_de(0, {"estado": estado}) == estado


def test_el_radio_es_de_35_metros(client, repo, admin):
    t = _tramo(repo, geom=_linea(largo=15, puntos=2))      # una sola muestra, en el medio
    _comercio(repo, 7.5, este_m=34)
    assert _por_id(_mapa_admin(client, admin))[t]["comercios"] == 1
    calles_mapa.limpiar_cache()
    repo.comercios.clear()
    _comercio(repo, 7.5, este_m=37)
    assert _por_id(_mapa_admin(client, admin))[t]["comercios"] == 0


def test_no_cuentan_comercios_de_baja_sin_gps_ni_de_otra_ciudad(client, repo, admin):
    t = _tramo(repo)
    _comercio(repo, 100, activo=False)
    _comercio(repo, 100, ciudad=SANTA_CRUZ)
    repo.crear_comercio({"nombre": "Sin GPS", "activo": True, "ciudad_id": BERMEJO, "lat": None, "lng": None})
    tr = _por_id(_mapa_admin(client, admin))[t]
    assert tr["comercios"] == 0 and tr["estado"] == "pendiente"


def test_muestreo_cada_15_metros_o_menos():
    xy = calles_mapa.proyector(LAT0)
    pts = [xy(*p) for p in _linea(largo=100, puntos=3)]
    m = calles_mapa.muestrear(pts)
    assert len(m) == 7                                    # ceil(100 / 15)
    assert all(math.hypot(b[0] - a[0], b[1] - a[1]) <= 15.01 for a, b in zip(m, m[1:]))
    assert len(calles_mapa.muestrear([pts[0], pts[0]])) == 1      # sin largo: un punto


# ══════════════════════════════════════════════ marcas

def test_marca_manual_gana_y_la_ultima_vale(client, repo, admin):
    t = _tramo(repo)
    _a_lo_largo(repo, 0, 300)
    assert _por_id(_mapa_admin(client, admin))[t]["estado"] == "recorrida"

    for estado, nota in [("sin_comercios", "Casas"), ("pendiente", None), ("sin_comercios", "Baldío")]:
        r = client.post(f"/admin/calles/{t}/marca", headers=_h(admin), json={"estado": estado, "nota": nota})
        assert r.status_code == 200, r.text
        tr = _por_id(_mapa_admin(client, admin))[t]             # la caché se invalida con cada marca
        assert tr["estado"] == estado
        assert tr["marca"]["estado"] == estado and tr["marca"]["nota"] == nota
        assert tr["marca"]["actor"] == "admin@uruku.bo"
        assert tr["cobertura"] == 100.0                        # la cobertura sigue siendo la medida
    assert len(repo.calles_marcas) == 3                        # un registro: no se pisa nada


def test_marca_pendiente_reabre_una_calle_recorrida(client, repo, admin):
    t = _tramo(repo)
    _a_lo_largo(repo, 0, 300)
    client.post(f"/admin/calles/{t}/marca", headers=_h(admin), json={"estado": "pendiente"})
    assert _por_id(_mapa_admin(client, admin))[t]["estado"] == "pendiente"


def test_marca_valida_el_cuerpo(client, repo, admin):
    t = _tramo(repo)
    h = _h(admin)
    assert client.post(f"/admin/calles/{t}/marca", headers=h, json={"estado": "parcial"}).status_code == 422
    assert client.post(f"/admin/calles/{t}/marca", headers=h, json={}).status_code == 422
    assert client.post(f"/admin/calles/{t}/marca", headers=h,
                       json={"estado": "recorrida", "nota": "x" * 201}).status_code == 422
    ok = client.post(f"/admin/calles/{t}/marca", headers=h, json={"estado": "recorrida", "nota": "x" * 200})
    assert ok.status_code == 200
    vacia = client.post(f"/admin/calles/{t}/marca", headers=h, json={"estado": "recorrida", "nota": "   "})
    assert vacia.json()["marca"]["nota"] is None
    assert client.post("/admin/calles/no-existe/marca", headers=h, json={"estado": "recorrida"}).status_code == 404


def test_agente_marca_un_tramo_de_su_ciudad(client, repo, agente, admin):
    t = _tramo(repo)
    r = client.post(f"/campo/calles/{t}/marca", headers=_h(agente), json={"estado": "sin_comercios", "nota": "Baldío"})
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "marca": {"estado": "sin_comercios", "nota": "Baldío", "actor": "ana.perez",
                                              "created_at": r.json()["marca"]["created_at"]}}
    # Queda gris para todos: el admin la ve, con el email completo.
    tr = _por_id(_mapa_admin(client, admin))[t]
    assert tr["estado"] == "sin_comercios" and tr["marca"]["actor"] == "ana.perez@uruku.bo"
    assert repo.calles_marcas[0]["actor"] == "ana.perez@uruku.bo"


def test_agente_de_otra_ciudad_recibe_404(client, repo, agente, agente_sc):
    t = _tramo(repo)                                        # tramo de Bermejo
    h = _h(agente_sc)
    assert client.post(f"/campo/calles/{t}/marca", headers=h, json={"estado": "recorrida"}).status_code == 404
    assert client.post("/campo/calles/inexistente/marca", headers=h, json={"estado": "recorrida"}).status_code == 404
    assert repo.calles_marcas == []
    # y un agente sin ciudad asignada tampoco marca nada
    sin = auth.make_agente_token("sin@uruku.bo")
    assert client.post(f"/campo/calles/{t}/marca", headers=_h(sin), json={"estado": "recorrida"}).status_code == 404


def test_tramo_de_baja_no_se_marca(client, repo, agente, admin):
    t = _tramo(repo)
    repo.calles_tramos[t]["activo"] = False
    assert client.post(f"/campo/calles/{t}/marca", headers=_h(agente), json={"estado": "recorrida"}).status_code == 404
    assert client.post(f"/admin/calles/{t}/marca", headers=_h(admin), json={"estado": "recorrida"}).status_code == 404
    assert _mapa_admin(client, admin)["tramos"] == []


# ══════════════════════════════════════════════ ultimo, resumen y vista del agente

def test_ultimo_es_la_carga_mas_reciente_con_capturado_en_o_created_at(client, repo, admin):
    t = _tramo(repo)
    _comercio(repo, 50, created_at="2026-10-01T10:00:00+00:00", cargado_por="viejo@uruku.bo")
    # capturado_en (la hora del celular) pisa created_at: se cargó el 5/10 aunque subió el 9/10.
    _comercio(repo, 150, created_at="2026-10-09T10:00:00+00:00", capturado_en="2026-10-05T08:00:00Z",
              cargado_por="medio@uruku.bo")
    _comercio(repo, 250, created_at="2026-10-03T10:00:00-04:00", cargado_por="nuevo@uruku.bo")
    # Más nuevo, pero demasiado lejos de la calle: no cuenta.
    _comercio(repo, 150, este_m=200, created_at="2026-10-12T10:00:00+00:00", cargado_por="lejos@uruku.bo")
    tr = _por_id(_mapa_admin(client, admin))[t]
    assert tr["ultimo"] == {"fecha": "2026-10-05T08:00:00Z", "quien": "medio@uruku.bo"}


def test_ultimo_sin_quien_si_la_carga_no_tiene_agente(client, repo, admin):
    t = _tramo(repo)
    _comercio(repo, 100, cargado_por=None)
    assert _por_id(_mapa_admin(client, admin))[t]["ultimo"] == {"fecha": "2026-10-01T10:00:00+00:00", "quien": None}


def test_el_agente_ve_solo_la_parte_antes_de_la_arroba(client, repo, agente, admin):
    t = _tramo(repo)
    _a_lo_largo(repo, 0, 300, cargado_por="maria.lopez@uruku.bo")
    client.post(f"/admin/calles/{t}/marca", headers=_h(admin), json={"estado": "recorrida", "nota": "ok"})
    para_agente = client.get("/campo/calles", headers=_h(agente)).json()
    tr = _por_id(para_agente)[t]
    assert tr["ultimo"]["quien"] == "maria.lopez"
    assert tr["marca"]["actor"] == "admin"
    assert "@" not in str(tr["ultimo"]) + str(tr["marca"])
    # el admin sigue viendo el email completo (la caché no se contaminó)
    tr_admin = _por_id(_mapa_admin(client, admin))[t]
    assert tr_admin["ultimo"]["quien"] == "maria.lopez@uruku.bo" and tr_admin["marca"]["actor"] == "admin@uruku.bo"
    assert set(tr) == {"id", "nombre", "tipo", "geom", "longitud_m", "cobertura", "estado", "marca", "comercios", "ultimo"}
    assert set(tr["marca"]) == {"estado", "nota", "actor", "created_at"} and set(tr["ultimo"]) == {"fecha", "quien"}


def test_el_agente_ve_solo_su_ciudad(client, repo, agente, agente_sc):
    a = _tramo(repo, "Bermejo uno")
    b = _tramo(repo, "Cruceña uno", ciudad=SANTA_CRUZ)
    assert [t["id"] for t in client.get("/campo/calles", headers=_h(agente)).json()["tramos"]] == [a]
    assert [t["id"] for t in client.get("/campo/calles", headers=_h(agente_sc)).json()["tramos"]] == [b]
    sin = client.get("/campo/calles", headers=_h(auth.make_agente_token("sin@uruku.bo")))
    assert sin.status_code == 200 and sin.json()["tramos"] == [] and sin.json()["resumen"]["km_total"] == 0


def test_resumen_en_km(client, repo, admin):
    verde = _tramo(repo, "Verde", geom=_linea(largo=300))
    gris = _tramo(repo, "Gris", geom=_linea(norte_m=0, este_m=500, largo=200))
    roja = _tramo(repo, "Roja", geom=_linea(norte_m=0, este_m=1000, largo=500))
    _a_lo_largo(repo, 0, 300)
    client.post(f"/admin/calles/{gris}/marca", headers=_h(admin), json={"estado": "sin_comercios"})
    m = _mapa_admin(client, admin)
    estados = {t["nombre"]: t["estado"] for t in m["tramos"]}
    assert estados == {"Verde": "recorrida", "Gris": "sin_comercios", "Roja": "pendiente"}
    largos = {t["nombre"]: t["longitud_m"] for t in m["tramos"]}
    assert m["resumen"]["km_total"] == round(sum(largos.values()) / 1000, 2)
    assert m["resumen"]["km_recorridos"] == round(largos["Verde"] / 1000, 2)
    assert m["resumen"]["km_sin_comercios"] == round(largos["Gris"] / 1000, 2)
    # el % se mide sobre lo que hay que recorrer (sin las calles «sin comercios»)
    assert m["resumen"]["pct"] == round(100 * largos["Verde"] / (largos["Verde"] + largos["Roja"]), 1)
    assert set(m["resumen"]) == {"km_total", "km_recorridos", "km_sin_comercios", "km_a_recorrer", "pct"}
    assert verde and roja


def test_ciudad_sin_tramos_da_mapa_vacio(client, admin):
    m = _mapa_admin(client, admin)
    assert m["tramos"] == []
    assert m["resumen"] == {"km_total": 0.0, "km_recorridos": 0.0, "km_sin_comercios": 0.0, "km_a_recorrer": 0.0, "pct": 0.0}


def test_ciudad_desconocida_404(client, admin):
    assert client.get("/admin/calles/mapa?ciudad=no-existe", headers=_h(admin)).status_code == 404
    assert client.get("/admin/calles/mapa", headers=_h(admin)).status_code == 422


# ══════════════════════════════════════════════ caché

def test_la_cache_evita_recalcular_y_se_invalida(client, repo, admin, monkeypatch):
    t = _tramo(repo)
    llamadas = []
    original = repo.list_calles_tramos
    monkeypatch.setattr(repo, "list_calles_tramos", lambda c: llamadas.append(c) or original(c))
    _mapa_admin(client, admin)
    _mapa_admin(client, admin)
    assert len(llamadas) == 1                                   # la segunda salió de la caché
    # un alta nueva (sin pasar por la API) no se ve hasta que se invalida...
    _comercio(repo, 100)
    assert _por_id(_mapa_admin(client, admin))[t]["comercios"] == 0
    calles_mapa.invalidar(BERMEJO)
    assert _por_id(_mapa_admin(client, admin))[t]["comercios"] == 1
    assert len(llamadas) == 2
    # ...o hasta que vence el TTL
    _comercio(repo, 200)
    ahora = time.monotonic() + calles_mapa.TTL_S + 1
    monkeypatch.setattr(calles_mapa, "_ahora", lambda: ahora)
    assert _por_id(_mapa_admin(client, admin))[t]["comercios"] == 2


def test_la_cache_es_por_ciudad(client, repo, admin, agente_sc):
    a = _tramo(repo, "Bermejo")
    b = _tramo(repo, "Cruceña", ciudad=SANTA_CRUZ)
    _mapa_admin(client, admin)
    _mapa_admin(client, admin, "santa-cruz")
    client.post(f"/admin/calles/{a}/marca", headers=_h(admin), json={"estado": "sin_comercios"})
    assert _por_id(_mapa_admin(client, admin))[a]["estado"] == "sin_comercios"
    assert _por_id(_mapa_admin(client, admin, "santa-cruz"))[b]["estado"] == "pendiente"


def test_un_alta_de_campo_invalida_la_cache(client, repo, admin, agente):
    t = _tramo(repo)
    assert _por_id(_mapa_admin(client, admin))[t]["comercios"] == 0
    r = client.post("/campo/comercio", headers=_h(agente), data={
        "nombre": "Kiosco Nuevo", "whatsapp": "59170003333", "rubro_slugs": ["servicios"], "modalidad": "minorista",
        "lat": str(LAT0 + 100 * M_LAT), "lng": str(LNG0 + 10 * M_LNG)})
    assert r.status_code == 200, r.text
    assert _por_id(_mapa_admin(client, admin))[t]["comercios"] == 1


# ══════════════════════════════════════════════ permisos

RUTAS = [
    ("post", "/admin/calles/importar", {"ciudad": "bermejo"}),
    ("get", "/admin/calles/mapa?ciudad=bermejo", None),
    ("get", "/campo/calles", None),
    ("post", "/campo/calles/x/marca", {"estado": "recorrida"}),
    ("post", "/admin/calles/x/marca", {"estado": "recorrida"}),
]


@pytest.mark.parametrize("metodo,ruta,cuerpo", RUTAS)
def test_sin_token_401(client, metodo, ruta, cuerpo):
    r = getattr(client, metodo)(ruta, **({"json": cuerpo} if cuerpo else {}))
    assert r.status_code == 401


@pytest.mark.parametrize("metodo,ruta,cuerpo", RUTAS)
def test_un_comercio_recibe_403_en_todo(client, repo, metodo, ruta, cuerpo):
    token = auth.make_comercio_token("com-1", "dueno@uruku.bo", "usr-1")
    r = getattr(client, metodo)(ruta, headers=_h(token), **({"json": cuerpo} if cuerpo else {}))
    assert r.status_code == 403


def test_el_agente_no_entra_a_las_rutas_del_admin(client, repo, agente):
    h = _h(agente)
    assert client.get("/admin/calles/mapa?ciudad=bermejo", headers=h).status_code == 403
    assert client.post("/admin/calles/importar", headers=h, json={"ciudad": "bermejo"}).status_code == 403
    assert client.post("/admin/calles/x/marca", headers=h, json={"estado": "recorrida"}).status_code == 403


def test_el_admin_no_entra_a_la_ruta_del_agente_de_otro_rol_sin_permiso(client, repo):
    # `/campo/calles` pide «comercios.cargar»: el publicador (contenido, moderar, comercios.editar) no lo tiene.
    pub = auth.make_publicador_token("pub@uruku.bo")
    assert client.get("/campo/calles", headers=_h(pub)).status_code == 403


def test_importar_pide_lugares_y_el_mapa_pide_moderar(client, repo):
    pub = auth.make_publicador_token("pub@uruku.bo")          # moderar sí, lugares no
    assert client.post("/admin/calles/importar", headers=_h(pub), json={"ciudad": "bermejo"}).status_code == 403
    assert client.get("/admin/calles/mapa?ciudad=bermejo", headers=_h(pub)).status_code == 200
    contenido = auth.make_token("c@uruku.bo", rol="x", roles=["x"])
    assert client.get("/admin/calles/mapa?ciudad=bermejo", headers=_h(contenido)).status_code in (401, 403)


# ══════════════════════════════════════════════ importación (Overpass simulado)

def _via(way_id, tipo="residential", nombre="Calle X", puntos=((-22.7361, -64.3433), (-22.7355, -64.3433))):
    tags = {"highway": tipo}
    if nombre:
        tags["name"] = nombre
    return {"type": "way", "id": way_id, "tags": tags, "geometry": [{"lat": a, "lon": b} for a, b in puntos]}


class OverpassFalso:
    def __init__(self, vias=None, falla=False):
        self.vias, self.falla, self.cajas = vias or [], falla, []

    def __call__(self, caja):
        self.cajas.append(caja)
        if self.falla:
            raise calles_mapa.OverpassError("HTTP 504")
        return self.vias


def _inyectar(falso):
    app.dependency_overrides[calles_mapa.get_overpass] = lambda: falso
    return falso


def test_importar_guarda_los_tramos_y_responde_tramos_y_km(client, repo, admin):
    _comercio(repo, 0)
    _comercio(repo, 500)
    falso = _inyectar(OverpassFalso([
        _via(1, "residential", "Calle Uno", puntos=((-22.73610123, -64.34330456), (-22.73549999, -64.34330456))),
        _via(2, "primary", "Ruta 50"),
        _via(3, "tertiary_link", None),
        _via(4, "pedestrian", "Peatonal"),
    ]))
    r = client.post("/admin/calles/importar", headers=_h(admin), json={"ciudad": "bermejo"})
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert set(cuerpo) == {"tramos", "km"} and cuerpo["tramos"] == 4
    guardados = sorted(repo.calles_tramos.values(), key=lambda t: t["osm_way_id"])
    assert cuerpo["km"] == round(sum(t["longitud_m"] for t in guardados) / 1000, 2) and cuerpo["km"] > 0
    assert guardados[0]["geom"] == [[-22.7361, -64.3433], [-22.7355, -64.3433]]      # 5 decimales
    assert guardados[2]["nombre"] is None and guardados[2]["tipo"] == "tertiary_link"
    assert all(t["ciudad_id"] == BERMEJO and t["activo"] for t in guardados)
    # la caja son los comercios con 400 m de margen
    s, w, n, e = falso.cajas[0]
    assert s == pytest.approx(LAT0 - 400 * M_LAT, abs=2e-5) and n == pytest.approx(LAT0 + 900 * M_LAT, abs=2e-5)
    assert w == pytest.approx(LNG0 - 390 * M_LNG, abs=2e-5) and e == pytest.approx(LNG0 + 410 * M_LNG, abs=2e-5)


def test_importar_filtra_los_tipos_de_via(client, repo, admin):
    _comercio(repo, 0)
    _inyectar(OverpassFalso(
        [_via(i, tipo) for i, tipo in enumerate(
            ["primary", "primary_link", "secondary", "secondary_link", "tertiary", "tertiary_link", "residential",
             "unclassified", "living_street", "pedestrian"], start=1)]
        + [_via(100 + i, tipo) for i, tipo in enumerate(
            ["footway", "service", "track", "path", "cycleway", "steps", "motorway", "residential_x"])]
        + [{"type": "node", "id": 500, "tags": {"highway": "residential"}},
           {"type": "way", "id": 501, "tags": {"highway": "residential"}, "geometry": [{"lat": 1, "lon": 1}]},   # 1 punto
           {"type": "way", "id": 502, "tags": {"highway": "residential"}}]))                                       # sin geometría
    r = client.post("/admin/calles/importar", headers=_h(admin), json={"ciudad": "bermejo"})
    assert r.json()["tramos"] == 10
    assert {t["tipo"] for t in repo.calles_tramos.values()} == {
        "primary", "primary_link", "secondary", "secondary_link", "tertiary", "tertiary_link", "residential",
        "unclassified", "living_street", "pedestrian"}


def test_importar_dos_veces_no_duplica_y_conserva_las_marcas(client, repo, admin):
    _comercio(repo, 0)
    _inyectar(OverpassFalso([_via(1, nombre="Vieja"), _via(2)]))
    h = _h(admin)
    client.post("/admin/calles/importar", headers=h, json={"ciudad": "bermejo"})
    tid = next(t["id"] for t in repo.calles_tramos.values() if t["osm_way_id"] == 1)
    client.post(f"/admin/calles/{tid}/marca", headers=h, json={"estado": "sin_comercios"})
    ids = {t["osm_way_id"]: t["id"] for t in repo.calles_tramos.values()}

    _inyectar(OverpassFalso([_via(1, nombre="Renombrada"), _via(2), _via(3, nombre="Nueva")]))
    r = client.post("/admin/calles/importar", headers=h, json={"ciudad": "bermejo"})
    assert r.json()["tramos"] == 3
    assert len(repo.calles_tramos) == 3                          # 1 y 2 se actualizaron, 3 es nueva
    assert {w: repo.calles_tramos[i]["osm_way_id"] for w, i in ids.items()} == {1: 1, 2: 2}      # mismos ids
    assert repo.calles_tramos[tid]["nombre"] == "Renombrada"
    mapa = _mapa_admin(client, admin)
    assert _por_id(mapa)[tid]["estado"] == "sin_comercios"       # la marca sigue en pie
    # y el mapa se recalculó solo (la importación invalida la caché)
    assert len(mapa["tramos"]) == 3


def test_importar_overpass_caido_da_502_legible(client, repo, admin):
    _comercio(repo, 0)
    _inyectar(OverpassFalso(falla=True))
    r = client.post("/admin/calles/importar", headers=_h(admin), json={"ciudad": "bermejo"})
    assert r.status_code == 502
    assert "OpenStreetMap" in r.json()["detail"] and "Probá de nuevo" in r.json()["detail"]
    assert repo.calles_tramos == {}


def test_importar_ciudad_desconocida_404(client, repo, admin):
    _inyectar(OverpassFalso())
    assert client.post("/admin/calles/importar", headers=_h(admin), json={"ciudad": "no-existe"}).status_code == 404
    assert client.post("/admin/calles/importar", headers=_h(admin), json={"ciudad": ""}).status_code == 422


def test_importar_sin_comercios_usa_el_centro_de_la_ciudad(client, repo, admin):
    falso = _inyectar(OverpassFalso([_via(1)]))
    r = client.post("/admin/calles/importar", headers=_h(admin), json={"ciudad": "bermejo"})
    assert r.status_code == 200 and r.json()["tramos"] == 1
    s, w, n, e = falso.cajas[0]
    assert s < -22.7361 < n and w < -64.3433 < e


def test_la_caja_ignora_un_gps_roto():
    buenos = [{"lat": LAT0 + i * 0.0001, "lng": LNG0 + i * 0.0001} for i in range(300)]
    caja = calles_mapa.caja_de(buenos + [{"lat": -17.78, "lng": -63.18}])     # uno en Santa Cruz
    assert caja is not None and caja[2] - caja[0] < 0.1
    assert calles_mapa.caja_de([{"lat": -17.78, "lng": -63.18}, {"lat": LAT0, "lng": LNG0}]) is None   # no hay cuál creerle
    assert calles_mapa.caja_de([{"lat": None, "lng": None}, {"lat": 0, "lng": 0}]) is None


# ── el cliente HTTP real, con httpx simulado ─────────────────────────────────

class _Resp:
    def __init__(self, status=200, json=None):
        self.status_code, self._json = status, json

    def json(self):
        if self._json is None:
            raise ValueError("no es JSON")
        return self._json


@pytest.fixture
def sin_pausa(monkeypatch):
    monkeypatch.setattr(calles_mapa.time, "sleep", lambda s: None)


def test_descargar_vias_reintenta_con_otro_servidor(monkeypatch, sin_pausa):
    pedidos = []

    def post(url, **kw):
        pedidos.append((url, kw))
        if len(pedidos) == 1:
            raise httpx.ConnectTimeout("lento")
        return _Resp(200, {"elements": [_via(1)]})

    monkeypatch.setattr(calles_mapa.httpx, "post", post)
    vias = calles_mapa.descargar_vias((-22.8, -64.4, -22.7, -64.3))
    assert len(vias) == 1
    assert [u for u, _ in pedidos] == list(calles_mapa.OVERPASS_URLS)
    assert pedidos[0][1]["timeout"].read == calles_mapa.TIMEOUT_HTTP_S
    consulta = pedidos[0][1]["data"]["data"]
    assert "highway" in consulta and "out geom(" in consulta and f"timeout:{calles_mapa.TIMEOUT_QUERY_S}" in consulta


@pytest.mark.parametrize("respuesta", [
    _Resp(504), _Resp(429), _Resp(200, None), _Resp(200, {"elements": [], "remark": "runtime error: Query timed out"}),
])
def test_descargar_vias_falla_si_los_dos_intentos_fallan(monkeypatch, sin_pausa, respuesta):
    llamadas = []
    monkeypatch.setattr(calles_mapa.httpx, "post", lambda url, **kw: llamadas.append(url) or respuesta)
    with pytest.raises(calles_mapa.OverpassError):
        calles_mapa.descargar_vias((-22.8, -64.4, -22.7, -64.3))
    assert len(llamadas) == 2                                      # un intento y UN reintento


def test_importar_con_el_cliente_real_caido_da_502(client, repo, admin, monkeypatch, sin_pausa):
    _comercio(repo, 0)

    def post(url, **kw):
        raise httpx.ConnectError("sin red")

    monkeypatch.setattr(calles_mapa.httpx, "post", post)
    r = client.post("/admin/calles/importar", headers=_h(admin), json={"ciudad": "bermejo"})
    assert r.status_code == 502 and "OpenStreetMap" in r.json()["detail"]


# ══════════════════════════════════════════════ rendimiento

def test_600_tramos_y_1300_comercios_en_menos_de_un_segundo(client, repo, admin):
    rnd = random.Random(7)
    filas = []
    for i in range(600):
        lat = LAT0 + rnd.uniform(0, 3000) * M_LAT
        lng = LNG0 + rnd.uniform(0, 3000) * M_LNG
        geom = [[round(lat + k * 80 * M_LAT, 5), round(lng + k * rnd.uniform(-20, 20) * M_LNG, 5)] for k in range(6)]
        filas.append({"ciudad_id": BERMEJO, "osm_way_id": i, "nombre": f"Calle {i}", "tipo": "residential",
                      "geom": geom, "longitud_m": int(calles_mapa.largo_m(geom)), "activo": True})
    repo.upsert_calles_tramos(filas)
    for _ in range(1300):
        _comercio(repo, rnd.uniform(0, 3000), rnd.uniform(0, 3000))
    t0 = time.perf_counter()
    r = client.get("/admin/calles/mapa?ciudad=bermejo", headers=_h(admin))
    primera = time.perf_counter() - t0
    assert r.status_code == 200 and len(r.json()["tramos"]) == 600
    assert primera < 1.0, f"{primera:.2f} s"
    t0 = time.perf_counter()
    client.get("/admin/calles/mapa?ciudad=bermejo", headers=_h(admin))        # de la caché
    assert time.perf_counter() - t0 < primera
    estados = {t["estado"] for t in r.json()["tramos"]}
    assert estados & {"parcial", "recorrida"} and "pendiente" in estados      # el cálculo hace algo, no es todo igual


# ══════════════════════════════════════════════ el repo REAL (un cliente PostgREST de mentira)

class _Q:
    def __init__(self, db, tabla):
        self.db, self.tabla, self.pedido = db, tabla, []

    def __getattr__(self, nombre):
        def _llamar(*a, **k):
            self.pedido.append((nombre, a, k))
            return self
        return _llamar

    @property
    def not_(self):
        return self

    def execute(self):
        self.db.consultas.append((self.tabla, self.pedido))
        return type("R", (), {"data": list(self.db.datos.get(self.tabla, []))})()


class _Db:
    def __init__(self, datos=None):
        self.datos, self.consultas = datos or {}, []

    def table(self, tabla):
        return _Q(self, tabla)


def _repo_real(datos=None):
    repo = SupabaseRepo.__new__(SupabaseRepo)
    repo._db = _Db(datos)
    return repo


def test_repo_real_upsert_por_ciudad_y_osm_way_id_de_a_200():
    repo = _repo_real()
    assert repo.upsert_calles_tramos([{"ciudad_id": "c", "osm_way_id": i} for i in range(450)]) == 450
    upserts = [p for _, ped in repo._db.consultas for p in ped if p[0] == "upsert"]
    assert [len(p[1][0]) for p in upserts] == [200, 200, 50]
    assert all(p[2] == {"on_conflict": "ciudad_id,osm_way_id"} for p in upserts)


def test_repo_real_se_queda_con_la_ultima_marca_de_cada_tramo():
    # PostgREST las devuelve de la más nueva a la más vieja
    marcas = [
        {"id": "3", "tramo_id": "a", "estado": "pendiente", "created_at": "3", "calles_tramos": {"ciudad_id": "c"}},
        {"id": "2", "tramo_id": "b", "estado": "recorrida", "created_at": "2", "calles_tramos": {"ciudad_id": "c"}},
        {"id": "1", "tramo_id": "a", "estado": "sin_comercios", "created_at": "1", "calles_tramos": {"ciudad_id": "c"}},
    ]
    out = _repo_real({"calles_marcas": marcas}).list_calles_marcas_ultimas("c")
    assert {m["tramo_id"]: m["estado"] for m in out} == {"a": "pendiente", "b": "recorrida"}
    assert all("calles_tramos" not in m for m in out)


def test_repo_real_get_calle_tramo_con_id_que_no_es_uuid_no_consulta():
    repo = _repo_real()
    assert repo.get_calle_tramo("cualquier-cosa") is None
    assert repo._db.consultas == []


# ══════════════════════════════════════════════ migración 0152

def _sql(carpeta):
    return (RAIZ / carpeta / "0152_calles_tramos.sql").read_text(encoding="utf-8")


def test_0152_igual_en_las_dos_carpetas():
    assert _sql("supabase/migrations") == _sql("selfhost/postgres-init")


def test_0152_privada_idempotente_y_sin_borrado_fisico():
    low = _sql("supabase/migrations").lower()
    assert "create table if not exists public.calles_tramos" in low
    assert "create table if not exists public.calles_marcas" in low
    assert "enable row level security" in low
    assert "to anon" not in low and "to authenticated" not in low
    assert "revoke all on public.calles_tramos from public, anon, authenticated" in low
    assert "revoke all on public.calles_marcas from public, anon, authenticated" in low
    assert "grant all on public.calles_tramos to service_role" in low
    assert "create unique index if not exists" in low and "(ciudad_id, osm_way_id)" in low
    assert "delete from" not in low and "drop table" not in low


def test_0152_en_postgres_real(pg0149):
    """Con `URUKU_PG_TEST_CONTAINER`: la 0152 dos veces seguidas; el backend escribe y lee; anon,
    authenticated y PUBLIC no pueden ni leer ni escribir; el único por (ciudad, vía) frena duplicados."""
    psql = pg0149
    psql("create table ciudades (id uuid primary key default gen_random_uuid(), slug text);"
         "grant select on ciudades to anon, authenticated; grant all on ciudades to service_role;")
    sql = _sql("supabase/migrations")
    psql(sql)
    psql(sql)                                                      # idempotente
    ciudad = psql("insert into ciudades (slug) values ('bermejo') returning id;", rol="service_role").stdout.split()[0]
    tramo = psql(f"""insert into calles_tramos (ciudad_id, osm_way_id, nombre, tipo, geom, longitud_m)
                     values ('{ciudad}', 1, 'Calle Uno', 'residential', '[[-22.7361,-64.3433],[-22.7355,-64.3433]]', 67)
                     returning id;""", rol="service_role").stdout.split()[0]
    psql(f"insert into calles_marcas (tramo_id, estado, nota, actor) values ('{tramo}', 'sin_comercios', 'x', 'a@b');",
         rol="service_role")
    assert psql("select count(*) from calles_marcas where tramo_id = '" + tramo + "';",
                rol="service_role").stdout.strip() == "1"
    # el upsert de PostgREST (ON CONFLICT sobre el único) actualiza en vez de duplicar
    psql(f"""insert into calles_tramos (ciudad_id, osm_way_id, nombre, geom)
             values ('{ciudad}', 1, 'Renombrada', '[[-22.7361,-64.3433],[-22.7355,-64.3433]]')
             on conflict (ciudad_id, osm_way_id) do update set nombre = excluded.nombre;""", rol="service_role")
    assert psql("select count(*), max(nombre) from calles_tramos;", rol="service_role").stdout.strip() == "1|Renombrada"
    # los checks
    assert psql(f"insert into calles_marcas (tramo_id, estado) values ('{tramo}', 'parcial');",
                rol="service_role", check=False).returncode != 0
    assert psql(f"insert into calles_marcas (tramo_id, estado, nota) values ('{tramo}', 'recorrida', '{'x' * 201}');",
                rol="service_role", check=False).returncode != 0
    assert psql(f"insert into calles_tramos (ciudad_id, osm_way_id, geom) values ('{ciudad}', 9, '[[1,2]]');",
                rol="service_role", check=False).returncode != 0
    # anon / authenticated: ni leer ni escribir
    for rol in ("anon", "authenticated"):
        for tabla in ("calles_tramos", "calles_marcas"):
            assert psql(f"select * from {tabla};", rol=rol, check=False).returncode != 0
            assert psql(f"insert into {tabla} default values;", rol=rol, check=False).returncode != 0
            assert psql(f"update {tabla} set id = id;", rol=rol, check=False).returncode != 0
    # RLS activo en las dos
    assert psql("select count(*) from pg_class where relname in ('calles_tramos','calles_marcas') and relrowsecurity;"
                ).stdout.strip() == "2"
