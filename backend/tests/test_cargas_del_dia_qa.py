"""QA de «Cargas del día» (docs/cargas-del-dia.md): lo que test_cargas_del_dia.py no cubre.

Criterios 1..5 de la spec de punta a punta (alta -> panel), bordes de hora
(00:00 / 23:59 de Bolivia, segundos, offsets, hora sin zona), tramos al segundo,
parámetros fuera de rango, quién puede entrar y el alta sin `capturado_en`.

Los tests marcados `xfail(strict=True)` documentan un BUG ABIERTO: describen el
comportamiento ESPERADO y hoy fallan. Cuando se arregle el código, el xfail
estricto avisa (XPASS) para que se saque la marca.
"""
from datetime import datetime, timedelta, timezone
from io import BytesIO

import pytest
import structlog
from PIL import Image

from app.core import auth
from app.services import cargas

DIA = "2026-10-06"
PEDRO = "pedro@uruku.bo"
ANA = "ana@uruku.bo"
UTC = timezone.utc


# ───────────────────────────────────────────────────────────────── ayudas
def iso_bo(fecha_hora: str) -> str:
    """'2026-10-06T23:59:59' (hora de Bolivia) -> ISO en UTC, con segundos."""
    return datetime.fromisoformat(fecha_hora).replace(tzinfo=cargas.BOLIVIA).astimezone(UTC).isoformat()


def sembrar(repo, fecha_hora, *, agente=PEDRO, offline=False, llegada=None, **extra):
    """Un comercio de campo. `fecha_hora` = la hora de Bolivia de la carga (con segundos).

    offline=True: va en `capturado_en` y `created_at` = `llegada` (por defecto 5 días después).
    """
    fila = {"cargado_por": agente, "activo": True, "nombre": f"L {fecha_hora[-8:]}",
            "slug": f"l-{len(repo.comercios)}", "lat": -22.7361, "lng": -64.3433, **extra}
    if offline:
        fila["capturado_en"] = iso_bo(fecha_hora)
        fila["created_at"] = llegada or iso_bo(fecha_hora.replace(fecha_hora[:10], "2026-10-11"))
    else:
        fila["created_at"] = iso_bo(fecha_hora)
    return repo.seed_comercio(**fila)


def admin_h():
    return {"Authorization": "Bearer " + auth.make_token("admin@uruku.bo", rol="admin")}


def dia(client, fecha=DIA, **params):
    r = client.get("/admin/cargas/dia", headers=admin_h(), params={"fecha": fecha, **params})
    assert r.status_code == 200, r.text
    return r.json()


def agentes_de(client, fecha=DIA):
    return {a["agente"]: a for a in dia(client, fecha)["agentes"]}


# ───────────────────────── criterio 1, de punta a punta: alta (sin señal) -> panel
def _login_agente(client):
    r = client.post("/auth/campo/login", json={"email": "agente@bermejolive.com", "password": "campo1234"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _foto():
    buf = BytesIO()
    Image.new("RGB", (10, 10), color="red").save(buf, format="JPEG")
    buf.seek(0)
    return {"foto": ("t.jpg", buf, "image/jpeg")}


def _alta(client, repo, capturado=None, headers=None, con_foto=True):
    data = {"nombre": "Gomería", "rubro_slugs": ["gomeria"], "lat": "-22.7361", "lng": "-64.3433"}
    if capturado is not None:
        data["capturado_en"] = capturado
    with structlog.testing.capture_logs() as logs:
        r = client.post("/campo/comercio", headers=headers or _login_agente(client), data=data,
                        files=_foto() if con_foto else None)
    assert r.status_code == 200, r.text
    descartes = [e for e in logs if e["event"] == "campo.capturado_en_descartado"]
    return repo.comercios[list(repo.comercios)[-1]], descartes


def test_criterio1_e2e_alta_cargada_hace_3h_aparece_a_esa_hora_y_no_a_la_de_llegada(client, repo):
    """El celular guardó a las (ahora - 3 h) y la carga recién llega al servidor.
    El panel tiene que mostrar la hora del celular y marcar «subido tarde»."""
    capturado = (datetime.now(UTC) - timedelta(hours=3)).replace(microsecond=0)
    com, _ = _alta(client, repo, capturado.isoformat())
    com["created_at"] = datetime.now(UTC).isoformat()          # lo que pone la base al insertar
    fecha = cargas.dia_bolivia(capturado).isoformat()
    (a,) = [x for x in dia(client, fecha)["agentes"] if x["agente"] == com["cargado_por"]]
    (p,) = a["puntos"]
    assert p["hora"] == cargas.hhmm(capturado)
    assert p["hora_del_celular"] is True and p["subido_tarde"] is True
    assert a["desde"] == a["hasta"] == cargas.hhmm(capturado)


def test_criterio1_e2e_diez_altas_en_cola_llegan_juntas_pero_salen_espaciadas(client, repo):
    """La cola sube 10 comercios en el mismo minuto; las horas del celular están
    espaciadas 20 min: tiene que verse UN tramo de 3 h 00, no un minuto de trabajo."""
    base = datetime(2026, 10, 6, 9, 0, tzinfo=cargas.BOLIVIA)
    llegada = datetime(2026, 10, 6, 18, 0, tzinfo=cargas.BOLIVIA)
    for i in range(10):
        sembrar(repo, (base + timedelta(minutes=20 * i)).strftime("%Y-%m-%dT%H:%M:%S"),
                offline=True, llegada=llegada.astimezone(UTC).isoformat())
    a = agentes_de(client)[PEDRO]
    assert a["comercios"] == 10
    assert (a["desde"], a["hasta"]) == ("09:00", "12:00")
    assert a["minutos_trabajados"] == 180
    assert len(a["tramos"]) == 1
    assert all(p["subido_tarde"] for p in a["puntos"])


def test_sin_capturado_en_se_ve_amontonado_y_no_marca_subido_tarde(client, repo):
    """Lo anterior al 6/10: sin `capturado_en`, la hora es la de llegada (el aviso fijo lo explica)."""
    for s in (0, 5, 10):
        sembrar(repo, f"2026-10-06T18:00:{s:02d}")
    a = agentes_de(client)[PEDRO]
    assert a["minutos_trabajados"] == 0 and len(a["tramos"]) == 1
    assert not any(p["subido_tarde"] or p["hora_del_celular"] for p in a["puntos"])


# ───────────────────────── criterio 2: el día de Bolivia, en los bordes
@pytest.mark.parametrize("offline", [False, True])
def test_23_59_59_es_del_dia_y_00_00_00_es_del_siguiente(client, repo, offline):
    sembrar(repo, "2026-10-06T23:59:59", offline=offline)
    sembrar(repo, "2026-10-07T00:00:00", offline=offline)
    sembrar(repo, "2026-10-06T00:00:00", offline=offline, agente=ANA)
    sembrar(repo, "2026-10-05T23:59:59", offline=offline, agente=ANA)
    d6, d7, d5 = agentes_de(client), agentes_de(client, "2026-10-07"), agentes_de(client, "2026-10-05")
    assert (d6[PEDRO]["comercios"], d6[ANA]["comercios"]) == (1, 1)
    assert d6[PEDRO]["hasta"] == "23:59" and d6[ANA]["desde"] == "00:00"
    assert d7[PEDRO]["comercios"] == 1 and d7[PEDRO]["desde"] == "00:00" and ANA not in d7
    assert d5[ANA]["comercios"] == 1 and d5[ANA]["hasta"] == "23:59" and PEDRO not in d5


def test_el_limite_utc_04_00_separa_los_dias(client, repo):
    """03:59:59Z del 7 = 23:59:59 del 6 en Bolivia; 04:00:00Z = 00:00:00 del 7."""
    repo.seed_comercio(cargado_por=PEDRO, activo=True, nombre="a", lat=1, lng=1, created_at="2026-10-07T03:59:59+00:00")
    repo.seed_comercio(cargado_por=PEDRO, activo=True, nombre="b", lat=1, lng=1, created_at="2026-10-07T04:00:00+00:00")
    assert agentes_de(client)[PEDRO]["comercios"] == 1
    assert agentes_de(client, "2026-10-07")[PEDRO]["comercios"] == 1


def test_un_tramo_no_cruza_la_medianoche(client, repo):
    """23:50 y 00:10 están a 20 min pero son de dias distintos: cada dia tiene su fila y su tramo."""
    sembrar(repo, "2026-10-06T23:50:00")
    sembrar(repo, "2026-10-07T00:10:00")
    assert agentes_de(client)[PEDRO]["tramos"] == [
        {"n": 1, "desde": "23:50", "hasta": "23:50", "minutos": 0, "comercios": 1}]
    assert agentes_de(client, "2026-10-07")[PEDRO]["comercios"] == 1


def test_offline_capturado_ayer_y_subido_hoy_cuenta_ayer_tambien_en_el_historial(client, repo):
    hoy = cargas.hoy_bolivia()
    ayer = hoy - timedelta(days=1)
    c = sembrar(repo, f"{ayer.isoformat()}T22:00:00", offline=True, llegada=cargas.ahora_utc().isoformat())
    assert c["created_at"] > c["capturado_en"]
    items = client.get("/admin/cargas/historial", headers=admin_h(), params={"dias": 3}).json()["items"]
    assert [(i["fecha"], i["comercios"]) for i in items] == [(ayer.isoformat(), 1)]


def test_historial_dias_1_incluye_hoy_hasta_las_23_59_y_deja_afuera_las_23_59_de_ayer(client, repo):
    hoy = cargas.hoy_bolivia()
    ayer = hoy - timedelta(days=1)
    sembrar(repo, f"{ayer.isoformat()}T23:59:59")
    sembrar(repo, f"{hoy.isoformat()}T00:00:00", agente=ANA)
    sembrar(repo, f"{hoy.isoformat()}T23:59:59")
    items = client.get("/admin/cargas/historial", headers=admin_h(), params={"dias": 1}).json()["items"]
    assert [(i["fecha"], i["agente"], i["comercios"]) for i in items] == [
        (hoy.isoformat(), ANA, 1), (hoy.isoformat(), PEDRO, 1)]


# ───────────────────────── criterio 3: corte de tramo, al segundo
def test_30_minutos_y_un_segundo_es_otro_tramo_y_30_00_es_el_mismo(client, repo):
    sembrar(repo, "2026-10-06T10:00:00")
    sembrar(repo, "2026-10-06T10:30:00")                       # +30:00 exacto -> mismo tramo
    sembrar(repo, "2026-10-06T11:00:01")                       # +30:01 -> tramo nuevo
    a = agentes_de(client)[PEDRO]
    assert [p["tramo"] for p in a["puntos"]] == [1, 1, 2]
    assert [t["comercios"] for t in a["tramos"]] == [2, 1]


def test_el_corte_usa_la_hora_del_celular_no_la_de_llegada(client, repo):
    """Llegan con 1 minuto de diferencia, pero se cargaron con 2 horas."""
    sembrar(repo, "2026-10-06T10:00:00", offline=True, llegada=iso_bo("2026-10-06T18:00:00"))
    sembrar(repo, "2026-10-06T12:00:00", offline=True, llegada=iso_bo("2026-10-06T18:01:00"))
    assert [p["tramo"] for p in agentes_de(client)[PEDRO]["puntos"]] == [1, 2]


def test_el_corte_es_por_agente_no_global(client, repo):
    sembrar(repo, "2026-10-06T10:00:00")
    sembrar(repo, "2026-10-06T10:20:00", agente=ANA)
    sembrar(repo, "2026-10-06T10:40:00")                       # Pedro: 40 min desde la suya, Ana en el medio
    a = agentes_de(client)
    assert [p["tramo"] for p in a[PEDRO]["puntos"]] == [1, 2]
    assert len(a[ANA]["tramos"]) == 1


# ───────────────────────── criterio 4: capturado_en en el alta, bordes
def test_alta_acepta_hace_6d23h_y_descarta_hace_7d1h(client, repo):
    ok, d_ok = _alta(client, repo, (datetime.now(UTC) - timedelta(days=6, hours=23)).isoformat())
    assert ok.get("capturado_en") and d_ok == []
    mal, d_mal = _alta(client, repo, (datetime.now(UTC) - timedelta(days=7, hours=1)).isoformat())
    assert not mal.get("capturado_en") and len(d_mal) == 1


def test_alta_acepta_4_minutos_en_el_futuro_y_descarta_6(client, repo):
    ok, d_ok = _alta(client, repo, (datetime.now(UTC) + timedelta(minutes=4)).isoformat())
    assert ok.get("capturado_en") and d_ok == []
    mal, d_mal = _alta(client, repo, (datetime.now(UTC) + timedelta(minutes=6)).isoformat())
    assert not mal.get("capturado_en") and len(d_mal) == 1


def test_alta_descarta_el_futuro_de_un_dia_y_de_un_ano(client, repo):
    for delta in (timedelta(days=1), timedelta(days=365)):
        com, d = _alta(client, repo, (datetime.now(UTC) + delta).isoformat())
        assert not com.get("capturado_en") and len(d) == 1


@pytest.mark.parametrize("basura", [
    "", "   ", "null", "undefined", "NaN", "0", "1759770000", "2026-13-45T10:00:00Z",
    "2026-10-06T10:00:00+25:00", "<script>alert(1)</script>", "'; drop table comercios; --",
    "9" * 500, "../../etc/passwd", "2026-10-06T10:00:00Z\n\rX-Inyectado: 1",
])
def test_alta_con_capturado_en_basura_no_rompe_y_no_guarda_nada(client, repo, basura):
    com, descartes = _alta(client, repo, basura)
    assert not com.get("capturado_en")
    if basura.strip():
        assert len(descartes) == 1
        assert len(descartes[0]["capturado_en"]) <= 40        # el log no se llena con 500 caracteres
    else:
        assert descartes == []


def test_alta_con_offset_distinto_de_z_guarda_el_mismo_instante(client, repo):
    """'-04:00' (Bolivia) y '+00:00' son el mismo instante: se guarda con zona, sin correrlo."""
    instante = (datetime.now(UTC) - timedelta(hours=2)).replace(microsecond=0)
    for texto in (instante.astimezone(cargas.BOLIVIA).isoformat(),
                  instante.astimezone(timezone(timedelta(hours=5, minutes=30))).isoformat()):
        com, d = _alta(client, repo, texto)
        assert d == []
        assert cargas.parse_ts(com["capturado_en"]) == instante


def test_alta_con_hora_sin_zona_se_toma_como_utc(client, repo):
    """DECISIÓN DOCUMENTADA (parse_ts): una hora sin zona se toma como UTC. El celular manda
    siempre `toISOString()` (con Z), así que no ocurre; pero si algún cliente mandara la hora
    LOCAL sin zona, la carga se correría 4 h (09:00 de Bolivia -> 05:00 en el panel)."""
    local_bo = (datetime.now(cargas.BOLIVIA) - timedelta(hours=2)).replace(microsecond=0, tzinfo=None)
    com, d = _alta(client, repo, local_bo.isoformat())          # sin zona
    guardado = cargas.parse_ts(com["capturado_en"])
    assert guardado.tzinfo is not None
    assert guardado.replace(tzinfo=None) == local_bo           # tratada como UTC
    assert guardado != local_bo.replace(tzinfo=cargas.BOLIVIA)  # NO como hora de Bolivia


def test_alta_sin_capturado_en_funciona_y_no_manda_la_clave_a_la_base(client, repo):
    """Compatibilidad: una app vieja (sin el campo) o una base sin la 0138 siguen andando."""
    com, descartes = _alta(client, repo, None)
    assert "capturado_en" not in com
    assert descartes == []
    assert com["cargado_por"] and com["fuente"] == "campo"


def test_alta_sin_capturado_en_ni_foto_funciona(client, repo):
    com, _ = _alta(client, repo, None, con_foto=False)
    assert "capturado_en" not in com


def test_alta_con_dos_capturado_en_no_rompe(client, repo):
    r = client.post("/campo/comercio", headers=_login_agente(client),
                    data={"nombre": "X", "rubro_slugs": ["otros"], "lat": "-22.7", "lng": "-64.3",
                          "capturado_en": [(datetime.now(UTC) - timedelta(hours=1)).isoformat(), "basura"]},
                    files=_foto())
    assert r.status_code == 200, r.text


# ───────────────────────── criterio 5: sólo el admin entra
RUTAS = ["/admin/cargas/dia", f"/admin/cargas/dia?fecha={DIA}", "/admin/cargas/historial",
         "/admin/cargas/historial?dias=7&ciudad=bermejo"]


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("ruta", RUTAS)
@pytest.mark.parametrize("rol", ["moderador", "publicador"])
def test_otros_roles_del_equipo_no_entran(client, ruta, rol):
    assert client.get(ruta, headers=_bearer(auth.make_token("x@uruku.bo", rol=rol))).status_code == 403


@pytest.mark.parametrize("ruta", RUTAS)
def test_token_de_comprador_no_entra(client, ruta):
    assert client.get(ruta, headers=_bearer(auth.make_usuario_token("u1", "59171234567"))).status_code in (401, 403)


@pytest.mark.parametrize("ruta", RUTAS)
def test_rol_admin_en_el_token_sin_permisos_no_se_inventa(client, ruta):
    """Un token con `rol: agente` pero con la lista de permisos vacía no entra."""
    assert client.get(ruta, headers=_bearer(auth.make_token("a@uruku.bo", rol="agente", permisos=[]))).status_code == 403


@pytest.mark.parametrize("ruta", RUTAS)
def test_token_vencido_o_firmado_con_otra_clave_no_entra(client, ruta):
    import jwt as pyjwt
    base = {"sub": "a@x", "email": "a@x", "rol": "admin", "roles": ["admin"], "permisos": ["*"]}
    vencido = pyjwt.encode({**base, "exp": int((datetime.now(UTC) - timedelta(hours=1)).timestamp())},
                           auth.settings.jwt_secret, algorithm="HS256")
    ajeno = pyjwt.encode({**base, "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp())},
                         "otra-clave", algorithm="HS256")
    sin_firma = pyjwt.encode({**base}, key=None, algorithm="none")
    for t in (vencido, ajeno, sin_firma):
        assert client.get(ruta, headers=_bearer(t)).status_code == 401


@pytest.mark.parametrize("ruta", RUTAS)
def test_cabecera_authorization_mal_formada_es_401(client, ruta):
    for h in ({"Authorization": "Basic abc"}, {"Authorization": "Bearer"}, {"Authorization": ""}):
        assert client.get(ruta, headers=h).status_code == 401


def test_el_admin_entra(client):
    assert client.get("/admin/cargas/dia", headers=admin_h()).status_code == 200
    assert client.get("/admin/cargas/historial", headers=admin_h()).status_code == 200


@pytest.mark.parametrize("metodo", ["post", "put", "delete", "patch"])
def test_las_rutas_son_de_solo_lectura(client, metodo):
    assert getattr(client, metodo)("/admin/cargas/dia", headers=admin_h()).status_code == 405
    assert getattr(client, metodo)("/admin/cargas/historial", headers=admin_h()).status_code == 405


# ───────────────────────── parámetros
@pytest.mark.parametrize("dias", [0, -1, 366, 1000, "x", "1.5", ""])
def test_historial_dias_invalido_es_422(client, dias):
    assert client.get("/admin/cargas/historial", headers=admin_h(), params={"dias": dias}).status_code == 422


@pytest.mark.parametrize("dias", [1, 365])
def test_historial_dias_en_los_extremos_es_valido(client, dias):
    assert client.get("/admin/cargas/historial", headers=admin_h(), params={"dias": dias}).status_code == 200


def test_ciudad_con_caracteres_raros_no_rompe(client, repo):
    sembrar(repo, "2026-10-06T10:00:00")
    for ciudad in ("bermejo,or=(id.gt.0)", "' or 1=1 --", "../..", "a" * 500, "%00", "bermejo&fecha=2000-01-01"):
        r = client.get("/admin/cargas/dia", headers=admin_h(), params={"fecha": DIA, "ciudad": ciudad})
        assert r.status_code == 200, (ciudad, r.text)
        assert r.json()["fecha"] == DIA                          # no se coló otro parámetro


def test_fecha_con_espacios_y_unicode_es_400_no_500(client):
    for f in ("２０２６-10-06", "2026-10-06 ", " 2026-10-06", "2026/10/06", "-2026-10-0", "٢٠٢٦-١٠-٠٦"):
        r = client.get("/admin/cargas/dia", headers=admin_h(), params={"fecha": f})
        assert r.status_code in (200, 400), (f, r.status_code)
        assert r.status_code != 500


@pytest.mark.parametrize("fecha", ["2999-01-01", "0001-01-01", "2019-12-31", "2101-01-01"])
def test_fecha_fuera_de_2020_2100_es_invalida(client, fecha):
    r = client.get("/admin/cargas/dia", headers=admin_h(), params={"fecha": fecha})
    assert r.status_code == 400


@pytest.mark.parametrize("fecha", ["2020-01-01", "2100-12-31"])
def test_los_bordes_del_rango_valen(client, fecha):
    assert dia(client, fecha) == {"fecha": fecha, "agentes": []}


def test_BUG_fecha_9999_12_31_no_debe_ser_500(client):
    r = client.get("/admin/cargas/dia", headers=admin_h(), params={"fecha": "9999-12-31"})
    assert r.status_code in (200, 400)


def test_fecha_vacia_se_toma_como_hoy(client):
    """Documenta: `fecha=` (vacía) no es 400 sino «hoy»."""
    r = client.get("/admin/cargas/dia?fecha=", headers=admin_h())
    assert r.status_code == 200 and r.json()["fecha"] == cargas.hoy_bolivia().isoformat()


# ───────────────────────── casos borde del cálculo
def test_dos_cargas_con_la_misma_hora_van_en_un_tramo_y_en_orden_estable(client, repo):
    a1 = sembrar(repo, "2026-10-06T10:00:00", id="aaa", lat=-22.70, lng=-64.30)
    b1 = sembrar(repo, "2026-10-06T10:00:00", id="bbb", lat=-22.71, lng=-64.30)
    for _ in range(3):                                           # el orden no depende del azar
        a = agentes_de(client)[PEDRO]
        assert [p["id"] for p in a["puntos"]] == ["aaa", "bbb"]
    assert a["puntos"][1]["min_desde_anterior"] == 0
    assert 1100 <= a["puntos"][1]["m_desde_anterior"] <= 1120
    assert len(a["tramos"]) == 1 and a["minutos_trabajados"] == 0 and a["comercios"] == 2
    assert a1["id"] != b1["id"]


def test_un_agente_con_un_solo_punto(client, repo):
    sembrar(repo, "2026-10-06T10:07:00")
    a = agentes_de(client)[PEDRO]
    assert (a["comercios"], a["desde"], a["hasta"]) == (1, "10:07", "10:07")
    assert (a["minutos_trabajados"], a["metros"]) == (0, 0)
    assert a["tramos"] == [{"n": 1, "desde": "10:07", "hasta": "10:07", "minutos": 0, "comercios": 1}]
    (p,) = a["puntos"]
    assert p["min_desde_anterior"] is None and p["m_desde_anterior"] is None and p["orden"] == 1
    assert a["por_hora"] == [{"hora": "10", "comercios": 1}]


def test_punto_sin_coordenadas_en_el_medio_no_suma_ni_inventa_metros(client, repo):
    """A (con GPS) -> B (sin GPS) -> C (con GPS), todo en un tramo. Spec: los puntos sin
    lat/lng no suman. Hoy el tramo A->C tampoco se cuenta (se subestima el recorrido):
    se documenta, no es un error del código sino de la regla."""
    sembrar(repo, "2026-10-06T09:00:00", lat=-22.7000, lng=-64.3000)
    sembrar(repo, "2026-10-06T09:05:00", lat=None, lng=None)
    sembrar(repo, "2026-10-06T09:10:00", lat=-22.7100, lng=-64.3000)
    a = agentes_de(client)[PEDRO]
    assert [p["m_desde_anterior"] for p in a["puntos"]] == [None, None, None]
    assert a["metros"] == 0
    assert [p["tramo"] for p in a["puntos"]] == [1, 1, 1]
    assert a["puntos"][2]["min_desde_anterior"] == 5


def test_punto_con_solo_lat_o_solo_lng_no_suma(client, repo):
    sembrar(repo, "2026-10-06T09:00:00", lat=-22.7000, lng=-64.3000)
    sembrar(repo, "2026-10-06T09:05:00", lat=-22.7100, lng=None)
    sembrar(repo, "2026-10-06T09:10:00", lat=None, lng=-64.3000)
    assert agentes_de(client)[PEDRO]["metros"] == 0


def test_coordenadas_como_texto_no_rompen(client, repo):
    """PostgREST devuelve numeric como número, pero un string no debe tirar 500."""
    sembrar(repo, "2026-10-06T09:00:00", lat="-22.7000", lng="-64.3000")
    sembrar(repo, "2026-10-06T09:05:00", lat="basura", lng="x")
    assert agentes_de(client)[PEDRO]["metros"] == 0


def test_el_primer_punto_del_dia_sin_gps_no_impide_medir_el_resto(client, repo):
    sembrar(repo, "2026-10-06T09:00:00", lat=None, lng=None)
    sembrar(repo, "2026-10-06T09:05:00", lat=-22.7000, lng=-64.3000)
    sembrar(repo, "2026-10-06T09:10:00", lat=-22.7010, lng=-64.3000)
    assert 105 <= agentes_de(client)[PEDRO]["metros"] <= 117


def test_hora_con_offset_menos_04_00_en_la_base(client, repo):
    """PostgREST puede devolver `-04:00` si la sesión está en esa zona: mismo instante."""
    repo.seed_comercio(cargado_por=PEDRO, activo=True, nombre="a", lat=1, lng=1,
                       created_at="2026-10-06T23:30:00-04:00")
    repo.seed_comercio(cargado_por=PEDRO, activo=True, nombre="b", lat=1, lng=1,
                       capturado_en="2026-10-06T23:40:00-04:00", created_at="2026-10-07T09:00:00-04:00")
    a = agentes_de(client)[PEDRO]
    assert (a["desde"], a["hasta"], a["comercios"]) == ("23:30", "23:40", 2)
    assert agentes_de(client, "2026-10-07") == {}


def test_hora_sin_zona_en_la_base_se_toma_como_utc(client, repo):
    """DECISIÓN DOCUMENTADA: un timestamp sin zona se toma como UTC (PostgREST siempre manda zona)."""
    repo.seed_comercio(cargado_por=PEDRO, activo=True, nombre="a", lat=1, lng=1, created_at="2026-10-06T14:00:00")
    assert agentes_de(client)[PEDRO]["desde"] == "10:00"


def test_filas_sin_ninguna_hora_o_con_hora_ilegible_se_ignoran(client, repo):
    repo.seed_comercio(cargado_por=PEDRO, activo=True, nombre="sin hora", lat=1, lng=1)
    repo.seed_comercio(cargado_por=PEDRO, activo=True, nombre="rota", lat=1, lng=1, created_at="ayer")
    sembrar(repo, "2026-10-06T10:00:00")
    assert agentes_de(client)[PEDRO]["comercios"] == 1


def test_capturado_en_ilegible_cae_a_created_at(client, repo):
    repo.seed_comercio(cargado_por=PEDRO, activo=True, nombre="a", lat=1, lng=1,
                       capturado_en="basura", created_at=iso_bo("2026-10-06T10:00:00"))
    (p,) = agentes_de(client)[PEDRO]["puntos"]
    assert p["hora"] == "10:00" and p["hora_del_celular"] is False


def test_el_comercio_inactivo_o_sin_cargado_por_no_suma_en_nada(client, repo):
    sembrar(repo, "2026-10-06T10:00:00")
    sembrar(repo, "2026-10-06T10:05:00", activo=False)
    sembrar(repo, "2026-10-06T10:10:00", agente=None)
    sembrar(repo, "2026-10-06T10:15:00", agente="   ")
    a = agentes_de(client)[PEDRO]
    assert (a["comercios"], a["hasta"], a["minutos_trabajados"], a["metros"]) == (1, "10:00", 0, 0)
    assert a["por_hora"] == [{"hora": "10", "comercios": 1}]
    assert [p["nombre"] for p in a["puntos"]] == ["L 10:00:00"]
    items = client.get("/admin/cargas/historial", headers=admin_h(), params={"dias": 365}).json()["items"]
    assert [i["comercios"] for i in items] == [1]
    # y un día entero de inactivos no deja una fila fantasma
    assert agentes_de(client, "2026-10-05") == {}


def test_un_comercio_dado_de_baja_despues_sale_del_panel(client, repo):
    c = sembrar(repo, "2026-10-06T10:00:00")
    sembrar(repo, "2026-10-06T10:10:00")
    assert agentes_de(client)[PEDRO]["comercios"] == 2
    c["activo"] = False
    assert agentes_de(client)[PEDRO]["comercios"] == 1


def test_ciudad_filtra_por_fila_y_por_agente_en_dia_e_historial(client, repo):
    hoy = cargas.hoy_bolivia().isoformat()
    sembrar(repo, f"{hoy}T10:00:00", ciudad_id="ciu-1")
    sembrar(repo, f"{hoy}T10:05:00", ciudad_id="ciu-tarija")
    sembrar(repo, f"{hoy}T10:10:00", ciudad_id=None)
    d = dia(client, hoy, ciudad="bermejo")
    assert [(a["agente"], a["comercios"]) for a in d["agentes"]] == [(PEDRO, 1)]
    assert d["agentes"][0]["metros"] == 0 and len(d["agentes"][0]["puntos"]) == 1
    h = client.get("/admin/cargas/historial", headers=admin_h(), params={"ciudad": "tarija"}).json()["items"]
    assert [(i["agente"], i["comercios"]) for i in h] == [(PEDRO, 1)]
    h_todas = client.get("/admin/cargas/historial", headers=admin_h()).json()["items"]
    assert h_todas[0]["comercios"] == 3


def test_el_minutaje_redondea_por_tramo_y_nunca_es_negativo(client, repo):
    sembrar(repo, "2026-10-06T10:00:00")
    sembrar(repo, "2026-10-06T10:00:40")                         # 40 s -> 1 min
    sembrar(repo, "2026-10-06T12:00:00")
    a = agentes_de(client)[PEDRO]
    assert a["tramos"][0]["minutos"] == 1 and a["minutos_trabajados"] == 1
    assert all(p["min_desde_anterior"] is None or p["min_desde_anterior"] >= 0 for p in a["puntos"])


def test_subido_tarde_con_reloj_adelantado_no_da_negativo_ni_marca(client, repo):
    """capturado_en posterior a la llegada (reloj del celular adelantado): no es «tarde»."""
    sembrar(repo, "2026-10-06T10:05:00", offline=True, llegada=iso_bo("2026-10-06T10:00:00"))
    (p,) = agentes_de(client)[PEDRO]["puntos"]
    assert p["subido_tarde"] is False and p["hora_del_celular"] is True


def test_capturado_en_con_created_at_en_otra_ventana_manda_capturado(client, repo):
    """La rama `capturado_en is null` del filtro real no puede dejar entrar a uno con capturado_en fuera del día."""
    sembrar(repo, "2026-10-05T10:00:00", offline=True, llegada=iso_bo("2026-10-06T10:00:00"))
    assert agentes_de(client) == {}
    assert agentes_de(client, "2026-10-05")[PEDRO]["comercios"] == 1


def test_muchos_agentes_y_muchos_comercios_no_se_mezclan(client, repo):
    for ag in range(5):
        for i in range(40):
            sembrar(repo, f"2026-10-06T{9 + i // 10:02d}:{(i % 10) * 5:02d}:00", agente=f"ag{ag}@uruku.bo")
    a = agentes_de(client)
    assert sorted(a) == [f"ag{i}@uruku.bo" for i in range(5)]
    assert all(x["comercios"] == 40 and len(x["puntos"]) == 40 for x in a.values())
    assert [p["orden"] for p in a["ag0@uruku.bo"]["puntos"]] == list(range(1, 41))


def test_nombres_del_equipo_no_se_filtran_a_otro_agente(client, repo):
    repo.agentes["u1"] = {"id": "u1", "email": ANA, "nombre": "Ana Gómez", "activo": True}
    sembrar(repo, "2026-10-06T10:00:00")
    sembrar(repo, "2026-10-06T10:00:00", agente=ANA)
    a = agentes_de(client)
    assert a[ANA]["agente_nombre"] == "Ana Gómez" and a[PEDRO]["agente_nombre"] is None


def test_nombre_con_html_viaja_tal_cual_y_el_front_lo_escapa(client, repo):
    """El backend no escapa (es JSON); el popup del mapa usa escapeHtml (revisado a mano)."""
    sembrar(repo, "2026-10-06T10:00:00", nombre="<img src=x onerror=alert(1)>", portada_thumb_url="javascript:alert(1)")
    (p,) = agentes_de(client)[PEDRO]["puntos"]
    assert p["nombre"] == "<img src=x onerror=alert(1)>"
    assert p["foto"] == "javascript:alert(1)"                    # el front filtra: fotoSegura() sólo deja http(s):// o /


# ───────────────────────── multi-agente: el mismo agente con distinta capitalización
def test_BUG_login_de_campo_con_mayuscula_parte_al_agente_en_dos(client, repo):
    """El teclado del celular pone mayúscula sola (ver auth.mismo_email). El login de campo
    ACEPTA ese correo, pero `cargado_por` queda tal cual se tipeó: el mismo agente aparece
    partido en dos filas en Cargas (y en «Altas por día», que cuenta agentes distintos)."""
    def alta_como(email):
        r = client.post("/auth/campo/login", json={"email": email, "password": "campo1234"})
        assert r.status_code == 200, r.text
        _alta(client, repo, None, headers=_bearer(r.json()["access_token"]))
        repo.comercios[list(repo.comercios)[-1]]["created_at"] = iso_bo("2026-10-06T10:00:00")

    alta_como("agente@bermejolive.com")
    alta_como("Agente@BermejoLive.com")
    agentes = [a for a in dia(client)["agentes"]]
    assert len(agentes) == 1, [a["agente"] for a in agentes]      # esperado: UN agente con 2 comercios


def test_el_mismo_correo_con_otra_capitalizacion_es_un_solo_agente_en_el_servicio():
    """cargas.detalle_dia agrupa por el correo en minúscula: arregla también lo
    que ya quedó guardado con mayúscula antes del fix del login."""
    filas = [{"id": "1", "cargado_por": "Pedro@uruku.bo", "created_at": "2026-10-06T14:00:00+00:00"},
             {"id": "2", "cargado_por": "pedro@uruku.bo", "created_at": "2026-10-06T14:10:00+00:00"}]
    d = cargas.detalle_dia(filas, datetime(2026, 10, 6).date())
    assert [(a["agente"], a["comercios"]) for a in d["agentes"]] == [("pedro@uruku.bo", 2)]


# ───────────────────────── piezas puras
@pytest.mark.parametrize("texto,esperado", [
    ("2026-10-06T10:00:00-04:00", datetime(2026, 10, 6, 14, 0, tzinfo=UTC)),
    ("2026-10-06T10:00:00+00:00", datetime(2026, 10, 6, 10, 0, tzinfo=UTC)),
    ("2026-10-06T10:00:00z", datetime(2026, 10, 6, 10, 0, tzinfo=UTC)),
    ("2026-10-06T10:00:00", datetime(2026, 10, 6, 10, 0, tzinfo=UTC)),          # sin zona = UTC
    ("2026-10-06", datetime(2026, 10, 6, 0, 0, tzinfo=UTC)),                    # sólo fecha = 00:00 UTC
    ("2026-10-06T10:00:00.123Z", datetime(2026, 10, 6, 10, 0, 0, 123000, tzinfo=UTC)),
])
def test_parse_ts_formas(texto, esperado):
    assert cargas.parse_ts(texto) == esperado


@pytest.mark.parametrize("v", [None, "", "  ", "x", 12345, [], {}, "2026-13-01T00:00:00Z"])
def test_parse_ts_devuelve_none_con_lo_que_no_es_fecha(v):
    assert cargas.parse_ts(v) is None


def test_historial_vacio_y_dia_vacio():
    assert cargas.historial([]) == []
    assert cargas.detalle_dia([], datetime(2026, 10, 6).date()) == {"fecha": "2026-10-06", "agentes": []}


def test_hhmm_y_dia_bolivia_en_el_cambio_de_dia_utc():
    assert cargas.hhmm(datetime(2026, 10, 7, 3, 59, 59, tzinfo=UTC)) == "23:59"
    assert cargas.hhmm(datetime(2026, 10, 7, 4, 0, 0, tzinfo=UTC)) == "00:00"
    assert cargas.dia_bolivia(datetime(2026, 10, 7, 3, 59, 59, tzinfo=UTC)).isoformat() == "2026-10-06"
    assert cargas.dia_bolivia(datetime(2026, 10, 7, 4, 0, 0, tzinfo=UTC)).isoformat() == "2026-10-07"


def test_hoy_bolivia_a_las_21_en_bolivia_sigue_siendo_hoy():
    # 21:00 Bolivia = 01:00 UTC del día siguiente
    assert cargas.hoy_bolivia(datetime(2026, 10, 7, 1, 0, tzinfo=UTC)).isoformat() == "2026-10-06"
    assert cargas.hoy_bolivia(datetime(2026, 10, 7, 4, 0, tzinfo=UTC)).isoformat() == "2026-10-07"


def test_altas_por_dia_en_el_borde_de_bolivia(repo):
    repo.seed_comercio(cargado_por=PEDRO, activo=True, created_at="2026-10-07T03:59:59+00:00")
    repo.seed_comercio(cargado_por=PEDRO, activo=True, created_at="2026-10-07T04:00:00+00:00")
    assert {d["dia"]: d["altas"] for d in repo.altas_por_dia(365)} == {"2026-10-06": 1, "2026-10-07": 1}
