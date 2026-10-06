"""Cargas del día (docs/cargas-del-dia.md, 6/10/2026): qué cargó cada agente,
cuándo y por dónde.

Criterios de la spec: 1 (la carga sin señal sale a la hora del celular), 2 (las
22:00 de Bolivia cuentan en ese día), 3 (corte de tramo en 30 minutos),
4 (`capturado_en` fuera de rango se descarta), 5 (sólo el admin entra).
El resto: ciudad, fecha inválida, metros por tramo, inactivos, historial,
«altas por día» en hora de Bolivia, el repo real y la migración 0138.
"""
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

import pytest
import structlog
from PIL import Image

from app.core import auth
from app.db.repository import SupabaseRepo
from app.services import cargas

DIA = "2026-10-06"
PEDRO = "pedro@uruku.bo"
ANA = "ana@uruku.bo"


# ───────────────────────────────────────────────────────────────── ayudas
def bo(hhmm: str, dia: str = DIA) -> str:
    """Una hora de Bolivia (UTC−4) como el ISO en UTC que guarda la base."""
    local = datetime.fromisoformat(f"{dia}T{hhmm}:00").replace(tzinfo=cargas.BOLIVIA)
    return local.astimezone(timezone.utc).isoformat()


def cargar(repo, hhmm, *, dia=DIA, agente=PEDRO, llegada=None, offline=False, **extra):
    """Siembra un comercio de campo. `hhmm` es la hora de Bolivia de la carga.

    Online: `created_at` = esa hora. Offline: `capturado_en` = esa hora y
    `created_at` = `llegada` (cuando volvió la señal).
    """
    fila = {"cargado_por": agente, "activo": True, "nombre": f"Local {hhmm}",
            "slug": f"local-{hhmm.replace(':', '')}-{len(repo.comercios)}",
            "lat": -22.7361, "lng": -64.3433, **extra}
    if offline:
        fila["capturado_en"] = bo(hhmm, dia)
        fila["created_at"] = llegada or bo("23:00", dia)
    else:
        fila["created_at"] = bo(hhmm, dia)
    return repo.seed_comercio(**fila)


def admin_h():
    return {"Authorization": "Bearer " + auth.make_token("admin@uruku.bo", rol="admin")}


def dia_de(client, fecha=DIA, **params):
    r = client.get("/admin/cargas/dia", headers=admin_h(), params={"fecha": fecha, **params})
    assert r.status_code == 200, r.text
    return r.json()


def agente_de(client, email=PEDRO, **kw):
    (a,) = [a for a in dia_de(client, **kw)["agentes"] if a["agente"] == email]
    return a


# ───────────────────────────────────── criterio 1: la hora del celular manda
def test_una_carga_sin_senal_aparece_a_la_hora_del_celular(client, repo):
    """Cargada a las 10:00, llegó al servidor a las 13:00."""
    cargar(repo, "10:00", offline=True, llegada=bo("13:00"))
    cargar(repo, "10:05", offline=True, llegada=bo("13:00"))
    a = agente_de(client)
    assert a["desde"] == "10:00" and a["hasta"] == "10:05"
    assert [p["hora"] for p in a["puntos"]] == ["10:00", "10:05"]
    assert all(p["hora_del_celular"] and p["subido_tarde"] for p in a["puntos"])
    assert a["por_hora"] == [{"hora": "10", "comercios": 2}]


def test_sin_capturado_en_manda_la_hora_de_llegada(client, repo):
    cargar(repo, "09:30")
    (p,) = agente_de(client)["puntos"]
    assert p["hora"] == "09:30"
    assert p["hora_del_celular"] is False
    assert p["subido_tarde"] is False


def test_subido_tarde_es_mas_de_diez_minutos(client, repo):
    cargar(repo, "10:00", offline=True, llegada=bo("10:10"))   # justo 10: no
    cargar(repo, "10:20", offline=True, llegada=bo("10:31"))   # 11: sí
    p1, p2 = agente_de(client)["puntos"]
    assert p1["subido_tarde"] is False
    assert p2["subido_tarde"] is True


def test_un_comercio_cuenta_en_el_dia_de_su_hora_aunque_llegue_al_dia_siguiente(client, repo):
    cargar(repo, "16:00", offline=True, llegada=bo("08:00", "2026-10-07"))
    assert agente_de(client)["comercios"] == 1
    assert dia_de(client, "2026-10-07")["agentes"] == []


# ───────────────────────────────────── criterio 2: el día es el de Bolivia
def test_las_22_de_bolivia_cuentan_en_ese_dia_y_no_en_el_siguiente(client, repo):
    """22:00 en Bolivia son las 02:00 UTC del día siguiente."""
    c = cargar(repo, "22:00")
    assert c["created_at"].startswith("2026-10-07T02:00")
    assert agente_de(client)["comercios"] == 1
    assert dia_de(client, "2026-10-07")["agentes"] == []


def test_las_00_00_de_bolivia_ya_son_el_dia_nuevo(client, repo):
    cargar(repo, "00:00")
    cargar(repo, "23:59", dia="2026-10-05")
    assert agente_de(client)["comercios"] == 1
    assert agente_de(client, fecha="2026-10-05")["comercios"] == 1


def test_sin_fecha_es_hoy_en_bolivia(client, repo):
    repo.seed_comercio(cargado_por=PEDRO, activo=True, nombre="Ahora",
                       created_at=datetime.now(timezone.utc).isoformat())
    r = client.get("/admin/cargas/dia", headers=admin_h())
    assert r.status_code == 200
    assert r.json()["fecha"] == cargas.hoy_bolivia().isoformat()
    assert [a["agente"] for a in r.json()["agentes"]] == [PEDRO]


# ───────────────────────────────────── criterio 3: tramos con corte en 30 min
def test_31_minutos_son_dos_tramos(client, repo):
    cargar(repo, "10:00")
    cargar(repo, "10:31")
    a = agente_de(client)
    assert [(t["desde"], t["hasta"], t["comercios"]) for t in a["tramos"]] == [
        ("10:00", "10:00", 1), ("10:31", "10:31", 1)]
    assert [p["tramo"] for p in a["puntos"]] == [1, 2]
    assert a["minutos_trabajados"] == 0          # dos tramos de un solo punto
    assert a["puntos"][1]["min_desde_anterior"] == 31


def test_30_minutos_son_un_tramo(client, repo):
    cargar(repo, "10:00")
    cargar(repo, "10:30")
    a = agente_de(client)
    assert a["tramos"] == [{"n": 1, "desde": "10:00", "hasta": "10:30", "minutos": 30, "comercios": 2}]
    assert a["minutos_trabajados"] == 30


def test_minutos_trabajados_es_la_suma_de_los_tramos(client, repo):
    for h in ("09:00", "09:20", "09:40"):        # tramo 1: 40 min
        cargar(repo, h)
    for h in ("14:00", "14:25"):                 # tramo 2: 25 min
        cargar(repo, h)
    a = agente_de(client)
    assert [t["minutos"] for t in a["tramos"]] == [40, 25]
    assert a["minutos_trabajados"] == 65
    assert (a["desde"], a["hasta"], a["comercios"]) == ("09:00", "14:25", 5)


def test_los_puntos_salen_ordenados_por_hora_aunque_lleguen_desordenados(client, repo):
    cargar(repo, "11:00")
    cargar(repo, "09:00")
    cargar(repo, "10:00")
    a = agente_de(client)
    assert [p["hora"] for p in a["puntos"]] == ["09:00", "10:00", "11:00"]
    assert [p["orden"] for p in a["puntos"]] == [1, 2, 3]
    assert a["puntos"][0]["min_desde_anterior"] is None


# ───────────────────────────────────── metros
def test_los_metros_no_suman_el_salto_entre_tramos(client, repo):
    """Dos pares de puntos a ~111 m cada uno; el almuerzo en otra zona no cuenta."""
    cargar(repo, "09:00", lat=-22.7000, lng=-64.3000)
    cargar(repo, "09:10", lat=-22.7010, lng=-64.3000)      # tramo 1: ~111 m
    cargar(repo, "15:00", lat=-22.9000, lng=-64.5000)      # otra zona, 5+ horas después
    cargar(repo, "15:10", lat=-22.9010, lng=-64.5000)      # tramo 2: ~111 m
    a = agente_de(client)
    assert len(a["tramos"]) == 2
    assert 215 <= a["metros"] <= 230                       # 2 × ~111, no 30 km
    p = a["puntos"]
    assert p[0]["m_desde_anterior"] is None
    assert 105 <= p[1]["m_desde_anterior"] <= 117
    assert p[2]["m_desde_anterior"] is None                # primer punto del tramo 2
    assert p[2]["min_desde_anterior"] == 350               # el hueco sí se informa
    assert 105 <= p[3]["m_desde_anterior"] <= 117
    assert a["metros"] == sum(x["m_desde_anterior"] or 0 for x in p)


def test_un_punto_sin_coordenadas_no_suma_metros(client, repo):
    cargar(repo, "09:00", lat=-22.7000, lng=-64.3000)
    cargar(repo, "09:05", lat=None, lng=None)
    cargar(repo, "09:10", lat=-22.7010, lng=-64.3000)
    a = agente_de(client)
    assert a["metros"] == 0
    assert a["puntos"][1]["m_desde_anterior"] is None
    assert len(a["puntos"]) == 3


def test_haversine_conocido():
    # Un grado de latitud ≈ 111,19 km.
    assert cargas.metros_entre(0, 0, 1, 0) == pytest.approx(111_195, rel=0.001)
    assert cargas.metros_entre(-22.7, -64.3, -22.7, -64.3) == 0
    assert cargas.metros_entre(None, 0, 1, 0) is None


# ───────────────────────────────────── el contenido de cada punto
def test_el_punto_trae_foto_rubro_ciudad_y_nombre_del_agente(client, repo):
    cargar(repo, "10:00", portada_thumb_url="https://x/t.jpg", rubros={"nombre": "Ropa", "slug": "ropa"},
           ciudades={"nombre": "Bermejo", "slug": "bermejo"})
    repo.agentes["u1"] = {"id": "u1", "email": PEDRO.upper(), "nombre": "Pedro Pérez", "activo": True}
    a = agente_de(client)
    p = a["puntos"][0]
    assert (p["foto"], p["rubro"], p["ciudad"]) == ("https://x/t.jpg", "Ropa", "Bermejo")
    assert p["slug"] and p["id"] and p["nombre"] == "Local 10:00"
    assert (p["lat"], p["lng"]) == (-22.7361, -64.3433)
    assert a["agente_nombre"] == "Pedro Pérez"


def test_sin_nombre_cargado_el_agente_nombre_es_null(client, repo):
    cargar(repo, "10:00")
    assert agente_de(client)["agente_nombre"] is None


def test_por_hora_cuenta_en_hora_de_bolivia(client, repo):
    for h in ("09:05", "09:50", "11:00"):
        cargar(repo, h)
    assert agente_de(client)["por_hora"] == [
        {"hora": "09", "comercios": 2}, {"hora": "11", "comercios": 1}]


def test_formato_exacto_de_la_respuesta(client, repo):
    cargar(repo, "10:00")
    r = dia_de(client)
    assert set(r) == {"fecha", "agentes"}
    a = r["agentes"][0]
    assert set(a) == {"agente", "agente_nombre", "comercios", "desde", "hasta", "minutos_trabajados",
                      "metros", "tramos", "por_hora", "puntos"}
    assert set(a["tramos"][0]) == {"n", "desde", "hasta", "minutos", "comercios"}
    assert set(a["puntos"][0]) == {"orden", "tramo", "id", "slug", "nombre", "lat", "lng", "hora",
                                   "hora_del_celular", "subido_tarde", "min_desde_anterior",
                                   "m_desde_anterior", "foto", "rubro", "ciudad"}


# ───────────────────────────────────── quién cuenta y quién no
def test_los_inactivos_y_los_sin_agente_no_aparecen(client, repo):
    cargar(repo, "10:00")
    cargar(repo, "10:10", activo=False)
    cargar(repo, "10:20", agente=None)            # importado: sin cargado_por
    cargar(repo, "10:30", agente="")
    a = agente_de(client)
    assert a["comercios"] == 1
    assert len(dia_de(client)["agentes"]) == 1


def test_cada_agente_tiene_lo_suyo(client, repo):
    cargar(repo, "10:00")
    cargar(repo, "10:01")
    cargar(repo, "11:00", agente=ANA)
    r = dia_de(client)
    assert [(a["agente"], a["comercios"]) for a in r["agentes"]] == [(ANA, 1), (PEDRO, 2)]


# ───────────────────────────────────── ciudad
def test_filtra_por_ciudad(client, repo):
    cargar(repo, "10:00", ciudad_id="ciu-1")             # bermejo
    cargar(repo, "10:10", ciudad_id="ciu-tarija")
    cargar(repo, "10:20", ciudad_id="ciu-tarija", agente=ANA)
    sin = dia_de(client)
    assert sum(a["comercios"] for a in sin["agentes"]) == 3
    tarija = dia_de(client, ciudad="tarija")
    assert [(a["agente"], a["comercios"]) for a in tarija["agentes"]] == [(ANA, 1), (PEDRO, 1)]
    bermejo = dia_de(client, ciudad="bermejo")
    assert [(a["agente"], a["comercios"]) for a in bermejo["agentes"]] == [(PEDRO, 1)]


def test_una_ciudad_desconocida_da_lista_vacia_no_500(client, repo):
    cargar(repo, "10:00")
    assert dia_de(client, ciudad="no-existe") == {"fecha": DIA, "agentes": []}
    r = client.get("/admin/cargas/historial", headers=admin_h(), params={"ciudad": "no-existe"})
    assert r.status_code == 200
    assert r.json() == {"items": []}


# ───────────────────────────────────── fecha inválida
@pytest.mark.parametrize("fecha", ["hoy", "2026-13-45", "2026-02-30", "2026-1-5", "06/10/2026",
                                   "20261006", "2026-10-06T10:00"])
def test_fecha_invalida_es_400(client, fecha):
    r = client.get("/admin/cargas/dia", headers=admin_h(), params={"fecha": fecha})
    assert r.status_code == 400
    assert r.json()["detail"] == "Fecha inválida, usá AAAA-MM-DD"


# ───────────────────────────────────── el historial
def test_historial_una_fila_por_dia_y_agente_del_mas_nuevo_al_mas_viejo(client, repo):
    hoy = cargas.hoy_bolivia()
    ayer, antes = (hoy - timedelta(days=1)).isoformat(), (hoy - timedelta(days=3)).isoformat()
    cargar(repo, "09:00", dia=ayer)
    cargar(repo, "09:20", dia=ayer)
    cargar(repo, "15:00", dia=ayer)
    cargar(repo, "10:00", dia=ayer, agente=ANA)
    cargar(repo, "08:00", dia=antes)
    r = client.get("/admin/cargas/historial", headers=admin_h())
    assert r.status_code == 200
    items = r.json()["items"]
    assert [(i["fecha"], i["agente"]) for i in items] == [(ayer, ANA), (ayer, PEDRO), (antes, PEDRO)]
    pedro = items[1]
    assert pedro == {"fecha": ayer, "agente": PEDRO, "agente_nombre": None, "comercios": 3,
                     "desde": "09:00", "hasta": "15:00", "minutos_trabajados": 20,
                     "tramos": 2, "metros": 0}


def test_historial_respeta_dias_y_la_ciudad(client, repo):
    hoy = cargas.hoy_bolivia()
    cargar(repo, "10:00", dia=hoy.isoformat(), ciudad_id="ciu-1")
    cargar(repo, "10:00", dia=(hoy - timedelta(days=5)).isoformat(), ciudad_id="ciu-1")
    cargar(repo, "10:00", dia=hoy.isoformat(), ciudad_id="ciu-tarija", agente=ANA)

    def fechas(**p):
        r = client.get("/admin/cargas/historial", headers=admin_h(), params=p)
        assert r.status_code == 200, r.text
        return [i["fecha"] for i in r.json()["items"]]

    assert len(fechas(dias=365)) == 3
    assert fechas(dias=1) == [hoy.isoformat()] * 2           # sólo hoy: Pedro (bermejo) y Ana (tarija)
    assert len(fechas(dias=5)) == 2                          # hace 5 días queda afuera
    assert len(fechas(dias=6)) == 3
    assert fechas(dias=365, ciudad="tarija") == [hoy.isoformat()]


@pytest.mark.parametrize("dias", [0, 366, "x"])
def test_historial_dias_fuera_de_rango_es_422(client, dias):
    r = client.get("/admin/cargas/historial", headers=admin_h(), params={"dias": dias})
    assert r.status_code == 422


def test_historial_usa_la_hora_del_celular_y_el_dia_de_bolivia(client, repo):
    ayer = (cargas.hoy_bolivia() - timedelta(days=1)).isoformat()
    cargar(repo, "22:30", dia=ayer)                          # 02:30 UTC de hoy
    items = client.get("/admin/cargas/historial", headers=admin_h()).json()["items"]
    assert [i["fecha"] for i in items] == [ayer]


# ───────────────────────────────────── criterio 5: sólo el admin
RUTAS = ["/admin/cargas/dia", f"/admin/cargas/dia?fecha={DIA}", "/admin/cargas/historial"]


@pytest.mark.parametrize("ruta", RUTAS)
def test_sin_token_401(client, ruta):
    assert client.get(ruta).status_code == 401


@pytest.mark.parametrize("ruta", RUTAS)
def test_token_de_agente_no_entra(client, ruta):
    h = {"Authorization": "Bearer " + auth.make_agente_token("agente@bermejolive.com")}
    assert client.get(ruta, headers=h).status_code in (401, 403)


@pytest.mark.parametrize("ruta", RUTAS)
def test_token_de_comercio_no_entra(client, ruta):
    h = {"Authorization": "Bearer " + auth.make_comercio_token("com-1", "x@y.com")}
    assert client.get(ruta, headers=h).status_code in (401, 403)


@pytest.mark.parametrize("ruta", RUTAS)
def test_token_falso_no_entra(client, ruta):
    assert client.get(ruta, headers={"Authorization": "Bearer abc.def.ghi"}).status_code in (401, 403)


# ───────────────────────────────────── criterio 4: capturado_en en el alta
def _login_agente(client):
    r = client.post("/auth/campo/login", json={"email": "agente@bermejolive.com", "password": "campo1234"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _foto():
    buf = BytesIO()
    Image.new("RGB", (10, 10), color="red").save(buf, format="JPEG")
    buf.seek(0)
    return {"foto": ("t.jpg", buf, "image/jpeg")}


def _alta(client, repo, capturado=None):
    data = {"nombre": "Gomería", "rubro_slugs": ["gomeria"], "lat": "-22.7361", "lng": "-64.3433"}
    if capturado is not None:
        data["capturado_en"] = capturado
    with structlog.testing.capture_logs() as logs:
        r = client.post("/campo/comercio", headers=_login_agente(client), data=data, files=_foto())
    assert r.status_code == 200, r.text
    descartes = [e for e in logs if e["event"] == "campo.capturado_en_descartado"]
    return repo.comercios[list(repo.comercios)[-1]], descartes


def _iso(delta):
    return (datetime.now(timezone.utc) + delta).isoformat()


def test_alta_guarda_la_hora_del_celular_si_es_razonable(client, repo):
    hace_2h = datetime.now(timezone.utc) - timedelta(hours=2)
    com, descartes = _alta(client, repo, hace_2h.isoformat())
    assert descartes == []
    assert cargas.parse_ts(com["capturado_en"]) == hace_2h


def test_alta_acepta_el_sufijo_z(client, repo):
    hace_1h = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(microsecond=0)
    com, descartes = _alta(client, repo, hace_1h.strftime("%Y-%m-%dT%H:%M:%SZ"))
    assert descartes == []
    assert cargas.parse_ts(com["capturado_en"]) == hace_1h


def test_alta_acepta_una_hora_con_el_offset_de_bolivia(client, repo):
    hace_1h = (datetime.now(timezone.utc) - timedelta(hours=1)).astimezone(cargas.BOLIVIA)
    com, _ = _alta(client, repo, hace_1h.isoformat())
    assert cargas.parse_ts(com["capturado_en"]) == hace_1h


def test_alta_descarta_un_capturado_en_de_dentro_de_una_hora(client, repo):
    com, descartes = _alta(client, repo, _iso(timedelta(hours=1)))
    assert "capturado_en" not in com or com["capturado_en"] is None
    assert len(descartes) == 1


def test_alta_descarta_un_capturado_en_de_hace_un_mes(client, repo):
    com, descartes = _alta(client, repo, _iso(-timedelta(days=30)))
    assert not com.get("capturado_en")
    assert len(descartes) == 1


def test_alta_descarta_lo_que_no_es_una_fecha(client, repo):
    com, descartes = _alta(client, repo, "ayer a la tarde")
    assert not com.get("capturado_en")
    assert len(descartes) == 1


def test_alta_sin_capturado_en_no_loguea_descarte(client, repo):
    com, descartes = _alta(client, repo)
    assert not com.get("capturado_en")
    assert descartes == []


def test_los_limites_son_siete_dias_y_cinco_minutos():
    ahora = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
    assert cargas.capturado_valido(ahora - timedelta(days=7, seconds=-1), ahora)
    assert not cargas.capturado_valido(ahora - timedelta(days=7, seconds=1), ahora)
    assert cargas.capturado_valido(ahora + timedelta(minutes=5), ahora)
    assert not cargas.capturado_valido(ahora + timedelta(minutes=5, seconds=1), ahora)
    assert not cargas.capturado_valido(None, ahora)


# ───────────────────────────────────── «altas por día» en hora de Bolivia
def test_altas_por_dia_corta_en_hora_de_bolivia(repo):
    cargar(repo, "21:00")              # 01:00 UTC del 7: en Bolivia sigue siendo el 6
    cargar(repo, "10:00")
    cargar(repo, "00:30", dia="2026-10-07")   # 04:30 UTC del 7
    dias = {d["dia"]: d["altas"] for d in repo.altas_por_dia(365)}
    assert dias == {"2026-10-07": 1, "2026-10-06": 2}


# ───────────────────────────────────── piezas puras
def test_limites_de_un_dia_de_bolivia_en_utc():
    desde, hasta = cargas.limites_dia_utc(datetime(2026, 10, 6).date())
    assert cargas.iso_z(desde) == "2026-10-06T04:00:00Z"
    assert cargas.iso_z(hasta) == "2026-10-07T04:00:00Z"


def test_hora_de_carga_prefiere_la_del_celular():
    h, celular = cargas.hora_de_carga({"capturado_en": "2026-10-06T14:00:00Z",
                                       "created_at": "2026-10-06T17:00:00+00:00"})
    assert celular and h.hour == 14
    h, celular = cargas.hora_de_carga({"capturado_en": None, "created_at": "2026-10-06T17:00:00+00:00"})
    assert not celular and h.hour == 17
    assert cargas.hora_de_carga({}) == (None, False)


def test_timestamp_de_postgrest_con_microsegundos():
    assert cargas.parse_ts("2026-10-06T14:00:00.123456+00:00").microsecond == 123456
    assert cargas.parse_ts("basura") is None
    assert cargas.parse_ts(None) is None


# ───────────────────────────────────── el repo real (consulta PostgREST)
class _Consulta:
    """Un query builder de mentira: anota lo que se le pide y entrega páginas."""

    def __init__(self, filas):
        self.filas, self.llamadas, self.rangos = filas, [], []

    def __getattr__(self, nombre):
        if nombre == "not_":
            self.llamadas.append(("not_",))
            return self

        def _llamar(*a, **kw):
            if nombre == "range":
                self.rangos.append(a)
            else:
                self.llamadas.append((nombre, *a))
            return self
        return _llamar

    def execute(self):
        ini, fin = self.rangos[-1]

        class R:
            data = self.filas[ini:fin + 1]
        return R()


class _Db:
    def __init__(self, filas):
        self.q = _Consulta(filas)

    def table(self, nombre):
        assert nombre == "comercios"
        return self.q


def _repo_real(filas):
    r = SupabaseRepo.__new__(SupabaseRepo)
    r._db = _Db(filas)
    return r


def test_el_repo_real_arma_el_filtro_y_pagina_de_a_mil():
    filas = [{"id": str(i)} for i in range(2300)]
    repo = _repo_real(filas)
    desde, hasta = cargas.limites_dia_utc(datetime(2026, 10, 6).date())
    out = repo.list_cargas_de_agentes(desde, hasta, "ciu-1")
    assert len(out) == 2300                                   # PostgREST corta en 1000: se pagina
    assert repo._db.q.rangos == [(0, 999), (1000, 1999), (2000, 2999)]
    llamadas = repo._db.q.llamadas
    (or_,) = {c[1] for c in llamadas if c[0] == "or_"}         # el mismo filtro en cada página
    assert or_ == ("and(capturado_en.gte.2026-10-06T04:00:00Z,capturado_en.lt.2026-10-07T04:00:00Z),"
                      "and(capturado_en.is.null,created_at.gte.2026-10-06T04:00:00Z,"
                      "created_at.lt.2026-10-07T04:00:00Z)")
    assert "+" not in or_
    assert ("eq", "activo", True) in llamadas
    assert ("eq", "ciudad_id", "ciu-1") in llamadas
    assert ("is_", "cargado_por", "null") in llamadas
    sel = next(c for c in llamadas if c[0] == "select")
    for col in ("capturado_en", "cargado_por", "portada_thumb_url", "rubros!comercios_rubro_id_fkey(nombre, slug)",
                "ciudades(nombre, slug)"):
        assert col in sel[1]


def test_el_repo_real_sin_ciudad_no_filtra_por_ciudad():
    repo = _repo_real([])
    desde, hasta = cargas.limites_dia_utc(datetime(2026, 10, 6).date())
    assert repo.list_cargas_de_agentes(desde, hasta) == []
    assert not [c for c in repo._db.q.llamadas if c[:2] == ("eq", "ciudad_id")]


# ───────────────────────────────────── la migración
def _sql(carpeta):
    raiz = Path(__file__).resolve().parents[2]
    return (raiz / carpeta / "0138_cargas_hora_del_celular.sql").read_text(encoding="utf-8")


def test_la_migracion_0138_es_idempotente_y_esta_en_los_dos_lados():
    sql = _sql("supabase/migrations")
    assert sql == _sql("selfhost/postgres-init")
    assert "add column if not exists capturado_en timestamptz" in sql
    assert "create index if not exists" in sql and "where cargado_por is not null" in sql
    assert "comment on column comercios.capturado_en" in sql


def test_alta_sin_la_columna_reintenta_sin_la_hora_del_celular(client, repo, monkeypatch):
    """Backend desplegado antes que la 0138 (o PostgREST sin recargar el
    esquema): el insert con `capturado_en` falla. El comercio igual se guarda;
    se pierde sólo la hora del celular."""
    original = repo.crear_comercio
    intentos = []

    def crear(row):
        intentos.append(dict(row))
        if "capturado_en" in row:
            raise Exception("PGRST204: Could not find the 'capturado_en' column of 'comercios' in the schema cache")
        return original(row)

    monkeypatch.setattr(repo, "crear_comercio", crear)
    with structlog.testing.capture_logs() as logs:
        r = client.post("/campo/comercio", headers=_login_agente(client),
                        data={"nombre": "Gomería", "lat": "-22.7361", "lng": "-64.3433",
                              "capturado_en": _iso(-timedelta(minutes=5))}, files=_foto())
    assert r.status_code == 200, r.text
    assert len(intentos) == 2 and "capturado_en" not in intentos[1]
    assert any(e["event"] == "campo.capturado_en_sin_columna" for e in logs)


def test_otro_error_del_insert_no_se_tapa(client, repo, monkeypatch):
    def crear(row):
        raise RuntimeError("se cayó la base")

    monkeypatch.setattr(repo, "crear_comercio", crear)
    with pytest.raises(RuntimeError, match="se cayó la base"):
        client.post("/campo/comercio", headers=_login_agente(client),
                    data={"nombre": "Gomería", "lat": "-22.7361", "lng": "-64.3433",
                          "capturado_en": _iso(-timedelta(minutes=5))}, files=_foto())
