"""El tablero del panel: `GET /admin/resumen` (docs/admin-rediseno.md §3-§5).

Qué se prueba: la forma EXACTA del contrato (`ResumenAdmin` en frontend/lib/api.ts),
el filtro por ciudad (y que `por_ciudad` trae siempre todas), el slug desconocido,
la serie de 30 días completa con el corte de día de Bolivia, que una parte caída
viene en `null` sin tumbar el resto, quién puede pedirlo, el repo real (una sola
llamada, nada de bajar filas), el cliente de Reservalo y la migración 0139.

La función SQL en sí se probó contra un Postgres 16 real (ver el reporte); acá el
FakeRepo es su espejo en Python.
"""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
import structlog

from app.core import auth
from app.db.repository import SupabaseRepo
from app.services import cargas, resumen_admin, vencimientos
from app.services.reservalo_sync import ReservaloSyncClient, get_reservalo_sync_client
from app.main import app

HOY = date(2026, 10, 6)
_HOY_REAL = cargas.hoy_bolivia          # el de verdad, antes de que el fixture lo fije
BERMEJO, SANTA_CRUZ = "ciu-1", "ciu-santa-cruz"


# ───────────────────────────────────────────────────────────────── ayudas
def bo(hhmm: str, dia: str = "2026-10-06") -> str:
    """Una hora de Bolivia (UTC−4) como el ISO en UTC que guarda la base."""
    local = datetime.fromisoformat(f"{dia}T{hhmm}:00").replace(tzinfo=cargas.BOLIVIA)
    return local.astimezone(timezone.utc).isoformat()


def headers(token):
    return {"Authorization": f"Bearer {token}"}


def admin_h():
    return headers(auth.make_token("admin@uruku.bo", rol="admin"))


class ReservaloFalso:
    """Lo que el endpoint le pide a Reservalo: cuántas consultas esperan."""

    def __init__(self, pendientes=0):
        self.pendientes = pendientes

    def contar_consultas_pendientes(self, timeout=5.0):
        return self.pendientes


@pytest.fixture(autouse=True)
def _sin_red_ni_cache(monkeypatch):
    """Los certificados TLS NO se miden en los tests (no hay red) y su cache de
    módulo no pasa de un test al siguiente. `hoy` de Bolivia fijo en el 6/10."""
    llamadas = []

    def cert(host, puerto=443, timeout=6.0):
        llamadas.append(host)
        return {"host": host, "ok": True, "dias": 90, "estado": "ok"}

    monkeypatch.setattr(vencimientos, "vence_certificado", cert)
    vencimientos.limpiar_cache_certificados()
    monkeypatch.setattr(cargas, "hoy_bolivia", lambda ahora=None: HOY)
    yield llamadas
    vencimientos.limpiar_cache_certificados()


@pytest.fixture
def reservalo():
    return ReservaloFalso()


@pytest.fixture
def api(client, repo, reservalo):
    """El TestClient con Reservalo reemplazado (el `client` limpia los overrides al cerrar)."""
    app.dependency_overrides[get_reservalo_sync_client] = lambda: reservalo
    return client


def pedir(api, ciudad=None, h=None):
    return api.get("/admin/resumen", headers=h or admin_h(), params={"ciudad": ciudad} if ciudad else {})


def resumen(api, ciudad=None):
    r = pedir(api, ciudad)
    assert r.status_code == 200, r.text
    return r.json()


def sembrar(repo):
    """Dos ciudades con comercios de todos los colores, más pendientes y actividad."""
    c1 = repo.seed_comercio(nombre="A", activo=True, verificado=True, ciudad_id=BERMEJO, horario="8 a 18",
                            whatsapp="59170000001", portada_url="http://x/a.jpg", rubro_id="r-1",
                            created_at=bo("10:00"), paga_hasta="2026-10-08")             # por vencer
    c2 = repo.seed_comercio(nombre="B", activo=True, verificado=False, ciudad_id=BERMEJO, horario="",
                            whatsapp="", portada_url=None, rubro_id=repo.rubros.setdefault("otros", "rub-otros"),
                            created_at=bo("11:00", "2026-10-05"))
    c3 = repo.seed_comercio(nombre="C", activo=True, verificado=False, ciudad_id=BERMEJO, horario="9 a 12",
                            horario_estimado=True, whatsapp="59170000003", portada_url="", rubro_id=None,
                            created_at=bo("12:00"), paga_hasta="2026-09-01")             # vencido
    c4 = repo.seed_comercio(nombre="D", activo=True, verificado=True, ciudad_id=SANTA_CRUZ, horario="  ",
                            whatsapp="59170000004", portada_url="http://x/d.jpg", rubro_id="r-1",
                            created_at=bo("09:00"), suspendido=True)                     # suspendido
    repo.seed_comercio(nombre="Baja", activo=False, verificado=False, ciudad_id=BERMEJO,
                       created_at=bo("09:00"))                                           # no cuenta nunca
    return c1, c2, c3, c4


# ──────────────────────────────────────────── 1. la forma exacta del contrato
FORMA_COMERCIOS = {"total", "verificados", "sin_verificar", "sin_horario", "horario_estimado",
                   "sin_whatsapp", "sin_foto", "sin_rubro"}
FORMA_PENDIENTES = {"publicaciones", "comercios_sin_verificar", "pagos", "reclamos", "cambio_numero",
                    "suscripciones", "vencimientos", "recepcion_sin_comercio"}


def test_la_respuesta_tiene_exactamente_la_forma_de_ResumenAdmin(api, repo):
    sembrar(repo)
    d = resumen(api)
    assert set(d) == {"ciudad", "comercios", "por_ciudad", "pendientes", "actividad"}
    assert d["ciudad"] is None
    assert set(d["comercios"]) == FORMA_COMERCIOS
    assert all(isinstance(v, int) for v in d["comercios"].values())
    assert set(d["pendientes"]) == FORMA_PENDIENTES
    assert all(isinstance(v, int) for v in d["pendientes"].values())      # con todo sano, ninguno es null
    assert set(d["actividad"]) == {"visitas_7d", "contactos_7d", "serie_30d"}
    assert isinstance(d["actividad"]["visitas_7d"], int) and isinstance(d["actividad"]["contactos_7d"], int)
    for ci in d["por_ciudad"]:
        assert set(ci) == {"slug", "nombre", "total", "sin_verificar", "sin_horario"}
        assert isinstance(ci["slug"], str) and isinstance(ci["nombre"], str)
    for fila in d["actividad"]["serie_30d"]:
        assert set(fila) == {"dia", "altas", "visitas", "contactos"}
        assert isinstance(fila["dia"], str) and len(fila["dia"]) == 10


def test_los_numeros_de_los_comercios(api, repo):
    sembrar(repo)
    c = resumen(api)["comercios"]
    # 4 activos (el dado de baja no cuenta): A, B, C, D.
    assert c["total"] == 4
    assert (c["verificados"], c["sin_verificar"]) == (2, 2)
    assert c["sin_horario"] == 2          # B (vacío) y D (sólo espacios); el estimado de C cuenta como CON horario
    assert c["horario_estimado"] == 1
    assert c["sin_whatsapp"] == 1         # B
    assert c["sin_foto"] == 2             # B (null) y C (vacío)
    assert c["sin_rubro"] == 2            # B (rubro «otros») y C (sin rubro)


def test_los_pendientes_con_su_fuente(api, repo, reservalo):
    c1, *_ = sembrar(repo)
    repo.publicaciones += [{"id": "p1", "estado": "pendiente", "activo": True},
                           {"id": "p2", "estado": "pendiente", "activo": True},
                           {"id": "p3", "estado": "aprobado", "activo": True},
                           {"id": "p4", "estado": "pendiente", "activo": False}]
    repo.pagos["g1"] = {"id": "g1", "estado": "pendiente", "comercio_id": c1["id"]}
    repo.pagos["g2"] = {"id": "g2", "estado": "confirmado", "comercio_id": c1["id"]}
    repo.reclamos["r1"] = {"id": "r1", "estado": "pendiente"}
    repo.reclamos["r2"] = {"id": "r2", "estado": "respondido"}
    repo.solicitudes_numero["s1"] = {"id": "s1", "estado": "pendiente"}
    repo.solicitudes_numero["s2"] = {"id": "s2", "estado": "aprobada"}
    repo.wa_inbox["m1"] = {"resultado": "sin_comercio", "created_at": bo("09:00")}
    repo.wa_inbox["m2"] = {"resultado": "sin_comercio", "created_at": bo("09:00", "2026-09-20")}  # hace 16 días
    repo.wa_inbox["m3"] = {"resultado": "publicada", "created_at": bo("09:00")}
    reservalo.pendientes = 3

    p = resumen(api)["pendientes"]
    assert p["publicaciones"] == 2
    assert p["comercios_sin_verificar"] == 2
    assert p["pagos"] == 1
    assert p["reclamos"] == 1 + 3         # reclamos pendientes + consultas pendientes de Reservalo
    assert p["cambio_numero"] == 1
    assert p["suscripciones"] == 3        # A por vencer, C vencido, D suspendido
    assert p["vencimientos"] == 0
    assert p["recepcion_sin_comercio"] == 1


# ─────────────────────────────────────────────────────── 2. filtro por ciudad
def test_con_ciudad_los_comercios_son_los_de_esa_ciudad(api, repo):
    sembrar(repo)
    todos = resumen(api)
    d = resumen(api, "santa-cruz")
    assert d["ciudad"] == "santa-cruz"
    assert d["comercios"]["total"] == 1 and d["comercios"]["verificados"] == 1
    assert d["comercios"]["sin_horario"] == 1
    assert d["pendientes"]["comercios_sin_verificar"] == 0
    b = resumen(api, "bermejo")["comercios"]
    assert b["total"] == 3 and b["sin_verificar"] == 2
    # El filtro no se come a los demás: las dos ciudades suman el total.
    assert b["total"] + d["comercios"]["total"] == todos["comercios"]["total"]


def test_por_ciudad_trae_siempre_todas_con_o_sin_filtro(api, repo):
    sembrar(repo)
    sin = resumen(api)["por_ciudad"]
    assert sin == resumen(api, "bermejo")["por_ciudad"] == resumen(api, "santa-cruz")["por_ciudad"]
    assert {c["slug"] for c in sin} == {"bermejo", "santa-cruz"}
    assert next(c for c in sin if c["slug"] == "bermejo") == {
        "slug": "bermejo", "nombre": "Bermejo", "total": 3, "sin_verificar": 2, "sin_horario": 1}


def test_la_actividad_tambien_respeta_la_ciudad(api, repo):
    c1, _, _, c4 = sembrar(repo)
    repo.visitas += [{"dia": "2026-10-06", "ruta": "/", "sesion": "a", "ciudad_slug": "bermejo"},
                     {"dia": "2026-10-06", "ruta": "/", "sesion": "b", "ciudad_slug": "santa-cruz"},
                     {"dia": "2026-10-06", "ruta": "/", "sesion": "c", "ciudad_slug": "santa-cruz"}]
    repo.leads += [{"comercio_id": c1["id"], "tipo": "whatsapp", "created_at": bo("12:00")},
                   {"comercio_id": c4["id"], "tipo": "mapa", "created_at": bo("12:00")},
                   {"comercio_id": c4["id"], "tipo": "telefono", "created_at": bo("13:00")}]
    assert (resumen(api)["actividad"]["visitas_7d"], resumen(api)["actividad"]["contactos_7d"]) == (3, 3)
    b = resumen(api, "bermejo")["actividad"]
    assert (b["visitas_7d"], b["contactos_7d"]) == (1, 1)
    s = resumen(api, "santa-cruz")["actividad"]
    assert (s["visitas_7d"], s["contactos_7d"]) == (2, 2)


# ──────────────────────────────────────────────────────── 3. slug desconocido
def test_un_slug_desconocido_da_ceros_y_no_un_500(api, repo):
    sembrar(repo)
    repo.visitas.append({"dia": "2026-10-06", "ruta": "/", "sesion": "a", "ciudad_slug": "bermejo"})
    r = pedir(api, "atlantida")                      # el FakeRepo lo trata como inexistente
    assert r.status_code == 200
    d = r.json()
    assert d["ciudad"] == "atlantida"
    assert d["comercios"] == {k: 0 for k in FORMA_COMERCIOS}
    assert d["pendientes"]["comercios_sin_verificar"] == 0
    assert d["actividad"]["visitas_7d"] == 0
    assert sum(f["altas"] + f["visitas"] + f["contactos"] for f in d["actividad"]["serie_30d"]) == 0
    assert len(d["por_ciudad"]) == 2                 # las ciudades de verdad siguen ahí


def test_ciudad_vacia_o_con_espacios_es_sin_ciudad(api, repo):
    sembrar(repo)
    assert resumen(api, "  ")["ciudad"] is None
    assert resumen(api, "  ")["comercios"]["total"] == 4


# ───────────────────────────────────────────── 4. la serie de 30 días completa
def test_la_serie_son_30_dias_del_mas_viejo_a_hoy_con_los_vacios_en_cero(api, repo):
    c1, *_ = sembrar(repo)
    repo.visitas += [{"dia": "2026-10-06", "ruta": "/", "sesion": "a", "ciudad_slug": "bermejo"},
                     {"dia": "2026-09-20", "ruta": "/", "sesion": "b", "ciudad_slug": "bermejo"}]
    repo.leads.append({"comercio_id": c1["id"], "tipo": "whatsapp", "created_at": bo("10:00", "2026-09-20")})
    serie = resumen(api)["actividad"]["serie_30d"]
    assert len(serie) == 30
    assert serie[0]["dia"] == "2026-09-07" and serie[-1]["dia"] == "2026-10-06"
    assert [f["dia"] for f in serie] == sorted(f["dia"] for f in serie)
    assert len({f["dia"] for f in serie}) == 30                      # ni repetidos ni salteados
    por_dia = {f["dia"]: f for f in serie}
    assert por_dia["2026-10-06"] == {"dia": "2026-10-06", "altas": 3, "visitas": 1, "contactos": 0}
    assert por_dia["2026-09-20"] == {"dia": "2026-09-20", "altas": 0, "visitas": 1, "contactos": 1}
    assert por_dia["2026-10-05"]["altas"] == 1
    vacio = por_dia["2026-09-25"]
    assert vacio == {"dia": "2026-09-25", "altas": 0, "visitas": 0, "contactos": 0}


def test_el_dia_de_la_serie_es_el_de_bolivia_no_el_de_utc(api, repo):
    """21:00 de Bolivia del 6/10 ya es el 7/10 en UTC: cuenta para el 6."""
    repo.seed_comercio(nombre="Noche", activo=True, ciudad_id=BERMEJO, created_at="2026-10-07T01:00:00+00:00")
    repo.seed_comercio(nombre="Madrugada", activo=True, ciudad_id=BERMEJO, created_at="2026-10-06T03:00:00+00:00")
    serie = {f["dia"]: f for f in resumen(api)["actividad"]["serie_30d"]}
    assert serie["2026-10-06"]["altas"] == 1       # la de las 21:00 (01:00Z del 7)
    assert serie["2026-10-05"]["altas"] == 1       # la de las 23:00 del 5 (03:00Z del 6)
    assert "2026-10-07" not in serie


def test_hoy_es_el_de_bolivia_a_las_22_horas(monkeypatch, repo):
    """Servidor en UTC: a las 02:00Z del 7 son las 22:00 del 6 en Bermejo."""
    monkeypatch.setattr(cargas, "hoy_bolivia", _HOY_REAL)      # el cálculo real, con el reloj fijado:
    monkeypatch.setattr(cargas, "ahora_utc", lambda: datetime(2026, 10, 7, 2, 0, tzinfo=timezone.utc))
    monkeypatch.setattr(vencimientos, "vence_certificado",
                        lambda h, puerto=443, timeout=6.0: {"host": h, "estado": "ok"})
    d = resumen_admin.armar_resumen(repo, ReservaloFalso(), None)
    assert d["actividad"]["serie_30d"][-1]["dia"] == "2026-10-06"


def test_rellenar_serie_descarta_lo_de_afuera_y_no_inventa_numeros():
    filas = [{"dia": "2026-10-06", "altas": 2, "visitas": 5, "contactos": 1},
             {"dia": "2026-08-01", "altas": 9, "visitas": 9, "contactos": 9},     # fuera de la ventana
             {"dia": "2026-10-07", "altas": 9, "visitas": 9, "contactos": 9},     # futuro
             {"dia": "2026-10-04", "altas": None, "visitas": "3"}]
    serie = resumen_admin.rellenar_serie(filas, HOY)
    assert len(serie) == 30
    assert serie[-1] == {"dia": "2026-10-06", "altas": 2, "visitas": 5, "contactos": 1}
    assert serie[-3] == {"dia": "2026-10-04", "altas": 0, "visitas": 3, "contactos": 0}
    assert sum(f["altas"] for f in serie) == 2
    assert resumen_admin.rellenar_serie([], HOY)[0]["dia"] == "2026-09-07"


# ───────────────────────────────────────── 5. una parte que falla viene en null
def test_una_parte_de_la_base_en_null_no_tumba_el_resto(api, repo):
    sembrar(repo)
    repo.reclamos["r1"] = {"id": "r1", "estado": "pendiente"}
    repo.pagos["g1"] = {"id": "g1", "estado": "pendiente", "comercio_id": "x"}
    repo.resumen_admin_nulos = frozenset({"pendientes.pagos", "actividad.serie_30d", "actividad.visitas_7d"})
    with structlog.testing.capture_logs() as logs:
        d = resumen(api)
    assert d["pendientes"]["pagos"] is None
    assert d["actividad"]["serie_30d"] is None and d["actividad"]["visitas_7d"] is None
    assert d["actividad"]["contactos_7d"] == 0                 # lo demás, bien
    assert d["pendientes"]["reclamos"] == 1 and d["comercios"]["total"] == 4
    partes = {l["parte"] for l in logs if l["event"] == "admin.resumen_parcial"}
    assert partes == {"pendientes.pagos", "actividad.serie_30d", "actividad.visitas_7d"}


def test_si_reservalo_no_contesta_los_reclamos_vienen_en_null_y_el_resto_sigue(api, repo, reservalo):
    sembrar(repo)
    repo.reclamos["r1"] = {"id": "r1", "estado": "pendiente"}
    repo.publicaciones.append({"id": "p1", "estado": "pendiente", "activo": True})
    reservalo.pendientes = None                                 # no contestó
    with structlog.testing.capture_logs() as logs:
        d = resumen(api)
    assert d["pendientes"]["reclamos"] is None
    assert d["pendientes"]["publicaciones"] == 1 and d["comercios"]["total"] == 4
    parciales = [l for l in logs if l["event"] == "admin.resumen_parcial"]
    assert [l["parte"] for l in parciales] == ["pendientes.reclamos"]


def test_si_reservalo_explota_tambien_es_solo_esa_parte(api, repo, reservalo):
    sembrar(repo)

    def explota(timeout=5.0):
        raise RuntimeError("conexión rechazada")

    reservalo.contar_consultas_pendientes = explota
    with structlog.testing.capture_logs() as logs:
        d = resumen(api)
    assert d["pendientes"]["reclamos"] is None and d["comercios"]["total"] == 4
    parciales = [l for l in logs if l["event"] == "admin.resumen_parcial"]
    assert [l["parte"] for l in parciales] == ["pendientes.reclamos"]        # una sola vez
    assert "conexión rechazada" in parciales[0]["motivo"]


def test_si_fallan_los_vencimientos_solo_esa_parte_es_null(api, repo, monkeypatch):
    sembrar(repo)
    monkeypatch.setattr(repo, "list_vencimientos", lambda: (_ for _ in ()).throw(RuntimeError("tabla caída")))
    with structlog.testing.capture_logs() as logs:
        d = resumen(api)
    assert d["pendientes"]["vencimientos"] is None
    assert d["pendientes"]["suscripciones"] == 3 and d["comercios"]["total"] == 4
    assert [l["parte"] for l in logs if l["event"] == "admin.resumen_parcial"] == ["pendientes.vencimientos"]


def test_sin_poder_contar_los_comercios_es_un_503_y_no_un_500(api, repo):
    repo.resumen_admin_falla = True
    with structlog.testing.capture_logs() as logs:
        r = pedir(api)
    assert r.status_code == 503
    assert "resumen" in r.json()["detail"].lower()
    assert any(l["event"] == "admin.resumen_fallo" for l in logs)


def test_una_respuesta_de_la_base_sin_comercios_tambien_es_503(api, repo, monkeypatch):
    monkeypatch.setattr(repo, "resumen_admin", lambda ciudad, hoy: {})
    assert pedir(api).status_code == 503


# ──────────────────────────────────────────────────────────── 6. vencimientos
def test_los_vencimientos_suman_fechas_cargadas_y_certificados(api, repo, _sin_red_ni_cache, monkeypatch):
    hoy = vencimientos.hoy_local()
    repo.crear_vencimiento({"nombre": "dominio", "vence_el": (hoy + timedelta(days=3)).isoformat()})     # crítico
    repo.crear_vencimiento({"nombre": "vps", "vence_el": (hoy - timedelta(days=1)).isoformat()})         # vencido
    repo.crear_vencimiento({"nombre": "chip", "vence_el": (hoy + timedelta(days=200)).isoformat()})      # ok
    repo.crear_vencimiento({"nombre": "sin fecha", "vence_el": None})                                    # no es alerta
    monkeypatch.setattr(vencimientos, "vence_certificado",
                        lambda h, puerto=443, timeout=6.0: {"host": h, "estado": "critico" if h == "uruku.bo" else "ok"})
    assert resumen(api)["pendientes"]["vencimientos"] == 2 + 1


def test_el_numero_coincide_con_las_alertas_de_la_pestana_vencimientos(api, repo, monkeypatch):
    hoy = vencimientos.hoy_local()
    repo.crear_vencimiento({"nombre": "dominio", "vence_el": (hoy + timedelta(days=10)).isoformat()})   # por vencer
    repo.crear_vencimiento({"nombre": "otro", "vence_el": (hoy - timedelta(days=5)).isoformat()})
    monkeypatch.setattr(vencimientos, "vence_certificado",
                        lambda h, puerto=443, timeout=6.0: {"host": h, "estado": "por_vencer" if h.startswith("db") else "ok"})
    pestana = api.get("/admin/vencimientos", headers=admin_h()).json()["alertas"]
    vencimientos.limpiar_cache_certificados()
    assert resumen(api)["pendientes"]["vencimientos"] == pestana == 3


def test_los_certificados_se_miden_una_vez_y_se_recuerdan(api, repo, _sin_red_ni_cache):
    resumen(api)
    resumen(api)
    resumen(api)
    assert len(_sin_red_ni_cache) == len(vencimientos.HOSTS_TLS)       # cinco hosts, una sola vuelta


def test_un_host_que_no_responde_no_suma_alertas(api, repo, monkeypatch):
    monkeypatch.setattr(vencimientos, "vence_certificado",
                        lambda h, puerto=443, timeout=6.0: {"host": h, "ok": False, "estado": "sin_dato"})
    assert resumen(api)["pendientes"]["vencimientos"] == 0


# ───────────────────────────────────────────────────────── 7. quién lo puede pedir
def test_sin_token_es_401(api):
    assert api.get("/admin/resumen").status_code == 401


def test_token_basura_es_401(api):
    assert pedir(api, h=headers("esto.no.es.un.jwt")).status_code == 401


@pytest.mark.parametrize("token", [
    lambda: auth.make_agente_token("agente@uruku.bo", ciudad_slug="bermejo"),
    lambda: auth.make_comercio_token("com-1", "x@y.com"),
    lambda: auth.make_usuario_token("usu-1", "59170000000"),
    lambda: auth.make_token("v@uruku.bo", rol="rol-sin-permisos"),
], ids=["agente", "comercio", "comprador", "rol-sin-permisos"])
def test_agentes_comercios_y_compradores_no_entran(api, token):
    assert pedir(api, h=headers(token())).status_code == 403


@pytest.mark.parametrize("token", [
    lambda: auth.make_token("a@uruku.bo", rol="admin"),
    lambda: auth.make_token("m@uruku.bo", rol="moderador"),
    lambda: auth.make_publicador_token("p@uruku.bo"),
    # Un rol armado desde el panel con UN solo permiso cualquiera del equipo.
    lambda: auth.make_token("r@uruku.bo", rol="cobrador", roles=["cobrador"], permisos=["pagos"]),
], ids=["admin", "moderador", "publicador", "rol-propio-con-un-permiso"])
def test_cualquier_usuario_del_panel_entra_con_su_rol(api, token):
    assert pedir(api, h=headers(token())).status_code == 200


def test_un_token_con_solo_cargar_comercios_no_es_del_panel(api):
    t = auth.make_token("c@uruku.bo", rol="cargador", roles=["cargador"], permisos=["comercios.cargar"])
    assert pedir(api, h=headers(t)).status_code == 403


# ──────────────────────────────────────────── 8. el repo real y el cliente de Reservalo
class _Rpc:
    def __init__(self, data):
        self._data, self.llamado = data, None

    def execute(self):
        class R:  # noqa: D401
            pass
        r = R()
        r.data = self._data
        return r


class _DbFalsa:
    """Registra qué se le pide: el tablero debe ser UNA llamada `rpc`, ninguna tabla."""

    def __init__(self, data):
        self.data, self.rpcs, self.tablas = data, [], []

    def rpc(self, nombre, params):
        self.rpcs.append((nombre, params))
        return _Rpc(self.data)

    def table(self, nombre):  # pragma: no cover — si se llama, el test falla
        self.tablas.append(nombre)
        raise AssertionError(f"el tablero no debe leer la tabla {nombre}")


def _repo_real(data):
    r = SupabaseRepo.__new__(SupabaseRepo)
    r._db = _DbFalsa(data)
    return r


def test_el_repo_real_es_una_sola_llamada_rpc_y_no_baja_filas():
    repo = _repo_real({"comercios": {"total": 1300}})
    out = repo.resumen_admin("bermejo", HOY)
    assert out == {"comercios": {"total": 1300}}
    assert repo._db.rpcs == [("admin_resumen", {"p_hoy": "2026-10-06", "p_ciudad_slug": "bermejo"})]
    assert repo._db.tablas == []


def test_el_repo_real_sin_ciudad_no_manda_el_parametro():
    repo = _repo_real({})
    repo.resumen_admin(None, HOY)
    assert repo._db.rpcs == [("admin_resumen", {"p_hoy": "2026-10-06"})]


def test_el_repo_real_responde_vacio_si_la_base_no_devuelve_un_objeto():
    assert _repo_real(None).resumen_admin(None, HOY) == {}


def test_el_cliente_de_reservalo_cuenta_las_pendientes(monkeypatch):
    from app.services import reservalo_sync

    monkeypatch.setattr(reservalo_sync.settings, "tienda_api_url", "http://tienda.test")
    monkeypatch.setattr(reservalo_sync.settings, "admin_sync_secret", "s3cret")
    visto = {}

    class Resp:
        def raise_for_status(self): pass
        def json(self): return {"items": [{"estado": "pendiente"}, {"estado": "respondida"}, {"estado": "pendiente"}]}

    def get(url, headers=None, params=None, timeout=None):
        visto.update(url=url, params=params, timeout=timeout)
        return Resp()

    monkeypatch.setattr(reservalo_sync.httpx, "get", get)
    assert ReservaloSyncClient().contar_consultas_pendientes() == 2
    assert visto["url"] == "http://tienda.test/api/admin-sync/consultas"
    assert visto["params"] == {"estado": "pendiente"} and visto["timeout"] <= 5


def test_el_cliente_de_reservalo_distingue_cero_de_no_contesto(monkeypatch):
    from app.services import reservalo_sync

    monkeypatch.setattr(reservalo_sync.settings, "tienda_api_url", "")
    monkeypatch.setattr(reservalo_sync.settings, "admin_sync_secret", "")
    assert ReservaloSyncClient().contar_consultas_pendientes() == 0          # sin configurar: no hay consultas

    monkeypatch.setattr(reservalo_sync.settings, "tienda_api_url", "http://tienda.test")
    monkeypatch.setattr(reservalo_sync.settings, "admin_sync_secret", "s3cret")

    def get(*a, **k):
        raise reservalo_sync.httpx.ConnectError("no responde")

    monkeypatch.setattr(reservalo_sync.httpx, "get", get)
    assert ReservaloSyncClient().contar_consultas_pendientes() is None       # configurado y caído: «no sé»


# ───────────────────────────────────────────────────────────── 9. la migración
def _sql(carpeta):
    raiz = Path(__file__).resolve().parents[2]
    return (raiz / carpeta / "0139_admin_resumen.sql").read_text(encoding="utf-8")


def test_la_migracion_0139_esta_igual_en_supabase_y_en_selfhost():
    assert _sql("supabase/migrations") == _sql("selfhost/postgres-init")


def test_la_migracion_0139_es_idempotente_y_el_publico_no_puede_llamarla():
    sql = _sql("supabase/migrations").lower()
    assert "create or replace function public.admin_resumen" in sql
    assert "revoke execute on function public.admin_resumen(text, date) from public, anon, authenticated" in sql
    assert "grant  execute on function public.admin_resumen(text, date) to service_role" in sql
    # Nada abierto a anon/authenticated, nada de borrar, y sólo lectura.
    assert " to anon" not in sql and " to authenticated" not in sql
    assert "delete from" not in sql and "drop " not in sql and "insert into" not in sql and "update " not in sql
    # Cada parte en su propio bloque, con el día de Bolivia.
    assert sql.count("exception when others then") >= 8
    assert "america/la_paz" in sql


# ───────────────────────── de la revisión de seguridad

def test_un_rol_del_sistema_vaciado_no_entra(client):
    """Vaciar los permisos de «moderador» desde Equipo es la única forma de
    apagar un rol del sistema. El token sale con `permisos: []`, y antes el
    respaldo para tokens viejos le devolvía todos los permisos de moderador."""
    t = auth.make_token("m@uruku.bo", rol="moderador", roles=["moderador"], permisos=[])
    assert client.get("/admin/resumen", headers=headers(t)).status_code == 403
    assert client.get("/moderacion/publicaciones", headers=headers(t)).status_code == 403


def test_un_token_viejo_sin_el_claim_sigue_con_los_permisos_de_su_rol():
    from app.core.permisos import permisos_de, tiene
    viejo = {"sub": "m@uruku.bo", "rol": "moderador"}          # emitido antes de los permisos
    assert permisos_de(viejo) and tiene(viejo, "moderar")
    assert permisos_de({"rol": "moderador", "permisos": []}) == []


# La de verdad: el fixture de arriba la reemplaza en cada test (no hay red).
_VENCE_REAL = vencimientos.vence_certificado


class _Sock:
    def __enter__(self): return self
    def __exit__(self, *a): return False


@pytest.mark.parametrize("codigo,estado", [(10, "vencido"), (62, "critico")])
def test_un_certificado_que_no_valida_es_alerta(monkeypatch, codigo, estado):
    """Con un certificado vencido el saludo TLS falla con
    SSLCertVerificationError; como `sin_dato` el tablero decía «al día»."""
    import ssl

    class _Ctx:
        def wrap_socket(self, *a, **k):
            e = ssl.SSLCertVerificationError("certificate verify failed")
            e.verify_code = codigo
            raise e

    monkeypatch.setattr(vencimientos.socket, "create_connection", lambda *a, **k: _Sock())
    monkeypatch.setattr(vencimientos.ssl, "create_default_context", lambda: _Ctx())
    r = _VENCE_REAL("uruku.bo")
    assert r["estado"] == estado and r["estado"] in vencimientos.ESTADOS_ALERTA


def test_un_host_que_no_contesta_sigue_siendo_sin_dato(monkeypatch):
    def caido(*a, **k):
        raise TimeoutError("timed out")
    monkeypatch.setattr(vencimientos.socket, "create_connection", caido)
    assert _VENCE_REAL("uruku.bo")["estado"] == "sin_dato"
