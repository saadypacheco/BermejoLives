"""`POST /admin/importados/aprobar-lote` (docs/home-ciudades.md §14): aprobar en bloque, por el MISMO camino que
aprobar de a uno, salteando repetidos, sin rubro y sin punto; simular no escribe; el tope; el permiso."""
import pytest

from app.api import moderacion
from app.core import auth

URL = "/admin/importados/aprobar-lote"
CIUDAD = "ciu-tj"


def h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def datos():
    return h(auth.make_token("datos@uruku.bo", rol="x", roles=["x"], permisos=["datos"]))


def _imp(repo, id, **kw):
    fila = {"id": id, "fuente": "turismo", "estado": "nuevo", "ciudad_id": CIUDAD, "nombre": f"Negocio {id}",
            "rubro_slug": "restaurantes", "lat": -21.53, "lng": -64.73, "duplicado_de": None,
            "telefono": "59144400000", "email": None, "direccion": "Calle Bolívar 1", "website": None, **kw}
    repo.importados[id] = fila
    return fila


def _cuerpo(**kw):
    return {"fuente": "turismo", "ciudad_id": CIUDAD, **kw}


def _sembrar_mezcla(repo):
    _imp(repo, "ok-1")
    _imp(repo, "ok-2", rubro_slug="bodegas")
    _imp(repo, "rep-1", duplicado_de="com-9")
    _imp(repo, "rep-2", duplicado_de="com-8")
    _imp(repo, "sinr-1", rubro_slug=None)
    _imp(repo, "sinr-2", rubro_slug="  ")
    _imp(repo, "sinp-1", lat=None, lng=None)
    _imp(repo, "sinp-2", lat=None, lng=-64.7)
    # lo que no entra en el lote: otra fuente, otra ciudad, ya revisados
    _imp(repo, "otra-fuente", fuente="osm")
    _imp(repo, "otra-ciudad", ciudad_id="ciu-sc")
    _imp(repo, "ya-promovido", estado="promovido")
    _imp(repo, "ya-descartado", estado="descartado")


# ───────────────────────────────────────────── permiso y validación

def test_sin_token_no_entra(client):
    assert client.post(URL, json=_cuerpo()).status_code in (401, 403)


def test_sin_permiso_datos_es_403(client, repo):
    sin = h(auth.make_token("otro@uruku.bo", rol="x", roles=["x"], permisos=["pagos"]))
    assert client.post(URL, json=_cuerpo(), headers=sin).status_code == 403


def test_el_permiso_es_el_mismo_que_para_aprobar_de_a_uno(client, repo):
    """Quien puede aprobar de a uno (`datos`) puede aprobar en bloque, y al revés."""
    _imp(repo, "ok-1")
    con_datos = h(auth.make_token("d@uruku.bo", rol="x", roles=["x"], permisos=["datos"]))
    assert client.post(URL, json=_cuerpo(), headers=con_datos).status_code == 200
    _imp(repo, "ok-2")
    sin = h(auth.make_token("otro@uruku.bo", rol="x", roles=["x"], permisos=["moderar"]))
    assert client.post("/admin/importados/ok-2/promover", json={}, headers=sin).status_code == 403
    assert client.post(URL, json=_cuerpo(), headers=sin).status_code == 403


@pytest.mark.parametrize("cuerpo", [{}, {"fuente": "turismo"}, {"ciudad_id": CIUDAD}, {"fuente": "x", "ciudad_id": CIUDAD},
                                    {"fuente": "turismo", "ciudad_id": ""}])
def test_cuerpo_invalido_es_422(client, datos, cuerpo):
    assert client.post(URL, json=cuerpo, headers=datos).status_code == 422


def test_la_ruta_no_choca_con_las_de_importado_id(client, datos, repo):
    r = client.post(URL, json=_cuerpo(), headers=datos)
    assert r.status_code == 200 and r.json() == {
        "aprobados": 0, "salteados": {"repetidos": 0, "sin_rubro": 0, "sin_punto": 0, "error": 0}, "restantes": 0}


# ───────────────────────────────────────────── simular

def test_simular_cuenta_sin_escribir_nada(client, datos, repo):
    _sembrar_mezcla(repo)
    antes = {k: dict(v) for k, v in repo.importados.items()}
    comercios_antes = dict(repo.comercios)
    r = client.post(URL, json=_cuerpo(simular=True), headers=datos)
    assert r.status_code == 200, r.text
    assert r.json() == {"aprobados": 2, "salteados": {"repetidos": 2, "sin_rubro": 2, "sin_punto": 2, "error": 0}, "restantes": 0}
    assert repo.importados == antes                      # ni un solo importado cambió
    assert repo.comercios == comercios_antes             # ni un comercio nuevo


def test_simular_y_aprobar_dan_el_mismo_resultado(client, datos, repo):
    _sembrar_mezcla(repo)
    simulado = client.post(URL, json=_cuerpo(simular=True), headers=datos).json()
    real = client.post(URL, json=_cuerpo(), headers=datos).json()
    assert simulado == real


# ───────────────────────────────────────────── aprobar de verdad

def test_aprueba_las_buenas_y_saltea_el_resto(client, datos, repo):
    _sembrar_mezcla(repo)
    r = client.post(URL, json=_cuerpo(), headers=datos)
    assert r.status_code == 200, r.text
    assert r.json() == {"aprobados": 2, "salteados": {"repetidos": 2, "sin_rubro": 2, "sin_punto": 2, "error": 0}, "restantes": 0}
    for ok in ("ok-1", "ok-2"):
        assert repo.importados[ok]["estado"] == "promovido" and repo.importados[ok]["comercio_id"] in repo.comercios
        assert repo.importados[ok]["revisado_por"] == "datos@uruku.bo"
    # los saltados siguen nuevos, sin tocar
    for salteado in ("rep-1", "rep-2", "sinr-1", "sinr-2", "sinp-1", "sinp-2"):
        assert repo.importados[salteado]["estado"] == "nuevo" and repo.importados[salteado].get("comercio_id") is None
    # lo que no es de esta fuente y ciudad, ni lo miró
    assert repo.importados["otra-fuente"]["estado"] == "nuevo" and repo.importados["otra-ciudad"]["estado"] == "nuevo"
    assert repo.importados["ya-promovido"].get("comercio_id") is None and repo.importados["ya-descartado"]["estado"] == "descartado"
    assert len(repo.comercios) == 2


def test_los_comercios_salen_igual_que_aprobando_de_a_uno(client, datos, repo):
    """Mismo camino: un importado aprobado en bloque y otro idéntico aprobado a mano dan el mismo comercio (salvo id
    y nombre): sin verificar, sin ser confiable, con el mismo origen, rubro, teléfono y dirección."""
    _imp(repo, "mano", nombre="Bodega Dos", rubro_slug="bodegas")
    assert client.post("/admin/importados/mano/promover", json={}, headers=datos).status_code == 200
    _imp(repo, "lote", nombre="Bodega Uno", rubro_slug="bodegas")
    assert client.post(URL, json=_cuerpo(), headers=datos).json()["aprobados"] == 1
    a = repo.comercios[repo.importados["lote"]["comercio_id"]]
    b = repo.comercios[repo.importados["mano"]["comercio_id"]]
    for campo in ("verificado", "confiable", "cargado_por", "activo", "telefono", "direccion", "whatsapp", "lat", "lng",
                  "ciudad_id", "horario", "sitio_web", "email"):
        assert a.get(campo) == b.get(campo), campo
    assert a["verificado"] is False and a["confiable"] is False and a["cargado_por"] == "import:turismo"
    assert repo.importados["lote"]["revisado_por"] == repo.importados["mano"]["revisado_por"]


def test_aprueba_llamando_a_promover_importado_y_no_a_una_copia(client, datos, repo, monkeypatch):
    """La prueba de «el mismo camino»: el lote llama a `promover_importado`, una vez por fila aprobable, con el cuerpo
    por defecto (el rubro y el nombre salen del importado) y el mismo admin."""
    _sembrar_mezcla(repo)
    llamadas = []
    original = moderacion.promover_importado

    def espia(importado_id, body, admin, repo_):
        llamadas.append((importado_id, body.model_dump(), admin["email"]))
        return original(importado_id, body, admin, repo_)

    monkeypatch.setattr(moderacion, "promover_importado", espia)
    client.post(URL, json=_cuerpo(), headers=datos)
    assert sorted(i for i, _, _ in llamadas) == ["ok-1", "ok-2"]
    for _, body, email in llamadas:
        assert body == {"nombre": None, "rubro_slug": None, "whatsapp": None, "sin_ubicacion": False}
        assert email == "datos@uruku.bo"


def test_una_segunda_llamada_no_repite_nada(client, datos, repo):
    _sembrar_mezcla(repo)
    client.post(URL, json=_cuerpo(), headers=datos)
    r = client.post(URL, json=_cuerpo(), headers=datos).json()
    assert r["aprobados"] == 0 and r["salteados"] == {"repetidos": 2, "sin_rubro": 2, "sin_punto": 2, "error": 0}
    assert len(repo.comercios) == 2


# ───────────────────────────────────────────── solo_con_punto = false

def test_sin_solo_con_punto_las_de_turismo_sin_punto_se_aprueban_sin_ubicacion(client, datos, repo):
    _sembrar_mezcla(repo)
    r = client.post(URL, json=_cuerpo(solo_con_punto=False), headers=datos)
    assert r.json() == {"aprobados": 4, "salteados": {"repetidos": 2, "sin_rubro": 2, "sin_punto": 0, "error": 0}, "restantes": 0}
    c = repo.comercios[repo.importados["sinp-1"]["comercio_id"]]
    assert c["lat"] is None and c["lng"] is None


def test_sin_solo_con_punto_una_fuente_que_exige_punto_cuenta_como_error(client, datos, repo):
    _imp(repo, "anh-1", fuente="anh", lat=None, lng=None)
    _imp(repo, "anh-2", fuente="anh")
    cuerpo = {"fuente": "anh", "ciudad_id": CIUDAD, "solo_con_punto": False}
    sim = client.post(URL, json={**cuerpo, "simular": True}, headers=datos).json()
    assert sim == {"aprobados": 1, "salteados": {"repetidos": 0, "sin_rubro": 0, "sin_punto": 0, "error": 1}, "restantes": 0}
    real = client.post(URL, json=cuerpo, headers=datos).json()
    assert real == sim
    assert repo.importados["anh-1"]["estado"] == "nuevo" and repo.importados["anh-2"]["estado"] == "promovido"


# ───────────────────────────────────────────── errores y tope

def test_una_fila_sin_nombre_cuenta_como_error_y_las_demas_siguen(client, datos, repo):
    _imp(repo, "sin-nombre", nombre="  ")
    _imp(repo, "bien")
    r = client.post(URL, json=_cuerpo(), headers=datos).json()
    assert r == {"aprobados": 1, "salteados": {"repetidos": 0, "sin_rubro": 0, "sin_punto": 0, "error": 1}, "restantes": 0}
    assert repo.importados["bien"]["estado"] == "promovido" and repo.importados["sin-nombre"]["estado"] == "nuevo"


def test_una_falla_de_la_base_en_una_fila_no_frena_el_lote(client, datos, repo, monkeypatch):
    _imp(repo, "a")
    _imp(repo, "b")
    original = repo.crear_comercio

    def falla_la_primera(row):
        if row["nombre"] == "Negocio a":
            raise RuntimeError("base caída")
        return original(row)

    monkeypatch.setattr(repo, "crear_comercio", falla_la_primera)
    r = client.post(URL, json=_cuerpo(), headers=datos).json()
    assert r == {"aprobados": 1, "salteados": {"repetidos": 0, "sin_rubro": 0, "sin_punto": 0, "error": 1}, "restantes": 0}
    assert repo.importados["a"]["estado"] == "nuevo" and repo.importados["b"]["estado"] == "promovido"


def test_el_tope_por_llamada_es_de_200_y_la_segunda_llamada_sigue(client, datos, repo):
    assert moderacion.TOPE_LOTE_APROBAR == 200
    for i in range(205):
        _imp(repo, f"n-{i:03d}")
    r1 = client.post(URL, json=_cuerpo(), headers=datos).json()
    assert r1["aprobados"] == 200 and r1["restantes"] == 5
    r2 = client.post(URL, json=_cuerpo(), headers=datos).json()
    assert r2["aprobados"] == 5 and r2["restantes"] == 0
    assert len(repo.comercios) == 205


def test_max_aprobar_limita_lo_que_se_aprueba_y_restantes_cuenta_el_resto(client, datos, repo):
    for i in range(7):
        _imp(repo, f"n-{i}")
    r = client.post(URL, json=_cuerpo(max_aprobar=3), headers=datos).json()
    assert r["aprobados"] == 3 and r["restantes"] == 4 and len(repo.comercios) == 3
    r = client.post(URL, json=_cuerpo(max_aprobar=3, simular=True), headers=datos).json()
    assert r["aprobados"] == 3 and r["restantes"] == 1 and len(repo.comercios) == 3        # simular no escribe
    r = client.post(URL, json=_cuerpo(max_aprobar=200), headers=datos).json()
    assert r["aprobados"] == 4 and r["restantes"] == 0


@pytest.mark.parametrize("valor", [0, -1, 201, "muchos", 1.5])
def test_max_aprobar_fuera_de_1_a_200_es_422(client, datos, valor):
    assert client.post(URL, json=_cuerpo(max_aprobar=valor), headers=datos).status_code == 422


def test_repetir_la_llamada_avanza_aunque_haya_mil_saltados_antes(client, datos, repo):
    """BUG-3 (QA): los saltados no ocupan el lugar de los aprobables, que siempre se alcanzan."""
    for i in range(1000):
        _imp(repo, f"a{i:04d}", duplicado_de="com-x")              # 1000 repetidos primero (por nombre)
    for i in range(5):
        _imp(repo, f"z{i}")                                        # 5 aprobables más abajo
    r1 = client.post(URL, json=_cuerpo(), headers=datos).json()
    assert r1["aprobados"] == 5 and r1["restantes"] == 0 and r1["salteados"]["repetidos"] == 1000


def test_restantes_no_cuenta_lo_que_falla_al_guardarse_en_esta_llamada(client, datos, repo, monkeypatch):
    for i in range(3):
        _imp(repo, f"n-{i}")
    original = repo.crear_comercio

    def falla_la_primera(row):
        if row["nombre"] == "Negocio n-0":
            raise RuntimeError("base caída")
        return original(row)

    monkeypatch.setattr(repo, "crear_comercio", falla_la_primera)
    r = client.post(URL, json=_cuerpo(max_aprobar=2), headers=datos).json()
    assert r == {"aprobados": 1, "salteados": {"repetidos": 0, "sin_rubro": 0, "sin_punto": 0, "error": 1}, "restantes": 1}


# ───────────────────────────────────────────── M2: sólo las fuentes oficiales

@pytest.mark.parametrize("fuente", ["tarjeta", "osm", "overture"])
def test_las_fuentes_no_oficiales_son_422_con_mensaje_claro(client, datos, repo, fuente):
    _imp(repo, "x", fuente=fuente)
    r = client.post(URL, json=_cuerpo(fuente=fuente), headers=datos)
    assert r.status_code == 422
    texto = str(r.json())
    assert "sólo vale para las fuentes oficiales" in texto and "turismo, anh y aduana" in texto
    assert repo.importados["x"]["estado"] == "nuevo"


@pytest.mark.parametrize("fuente", ["turismo", "anh", "aduana"])
def test_las_fuentes_oficiales_entran(client, datos, repo, fuente):
    _imp(repo, "x", fuente=fuente)
    r = client.post(URL, json=_cuerpo(fuente=fuente), headers=datos)
    assert r.status_code == 200 and r.json()["aprobados"] == 1


# ───────────────────────────────────────────── M1: una sola aprobación en bloque a la vez y reserva de la fila

def test_si_hay_otra_aprobacion_en_bloque_en_curso_es_409(client, datos, repo):
    _imp(repo, "x")
    assert moderacion._LOTE_APROBAR.acquire(blocking=False)
    try:
        for simular in (False, True):
            r = client.post(URL, json=_cuerpo(simular=simular), headers=datos)
            assert r.status_code == 409 and r.json()["detail"] == "Ya hay una aprobación en bloque en curso."
    finally:
        moderacion._LOTE_APROBAR.release()
    assert repo.importados["x"]["estado"] == "nuevo"
    assert client.post(URL, json=_cuerpo(), headers=datos).json()["aprobados"] == 1       # soltada, vuelve a andar


def test_el_candado_se_suelta_aunque_la_llamada_falle(client, datos, repo, monkeypatch):
    monkeypatch.setattr(repo, "list_importados_nuevos", lambda c, f: (_ for _ in ()).throw(RuntimeError("base caída")))
    with pytest.raises(RuntimeError):
        client.post(URL, json=_cuerpo(), headers=datos)
    assert moderacion._LOTE_APROBAR.acquire(blocking=False)
    moderacion._LOTE_APROBAR.release()


def test_una_fila_reservada_por_otra_aprobacion_da_409_y_no_crea_un_segundo_comercio(client, datos, repo):
    _imp(repo, "x")
    assert repo.reclamar_importado("x")                      # otra persona la está aprobando
    r = client.post("/admin/importados/x/promover", json={}, headers=datos)
    assert r.status_code == 409 and repo.comercios == {}
    # en bloque: la fila reservada cuenta como error y no se aprueba dos veces
    r = client.post(URL, json=_cuerpo(), headers=datos).json()
    assert r["aprobados"] == 0 and r["salteados"]["error"] == 1 and repo.comercios == {}


def test_carrera_aprobar_de_a_uno_mientras_se_crea_el_comercio_solo_gana_una(client, datos, repo, monkeypatch):
    """Mientras la primera aprobación está creando el comercio (ya reservó la fila), llega la segunda (a mano o en
    bloque): pierde. Resultado: un solo comercio."""
    _imp(repo, "x")
    original = repo.crear_comercio
    resultados = []

    def crear_y_competir(row):
        if not resultados:
            resultados.append(client.post("/admin/importados/x/promover", json={}, headers=datos).status_code)
            resultados.append(client.post(URL, json=_cuerpo(), headers=datos).json())
        return original(row)

    monkeypatch.setattr(repo, "crear_comercio", crear_y_competir)
    assert client.post("/admin/importados/x/promover", json={}, headers=datos).status_code == 200
    assert resultados[0] == 409
    assert resultados[1]["aprobados"] == 0 and resultados[1]["salteados"]["error"] == 1
    assert len(repo.comercios) == 1 and repo.importados["x"]["estado"] == "promovido"
    assert repo.importados["x"]["aprobando_desde"] is None


def test_si_falla_antes_de_crear_el_comercio_se_suelta_la_reserva(client, datos, repo, monkeypatch):
    _imp(repo, "x")
    original = repo.crear_comercio
    monkeypatch.setattr(repo, "crear_comercio", lambda row: (_ for _ in ()).throw(RuntimeError("base caída")))
    with pytest.raises(RuntimeError):
        client.post("/admin/importados/x/promover", json={}, headers=datos)
    assert repo.importados["x"]["estado"] == "nuevo" and repo.importados["x"]["aprobando_desde"] is None
    monkeypatch.setattr(repo, "crear_comercio", original)
    assert client.post("/admin/importados/x/promover", json={}, headers=datos).status_code == 200


def test_si_el_comercio_ya_se_creo_la_reserva_no_se_suelta(client, datos, repo, monkeypatch):
    """Si falla después de crear el comercio, soltar la reserva dejaría crear un segundo: se deja vencer."""
    _imp(repo, "x")
    monkeypatch.setattr(repo, "marcar_importado", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("base caída")))
    with pytest.raises(RuntimeError):
        client.post("/admin/importados/x/promover", json={}, headers=datos)
    assert len(repo.comercios) == 1 and repo.importados["x"]["aprobando_desde"] is not None
    assert repo.reclamar_importado("x") is False


def test_la_reserva_vence_a_los_10_minutos(repo):
    from datetime import datetime, timedelta, timezone
    _imp(repo, "x")
    assert repo.reclamar_importado("x") is True and repo.reclamar_importado("x") is False
    repo.importados["x"]["aprobando_desde"] = (datetime.now(timezone.utc) - timedelta(minutes=11)).isoformat()
    assert repo.reclamar_importado("x") is True
    repo.importados["x"]["estado"] = "promovido"
    repo.importados["x"]["aprobando_desde"] = None
    assert repo.reclamar_importado("x") is False


class _Cadena:
    """Un cliente de PostgREST de mentira: anota los llamados encadenados y contesta con `datos`."""

    def __init__(self, datos):
        self.llamados, self._datos = [], datos

    def __getattr__(self, nombre):
        def llamar(*a, **k):
            self.llamados.append((nombre, a))
            return self
        return llamar

    def execute(self):
        return type("R", (), {"data": self._datos})()


def test_la_reserva_real_es_una_actualizacion_condicional_sobre_estado_nuevo():
    from app.db.repository import SupabaseRepo
    for datos, esperado in (([{"id": "x"}], True), ([], False)):
        c = _Cadena(datos)
        assert SupabaseRepo(client=c).reclamar_importado("x") is esperado
        nombres = [n for n, _ in c.llamados]
        assert nombres[:2] == ["table", "update"] and ("eq", ("estado", "nuevo")) in c.llamados
        assert ("eq", ("id", "x")) in c.llamados
        o = next(a[0] for n, a in c.llamados if n == "or_")
        assert o.startswith("aprobando_desde.is.null,aprobando_desde.lt.")
        assert next(a[0] for n, a in c.llamados if n == "update").keys() == {"aprobando_desde"}


def test_la_tarjeta_real_es_una_actualizacion_condicional_sobre_la_portada():
    from app.db.repository import SupabaseRepo
    c = _Cadena([{"id": "c"}])
    assert SupabaseRepo(client=c).actualizar_portada_card("c", {"portada_card_url": "u"}, "https://x/p.jpg", None) is True
    assert ("eq", ("portada_url", "https://x/p.jpg")) in c.llamados and ("is_", ("portada_pos", "null")) in c.llamados
    c = _Cadena([])
    assert SupabaseRepo(client=c).actualizar_portada_card("c", {}, "https://x/p.jpg", 40) is False
    assert ("eq", ("portada_pos", 40)) in c.llamados


def test_deja_registro_con_structlog(client, datos, repo):
    import structlog
    _sembrar_mezcla(repo)
    with structlog.testing.capture_logs() as logs:
        client.post(URL, json=_cuerpo(simular=True), headers=datos)
    ev = next(l for l in logs if l["event"] == "importado.aprobar_lote")
    assert ev["simular"] is True and ev["fuente"] == "turismo" and ev["aprobados"] == 2
    assert ev["salteados_repetidos"] == 2 and ev["salteados_sin_rubro"] == 2 and ev["by"] == "datos@uruku.bo"
