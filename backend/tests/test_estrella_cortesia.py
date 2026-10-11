"""La estrella, el plan de cortesía y el orden por plan (docs/cerca-abiertos-estrella.md).

Qué se prueba:
- `PUT /admin/comercio/{id}/plan`: quién puede (sólo `pagos`), el slug validado
  contra `planes`, qué guarda y qué devuelve.
- `POST /admin/pagos/{id}/confirmar` con `plan` opcional.
- Que la cortesía no cuente como «por vencer / vencido» (Suscripciones, tablero,
  alertas de estadísticas, estado que ve el comercio) y que el job de bajas no la oculte.
- La regla de la estrella y del orden del plan: una tabla de casos contra el
  espejo en Python y, si hay un Postgres de Docker, contra la función SQL real
  de la migración 0143 (variable `URUKU_PG_TEST_CONTAINER`, ver abajo).
- La migración 0143: igual en las dos carpetas, idempotente, sin dar precios a anon,
  con `planes_orden()` unida una sola vez en `buscar_comercios`.
(Los permisos por columna de `comercios`, 0145, se prueban en
test_comercios_columnas_publicas.py.)
"""
import os
import re
import shutil
import subprocess
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core import auth
from app.db.repository import SupabaseRepo

BOLIVIA = timezone(timedelta(hours=-4))
RAIZ = Path(__file__).resolve().parents[2]


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _hoy_bolivia() -> date:
    return datetime.now(BOLIVIA).date()


def _dia(dias: int) -> str:
    return (_hoy_bolivia() + timedelta(days=dias)).isoformat()


@pytest.fixture
def token_pagos():
    # El permiso `pagos` lo tiene el admin (y cualquier rol del panel que lo reciba).
    return auth.make_token("admin@uruku.bo", rol="admin")


def _comercio(repo, **extra):
    c = repo.crear_comercio({"nombre": "Local", "slug": "local", "whatsapp": "59170000001",
                             "activo": True, "plan": "gratis", **extra})
    return c["id"]


# ───────────────────────────────────────────── PUT /admin/comercio/{id}/plan

def test_asignar_plan_y_cortesia(client, repo, token_pagos):
    cid = _comercio(repo)
    r = client.put(f"/admin/comercio/{cid}/plan", headers=_h(token_pagos),
                   json={"plan": "pro", "cortesia": True})
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["ok"] is True
    assert (cuerpo["plan"], cuerpo["plan_cortesia"], cuerpo["paga_hasta"]) == ("pro", True, None)
    assert cuerpo["comercio"] == {"id": cid, "plan": "pro", "plan_cortesia": True, "paga_hasta": None}
    assert repo.comercios[cid]["plan"] == "pro"
    assert repo.comercios[cid]["plan_cortesia"] is True


def test_asignar_plan_sin_cortesia_y_sacarla(client, repo, token_pagos):
    cid = _comercio(repo, plan="pro", plan_cortesia=True)
    # `cortesia` omitido = false: se saca la cortesía y queda el plan.
    r = client.put(f"/admin/comercio/{cid}/plan", headers=_h(token_pagos), json={"plan": "publica"})
    assert r.status_code == 200, r.text
    assert repo.comercios[cid]["plan"] == "publica"
    assert repo.comercios[cid]["plan_cortesia"] is False


def test_asignar_plan_no_toca_paga_hasta(client, repo, token_pagos):
    cid = _comercio(repo, paga_hasta=_dia(12))
    r = client.put(f"/admin/comercio/{cid}/plan", headers=_h(token_pagos),
                   json={"plan": "destacado", "cortesia": False})
    assert r.json()["paga_hasta"] == _dia(12)
    assert repo.comercios[cid]["paga_hasta"] == _dia(12)


def test_plan_inexistente_da_400_y_no_cambia_nada(client, repo, token_pagos):
    cid = _comercio(repo)
    r = client.put(f"/admin/comercio/{cid}/plan", headers=_h(token_pagos),
                   json={"plan": "platino", "cortesia": True})
    assert r.status_code == 400
    assert "platino" in r.json()["detail"]
    assert repo.comercios[cid]["plan"] == "gratis"
    assert not repo.comercios[cid].get("plan_cortesia")


def test_plan_inactivo_tampoco_se_puede_asignar(client, repo, token_pagos):
    repo.planes["pro"]["activo"] = False
    cid = _comercio(repo)
    r = client.put(f"/admin/comercio/{cid}/plan", headers=_h(token_pagos), json={"plan": "pro"})
    assert r.status_code == 400


def test_comercio_inexistente_da_404(client, token_pagos):
    r = client.put("/admin/comercio/no-existe/plan", headers=_h(token_pagos), json={"plan": "pro"})
    assert r.status_code == 404


@pytest.mark.parametrize("cuerpo", [{}, {"plan": ""}, {"plan": "x" * 61}, {"plan": "pro", "cortesia": "tal vez"}])
def test_el_cuerpo_se_valida(client, repo, token_pagos, cuerpo):
    cid = _comercio(repo)
    assert client.put(f"/admin/comercio/{cid}/plan", headers=_h(token_pagos), json=cuerpo).status_code == 422


def test_quien_puede_asignar_plan(client, repo, token_pagos):
    cid = _comercio(repo)
    url, cuerpo = f"/admin/comercio/{cid}/plan", {"plan": "pro", "cortesia": True}
    # Sin token y con tokens equivocados: nadie más que `pagos`.
    assert client.put(url, json=cuerpo).status_code in (401, 403)
    assert client.put(url, headers=_h("token-roto"), json=cuerpo).status_code in (401, 403)
    moderador = auth.make_token("mod@uruku.bo", rol="moderador")
    assert client.put(url, headers=_h(moderador), json=cuerpo).status_code == 403
    agente = auth.make_agente_token("agente@uruku.bo")
    assert client.put(url, headers=_h(agente), json=cuerpo).status_code == 403
    comercio = auth.make_comercio_token(cid, "dueno@x.com")
    assert client.put(url, headers=_h(comercio), json=cuerpo).status_code == 403
    # Ninguno de esos intentos tocó nada.
    assert repo.comercios[cid]["plan"] == "gratis"
    assert not repo.comercios[cid].get("plan_cortesia")
    # Y el que tiene `pagos` sí.
    assert client.put(url, headers=_h(token_pagos), json=cuerpo).status_code == 200


def test_un_rol_del_panel_con_el_permiso_pagos_puede(client, repo):
    cid = _comercio(repo)
    t = auth.make_token("cobros@uruku.bo", rol="cobrador", roles=["cobrador"], permisos=["pagos"])
    assert client.put(f"/admin/comercio/{cid}/plan", headers=_h(t), json={"plan": "pro"}).status_code == 200
    t_sin = auth.make_token("otro@uruku.bo", rol="otro", roles=["otro"], permisos=["datos"])
    assert client.put(f"/admin/comercio/{cid}/plan", headers=_h(t_sin), json={"plan": "pro"}).status_code == 403


def test_el_comercio_no_se_puede_dar_cortesia_desde_su_perfil(client, repo):
    """`plan_cortesia` no está entre los campos que el comercio edita de su perfil."""
    from app.api import comercio as api_comercio
    assert "plan_cortesia" not in api_comercio._CAMPOS_EDITABLES
    assert "plan_cortesia" not in api_comercio._CAMPOS_PERFIL


def test_asignar_plan_deja_el_log(client, repo, token_pagos):
    import structlog
    cid = _comercio(repo)
    with structlog.testing.capture_logs() as logs:
        client.put(f"/admin/comercio/{cid}/plan", headers=_h(token_pagos), json={"plan": "pro", "cortesia": True})
    ev = [l for l in logs if l["event"] == "comercio.plan_asignado"]
    assert len(ev) == 1
    assert ev[0]["comercio"] == cid and ev[0]["plan"] == "pro" and ev[0]["cortesia"] is True
    assert ev[0]["by"] == "admin@uruku.bo"


# ───────────────────────────────────────────── confirmar pago con plan

def _pago_pendiente(repo, cid):
    pid = "pag-1"
    repo.pagos[pid] = {"id": pid, "comercio_id": cid, "estado": "pendiente", "monto": 70}
    return pid


def test_confirmar_pago_con_plan_asigna_el_plan_y_extiende(client, repo, token_pagos):
    cid = _comercio(repo)
    pid = _pago_pendiente(repo, cid)
    r = client.post(f"/admin/pagos/{pid}/confirmar", headers=_h(token_pagos),
                    json={"meses": 2, "plan": "destacado"})
    assert r.status_code == 200, r.text
    assert r.json()["plan"] == "destacado"
    assert r.json()["paga_hasta"]
    assert repo.comercios[cid]["plan"] == "destacado"
    assert repo.comercios[cid]["paga_hasta"] == r.json()["paga_hasta"]
    assert repo.pagos[pid]["estado"] == "confirmado"


def test_confirmar_pago_sin_plan_queda_como_siempre(client, repo, token_pagos):
    cid = _comercio(repo)
    pid = _pago_pendiente(repo, cid)
    r = client.post(f"/admin/pagos/{pid}/confirmar", headers=_h(token_pagos), json={"meses": 1})
    assert r.status_code == 200, r.text
    assert "plan" not in r.json()
    assert repo.comercios[cid]["plan"] == "gratis"
    assert repo.comercios[cid]["paga_hasta"]
    # Y sin body, como siempre.
    pid2 = "pag-2"
    repo.pagos[pid2] = {"id": pid2, "comercio_id": cid, "estado": "pendiente", "monto": 70}
    assert client.post(f"/admin/pagos/{pid2}/confirmar", headers=_h(token_pagos), json={}).status_code == 200


def test_confirmar_pago_con_plan_inexistente_da_400_y_el_pago_sigue_pendiente(client, repo, token_pagos):
    cid = _comercio(repo)
    pid = _pago_pendiente(repo, cid)
    r = client.post(f"/admin/pagos/{pid}/confirmar", headers=_h(token_pagos),
                    json={"meses": 1, "plan": "platino"})
    assert r.status_code == 400
    assert repo.pagos[pid]["estado"] == "pendiente"
    assert repo.comercios[cid]["plan"] == "gratis"
    assert not repo.comercios[cid].get("paga_hasta")


def test_confirmar_pago_con_plan_sigue_pidiendo_permiso(client, repo):
    cid = _comercio(repo)
    pid = _pago_pendiente(repo, cid)
    moderador = auth.make_token("mod@uruku.bo", rol="moderador")
    r = client.post(f"/admin/pagos/{pid}/confirmar", headers=_h(moderador), json={"meses": 1, "plan": "pro"})
    assert r.status_code == 403
    assert repo.comercios[cid]["plan"] == "gratis"


# ───────────────────────────────────────────── la cortesía no vence

def _por_estado(client, token):
    items = client.get("/admin/suscripciones", headers=_h(token)).json()["items"]
    return {i["nombre"]: i for i in items}


def test_suscripciones_devuelve_plan_y_plan_cortesia_y_la_cortesia_no_vence(client, repo, token_pagos):
    _comercio(repo, nombre="Cortesia sin fecha", slug="c1", plan="pro", plan_cortesia=True)
    _comercio(repo, nombre="Cortesia vencida", slug="c2", plan="pro", plan_cortesia=True, paga_hasta=_dia(-90))
    _comercio(repo, nombre="Cortesia por vencer", slug="c3", plan="pro", plan_cortesia=True, paga_hasta=_dia(2))
    _comercio(repo, nombre="Paga vencido", slug="c4", plan="pro", paga_hasta=_dia(-3))
    _comercio(repo, nombre="Paga por vencer", slug="c5", plan="pro", paga_hasta=_dia(3))
    _comercio(repo, nombre="Paga al dia", slug="c6", plan="publica", paga_hasta=_dia(40))

    por = _por_estado(client, token_pagos)
    for n in ("Cortesia sin fecha", "Cortesia vencida", "Cortesia por vencer"):
        assert por[n]["suscripcion_estado"] == "cortesia", n
        assert por[n]["plan_cortesia"] is True
        assert por[n]["plan"] == "pro"
    # Lo demás, igual que antes.
    assert por["Paga vencido"]["suscripcion_estado"] == "vencido"
    assert por["Paga por vencer"]["suscripcion_estado"] == "por_vencer"
    assert por["Paga al dia"]["suscripcion_estado"] == "activo"
    assert por["Paga al dia"]["plan_cortesia"] is False and por["Paga al dia"]["plan"] == "publica"


def test_cortesia_suspendida_se_muestra_suspendida(client, repo, token_pagos):
    _comercio(repo, nombre="Cortesia parada", plan="pro", plan_cortesia=True, suspendido=True)
    assert _por_estado(client, token_pagos)["Cortesia parada"]["suscripcion_estado"] == "suspendido"


def test_el_tablero_no_cuenta_la_cortesia_como_por_vencer(client, repo):
    _comercio(repo, nombre="Cortesia vencida", slug="c1", plan="pro", plan_cortesia=True, paga_hasta=_dia(-90))
    _comercio(repo, nombre="Cortesia por vencer", slug="c2", plan="pro", plan_cortesia=True, paga_hasta=_dia(2))
    _comercio(repo, nombre="Cortesia sin fecha", slug="c3", plan="pro", plan_cortesia=True)
    _comercio(repo, nombre="Vencido", slug="c4", plan="pro", paga_hasta=_dia(-3))
    t = auth.make_token("admin@uruku.bo", rol="admin")
    r = client.get("/admin/resumen", headers=_h(t))
    assert r.status_code == 200, r.text
    assert r.json()["pendientes"]["suscripciones"] == 1  # sólo «Vencido»


def test_el_tablero_cuenta_la_cortesia_suspendida(client, repo):
    _comercio(repo, nombre="Cortesia parada", plan="pro", plan_cortesia=True, suspendido=True)
    t = auth.make_token("admin@uruku.bo", rol="admin")
    assert client.get("/admin/resumen", headers=_h(t)).json()["pendientes"]["suscripciones"] == 1


def test_el_estado_que_ve_el_comercio_de_cortesia(client, repo):
    from app.api.comercio import _estado_suscripcion
    sano = _estado_suscripcion({"plan": "pro", "plan_cortesia": True, "paga_hasta": _dia(-60)})
    assert sano["estado"] == "cortesia" and sano["plan_cortesia"] is True and sano["dias_restantes"] is None
    sin_fecha = _estado_suscripcion({"plan": "pro", "plan_cortesia": True})
    assert sin_fecha["estado"] == "cortesia"
    parada = _estado_suscripcion({"plan": "pro", "plan_cortesia": True, "suspendido": True})
    assert parada["estado"] == "suspendido"
    # Los demás, sin cambios.
    assert _estado_suscripcion({"plan": "pro"})["estado"] == "sin_pago"
    assert _estado_suscripcion({"plan": "pro", "paga_hasta": _dia(-1)})["estado"] == "vencido"
    assert _estado_suscripcion({"plan": "pro", "paga_hasta": _dia(3)})["estado"] == "por_vencer"
    assert _estado_suscripcion({"plan": "pro", "paga_hasta": _dia(30)})["estado"] == "activo"
    assert _estado_suscripcion({"plan": "gratis"})["plan_cortesia"] is False


def test_el_job_de_bajas_no_oculta_a_la_cortesia(repo):
    viejo = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat()
    cort_sin_fecha = _comercio(repo, nombre="A", slug="a", plan="pro", plan_cortesia=True, created_at=viejo)
    cort_vencida = _comercio(repo, nombre="B", slug="b", plan="pro", plan_cortesia=True,
                             paga_hasta=_dia(-300), created_at=viejo)
    paga_vencido = _comercio(repo, nombre="C", slug="c", plan="pro", paga_hasta=_dia(-300), created_at=viejo)
    nunca_pago = _comercio(repo, nombre="D", slug="d", created_at=viejo)
    assert repo.ocultar_comercios_vencidos(dias=40, dias_gracia=30) == 2
    assert repo.comercios[cort_sin_fecha]["activo"] and repo.comercios[cort_vencida]["activo"]
    assert not repo.comercios[paga_vencido]["activo"] and not repo.comercios[nunca_pago]["activo"]


# ───────────────────────────────────────────── el repo REAL (un cliente PostgREST de mentira)

class _Consulta:
    """Una consulta encadenable de PostgREST que anota qué se le pidió."""

    def __init__(self, db, tabla):
        self.db, self.tabla, self.op, self.filtros, self.valores = db, tabla, "select", [], None

    def __getattr__(self, nombre):
        def _llamar(*a, **k):
            if nombre in ("update", "insert", "upsert"):
                self.op, self.valores = nombre, (a[0] if a else None)
            else:
                self.filtros.append((nombre, a))
            return self
        return _llamar

    @property
    def not_(self):
        return self

    def execute(self):
        self.db.consultas.append(self)
        filas = self.db.datos.get(self.tabla, [])
        return SimpleNamespace(data=list(filas), count=len(filas))


class _DbFalsa:
    def __init__(self, datos):
        self.datos, self.consultas = datos, []

    def table(self, tabla):
        return _Consulta(self, tabla)


def _repo_real(datos):
    r = SupabaseRepo.__new__(SupabaseRepo)
    r._db = _DbFalsa(datos)
    return r


def test_repo_real_list_suscripciones_pide_plan_cortesia_y_marca_cortesia():
    repo = _repo_real({"comercios": [
        {"id": "1", "nombre": "A", "plan": "pro", "plan_cortesia": True, "paga_hasta": _dia(-50), "suspendido": False},
        {"id": "2", "nombre": "B", "plan": "pro", "plan_cortesia": False, "paga_hasta": _dia(-50), "suspendido": False},
        {"id": "3", "nombre": "C", "plan": "pro", "plan_cortesia": None, "paga_hasta": _dia(30), "suspendido": False},
        {"id": "4", "nombre": "D", "plan": "pro", "plan_cortesia": True, "paga_hasta": None, "suspendido": True},
    ]})
    items = {i["nombre"]: i for i in repo.list_suscripciones()}
    assert items["A"]["suscripcion_estado"] == "cortesia" and items["A"]["plan_cortesia"] is True
    assert items["B"]["suscripcion_estado"] == "vencido" and items["B"]["plan_cortesia"] is False
    assert items["C"]["suscripcion_estado"] == "activo" and items["C"]["plan_cortesia"] is False
    assert items["D"]["suscripcion_estado"] == "suspendido"
    pedido = repo._db.consultas[0].filtros[0]
    assert pedido[0] == "select" and "plan_cortesia" in pedido[1][0] and "plan" in pedido[1][0]


def test_repo_real_las_alertas_de_estadisticas_no_cuentan_la_cortesia():
    repo = _repo_real({"comercios": [
        {"id": "1", "nombre": "cort vencida", "created_at": "2020-01-01", "suspendido": False,
         "paga_hasta": _dia(-90), "plan_cortesia": True},
        {"id": "2", "nombre": "cort por vencer", "created_at": "2020-01-01", "suspendido": False,
         "paga_hasta": _dia(1), "plan_cortesia": True},
        {"id": "3", "nombre": "vencido", "created_at": "2020-01-01", "suspendido": False,
         "paga_hasta": _dia(-90), "plan_cortesia": False},
        {"id": "4", "nombre": "por vencer", "created_at": "2020-01-01", "suspendido": False,
         "paga_hasta": _dia(1), "plan_cortesia": False},
        {"id": "5", "nombre": "suspendido", "created_at": "2020-01-01", "suspendido": True,
         "paga_hasta": None, "plan_cortesia": False},
    ]})
    alertas = repo.estadisticas_admin()["alertas"]
    assert alertas == {"vencido": 1, "suspendido": 1, "por_vencer": 1}


def test_repo_real_el_job_de_bajas_excluye_la_cortesia_en_las_dos_pasadas():
    repo = _repo_real({"comercios": []})
    repo.ocultar_comercios_vencidos(dias=40, dias_gracia=30)
    updates = [c for c in repo._db.consultas if c.op == "update"]
    assert len(updates) == 2
    for u in updates:
        assert ("eq", ("plan_cortesia", False)) in u.filtros


def test_repo_real_asignar_plan_escribe_plan_y_cortesia():
    repo = _repo_real({"comercios": [{"id": "c1", "plan": "pro", "plan_cortesia": True, "paga_hasta": None}]})
    out = repo.asignar_plan_comercio("c1", "pro", True)
    assert out == {"id": "c1", "plan": "pro", "plan_cortesia": True, "paga_hasta": None}
    u = repo._db.consultas[-1]
    assert u.op == "update" and u.valores == {"plan": "pro", "plan_cortesia": True}
    assert ("eq", ("id", "c1")) in u.filtros
    assert _repo_real({"comercios": []}).asignar_plan_comercio("nada", "pro", False) is None


def test_repo_real_confirmar_pago_con_plan_lo_escribe_y_sin_plan_no_lo_toca():
    pago = {"id": "p1", "comercio_id": "c1", "estado": "pendiente"}
    comercio = {"id": "c1", "plan": "gratis", "paga_hasta": None}
    repo = _repo_real({"pagos": [pago], "comercios": [comercio], "publicaciones": []})
    out = repo.confirmar_pago("p1", 1, "admin@uruku.bo", "destacado")
    assert out["plan"] == "destacado"
    cambios = [c.valores for c in repo._db.consultas if c.tabla == "comercios" and c.op == "update"]
    assert cambios[0]["plan"] == "destacado" and cambios[0]["suspendido"] is False and "paga_hasta" in cambios[0]

    repo = _repo_real({"pagos": [pago], "comercios": [comercio], "publicaciones": []})
    out = repo.confirmar_pago("p1", 1, "admin@uruku.bo")
    assert "plan" not in out
    cambios = [c.valores for c in repo._db.consultas if c.tabla == "comercios" and c.op == "update"]
    assert "plan" not in cambios[0]


# ───────────────────────────────────────────── la regla de la estrella

# (descripción, plan, cortesía, paga_hasta en días desde hoy-de-Bolivia | None, suspendido, plan_orden)
# Precios de la base: gratis 0 · publica 70 · destacado 140 · premium 140 (viejo) · pro 400 · empleado_ia 1250.
CASOS = [
    ("pago al día",                         "pro",       False,  30,   False, 3),
    ("vence hoy: todavía al día",           "publica",   False,  0,    False, 1),
    ("venció ayer: no",                     "pro",       False,  -1,   False, 0),
    ("suspendido: no",                      "pro",       False,  30,   True,  0),
    ("plan gratis al día: no",              "gratis",    False,  30,   False, 0),
    ("plan gratis sin fecha: no",           "gratis",    False,  None, False, 0),
    ("plan pago sin fecha ni cortesía: no", "pro",       False,  None, False, 0),
    ("cortesía sin fecha: sí",              "pro",       True,   None, False, 3),
    ("cortesía vencida: sí, no vence",      "pro",       True,   -200, False, 3),
    ("cortesía en un plan gratis: no",      "gratis",    True,   None, False, 0),
    ("cortesía suspendida: no",             "pro",       True,   None, True,  0),
    ("el más caro pesa más",                "empleado_ia", False, 30,  False, 4),
    ("destacado",                           "destacado", False,  30,   False, 2),
    ("mismo precio, mismo orden",           "premium",   False,  30,   False, 2),
    ("plan que no existe: no",              "fantasma",  False,  30,   False, 0),
]
PRECIOS = {"gratis": 0, "publica": 70, "destacado": 140, "premium": 140, "pro": 400, "empleado_ia": 1250}


def _espejo(plan, cortesia, paga_hasta_dias, suspendido, precios=PRECIOS):
    """La regla de 0143 en Python: plan pago (precio > 0) y al día (cortesía, o
    paga_hasta >= hoy de Bolivia y no suspendido). plan_orden = posición del precio
    entre los precios pagos distintos (más caro = más alto)."""
    if suspendido:                     # suspendido = sin estrella, también la cortesía
        return 0
    al_dia = cortesia or (paga_hasta_dias is not None and paga_hasta_dias >= 0)
    if not al_dia or precios.get(plan, 0) <= 0:
        return 0
    return sorted({p for p in precios.values() if p > 0}).index(precios[plan]) + 1


@pytest.mark.parametrize("desc,plan,cortesia,dias,suspendido,esperado", CASOS, ids=[c[0] for c in CASOS])
def test_regla_de_la_estrella_en_el_espejo(desc, plan, cortesia, dias, suspendido, esperado):
    assert _espejo(plan, cortesia, dias, suspendido) == esperado


# ----- contra un Postgres real (Docker). Opcional:
#   docker run -d --name pg-0143 -e POSTGRES_PASSWORD=x postgres:17-alpine
#   $env:URUKU_PG_TEST_CONTAINER="pg-0143"   (o export en bash)
# Crea una base descartable, arma el mínimo de tablas, corre las funciones de la
# migración 0143 TAL CUAL están en el archivo y la borra al terminar.

def _migracion(carpeta="supabase/migrations") -> str:
    return (RAIZ / carpeta / "0143_estrella_y_cortesia.sql").read_text(encoding="utf-8")


def _funciones_de_plan() -> str:
    sql = _migracion()
    ini = sql.index("create or replace function public.planes_orden")
    fin = sql.index("-- ------------------------------------------------------- buscar_comercios")
    return sql[ini:fin]


@pytest.fixture(scope="module")
def pg():
    contenedor = os.environ.get("URUKU_PG_TEST_CONTAINER")
    if not contenedor or not shutil.which("docker"):
        pytest.skip("sin Postgres de Docker (URUKU_PG_TEST_CONTAINER)")
    base = "t0143_" + uuid.uuid4().hex[:8]

    def psql(sql, db=base, check=True):
        p = subprocess.run(
            ["docker", "exec", "-i", contenedor, "psql", "-U", "postgres", "-d", db,
             "-v", "ON_ERROR_STOP=1", "-At", "-q", "-F", "|", "-f", "-"],
            input=sql, capture_output=True, text=True, encoding="utf-8")
        if check and p.returncode != 0:
            raise AssertionError(p.stderr)
        return p

    psql(f'create database "{base}"', db="postgres")
    try:
        psql("""
            do $$ begin
              begin create role anon nologin; exception when duplicate_object then null; end;
              begin create role authenticated nologin; exception when duplicate_object then null; end;
              begin create role service_role nologin; exception when duplicate_object then null; end;
            end $$;
            create table planes (slug text primary key, precio_mes numeric(10,2) not null default 0,
                                 nombre text);
            insert into planes values ('gratis',0,'Básico'),('publica',70,'Publica'),('destacado',140,'D'),
              ('premium',140,'Viejo'),('pro',400,'Pro'),('empleado_ia',1250,'E');
            create table comercios (id uuid primary key default gen_random_uuid(), nombre text, plan text,
              plan_cortesia boolean not null default false, paga_hasta date,
              suspendido boolean not null default false, activo boolean not null default true);
            grant usage on schema public to anon, authenticated, service_role;
            -- Como en 0134: el público lee `planes` SIN la columna precio_mes.
            revoke all on planes from anon, authenticated;
            grant select (slug, nombre) on planes to anon, authenticated;
            -- Como en 0145: el público lee `comercios` por COLUMNAS, sin plan_cortesia ni
            -- paga_hasta. Las funciones SECURITY DEFINER tienen que andar igual.
            grant select (id, nombre, plan, suspendido, activo) on comercios to anon, authenticated;
        """)
        psql(_funciones_de_plan())
        yield psql
    finally:
        psql(f'drop database if exists "{base}" with (force)', db="postgres", check=False)


def _sql_valor(valor):
    return "null" if valor is None else repr(valor) if isinstance(valor, bool) else f"'{valor}'" if isinstance(valor, str) else str(valor)


@pytest.mark.parametrize("desc,plan,cortesia,dias,suspendido,esperado", CASOS, ids=[c[0] for c in CASOS])
def test_regla_de_la_estrella_en_postgres(pg, desc, plan, cortesia, dias, suspendido, esperado):
    paga = "null" if dias is None else f"(now() at time zone 'America/La_Paz')::date + {dias}"
    out = pg(f"""
        set role anon;
        select public.plan_orden_de('{plan}', {str(cortesia).lower()}, {paga}, {str(suspendido).lower()});
    """).stdout.strip().splitlines()
    assert out[-1] == str(esperado), (desc, out)


def test_plan_publico_en_postgres(pg):
    pg("""
        insert into comercios (id, nombre, plan, plan_cortesia, paga_hasta, suspendido, activo) values
          ('00000000-0000-0000-0000-000000000001','pro al dia','pro',false,(now() at time zone 'America/La_Paz')::date + 5,false,true),
          ('00000000-0000-0000-0000-000000000002','pro vencido','pro',false,(now() at time zone 'America/La_Paz')::date - 1,false,true),
          ('00000000-0000-0000-0000-000000000003','cortesia','pro',true,null,false,true),
          ('00000000-0000-0000-0000-000000000004','baja','pro',true,null,false,false);
    """)
    def estrella(n):
        r = pg(f"set role anon; select estrella, plan_orden from public.plan_publico('00000000-0000-0000-0000-00000000000{n}');")
        return r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
    assert estrella(1) == "t|3"
    assert estrella(2) == "f|0"
    assert estrella(3) == "t|3"
    assert estrella(4) == ""          # dado de baja: no devuelve filas
    assert estrella(9) == ""          # no existe


def test_planes_orden_en_postgres_devuelve_orden_sin_precios(pg):
    """El ranking de los planes pagos: dense_rank del precio. `gratis` (precio 0) no
    entra; `destacado` y `premium` (mismo precio) empatan."""
    out = pg("set role anon; select slug, orden from public.planes_orden() order by orden, slug;").stdout.strip().splitlines()
    assert out == ["publica|1", "destacado|2", "premium|2", "pro|3", "empleado_ia|4"]
    assert not re.search(r"\b(70|140|400|1250)\b", "|".join(out))


def test_anon_no_lee_precio_mes_ni_siquiera_a_traves_de_las_funciones(pg):
    # Directo: no.
    directo = pg("set role anon; select precio_mes from planes;", check=False)
    assert directo.returncode != 0 and "permission denied" in directo.stderr
    # Por las funciones: sólo enteros de orden; en ninguna columna sale 70/140/400/1250.
    pg("insert into comercios (nombre, plan, plan_cortesia) values ('x','empleado_ia',true);")
    for consulta in ("select * from public.plan_publico((select id from comercios where nombre='x'))",
                     "select public.plan_orden_de('empleado_ia', true, null, false)"):
        salida = pg(f"set role anon; {consulta};").stdout.strip().splitlines()[-1]
        assert not re.search(r"\b(70|140|400|1250)\b", salida), salida


# ───────────────────────────────────────────── la migración 0143

def test_la_migracion_0143_esta_igual_en_supabase_y_en_selfhost():
    a = (RAIZ / "supabase/migrations/0143_estrella_y_cortesia.sql").read_bytes()
    b = (RAIZ / "selfhost/postgres-init/0143_estrella_y_cortesia.sql").read_bytes()
    assert a == b and a


def test_la_migracion_0143_es_idempotente_y_recarga_postgrest():
    sql = _migracion()
    assert "add column if not exists plan_cortesia boolean not null default false" in sql
    assert re.search(r"comment on column comercios\.plan_cortesia", sql)
    assert "drop function if exists buscar_comercios(text, text, text, text, numeric, numeric, text, int, int, text)" in sql
    assert sql.count("create or replace function") >= 4          # planes_orden, plan_orden_de, plan_publico, admin_resumen
    assert not re.search(r"create table(?! if not exists)", sql)
    assert sql.rstrip().endswith("notify pgrst, 'reload schema';")


def test_la_migracion_0143_no_expone_precio_mes_a_anon():
    sql = _migracion()
    # Ningún GRANT ni cambio de permisos sobre `planes`...
    assert not re.search(r"grant[^;]*\bplanes\b", sql, re.I)
    assert not re.search(r"(?m)^\s*(grant|revoke)\b[^;]*precio_mes", sql, re.I)
    # ...y el cálculo vive en funciones SECURITY DEFINER con search_path fijo.
    for nombre in ("planes_orden", "plan_orden_de", "plan_publico"):
        cuerpo = sql[sql.index(f"create or replace function public.{nombre}"):]
        cabecera = cuerpo[:cuerpo.index("$fn$")]
        assert "security definer" in cabecera, nombre
        assert "set search_path = public, pg_temp" in cabecera, nombre
        assert f"revoke execute on function public.{nombre}" in sql
        assert re.search(rf"grant\s+execute on function public\.{nombre}\([^)]*\) to anon, authenticated", sql), nombre
    # Ninguna de las dos devuelve el precio.
    assert "returns table (estrella boolean, plan_orden int)" in sql
    assert "returns table (slug text, orden int)" in sql
    assert "returns int" in sql


def test_la_migracion_0143_buscar_comercios_agrega_sin_quitar():
    sql = _migracion()
    anterior = (RAIZ / "supabase/migrations/0120_te_contesto.sql").read_text(encoding="utf-8")

    def columnas(texto):
        bloque = texto[texto.index("returns table ("):texto.index(")\nlanguage sql")]
        return [c.strip().split()[0] for c in bloque.replace("returns table (", "").split(",") if c.strip()]

    antes = columnas(anterior[anterior.index("create function buscar_comercios"):])
    ahora = columnas(sql[sql.index("create function buscar_comercios"):])
    assert ahora[:len(antes)] == antes                      # mismas columnas, mismo orden
    # las nuevas, al final (horario_estimado: el sello «Suele estar abierto» del buscador)
    assert ahora[len(antes):] == ["estrella", "plan_orden", "horario_estimado"]
    # Mismos parámetros y mismos grants que tenía.
    firma = "q text default null, p_rubro text default null, p_modalidad text default null,\n  p_zona text default null"
    assert firma in sql
    assert "to anon, authenticated, service_role" in sql[sql.index("grant  execute on function buscar_comercios"):]
    # El orden: relevancia, después el plan, después lo de siempre.
    assert "order by rank desc, plan_orden desc, principal desc, no_contesta asc, nombre, id" in sql
    assert "security definer" in sql[sql.index("create function buscar_comercios"):sql.index("as $$")].lower()


def _buscar_comercios_sql(sql: str) -> tuple[str, str]:
    """(cabecera, cuerpo) de buscar_comercios en la migración 0143."""
    ini = sql.index("create function buscar_comercios")
    return sql[ini:sql.index("as $$", ini)], sql[sql.index("as $$", ini):sql.index("$$;", sql.index("as $$", ini) + 5)]


def test_la_migracion_0143_buscar_comercios_une_planes_orden_una_vez_y_sin_plan_orden_de():
    cabecera, cuerpo = _buscar_comercios_sql(_migracion())
    # La velocidad: el ranking de precios se une UNA vez; nada por fila.
    assert cuerpo.count("public.planes_orden()") == 1
    assert "left join public.planes_orden() po on po.slug = f.plan" in cuerpo
    assert "plan_orden_de(" not in cuerpo                       # (el comentario puede nombrarla)
    # El «al día» va en línea, con el «hoy» de Bolivia y la misma regla que plan_orden_de.
    assert "(now() at time zone 'America/La_Paz')::date as hoy" in cuerpo
    assert "f.suspendido" in cuerpo
    assert "f.plan_cortesia or (f.paga_hasta is not null and f.paga_hasta >= f.hoy)" in cuerpo
    # Y se une sobre los que quedaron, no sobre la unión con publicaciones.
    assert cuerpo.index("con_plan as (") > cuerpo.index("filtrados as (")


def test_la_migracion_0143_buscar_comercios_es_definer_y_repite_lo_que_el_rls_dejaba_ver():
    """Desde la 0145 el público no lee `plan_cortesia` ni `paga_hasta`: la búsqueda
    los lee con permisos propios (SECURITY DEFINER) y a mano repite el RLS."""
    sql = _migracion()
    cabecera, cuerpo = _buscar_comercios_sql(sql)
    assert "security definer" in cabecera.lower()
    assert "set search_path = public, pg_temp" in cabecera
    assert "revoke execute on function buscar_comercios(text, text, text, text, numeric, numeric, text, int, int, text) from public;" in sql
    # RLS de comercios / publicaciones / rubros / zonas, escrito en la consulta.
    assert "where c.activo" in cuerpo
    assert "p.estado = 'aprobado' and p.activo" in cuerpo
    assert "pp.estado = 'aprobado' and pp.activo" in cuerpo
    assert "left join rubros r on r.id = c.rubro_id and r.activo" in cuerpo
    assert "left join zonas z on z.id = c.zona_id and z.activo" in cuerpo
    for alias, rel in (("r2", "cr"), ("r3", "cr2"), ("r4", "cr3"), ("r5", "cr4")):
        assert f"join rubros {alias} on {alias}.id = {rel}.rubro_id and {alias}.activo" in cuerpo, alias
    # Y no devuelve las columnas privadas.
    salida = cuerpo[cuerpo.rindex("select id, slug, nombre"):]
    for privada in ("plan_cortesia", "paga_hasta", "cargado_por", "capturado_en"):
        assert privada not in salida


def test_la_migracion_0143_el_tablero_no_cuenta_la_cortesia():
    sql = _migracion()
    assert "not c.plan_cortesia and c.paga_hasta is not null and c.paga_hasta <= v_hoy + 5" in sql
    # El resto de admin_resumen sigue siendo sólo del backend.
    assert "revoke execute on function public.admin_resumen(text, date) from public, anon, authenticated;" in sql
    assert "grant  execute on function public.admin_resumen(text, date) to service_role;" in sql



# ───────────────────────────────────────────── de la revisión

def test_no_se_da_cortesia_en_un_plan_gratis(client, repo, token_pagos):
    cid = _comercio(repo)
    r = client.put(f"/admin/comercio/{cid}/plan", headers=_h(token_pagos),
                   json={"plan": "gratis", "cortesia": True})
    assert r.status_code == 400
    assert repo.comercios[cid].get("plan_cortesia") in (None, False)


def test_confirmar_un_pago_con_plan_saca_la_cortesia(client, repo, token_pagos):
    cid = _comercio(repo, plan="pro", plan_cortesia=True)
    pago = _pago_pendiente(repo, cid)
    r = client.post(f"/admin/pagos/{pago}/confirmar", headers=_h(token_pagos), json={"meses": 1, "plan": "pro"})
    assert r.status_code == 200, r.text
    assert repo.comercios[cid]["plan_cortesia"] is False


def test_la_lista_de_planes_la_lee_quien_tiene_pagos(client, repo):
    from app.core import auth
    t = auth.make_token("cobra@uruku.bo", rol="cobrador", roles=["cobrador"], permisos=["pagos"])
    assert client.get("/admin/planes", headers=_h(t)).status_code == 200
    sin = auth.make_token("x@uruku.bo", rol="lugares", roles=["lugares"], permisos=["lugares"])
    assert client.get("/admin/planes", headers=_h(sin)).status_code == 403
