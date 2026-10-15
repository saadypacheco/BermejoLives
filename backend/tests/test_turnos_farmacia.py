"""Farmacias de turno (docs/farmacias-de-turno.md, migración 0154).

Qué se prueba:
- La importación con el JSON REAL del rol: 12 fichas nuevas, 7 existentes completadas sin pisar,
  140 turnos; es idempotente (segunda corrida: 0 creadas, 140 turnos y nada duplicado).
- Las horas: el turno del 15/10 va de 15/10 08:00 a 16/10 08:00 de La Paz (12:00Z a 12:00Z).
- Nada se escribe si el rol no cierra (ficha con `slug` que no está, turno que nombra a una
  farmacia que no existe, ciudad inexistente).
- El endpoint `POST /admin/farmacias/turnos/importar` (permiso `lugares`) y el comando
  `python -m app.scripts.importar_turnos_farmacia`.
- `ubicacion_aproximada` llega al agente y se apaga al re-tomar el GPS; `nota_interna` no sale.
- La migración 0154: igual en las dos carpetas, idempotente, privadas cerradas; y, contra un
  Postgres real de Docker (opcional, `URUKU_PG_TEST_CONTAINER`), dos veces y con anon leyendo
  `turnos_farmacia` pero no `ubicacion_aproximada` ni `nota_interna`.
"""
import copy
import json
import os
import re
import shutil
import subprocess
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.core import auth
from app.services import turnos_farmacia
from app.scripts import importar_turnos_farmacia as comando

RAIZ = Path(__file__).resolve().parents[2]
JSON_ROL = RAIZ / "backend/data/turnos_farmacia/bermejo-2026-10-04_2026-12-12.json"
# Las 7 que ya estaban en URUKU (traen `slug` en el rol).
SLUGS_EXISTENTES = ["farmacia-amanecer", "farmacia-los-angeles", "farmacia-copacabana",
                    "farmacia-corazon-de-jesus", "farmacia-popular", "farmacia-san-ramon",
                    "farmacia-senor-de-mayo"]


@pytest.fixture
def rol() -> dict:
    return json.loads(JSON_ROL.read_text(encoding="utf-8"))


@pytest.fixture
def repo_farmacias(repo):
    """El fake con el rubro `farmacia` y las 7 fichas que ya estaban, con algo cargado y algo no."""
    repo.rubros["farmacia"] = "rub-farmacia"
    # Amanecer ya tiene teléfono (distinto al del rol) y dirección: no se toca nada.
    repo.seed_comercio(slug="farmacia-amanecer", nombre="Farmacia Amanecer", ciudad_id="ciu-1",
                       rubro_id="rub-farmacia", telefono="70000001", direccion="Mi dirección cargada",
                       whatsapp="59170000001", activo=True)
    # Los Ángeles: sin teléfono ni dirección -> se completan los dos.
    repo.seed_comercio(slug="farmacia-los-angeles", nombre="Farmacia Los Ángeles", ciudad_id="ciu-1",
                       rubro_id="rub-farmacia", telefono=None, direccion=None, activo=True)
    # Copacabana: sin teléfono (en el rol sólo trae fijo) y dirección vacía como "".
    repo.seed_comercio(slug="farmacia-copacabana", nombre="Farmacia Copacabana", ciudad_id="ciu-1",
                       rubro_id="rub-farmacia", telefono="", direccion="  ", activo=True)
    for slug in ("farmacia-corazon-de-jesus", "farmacia-popular", "farmacia-san-ramon", "farmacia-senor-de-mayo"):
        repo.seed_comercio(slug=slug, nombre=slug.replace("-", " ").title(), ciudad_id="ciu-1",
                           rubro_id="rub-farmacia", telefono="69999999", direccion="Cargada", activo=True)
    return repo


def _farmacia(rol, nombre):
    return next(f for f in rol["farmacias"] if f["nombre"] == nombre)


def _por_slug(repo, slug):
    return next(c for c in repo.comercios.values() if c.get("slug") == slug)


# ───────────────────────────────────────────────────── el JSON del rol

def test_el_rol_trae_19_farmacias_70_dias_y_140_turnos(rol):
    assert len(rol["farmacias"]) == 19
    assert len(rol["turnos"]) == 70
    assert sum(len(d["farmacias"]) for d in rol["turnos"]) == 140
    assert sum(1 for f in rol["farmacias"] if f.get("slug")) == 7
    nombres = {f["nombre"] for f in rol["farmacias"]}
    assert all(n in nombres for d in rol["turnos"] for n in d["farmacias"])


# ───────────────────────────────────────────────────── las horas

def test_el_turno_del_15_10_va_de_las_08_a_las_08_de_bolivia():
    inicio, fin = turnos_farmacia.ventana(date(2026, 10, 15))
    assert datetime.fromisoformat(inicio) == datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)
    assert datetime.fromisoformat(fin) == datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)


def test_el_turno_de_fin_de_mes_cruza_el_mes():
    inicio, fin = turnos_farmacia.ventana(date(2026, 10, 31))
    assert datetime.fromisoformat(fin) == datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


def test_de_turno_ahora_es_inicio_menor_o_igual_a_ahora_y_ahora_menor_a_fin(repo_farmacias, rol):
    """Criterio 2 de la spec: el 15/10 a las 10:00 (Bolivia) están Ángeles y San Miguel; el 16/10 a
    las 07:59 siguen; a las 08:00 pasan a Señor de Mayo y Santa Isabel. Bolivia = UTC-4."""
    turnos_farmacia.importar(repo_farmacias, rol)

    def de_turno(momento_utc):
        return {repo_farmacias.comercios[t["comercio_id"]]["slug"]
                for t in repo_farmacias.turnos_farmacia.values()
                if datetime.fromisoformat(t["inicio"]) <= momento_utc < datetime.fromisoformat(t["fin"])}

    angeles_y_san_miguel = {"farmacia-los-angeles", "farmacia-san-miguel"}
    assert de_turno(datetime(2026, 10, 15, 14, 0, tzinfo=timezone.utc)) == angeles_y_san_miguel     # 15/10 10:00
    assert de_turno(datetime(2026, 10, 16, 11, 59, tzinfo=timezone.utc)) == angeles_y_san_miguel    # 16/10 07:59
    assert de_turno(datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)) == {                        # 16/10 08:00
        "farmacia-senor-de-mayo", "farmacia-santa-isabel"}
    assert de_turno(datetime(2026, 10, 15, 11, 59, tzinfo=timezone.utc)) != angeles_y_san_miguel    # 15/10 07:59: todavía el anterior


# ───────────────────────────────────────────────────── la importación

def test_importar_el_rol_real_crea_12_completa_7_y_carga_140_turnos(repo_farmacias, rol):
    r = turnos_farmacia.importar(repo_farmacias, rol)
    assert r["creadas"] == 12
    assert r["actualizadas"] == 7
    assert r["turnos"] == 140
    assert len(repo_farmacias.turnos_farmacia) == 140
    # 7 existentes + 12 nuevas = 19 fichas de farmacia, ninguna repetida.
    assert len(repo_farmacias.comercios) == 19
    assert len({c["slug"] for c in repo_farmacias.comercios.values()}) == 19


def test_las_12_fichas_nuevas_salen_completas(repo_farmacias, rol):
    turnos_farmacia.importar(repo_farmacias, rol)
    nuevas = [c for c in repo_farmacias.comercios.values() if c.get("fuente") == "turnos"]
    assert len(nuevas) == 12
    for c in nuevas:
        assert c["rubro_id"] == "rub-farmacia" and c["ciudad_id"] == "ciu-1"
        assert c["codigo"], "toda ficha nace con código (crear_comercio)"
        assert c["slug"].startswith("farmacia-")
        assert c["rubros"] == ["farmacia"], "el rubro está también en comercio_rubros"
        assert c["lat"] is not None and c["lng"] is not None
        assert c["ubicacion_aproximada"] is True
        assert c["activo"] if "activo" in c else True
        assert c["verificado"] is False and c["confiable"] is False
        assert c.get("whatsapp") is None, "no se supone WhatsApp"
        assert c["telefono"], "celular o fijo tal como está en la fuente"
    bermejo = next(c for c in nuevas if c["nombre"] == "Farmacia Bermejo")
    assert bermejo["slug"] == "farmacia-bermejo"
    assert bermejo["telefono"] == "72905917"
    assert bermejo["direccion"] == "Avenida Barrientos, entre Germán Busch y Virgen de Chaguaya"
    assert "78256292" in bermejo["nota_interna"]
    dorado = next(c for c in nuevas if c["nombre"] == "Farmacia Dorado")
    assert dorado["telefono"] == "6963028"          # sólo tiene fijo
    assert (dorado["lat"], dorado["lng"]) == (-22.736511, -64.335361)


def test_las_existentes_se_completan_sin_pisar(repo_farmacias, rol):
    turnos_farmacia.importar(repo_farmacias, rol)
    amanecer = _por_slug(repo_farmacias, "farmacia-amanecer")
    assert amanecer["telefono"] == "70000001"                        # ya tenía: no se pisa
    assert amanecer["direccion"] == "Mi dirección cargada"
    assert amanecer["whatsapp"] == "59170000001"
    angeles = _por_slug(repo_farmacias, "farmacia-los-angeles")
    assert angeles["telefono"] == "74503461"                         # el celular
    assert angeles["direccion"] == "Avenida Barrientos, al lado del Mercado Campesino"
    copa = _por_slug(repo_farmacias, "farmacia-copacabana")
    assert copa["telefono"] == "6961117"                             # sin celular: el fijo
    assert copa["direccion"] == "Avenida Barrientos, entre Cochabamba y Ameller"
    assert _por_slug(repo_farmacias, "farmacia-popular")["telefono"] == "69999999"
    # Las existentes no ganan coordenadas ni marcas: su ubicación no se toca.
    assert "ubicacion_aproximada" not in amanecer and "lat" not in amanecer


def test_los_turnos_guardan_inicio_y_fin(repo_farmacias, rol):
    turnos_farmacia.importar(repo_farmacias, rol)
    angeles = _por_slug(repo_farmacias, "farmacia-los-angeles")
    t = next(t for t in repo_farmacias.turnos_farmacia.values()
             if t["comercio_id"] == angeles["id"] and t["fecha"] == "2026-10-15")
    assert datetime.fromisoformat(t["inicio"]) == datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)
    assert datetime.fromisoformat(t["fin"]) == datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)
    assert t["fuente"] == "turnos" and t["activo"] is True
    assert all(datetime.fromisoformat(x["fin"]) - datetime.fromisoformat(x["inicio"]) == timedelta(hours=24)
               for x in repo_farmacias.turnos_farmacia.values())


def test_importar_dos_veces_no_duplica_nada(repo_farmacias, rol):
    turnos_farmacia.importar(repo_farmacias, rol)
    fichas = {cid: dict(c) for cid, c in repo_farmacias.comercios.items()}
    ids_turnos = set(repo_farmacias.turnos_farmacia)
    r = turnos_farmacia.importar(repo_farmacias, rol)
    assert r["creadas"] == 0
    assert r["actualizadas"] == 19                  # ahora las 19 ya existen
    assert r["datos_completados"] == 0              # y no quedó nada vacío por completar
    assert r["turnos"] == 140
    assert len(repo_farmacias.turnos_farmacia) == 140
    assert set(repo_farmacias.turnos_farmacia) == ids_turnos
    assert len(repo_farmacias.comercios) == 19
    assert {cid: dict(c) for cid, c in repo_farmacias.comercios.items()} == fichas


def test_reimportar_no_resucita_un_turno_dado_de_baja(repo_farmacias, rol):
    turnos_farmacia.importar(repo_farmacias, rol)
    t = next(iter(repo_farmacias.turnos_farmacia.values()))
    t["activo"] = False
    turnos_farmacia.importar(repo_farmacias, rol)
    assert t["activo"] is False
    assert len(repo_farmacias.turnos_farmacia) == 140


def test_reimportar_reencuentra_la_ficha_creada_aunque_cambie_el_slug(repo_farmacias, rol):
    turnos_farmacia.importar(repo_farmacias, rol)
    nueva = next(c for c in repo_farmacias.comercios.values() if c["nombre"] == "Farmacia Madrid")
    nueva["slug"] = "madrid-renombrada"
    turnos_farmacia.importar(repo_farmacias, rol)
    assert len([c for c in repo_farmacias.comercios.values() if c["nombre"] == "Farmacia Madrid"]) == 1


def test_una_ficha_creada_que_ahora_tiene_telefono_vacio_lo_recupera_pero_no_pisa(repo_farmacias, rol):
    turnos_farmacia.importar(repo_farmacias, rol)
    madrid = next(c for c in repo_farmacias.comercios.values() if c["nombre"] == "Farmacia Madrid")
    madrid["telefono"] = None
    madrid["direccion"] = "Otra, corregida por el agente"
    r = turnos_farmacia.importar(repo_farmacias, rol)
    assert madrid["telefono"] == "67386618" and r["datos_completados"] == 1
    assert madrid["direccion"] == "Otra, corregida por el agente"


def test_si_falta_una_ficha_con_slug_no_se_escribe_nada(repo_farmacias, rol):
    del repo_farmacias.comercios[_por_slug(repo_farmacias, "farmacia-popular")["id"]]
    antes = len(repo_farmacias.comercios)
    with pytest.raises(ValueError, match="farmacia-popular"):
        turnos_farmacia.importar(repo_farmacias, rol)
    assert len(repo_farmacias.comercios) == antes and not repo_farmacias.turnos_farmacia


def test_un_turno_que_nombra_a_una_farmacia_inexistente_no_escribe_nada(repo_farmacias, rol):
    rol["turnos"][0]["farmacias"][0] = "Fantasma"
    with pytest.raises(ValueError, match="Fantasma"):
        turnos_farmacia.importar(repo_farmacias, rol)
    assert len(repo_farmacias.comercios) == 7 and not repo_farmacias.turnos_farmacia


def test_una_farmacia_nueva_sin_coordenadas_no_se_crea_y_no_escribe_nada(repo_farmacias, rol):
    _farmacia(rol, "Madrid").pop("lat")
    with pytest.raises(ValueError, match="Madrid"):
        turnos_farmacia.importar(repo_farmacias, rol)
    assert len(repo_farmacias.comercios) == 7 and not repo_farmacias.turnos_farmacia


def test_ciudad_o_rubro_inexistente(repo_farmacias, rol):
    with pytest.raises(ValueError, match="no existe"):
        turnos_farmacia.importar(repo_farmacias, {**rol, "ciudad": "no-existe"})
    del repo_farmacias.rubros["farmacia"]
    with pytest.raises(ValueError, match="rubro"):
        turnos_farmacia.importar(repo_farmacias, rol)
    assert not repo_farmacias.turnos_farmacia


def test_una_zona_horaria_que_no_es_la_paz_se_rechaza(repo_farmacias, rol):
    rol["turno"]["zona"] = "America/Buenos_Aires"
    with pytest.raises(ValueError):
        turnos_farmacia.importar(repo_farmacias, rol)


# ───────────────────────────────────────────────────── el endpoint

def _h(token):
    return {"Authorization": f"Bearer {token}"}


def test_el_endpoint_importa_con_el_json_en_el_cuerpo(client, repo_farmacias, rol, admin_token):
    r = client.post("/admin/farmacias/turnos/importar", json=rol, headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "creadas": 12, "actualizadas": 7, "datos_completados": 2, "turnos": 140}
    r2 = client.post("/admin/farmacias/turnos/importar", json=rol, headers=_h(admin_token))
    assert r2.json()["creadas"] == 0 and r2.json()["turnos"] == 140
    assert len(repo_farmacias.turnos_farmacia) == 140


def test_el_endpoint_pide_el_permiso_lugares(client, repo_farmacias, rol):
    url = "/admin/farmacias/turnos/importar"
    assert client.post(url, json=rol).status_code in (401, 403)                     # sin token
    for token in (auth.make_agente_token("agente@x.com", "bermejo"),                 # agente
                  auth.make_publicador_token("pub@x.com"),                           # publicador: no tiene `lugares`
                  auth.make_comercio_token("com-1", "dueno@x.com"),                  # un comercio
                  auth.make_usuario_token("u-1", "59170000000")):                    # un comprador
        r = client.post(url, json=rol, headers=_h(token))
        assert r.status_code in (401, 403), (r.status_code, r.text)
    assert not repo_farmacias.turnos_farmacia and len(repo_farmacias.comercios) == 7
    # El moderador tiene `lugares`; el admin tiene todo.
    assert client.post(url, json=rol, headers=_h(auth.make_token("mod@x.com", rol="moderador"))).status_code == 200


def test_el_endpoint_rechaza_un_rol_que_no_cierra(client, repo_farmacias, rol, admin_token):
    url = "/admin/farmacias/turnos/importar"
    rol["turnos"][3]["farmacias"][1] = "Fantasma"
    r = client.post(url, json=rol, headers=_h(admin_token))
    assert r.status_code == 400 and "Fantasma" in r.json()["detail"]
    assert not repo_farmacias.turnos_farmacia
    # Forma inválida (fecha que no es fecha, lat fuera de rango): 422 de Pydantic.
    malo = copy.deepcopy(rol)
    malo["turnos"][0]["fecha"] = "ayer"
    assert client.post(url, json=malo, headers=_h(admin_token)).status_code == 422
    malo = copy.deepcopy(rol)
    _farmacia(malo, "Madrid")["lat"] = 999
    assert client.post(url, json=malo, headers=_h(admin_token)).status_code == 422
    assert client.post(url, json={}, headers=_h(admin_token)).status_code == 422


# ───────────────────────────────────────────────────── el comando

def test_el_comando_importa_e_imprime_el_resumen(repo_farmacias, capsys):
    assert comando.main([str(JSON_ROL)], repo=repo_farmacias) == 0
    salida = capsys.readouterr().out
    assert re.search(r"creadas:\s+12", salida)
    assert re.search(r"actualizadas:\s+7", salida)
    assert re.search(r"Turnos guardados:\s+140", salida)
    assert len(repo_farmacias.turnos_farmacia) == 140
    # Segunda corrida: nada nuevo.
    assert comando.main([str(JSON_ROL)], repo=repo_farmacias) == 0
    assert re.search(r"creadas:\s+0", capsys.readouterr().out)
    assert len(repo_farmacias.turnos_farmacia) == 140 and len(repo_farmacias.comercios) == 19


def test_el_comando_lee_de_la_entrada_estandar(repo_farmacias, capsys, monkeypatch):
    import io
    monkeypatch.setattr("sys.stdin", io.StringIO(JSON_ROL.read_text(encoding="utf-8")))
    assert comando.main(["-"], repo=repo_farmacias) == 0
    assert len(repo_farmacias.turnos_farmacia) == 140


def test_el_comando_falla_con_codigo_1_si_no_hay_archivo_o_el_rol_no_cierra(repo_farmacias, capsys, tmp_path):
    assert comando.main([str(tmp_path / "no-existe.json")], repo=repo_farmacias) == 1
    malo = tmp_path / "malo.json"
    malo.write_text("{no es json", encoding="utf-8")
    assert comando.main([str(malo)], repo=repo_farmacias) == 1
    sin_ciudad = tmp_path / "ciudad.json"
    sin_ciudad.write_text(json.dumps({"ciudad": "no-existe", "farmacias": [], "turnos": []}), encoding="utf-8")
    assert comando.main([str(sin_ciudad)], repo=repo_farmacias) == 1
    forma = tmp_path / "forma.json"
    forma.write_text(json.dumps({"farmacias": "x"}), encoding="utf-8")
    assert comando.main([str(forma)], repo=repo_farmacias) == 1
    assert "no se importó" in capsys.readouterr().err
    assert not repo_farmacias.turnos_farmacia


def test_el_comando_corre_como_modulo(tmp_path):
    """`python -m app.scripts.importar_turnos_farmacia` existe y responde a --help."""
    p = subprocess.run(["python", "-m", "app.scripts.importar_turnos_farmacia", "--help"],
                       capture_output=True, text=True, encoding="utf-8", cwd=RAIZ / "backend",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    assert p.returncode == 0 and "archivo" in p.stdout


# ───────────────────────────────────────────────────── la app del agente

AGENTE = {"email": "agente@bermejolive.com", "ciudad": "bermejo"}


def _token_agente():
    return auth.make_agente_token(AGENTE["email"], AGENTE["ciudad"])


def test_mis_comercios_trae_ubicacion_aproximada_y_no_la_nota_interna(client, repo_farmacias, rol):
    turnos_farmacia.importar(repo_farmacias, rol)
    r = client.get("/campo/mis-comercios", headers=_h(_token_agente()))
    assert r.status_code == 200, r.text
    items = {i["slug"]: i for i in r.json()["items"]}
    assert items["farmacia-bermejo"]["ubicacion_aproximada"] is True
    assert "nota_interna" not in items["farmacia-bermejo"]


def test_las_columnas_de_la_app_del_agente_piden_ubicacion_aproximada_y_no_la_nota():
    from app.db.repository import _COLS_COMERCIO_CAMPO
    cols = [c.strip() for c in _COLS_COMERCIO_CAMPO.split(",")]
    assert "ubicacion_aproximada" in cols and "nota_interna" not in cols


def test_re_tomar_el_gps_apaga_la_ubicacion_aproximada(client, repo_farmacias, rol):
    turnos_farmacia.importar(repo_farmacias, rol)
    bermejo = _por_slug(repo_farmacias, "farmacia-bermejo")
    assert bermejo["ubicacion_aproximada"] is True
    r = client.patch(f"/campo/mis-comercios/{bermejo['id']}", headers=_h(_token_agente()),
                     json={"lat": -22.7321, "lng": -64.3420})
    assert r.status_code == 200, r.text
    assert bermejo["ubicacion_aproximada"] is False
    assert (bermejo["lat"], bermejo["lng"]) == (-22.7321, -64.3420)
    assert "nota_interna" not in r.json()["comercio"]          # la nota no vuelve en la respuesta
    # Una ficha cuyo punto ya era del GPS sigue igual.
    otra = _por_slug(repo_farmacias, "farmacia-bolivar")
    assert otra["ubicacion_aproximada"] is True


def test_editar_otra_cosa_no_apaga_la_ubicacion_aproximada(client, repo_farmacias, rol):
    turnos_farmacia.importar(repo_farmacias, rol)
    bermejo = _por_slug(repo_farmacias, "farmacia-bermejo")
    r = client.patch(f"/campo/mis-comercios/{bermejo['id']}", headers=_h(_token_agente()),
                     json={"horario": "24 horas"})
    assert r.status_code == 200, r.text
    assert bermejo["ubicacion_aproximada"] is True


def test_el_gps_va_completo_o_no_va(client, repo_farmacias, rol):
    turnos_farmacia.importar(repo_farmacias, rol)
    bermejo = _por_slug(repo_farmacias, "farmacia-bermejo")
    lat0, lng0 = bermejo["lat"], bermejo["lng"]
    h = _h(_token_agente())
    for cuerpo in ({"lat": -22.7}, {"lng": -64.3}, {"lat": None, "lng": None}, {"lat": -22.7, "lng": None}):
        r = client.patch(f"/campo/mis-comercios/{bermejo['id']}", headers=h, json=cuerpo)
        assert r.status_code == 400, (cuerpo, r.text)
    for cuerpo in ({"lat": 123, "lng": -64.3}, {"lat": -22.7, "lng": 500}):
        assert client.patch(f"/campo/mis-comercios/{bermejo['id']}", headers=h, json=cuerpo).status_code == 422
    assert (bermejo["lat"], bermejo["lng"]) == (lat0, lng0) and bermejo["ubicacion_aproximada"] is True


# ───────────────────────────────────────────────────── la migración 0154

def _sin_comentarios(sql: str) -> str:
    return "\n".join(l for l in sql.splitlines() if not l.lstrip().startswith("--"))


def _0154(carpeta="supabase/migrations") -> str:
    return (RAIZ / carpeta / "0154_turnos_farmacia.sql").read_text(encoding="utf-8")


def test_la_0154_esta_igual_en_supabase_y_en_selfhost():
    a = (RAIZ / "supabase/migrations/0154_turnos_farmacia.sql").read_bytes()
    b = (RAIZ / "selfhost/postgres-init/0154_turnos_farmacia.sql").read_bytes()
    assert a == b and a


def test_la_0154_es_idempotente_transaccional_con_rls_y_grants_por_columna():
    sql = _sin_comentarios(_0154())
    assert sql.index("begin;") < sql.index("create table") < sql.index("commit;")
    assert sql.rstrip().endswith("notify pgrst, 'reload schema';")
    assert "create table if not exists public.turnos_farmacia" in sql
    assert not re.search(r"create table(?! if not exists)", sql)
    assert "add column if not exists ubicacion_aproximada boolean not null default false" in sql
    assert "add column if not exists nota_interna text" in sql
    assert "enable row level security" in sql and "using (activo)" in sql
    assert "grant select (id, comercio_id, fecha, inicio, fin) on public.turnos_farmacia to anon, authenticated;" in sql
    # Nunca un grant de tabla entera a anon, ni de las columnas privadas de comercios.
    assert not re.search(r"grant\s+select\s+on\s+(public\.)?turnos_farmacia\s+to\s+[^;]*anon", sql, re.I)
    assert not re.search(r"grant\s+select\s*\([^)]*(ubicacion_aproximada|nota_interna)[^)]*\)\s+on\s+public\.comercios", sql, re.I)
    assert "unique index if not exists turnos_farmacia_comercio_fecha_uq" in sql
    assert "references public.comercios(id)" in sql
    assert not re.search(r"\bdelete\s+from\b|\bdrop\s+table\b", sql, re.I)        # baja lógica, nunca física


# ───────────────────────────────────────────────────── contra un Postgres real (Docker)
# Opcional: URUKU_PG_TEST_CONTAINER=<contenedor postgres>. Arma una base con `comercios` como la
# deja la 0145 (grant por columnas) y corre la 0154 tal cual está en el archivo, dos veces.

@pytest.fixture(scope="module")
def pg():
    contenedor = os.environ.get("URUKU_PG_TEST_CONTAINER")
    if not contenedor or not shutil.which("docker"):
        pytest.skip("sin Postgres de Docker (URUKU_PG_TEST_CONTAINER)")
    base = "t0154_" + uuid.uuid4().hex[:8]

    def psql(sql, db=base, check=True, rol=None):
        if rol:
            sql = f"set role {rol};\n{sql}"
        p = subprocess.run(
            ["docker", "exec", "-i", contenedor, "psql", "-U", "postgres", "-d", db,
             "-v", "ON_ERROR_STOP=1", "-At", "-q", "-F", "|", "-f", "-"],
            input=sql, capture_output=True, text=True, encoding="utf-8")
        if check and p.returncode != 0:
            raise AssertionError(p.stderr)
        return p

    psql(f'create database "{base}"', db="postgres")
    try:
        # service_role como en selfhost/postgres-init/00-roles.sql: bypassa RLS.
        psql("""
            do $$ begin
              begin create role anon nologin; exception when duplicate_object then null; end;
              begin create role authenticated nologin; exception when duplicate_object then null; end;
              begin create role service_role nologin noinherit bypassrls; exception when duplicate_object then null; end;
            end $$;
            grant usage on schema public to anon, authenticated, service_role;
            create table comercios (id uuid primary key default gen_random_uuid(),
                                    slug text, nombre text, activo boolean not null default true);
            insert into comercios (slug, nombre) values ('farmacia-x', 'Farmacia X');
            -- Como la deja la 0145: tabla cerrada, columnas dadas una por una.
            revoke select on comercios from anon, authenticated;
            grant select (id, slug, nombre, activo) on comercios to anon, authenticated;
            grant all on comercios to service_role;
        """)
        yield psql
    finally:
        psql(f'drop database if exists "{base}" with (force)', db="postgres", check=False)


def test_0154_en_postgres_dos_veces_y_anon_lee_turnos_pero_no_lo_privado(pg):
    pg(_0154())
    pg(_0154())            # idempotente
    pg("""insert into turnos_farmacia (comercio_id, fecha, inicio, fin, fuente)
          select id, '2026-10-15', '2026-10-15T12:00:00Z', '2026-10-16T12:00:00Z', 'turnos' from comercios;
          insert into turnos_farmacia (comercio_id, fecha, inicio, fin, activo)
          select id, '2026-10-16', '2026-10-16T12:00:00Z', '2026-10-17T12:00:00Z', false from comercios;
          update comercios set ubicacion_aproximada = true, nota_interna = 'dudas';""", rol="service_role")
    for rol in ("anon", "authenticated"):
        # Lee las columnas públicas, y sólo el turno ACTIVO (la policy filtra; no hace falta pedir `activo`).
        r = pg("select id, comercio_id, fecha, inicio, fin from turnos_farmacia;", rol=rol)
        assert r.stdout.count("\n") == 1 and "2026-10-15" in r.stdout and "2026-10-16|" not in r.stdout
        # Lo privado de turnos_farmacia.
        for privada in ("fuente", "activo", "created_at"):
            r = pg(f"select {privada} from turnos_farmacia;", rol=rol, check=False)
            assert r.returncode != 0 and "permission denied" in r.stderr, (rol, privada)
        r = pg("select * from turnos_farmacia;", rol=rol, check=False)
        assert r.returncode != 0 and "permission denied" in r.stderr
        # Lo privado de comercios.
        for privada in ("ubicacion_aproximada", "nota_interna"):
            r = pg(f"select {privada} from comercios;", rol=rol, check=False)
            assert r.returncode != 0 and "permission denied" in r.stderr, (rol, privada)
            r = pg(f"select id from comercios where {privada} is not null;", rol=rol, check=False)
            assert r.returncode != 0 and "permission denied" in r.stderr, (rol, privada)
        # Las públicas de comercios siguen andando.
        pg("select id, slug, nombre, activo from comercios;", rol=rol)
        # Nadie público escribe.
        for sql in ("insert into turnos_farmacia (comercio_id, fecha, inicio, fin) select id, '2026-11-01', now(), now() + interval '1 day' from comercios;",
                    "update turnos_farmacia set fin = fin;", "delete from turnos_farmacia;"):
            r = pg(sql, rol=rol, check=False)
            assert r.returncode != 0 and "permission denied" in r.stderr, (rol, sql)
    # El backend ve todo, y el único (comercio_id, fecha) frena el duplicado.
    assert pg("select count(*) from turnos_farmacia;", rol="service_role").stdout.strip() == "2"
    r = pg("insert into turnos_farmacia (comercio_id, fecha, inicio, fin) select id, '2026-10-15', now(), now() + interval '1 day' from comercios;",
           rol="service_role", check=False)
    assert r.returncode != 0 and "duplicate key" in r.stderr
    assert pg("select ubicacion_aproximada, nota_interna from comercios;", rol="service_role").stdout.strip() == "t|dudas"


def test_el_duenio_que_marca_su_ubicacion_apaga_la_aproximada(client, repo):
    """Si el dueño corrige el punto desde Mi comercio, deja de ser aproximado."""
    from tests.conftest import comercio_token
    c = repo.seed_comercio(slug="farmacia-x", nombre="Farmacia X", activo=True,
                           lat=-22.73, lng=-64.33, ubicacion_aproximada=True)
    token = comercio_token(c["id"])
    r = client.put("/comercio/perfil", json={"lat": -22.7311, "lng": -64.3322},
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    assert repo.comercios[c["id"]]["ubicacion_aproximada"] is False
