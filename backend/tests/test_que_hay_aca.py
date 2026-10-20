"""«Qué hay acá» (docs/que-hay-aca.md): lo que el backend le da a la primera pantalla del agente.

- `GET /campo/mis-comercios` suma `estado_plan`, `fotos_count` y `rubro_slug` (sin precios).
- `GET /campo/ejemplos`: hasta 3 completos de la ciudad del agente.
- `GET /campo/planes`: planes de pago, sólo nombre.
- `POST /campo/mis-comercios/{id}/interes` y su rastro en `GET /admin/suscripciones`.
- La migración 0151.
"""
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.core import auth
from app.services import que_hay_aca
from tests.pg_0149 import pg0149  # noqa: F401

BOLIVIA = timezone(timedelta(hours=-4))
RAIZ = Path(__file__).resolve().parents[2]
CIUDAD = "ciu-1"            # «bermejo» en el fake
CIUDAD_AJENA = "ciu-santa-cruz"


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _dia(dias: int) -> str:
    return (datetime.now(BOLIVIA).date() + timedelta(days=dias)).isoformat()


@pytest.fixture
def agente():
    return auth.make_agente_token("agente@uruku.bo", ciudad_slug="bermejo")


@pytest.fixture
def admin():
    return auth.make_token("admin@uruku.bo", rol="admin")


def _comercio(repo, nombre="Local", **extra):
    base = {"nombre": nombre, "slug": nombre.lower().replace(" ", "-"), "whatsapp": "59170000001",
            "activo": True, "plan": "gratis", "ciudad_id": CIUDAD, "cargado_por": "otro@uruku.bo"}
    return repo.crear_comercio({**base, **extra})["id"]


def _fotos(repo, cid, n):
    for i in range(n):
        repo.add_foto_comercio({"comercio_id": cid, "url": f"/f/{cid}-{i}.jpg", "thumb_url": None, "orden": i})


def _completo(repo, nombre, rubro="ropa", fotos=3, **extra):
    """Un comercio que cumple los cinco requisitos de `es_completo`."""
    datos = {"portada_url": f"/p/{nombre}.jpg", "portada_thumb_url": f"/p/{nombre}-t.jpg",
             "horario": "Lun-Sáb 8:00-20:00", "prod_obs_human": "Ropa de mujer",
             "rubro_id": repo.get_rubro_id(rubro),
             "rubros": {"slug": rubro, "nombre": rubro.title()}}
    cid = _comercio(repo, nombre, **{**datos, **extra})
    _fotos(repo, cid, fotos)
    return cid


def _lista(client, token):
    r = client.get("/campo/mis-comercios", headers=_h(token))
    assert r.status_code == 200, r.text
    return {i["nombre"]: i for i in r.json()["items"]}


# ══════════════════════════════════════════════ estado_plan, sus 4 casos (+ bordes)

def test_estado_plan_al_dia(client, repo, agente):
    _comercio(repo, "Al dia", plan="publica", paga_hasta=_dia(10))
    assert _lista(client, agente)["Al dia"]["estado_plan"] == "al_dia"


def test_estado_plan_al_dia_el_mismo_dia_del_vencimiento(client, repo, agente):
    """`paga_hasta >= hoy de Bolivia`: el último día todavía está al día."""
    _comercio(repo, "Hoy vence", plan="publica", paga_hasta=_dia(0))
    assert _lista(client, agente)["Hoy vence"]["estado_plan"] == "al_dia"


def test_estado_plan_cortesia_no_vence(client, repo, agente):
    _comercio(repo, "Amigo", plan="destacado", plan_cortesia=True, paga_hasta=_dia(-90))
    assert _lista(client, agente)["Amigo"]["estado_plan"] == "cortesia"


def test_estado_plan_gratis(client, repo, agente):
    _comercio(repo, "Gratis", plan="gratis")
    _comercio(repo, "Gratis con fecha vieja", plan="gratis", paga_hasta=_dia(-5))   # volvió a gratis
    _comercio(repo, "Pago sin haber pagado", plan="publica")                        # «sin plan» del admin
    _comercio(repo, "Cortesia en gratis", plan="gratis", plan_cortesia=True)        # sin plan pago no hay sello
    lista = _lista(client, agente)
    assert {lista[n]["estado_plan"] for n in ("Gratis", "Gratis con fecha vieja", "Pago sin haber pagado",
                                             "Cortesia en gratis")} == {"gratis"}


def test_estado_plan_vencido(client, repo, agente):
    _comercio(repo, "Vencido", plan="publica", paga_hasta=_dia(-1))
    _comercio(repo, "Suspendido", plan="publica", paga_hasta=_dia(30), suspendido=True)
    _comercio(repo, "Cortesia suspendida", plan="destacado", plan_cortesia=True, suspendido=True)
    lista = _lista(client, agente)
    assert lista["Vencido"]["estado_plan"] == "vencido"
    assert lista["Suspendido"]["estado_plan"] == "vencido"       # suspendido nunca está al día
    assert lista["Cortesia suspendida"]["estado_plan"] == "vencido"


def test_estado_plan_usa_el_hoy_de_bolivia():
    c = {"plan_cortesia": False, "paga_hasta": "2026-10-13"}
    assert que_hay_aca.estado_plan(c, True, date(2026, 10, 13)) == "al_dia"
    assert que_hay_aca.estado_plan(c, True, date(2026, 10, 14)) == "vencido"
    assert que_hay_aca.estado_plan({"paga_hasta": "basura"}, True, date(2026, 10, 14)) == "gratis"


def test_la_lista_no_trae_precios_ni_paga_hasta_ni_el_plan(client, repo, agente):
    _comercio(repo, "Pago", plan="publica", paga_hasta=_dia(20), plan_cortesia=False, suspendido=False)
    item = _lista(client, agente)["Pago"]
    for k in ("plan", "plan_cortesia", "paga_hasta", "suspendido", "precio_mes", "codigo"):
        assert k not in item, k
    assert "precio" not in json.dumps(item)
    # y el comercio del fake no se tocó (la respuesta es una copia)
    assert repo.comercios[next(iter(repo.comercios))]["paga_hasta"] == _dia(20)


# ══════════════════════════════════════════════ fotos_count y rubro_slug

def test_fotos_count_y_rubro_slug(client, repo, agente):
    a = _comercio(repo, "Con fotos", rubros={"slug": "ropa", "nombre": "Ropa"})
    _comercio(repo, "Sin fotos")
    _fotos(repo, a, 4)
    otro = _comercio(repo, "Otra ciudad", ciudad_id=CIUDAD_AJENA)
    _fotos(repo, otro, 9)
    lista = _lista(client, agente)
    assert lista["Con fotos"]["fotos_count"] == 4 and lista["Con fotos"]["rubro_slug"] == "ropa"
    assert lista["Sin fotos"]["fotos_count"] == 0 and lista["Sin fotos"]["rubro_slug"] is None
    assert "Otra ciudad" not in lista


def test_la_lista_cuenta_las_fotos_en_una_sola_consulta(client, repo, agente, monkeypatch):
    for i in range(12):
        _fotos(repo, _comercio(repo, f"Local {i}"), 2)
    llamadas = []
    original = repo.contar_fotos_comercios
    monkeypatch.setattr(repo, "contar_fotos_comercios", lambda ids: llamadas.append(len(ids)) or original(ids))
    monkeypatch.setattr(repo, "list_fotos_comercio", lambda *_: pytest.fail("no se cuenta de a uno"))
    lista = _lista(client, agente)
    assert len(lista) == 12 and all(i["fotos_count"] == 2 for i in lista.values())
    assert llamadas == [12]


def test_los_propios_de_otra_ciudad_tambien_traen_el_sello(client, repo, agente):
    _comercio(repo, "Lo mio de afuera", ciudad_id=CIUDAD_AJENA, cargado_por="agente@uruku.bo",
              plan="publica", paga_hasta=_dia(5))
    item = _lista(client, agente)["Lo mio de afuera"]
    assert item["estado_plan"] == "al_dia" and item["fotos_count"] == 0


def test_ver_un_comercio_trae_lo_mismo_que_la_lista(client, repo, agente):
    cid = _comercio(repo, "Uno", plan="publica", paga_hasta=_dia(5), rubros={"slug": "ropa", "nombre": "Ropa"})
    _fotos(repo, cid, 2)
    r = client.get(f"/campo/mis-comercios/{cid}", headers=_h(agente))
    assert r.status_code == 200
    c = r.json()["comercio"]
    assert (c["estado_plan"], c["fotos_count"], c["rubro_slug"]) == ("al_dia", 2, "ropa")
    assert "paga_hasta" not in c and "plan" not in c


def test_mis_comercios_sigue_pidiendo_agente(client):
    assert client.get("/campo/mis-comercios").status_code in (401, 403)


# ══════════════════════════════════════════════ es_completo y GET /campo/ejemplos

@pytest.mark.parametrize("quita", ["portada_url", "whatsapp", "horario"])
def test_es_completo_exige_portada_whatsapp_y_horario(quita):
    c = {"portada_url": "x", "whatsapp": "5917", "horario": "8 a 20", "prod_obs_human": "algo"}
    assert que_hay_aca.es_completo(c, 3)
    assert not que_hay_aca.es_completo({**c, quita: "   "}, 3)
    assert not que_hay_aca.es_completo({k: v for k, v in c.items() if k != quita}, 3)


def test_es_completo_exige_tres_fotos_y_lo_que_vende():
    c = {"portada_url": "x", "whatsapp": "5917", "horario": "8 a 20", "prod_obs_human": "algo"}
    assert not que_hay_aca.es_completo(c, 2)
    assert que_hay_aca.es_completo(c, 7)
    sin_vende = {"portada_url": "x", "whatsapp": "5917", "horario": "8 a 20"}
    assert not que_hay_aca.es_completo(sin_vende, 3)
    assert que_hay_aca.es_completo({**sin_vende, "descripcion": "Venta de ropa"}, 3)      # la descripción alcanza
    assert not que_hay_aca.es_completo({**sin_vende, "prod_obs_human": " ", "descripcion": ""}, 3)


def _ejemplos(client, token, query=""):
    r = client.get(f"/campo/ejemplos{query}", headers=_h(token))
    assert r.status_code == 200, r.text
    return r.json()["items"]


def test_ejemplos_forma_de_cada_item(client, repo, agente):
    cid = _completo(repo, "Boutique Sol")
    [item] = _ejemplos(client, agente)
    assert item == {"id": cid, "slug": "boutique-sol", "nombre": "Boutique Sol",
                    "rubro_nombre": "Ropa", "portada_thumb_url": "/p/Boutique Sol-t.jpg"}


def test_ejemplos_son_hasta_tres_y_solo_completos(client, repo, agente):
    for n in ("A", "B", "C", "D", "E"):
        _completo(repo, f"Completo {n}")
    _completo(repo, "Con 2 fotos", fotos=2)
    _completo(repo, "Sin horario", horario=None)
    _completo(repo, "Sin portada", portada_url=None)
    _completo(repo, "Sin vende", prod_obs_human=None)
    _completo(repo, "Dado de baja", activo=False)
    _completo(repo, "Suspendido", suspendido=True)
    nombres = [i["nombre"] for i in _ejemplos(client, agente)]
    assert len(nombres) == 3 and all(n.startswith("Completo") for n in nombres)


def test_ejemplos_prefieren_el_rubro_y_completan_con_otros(client, repo, agente):
    _completo(repo, "Ropa 1", rubro="ropa")
    _completo(repo, "Calzado 1", rubro="calzado")
    _completo(repo, "Calzado 2", rubro="calzado")
    _completo(repo, "Ropa 2", rubro="ropa")
    solo_rubro = [i["nombre"] for i in _ejemplos(client, agente, "?rubro=calzado")]
    assert solo_rubro[:2] == ["Calzado 1", "Calzado 2"] and len(solo_rubro) == 3
    assert solo_rubro[2].startswith("Ropa")          # no alcanzaba el rubro: completa con otro
    ropa = [i["nombre"] for i in _ejemplos(client, agente, "?rubro=ropa")]
    assert ropa[:2] == ["Ropa 1", "Ropa 2"]


def test_ejemplos_excluyen_el_comercio_abierto(client, repo, agente):
    a = _completo(repo, "Abierto")
    _completo(repo, "Otro")
    nombres = [i["nombre"] for i in _ejemplos(client, agente, f"?excluir={a}")]
    assert nombres == ["Otro"]


def test_ejemplos_son_de_la_ciudad_del_agente(client, repo, agente):
    _completo(repo, "De Bermejo")
    _completo(repo, "De Santa Cruz", ciudad_id=CIUDAD_AJENA)
    assert [i["nombre"] for i in _ejemplos(client, agente)] == ["De Bermejo"]
    sc = auth.make_agente_token("sc@uruku.bo", ciudad_slug="santa-cruz")
    assert [i["nombre"] for i in _ejemplos(client, sc)] == ["De Santa Cruz"]


def test_ejemplos_rubro_inexistente_no_rompe_y_sin_ciudad_es_vacio(client, repo, agente):
    _completo(repo, "Uno")
    assert len(_ejemplos(client, agente, "?rubro=no-existe-este-rubro")) == 1
    sin_ciudad = auth.make_agente_token("x@uruku.bo")
    assert _ejemplos(client, sin_ciudad) == []


def test_ejemplos_cuentan_las_fotos_agrupado(client, repo, agente, monkeypatch):
    for i in range(6):
        _completo(repo, f"Local {i}")
    monkeypatch.setattr(repo, "list_fotos_comercio", lambda *_: pytest.fail("no se cuenta de a uno"))
    assert len(_ejemplos(client, agente)) == 3


def test_ejemplos_piden_agente(client):
    assert client.get("/campo/ejemplos").status_code in (401, 403)


# ══════════════════════════════════════════════ GET /campo/planes

def test_planes_son_los_pagos_y_activos_sin_precios(client, repo, agente):
    repo.planes["viejo"] = {"slug": "viejo", "nombre": "Viejo", "orden": 9, "precio_mes": 50, "activo": False}
    r = client.get("/campo/planes", headers=_h(agente))
    assert r.status_code == 200
    items = r.json()["items"]
    slugs = [i["slug"] for i in items]
    assert "gratis" not in slugs and "viejo" not in slugs
    assert slugs[:3] == ["publica", "destacado", "pro"]
    assert all(set(i) == {"slug", "nombre"} for i in items)
    assert {"slug": "destacado", "nombre": "Destacado"} in items
    cuerpo = r.text
    assert "precio" not in cuerpo and "140" not in cuerpo


def test_planes_piden_agente(client):
    assert client.get("/campo/planes").status_code in (401, 403)


# ══════════════════════════════════════════════ POST /campo/mis-comercios/{id}/interes

def _interes(client, token, cid, **body):
    return client.post(f"/campo/mis-comercios/{cid}/interes", headers=_h(token), json=body)


def test_interes_queda_en_comercio_eventos_con_detalle(client, repo, agente):
    cid = _comercio(repo, "Lo quiere")
    r = _interes(client, agente, cid, plan="destacado", nota="  Lo llama el lunes  ")
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "plan": "destacado", "nota": "Lo llama el lunes"}
    [ev] = repo.comercio_eventos
    assert (ev["comercio_id"], ev["tipo"], ev["actor"]) == (cid, "interes_plan", "agente@uruku.bo")
    assert ev["detalle"] == {"plan": "destacado", "nota": "Lo llama el lunes"}
    assert repo.comercios[cid]["plan"] == "gratis"          # anotar no cambia el plan


def test_interes_sin_nota(client, repo, agente):
    cid = _comercio(repo)
    assert _interes(client, agente, cid, plan="publica").status_code == 200
    assert _interes(client, agente, cid, plan="publica", nota="   ").json()["nota"] is None
    assert repo.comercio_eventos[0]["detalle"] == {"plan": "publica", "nota": None}


def test_interes_validaciones_dan_400_y_no_escriben(client, repo, agente):
    cid = _comercio(repo)
    assert _interes(client, agente, cid, plan="gratis").status_code == 400          # no es de pago
    assert _interes(client, agente, cid, plan="platino").status_code == 400         # no existe
    assert _interes(client, agente, cid, plan="  ").status_code == 400
    repo.planes["viejo"] = {"slug": "viejo", "nombre": "Viejo", "precio_mes": 50, "activo": False}
    assert _interes(client, agente, cid, plan="viejo").status_code == 400           # dado de baja
    assert _interes(client, agente, cid, plan="pro", nota="x" * 301).status_code == 400
    assert _interes(client, agente, cid, nota="hola").status_code == 422            # falta el plan
    assert repo.comercio_eventos == []
    assert _interes(client, agente, cid, plan="pro", nota="x" * 300).status_code == 200    # justo en el límite


def test_interes_regla_de_ciudad(client, repo, agente):
    ajeno = _comercio(repo, "Ajeno", ciudad_id=CIUDAD_AJENA)
    assert _interes(client, agente, ajeno, plan="pro").status_code == 404
    assert _interes(client, agente, "no-existe", plan="pro").status_code == 404
    assert repo.comercio_eventos == []
    # lo que cargó él en otra ciudad sí; y lo de su ciudad, lo haya cargado quien sea
    mio_afuera = _comercio(repo, "Mio de afuera", ciudad_id=CIUDAD_AJENA, cargado_por="agente@uruku.bo")
    de_otro = _comercio(repo, "De otro agente")
    assert _interes(client, agente, mio_afuera, plan="pro").status_code == 200
    assert _interes(client, agente, de_otro, plan="pro").status_code == 200


def test_interes_pide_agente_y_no_lo_hace_un_comercio(client, repo):
    cid = _comercio(repo)
    assert client.post(f"/campo/mis-comercios/{cid}/interes", json={"plan": "pro"}).status_code in (401, 403)
    comercio = auth.make_comercio_token(cid, "x@y.com")
    r = client.post(f"/campo/mis-comercios/{cid}/interes", headers=_h(comercio), json={"plan": "pro"})
    assert r.status_code in (401, 403)
    assert repo.comercio_eventos == []


def test_interes_si_la_auditoria_falla_avisa_y_no_dice_ok(client, repo, agente):
    cid = _comercio(repo)
    repo.falla_auditoria = True
    assert _interes(client, agente, cid, plan="pro").status_code == 502


# ══════════════════════════════════════════════ GET /admin/suscripciones suma `interes`

def _suscripciones(client, token):
    r = client.get("/admin/suscripciones", headers=_h(token))
    assert r.status_code == 200, r.text
    return {i["nombre"]: i for i in r.json()["items"]}


def test_admin_ve_el_interes(client, repo, agente, admin):
    a = _comercio(repo, "Interesado")
    _comercio(repo, "Sin interes")
    _interes(client, agente, a, plan="destacado", nota="Quiere vidriera")
    filas = _suscripciones(client, admin)
    i = filas["Interesado"]["interes"]
    assert set(i) == {"plan", "plan_nombre", "nota", "actor", "created_at"}
    assert (i["plan"], i["plan_nombre"], i["nota"], i["actor"]) == (
        "destacado", "Destacado", "Quiere vidriera", "agente@uruku.bo")
    assert i["created_at"]
    assert filas["Sin interes"]["interes"] is None


def test_admin_ve_solo_el_ultimo_interes(client, repo, agente, admin):
    a = _comercio(repo, "Cambio de idea")
    _interes(client, agente, a, plan="publica", nota="primero")
    otro = auth.make_agente_token("otro@uruku.bo", ciudad_slug="bermejo")
    _interes(client, otro, a, plan="pro", nota="después")
    i = _suscripciones(client, admin)["Cambio de idea"]["interes"]
    assert (i["plan"], i["nota"], i["actor"]) == ("pro", "después", "otro@uruku.bo")


def test_el_interes_desaparece_tras_un_pago_y_vuelve_con_uno_nuevo(client, repo, agente, admin):
    a = _comercio(repo, "Paga")
    b = _comercio(repo, "No paga")
    _interes(client, agente, a, plan="publica")
    _interes(client, agente, b, plan="publica")
    assert _suscripciones(client, admin)["Paga"]["interes"]["plan"] == "publica"

    r = client.post(f"/admin/comercio/{a}/pago", headers=_h(admin), json={"monto": 70, "meses": 1, "plan": "publica"})
    assert r.status_code == 200, r.text
    filas = _suscripciones(client, admin)
    assert filas["Paga"]["interes"] is None                     # el pago lo cerró
    assert filas["No paga"]["interes"] is not None              # el pago de otro no

    _interes(client, agente, a, plan="pro", nota="ahora quiere subir")
    assert _suscripciones(client, admin)["Paga"]["interes"]["plan"] == "pro"


def test_suscripciones_pide_el_interes_una_sola_vez(client, repo, admin, monkeypatch):
    for i in range(8):
        _comercio(repo, f"Local {i}")
    llamadas = []
    original = repo.intereses_de_plan_pendientes
    monkeypatch.setattr(repo, "intereses_de_plan_pendientes", lambda: llamadas.append(1) or original())
    assert len(_suscripciones(client, admin)) == 8 and len(llamadas) == 1


def test_el_interes_de_un_comercio_dado_de_baja_no_aparece(client, repo, agente, admin):
    a = _comercio(repo, "Se fue")
    _interes(client, agente, a, plan="pro")
    repo.comercios[a]["activo"] = False
    assert "Se fue" not in _suscripciones(client, admin)


# ══════════════════════════════════════════════ migración 0151

def _sql(carpeta):
    return (RAIZ / carpeta / "0151_eventos_detalle.sql").read_text(encoding="utf-8")


def test_0151_igual_en_las_dos_carpetas():
    assert _sql("supabase/migrations") == _sql("selfhost/postgres-init")


def test_0151_es_idempotente_y_privada():
    sql = _sql("supabase/migrations")
    low = sql.lower()
    assert "add column if not exists detalle jsonb" in low
    assert "create or replace function public.contar_fotos_comercios" in low
    # nunca se le da la columna ni la función al público
    assert "to anon" not in low and "to authenticated" not in low
    assert "revoke all on function public.contar_fotos_comercios(uuid[]) from public, anon, authenticated" in low
    assert "grant execute on function public.contar_fotos_comercios(uuid[]) to service_role" in low
    assert "drop " not in low and "delete from" not in low


# ══════════════════════════════════════════════ el repo REAL (un cliente PostgREST de mentira)

class _Q:
    def __init__(self, db, tabla):
        self.db, self.tabla, self.pedido = db, tabla, []

    def __getattr__(self, nombre):
        def _llamar(*a, **k):
            self.pedido.append((nombre, a))
            return self
        return _llamar

    @property
    def not_(self):
        return self

    def execute(self):
        self.db.consultas.append((self.tabla, self.pedido))
        return type("R", (), {"data": list(self.db.datos.get(self.tabla, []))})()


class _Rpc:
    def __init__(self, db, nombre, params):
        self.db, self.nombre, self.params = db, nombre, params

    def execute(self):
        self.db.consultas.append(("rpc:" + self.nombre, self.params))
        return type("R", (), {"data": self.db.rpcs[self.nombre](self.params)})()


class _Db:
    def __init__(self, datos=None, rpcs=None):
        self.datos, self.rpcs, self.consultas = datos or {}, rpcs or {}, []

    def table(self, tabla):
        return _Q(self, tabla)

    def rpc(self, nombre, params):
        return _Rpc(self, nombre, params)


def _repo_real(db):
    from app.db.repository import SupabaseRepo
    r = SupabaseRepo.__new__(SupabaseRepo)
    r._db = db
    return r


def test_repo_real_cuenta_fotos_con_el_rpc_en_tandas_grandes():
    db = _Db(rpcs={"contar_fotos_comercios": lambda p: {i: 3 for i in p["p_ids"][:2]}})
    repo = _repo_real(db)
    ids = [f"id-{i}" for i in range(4500)]
    cuenta = repo.contar_fotos_comercios(ids + ids[:10])         # repetidos y > 2000: 3 llamadas
    assert [c[0] for c in db.consultas] == ["rpc:contar_fotos_comercios"] * 3
    assert sum(len(c[1]["p_ids"]) for c in db.consultas) == 4500
    assert cuenta["id-0"] == 3 and cuenta["id-2000"] == 3 and "id-5" not in cuenta
    assert _repo_real(_Db()).contar_fotos_comercios([]) == {}


def test_repo_real_evento_con_detalle_lo_guarda_y_sin_detalle_no_manda_la_columna():
    db = _Db()
    repo = _repo_real(db)
    insertados = []

    class _Insert(_Q):
        def insert(self, fila):
            insertados.append(fila)
            return self

    db.table = lambda tabla: _Insert(db, tabla)
    repo.registrar_evento_comercio("c1", "interes_plan", "ag@uruku.bo", {"plan": "pro", "nota": None})
    repo.registrar_evento_comercio("c1", "clave_generada_por_admin", "admin@uruku.bo")
    assert insertados[0]["detalle"] == {"plan": "pro", "nota": None}
    assert "detalle" not in insertados[1]


def test_repo_real_intereses_toma_el_ultimo_y_lo_cierra_un_pago_posterior():
    def ev(cid, plan, t):
        return {"id": f"{cid}{t}", "comercio_id": cid, "actor": "ag",
                "detalle": {"plan": plan, "nota": None}, "created_at": t}

    db = _Db(datos={
        # vienen del más nuevo al más viejo (así los pide el repo)
        "comercio_eventos": [ev("A", "pro", "2026-10-13T12:00:00.5+00:00"),
                             ev("A", "publica", "2026-10-13T11:00:00+00:00"),
                             ev("B", "pro", "2026-10-13T10:00:00+00:00"),
                             ev("C", "pro", "2026-10-13T10:00:00+00:00")],
        "pagos": [{"id": "p1", "comercio_id": "B", "created_at": "2026-10-13T10:30:00.123456+00:00"},  # después: cierra B
                  {"id": "p2", "comercio_id": "C", "created_at": "2026-10-13T09:00:00+00:00"},         # antes: C sigue
                  {"id": "p3", "comercio_id": "A", "created_at": "2026-10-13T12:00:00.25+00:00"}],     # 0,25 s antes: A sigue
    })
    out = _repo_real(db).intereses_de_plan_pendientes()
    assert set(out) == {"A", "C"}
    assert out["A"]["plan"] == "pro" and out["A"]["created_at"] == "2026-10-13T12:00:00.5+00:00"
    assert [t for t, _ in db.consultas] == ["comercio_eventos", "pagos"]       # dos consultas, no una por comercio
    assert _repo_real(_Db()).intereses_de_plan_pendientes() == {}


def test_repo_real_ejemplos_filtra_en_la_base_lo_que_puede():
    db = _Db(datos={"comercios": []})
    _repo_real(db).list_ejemplos_candidatos("ciu-1", "rub-9", 50)
    pedido = db.consultas[0][1]
    for esperado in (("eq", ("ciudad_id", "ciu-1")), ("eq", ("activo", True)), ("eq", ("suspendido", False)),
                     ("eq", ("rubro_id", "rub-9")), ("limit", (50,))):
        assert esperado in pedido, esperado
    assert sum(1 for n, _ in pedido if n == "is_") == 3          # portada, WhatsApp y horario no nulos


def test_la_lista_de_campo_pide_las_columnas_del_plan_pero_no_las_devuelve():
    from app.db.repository import _COLS_COMERCIO_CAMPO
    pedidas = [c.strip() for c in _COLS_COMERCIO_CAMPO.split(",")]
    for col in ("plan", "plan_cortesia", "paga_hasta", "suspendido"):
        assert col in pedidas


# ══════════════════════════════════════════════ la 0151 en un Postgres real (opcional)

def test_0151_en_postgres_real(pg0149):
    """Con `URUKU_PG_TEST_CONTAINER`: aplica la 0151 sobre una base descartable y comprueba
    la columna privada y que el RPC cuenta agrupado. Dos veces seguidas (idempotente)."""
    psql = pg0149
    a, b, c = ("00000000-0000-0000-0000-00000000000" + x for x in "abc")
    psql("""
        create table comercio_fotos (id uuid primary key default gen_random_uuid(),
          comercio_id uuid not null references comercios(id), url text not null);
        grant select on comercio_fotos to anon, authenticated; grant all on comercio_fotos to service_role;
        create table comercio_eventos (id uuid primary key default gen_random_uuid(),
          comercio_id uuid not null references comercios(id), tipo text not null, actor text not null,
          created_at timestamptz not null default now());
        alter table comercio_eventos enable row level security;
        revoke all on comercio_eventos from public, anon, authenticated;
        grant all on comercio_eventos to service_role;
    """)
    sql = _sql("supabase/migrations")
    psql(sql)
    psql(sql)                                                    # idempotente
    psql(f"""
        insert into comercios (id, slug, nombre) values ('{a}', 'a', 'A'), ('{b}', 'b', 'B'), ('{c}', 'c', 'C');
        insert into comercio_fotos (comercio_id, url) values ('{a}', 'u1'), ('{a}', 'u2'), ('{b}', 'u3');
        insert into comercio_eventos (comercio_id, tipo, actor, detalle)
          values ('{a}', 'interes_plan', 'ag', '{{"plan":"pro","nota":null}}');
    """, rol="service_role")
    out = psql(f"select public.contar_fotos_comercios(array['{a}', '{b}', '{c}']::uuid[]);",
               rol="service_role").stdout.strip()
    assert json.loads(out) == {a: 2, b: 1}
    assert json.loads(psql("select public.contar_fotos_comercios(array[]::uuid[]);",
                           rol="service_role").stdout.strip()) == {}
    assert psql("select detalle->>'plan' from comercio_eventos;", rol="service_role").stdout.strip() == "pro"
    for rol in ("anon", "authenticated"):
        assert psql("select detalle from comercio_eventos;", rol=rol, check=False).returncode != 0
        assert psql("select public.contar_fotos_comercios(array[]::uuid[]);", rol=rol, check=False).returncode != 0
