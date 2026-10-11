"""QA de «Cerca de mí con abiertos, el orden por plan y la estrella»
(docs/cerca-abiertos-estrella.md): bordes, hostilidad y contrato front <-> back
que `test_estrella_cortesia.py` no cubre.

Los tests marcados `xfail(strict=True)` son BUGS CONFIRMADOS: cuando se arreglen
van a dar XPASS y, por ser `strict`, rompen la suite hasta que se les saque la
marca. Cada uno dice en `reason` qué falla y dónde.

Los dos tests de Postgres corren sólo si hay un contenedor
(`URUKU_PG_TEST_CONTAINER=<nombre>`), igual que en el archivo hermano.
"""
import inspect
import os
import re
import shutil
import subprocess
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import jwt as pyjwt
import pytest

from app.core import auth
from app.core.config import settings
from app.db.repository import SupabaseRepo

RAIZ = Path(__file__).resolve().parents[2]
FRONT = RAIZ / "frontend"
BOLIVIA = timezone(timedelta(hours=-4))


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _dia(dias: int) -> str:
    return (datetime.now(BOLIVIA).date() + timedelta(days=dias)).isoformat()


def _comercio(repo, **extra):
    c = repo.crear_comercio({"nombre": "Local", "slug": "local", "whatsapp": "59170000001",
                             "activo": True, "plan": "gratis", **extra})
    return c["id"]


def _pago(repo, cid, pid="pag-1"):
    repo.pagos[pid] = {"id": pid, "comercio_id": cid, "estado": "pendiente", "monto": 70}
    return pid


@pytest.fixture
def token_pagos():
    return auth.make_token("admin@uruku.bo", rol="admin")


# ───────────────────────────────────────── permisos: quién NO puede, con tokens hostiles

def _tokens_que_no_deben_pasar(cid):
    payload = {"sub": "x@x", "email": "x@x", "rol": "admin", "roles": ["admin"], "permisos": ["*"]}
    ahora = int(time.time())
    return {
        "vencido": pyjwt.encode({**payload, "exp": ahora - 60}, settings.jwt_secret, algorithm="HS256"),
        "otra_clave": pyjwt.encode({**payload, "exp": ahora + 3600}, "k" * 40, algorithm="HS256"),
        "alg_none": pyjwt.encode({**payload, "exp": ahora + 3600}, None, algorithm="none"),
        "publicador": auth.make_publicador_token("pub@uruku.bo"),
        "usuario_comprador": auth.make_usuario_token("u1", "59170000099"),
        "comercio_del_mismo": auth.make_comercio_token(cid, "dueno@x.com"),
        "agente": auth.make_agente_token("ag@uruku.bo"),
        "moderador": auth.make_token("mod@uruku.bo", rol="moderador"),
        "rol_sin_pagos": auth.make_token("o@uruku.bo", rol="otro", roles=["otro"], permisos=["moderar", "planes"]),
    }


def test_put_plan_y_confirmar_rechazan_todos_los_tokens_sin_permiso_pagos(client, repo):
    cid = _comercio(repo)
    pid = _pago(repo, cid)
    for nombre, tok in _tokens_que_no_deben_pasar(cid).items():
        r1 = client.put(f"/admin/comercio/{cid}/plan", headers=_h(tok), json={"plan": "pro", "cortesia": True})
        r2 = client.post(f"/admin/pagos/{pid}/confirmar", headers=_h(tok), json={"meses": 1, "plan": "pro"})
        assert r1.status_code in (401, 403), (nombre, r1.status_code, r1.text)
        assert r2.status_code in (401, 403), (nombre, r2.status_code, r2.text)
    # Nada se movió.
    assert repo.comercios[cid]["plan"] == "gratis"
    assert not repo.comercios[cid].get("plan_cortesia")
    assert repo.pagos[pid]["estado"] == "pendiente"
    assert not repo.comercios[cid].get("paga_hasta")
    # Sin cabecera Authorization.
    assert client.put(f"/admin/comercio/{cid}/plan", json={"plan": "pro"}).status_code in (401, 403)
    assert client.post(f"/admin/pagos/{pid}/confirmar", json={"meses": 1}).status_code in (401, 403)


def test_el_permiso_planes_no_alcanza_para_asignar_plan(client, repo):
    """`planes` (editar precios) y `pagos` (cobrar / dar cortesías) son cosas distintas."""
    cid = _comercio(repo)
    t = auth.make_token("p@uruku.bo", rol="x", roles=["x"], permisos=["planes", "datos", "moderar"])
    assert client.put(f"/admin/comercio/{cid}/plan", headers=_h(t), json={"plan": "pro", "cortesia": True}).status_code == 403


# ───────────────────────────────────────── PUT plan: hostilidad del cuerpo y del path

def test_put_plan_ignora_campos_de_mas_no_hay_mass_assignment(client, repo, token_pagos):
    cid = _comercio(repo, paga_hasta=_dia(9), suspendido=False, confiable=False, verificado=False)
    r = client.put(f"/admin/comercio/{cid}/plan", headers=_h(token_pagos), json={
        "plan": "pro", "cortesia": False, "paga_hasta": "2099-01-01", "suspendido": True,
        "activo": False, "confiable": True, "verificado": True, "slug": "hackeado"})
    assert r.status_code == 200, r.text
    c = repo.comercios[cid]
    assert (c["paga_hasta"], c["suspendido"], c["confiable"], c["verificado"], c["slug"]) == (_dia(9), False, False, False, "local")
    assert c["activo"] is True


@pytest.mark.parametrize("plan", [
    "PRO",                                   # mayúsculas: el slug es exacto
    "pro ' or '1'='1",                       # inyección clásica
    "pro&plan_cortesia=eq.true",             # intento de colar un filtro PostgREST
    "pro;drop table planes",
    "../pro",
    "<script>alert(1)</script>",
    "  ",                                    # sólo espacios: pasa min_length, no es un slug
    "pro\x00",
])
def test_put_plan_con_slugs_hostiles_da_400_y_no_cambia_nada(client, repo, token_pagos, plan):
    cid = _comercio(repo)
    r = client.put(f"/admin/comercio/{cid}/plan", headers=_h(token_pagos), json={"plan": plan, "cortesia": True})
    assert r.status_code in (400, 422), (plan, r.status_code, r.text)
    assert repo.comercios[cid]["plan"] == "gratis"
    assert not repo.comercios[cid].get("plan_cortesia")


def test_put_plan_recorta_espacios_del_slug(client, repo, token_pagos):
    cid = _comercio(repo)
    r = client.put(f"/admin/comercio/{cid}/plan", headers=_h(token_pagos), json={"plan": "  pro  ", "cortesia": True})
    assert r.status_code == 200 and r.json()["plan"] == "pro"
    assert repo.comercios[cid]["plan"] == "pro"


def test_put_plan_no_deja_ver_ningun_precio(client, repo, token_pagos):
    cid = _comercio(repo)
    r = client.put(f"/admin/comercio/{cid}/plan", headers=_h(token_pagos), json={"plan": "pro", "cortesia": True})
    assert "precio" not in r.text.lower()
    pid = _pago(repo, cid)
    r = client.post(f"/admin/pagos/{pid}/confirmar", headers=_h(token_pagos), json={"meses": 1, "plan": "pro"})
    assert "precio" not in r.text.lower()


def test_put_plan_forma_de_la_respuesta_es_la_que_el_front_espera(client, repo, token_pagos):
    """El front (`asignarPlanComercio`) no lee el cuerpo, pero la forma queda fija."""
    cid = _comercio(repo)
    j = client.put(f"/admin/comercio/{cid}/plan", headers=_h(token_pagos), json={"plan": "destacado", "cortesia": True}).json()
    assert set(j) == {"ok", "comercio", "plan", "plan_cortesia", "paga_hasta"}
    assert set(j["comercio"]) == {"id", "plan", "plan_cortesia", "paga_hasta"}
    assert isinstance(j["plan_cortesia"], bool) and j["ok"] is True


def test_confirmar_con_plan_inactivo_da_400_y_el_pago_sigue_pendiente(client, repo, token_pagos):
    repo.planes["pro"]["activo"] = False
    cid = _comercio(repo)
    pid = _pago(repo, cid)
    r = client.post(f"/admin/pagos/{pid}/confirmar", headers=_h(token_pagos), json={"meses": 1, "plan": "pro"})
    assert r.status_code == 400
    assert repo.pagos[pid]["estado"] == "pendiente"
    assert repo.comercios[cid]["plan"] == "gratis" and not repo.comercios[cid].get("paga_hasta")


def test_confirmar_con_plan_hostil_o_en_blanco(client, repo, token_pagos):
    cid = _comercio(repo)
    pid = _pago(repo, cid)
    for plan in ("PRO", "pro' or '1'='1", "x" * 61):
        r = client.post(f"/admin/pagos/{pid}/confirmar", headers=_h(token_pagos), json={"meses": 1, "plan": plan})
        assert r.status_code in (400, 422), (plan, r.status_code)
        assert repo.pagos[pid]["estado"] == "pendiente"
    # En blanco = «sin plan»: confirma como siempre y no toca el plan (documentado).
    r = client.post(f"/admin/pagos/{pid}/confirmar", headers=_h(token_pagos), json={"meses": 1, "plan": "   "})
    assert r.status_code == 200 and "plan" not in r.json()
    assert repo.comercios[cid]["plan"] == "gratis"


def test_confirmar_un_pago_con_plan_saca_la_cortesia_y_sin_plan_la_deja(client, repo, token_pagos):
    """Un pago confirmado con plan es un comercio que paga: deja de ser de cortesía
    (si no, seguiría sin vencer aunque pague). Sin plan en el body no se toca nada."""
    cid = _comercio(repo, plan="pro", plan_cortesia=True)
    pid = _pago(repo, cid)
    r = client.post(f"/admin/pagos/{pid}/confirmar", headers=_h(token_pagos), json={"meses": 1})
    assert r.status_code == 200
    assert repo.comercios[cid]["plan"] == "pro" and repo.comercios[cid]["plan_cortesia"] is True
    pid2 = _pago(repo, cid, "pag-2")
    r = client.post(f"/admin/pagos/{pid2}/confirmar", headers=_h(token_pagos), json={"meses": 1, "plan": "publica"})
    assert r.status_code == 200
    assert repo.comercios[cid]["plan"] == "publica" and repo.comercios[cid]["plan_cortesia"] is False


# ───────────────────────────────────────── el flujo completo de la cortesía (criterio 4)

def test_flujo_cortesia_punta_a_punta(client, repo, token_pagos):
    viejo = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat()
    cid = _comercio(repo, nombre="Amigo de URUKU", slug="amigo", created_at=viejo, paga_hasta=_dia(-300))
    # 1. el admin lo pone en el plan más caro visible, de cortesía
    r = client.put(f"/admin/comercio/{cid}/plan", headers=_h(token_pagos), json={"plan": "pro", "cortesia": True})
    assert r.status_code == 200
    # 2. en Suscripciones: «cortesia», nunca vencido
    fila = {i["nombre"]: i for i in client.get("/admin/suscripciones", headers=_h(token_pagos)).json()["items"]}["Amigo de URUKU"]
    assert fila["suscripcion_estado"] == "cortesia" and fila["plan"] == "pro" and fila["plan_cortesia"] is True
    # 3. no cuenta en el tablero
    assert client.get("/admin/resumen", headers=_h(token_pagos)).json()["pendientes"]["suscripciones"] == 0
    # 4. el job de bajas no lo oculta aunque pasaron 300 días
    assert repo.ocultar_comercios_vencidos(dias=40, dias_gracia=30) == 0
    assert repo.comercios[cid]["activo"] is True
    # 5. sacarle la cortesía lo devuelve a la regla común (vencido, y el job SÍ lo baja)
    client.put(f"/admin/comercio/{cid}/plan", headers=_h(token_pagos), json={"plan": "pro", "cortesia": False})
    fila = {i["nombre"]: i for i in client.get("/admin/suscripciones", headers=_h(token_pagos)).json()["items"]}["Amigo de URUKU"]
    assert fila["suscripcion_estado"] == "vencido"
    assert repo.ocultar_comercios_vencidos(dias=40, dias_gracia=30) == 1


def test_cortesia_en_plan_gratis_da_400_y_no_cambia_nada(client, repo, token_pagos):
    """La cortesía regala un plan PAGO: en uno gratis el panel dibujaría una estrella
    que en público no existe (el SQL lo cuenta como gratis)."""
    cid = _comercio(repo, plan="pro", plan_cortesia=True)
    r = client.put(f"/admin/comercio/{cid}/plan", headers=_h(token_pagos), json={"plan": "gratis", "cortesia": True})
    assert r.status_code == 400
    assert repo.comercios[cid]["plan"] == "pro" and repo.comercios[cid]["plan_cortesia"] is True
    # Sin cortesía, pasar a gratis sí se puede (y se la saca).
    r = client.put(f"/admin/comercio/{cid}/plan", headers=_h(token_pagos), json={"plan": "gratis", "cortesia": False})
    assert r.status_code == 200 and repo.comercios[cid]["plan_cortesia"] is False


def test_admin_planes_lo_lee_quien_cobra_y_no_el_resto(client, repo):
    """Suscripciones llena el selector de plan con GET /admin/planes."""
    cobrador = auth.make_token("c@uruku.bo", rol="cobrador", roles=["cobrador"], permisos=["pagos"])
    assert client.get("/admin/planes", headers=_h(cobrador)).status_code == 200
    sin = auth.make_token("s@uruku.bo", rol="s", roles=["s"], permisos=["datos"])
    assert client.get("/admin/planes", headers=_h(sin)).status_code == 403
    assert client.get("/admin/planes").status_code in (401, 403)
    agente = auth.make_agente_token("ag@uruku.bo")
    assert client.get("/admin/planes", headers=_h(agente)).status_code == 403


# ───────────────────────────────────────── contrato front <-> back del estado «cortesia»

def _estados_que_ve_el_comercio() -> set[str]:
    from app.api.comercio import _estado_suscripcion
    casos = [
        {"plan": "gratis"},
        {"plan": "pro"},
        {"plan": "pro", "paga_hasta": _dia(30)},
        {"plan": "pro", "paga_hasta": _dia(3)},
        {"plan": "pro", "paga_hasta": _dia(-3)},
        {"plan": "pro", "suspendido": True},
        {"plan": "pro", "plan_cortesia": True},
        {"plan": "pro", "plan_cortesia": True, "suspendido": True},
    ]
    return {_estado_suscripcion(c)["estado"] for c in casos}


def _literales_de_la_union(archivo: Path, nombre: str) -> set[str]:
    texto = archivo.read_text(encoding="utf-8")
    m = re.search(rf"{re.escape(nombre)}\s*=\s*([^;]+);", texto)
    assert m, f"no encontré {nombre} en {archivo}"
    return set(re.findall(r'"([a-z_]+)"', m.group(1)))


def _claves_del_mapa(archivo: Path, nombre: str) -> set[str]:
    texto = archivo.read_text(encoding="utf-8")
    ini = texto.index(f"const {nombre}")
    ini = texto.index("{", texto.index("=", ini))      # la llave del objeto, no la del tipo
    prof, i = 0, ini
    while True:
        prof += {"{": 1, "}": -1}.get(texto[i], 0)
        if prof == 0:
            break
        i += 1
    cuerpo = texto[ini + 1:i]
    return set(re.findall(r"^\s*([a-z_]+):\s*\{", cuerpo, re.M))


def test_el_admin_conoce_todos_los_estados_de_suscripciones():
    desde_back = {"activo", "por_vencer", "vencido", "suspendido", "sin_plan", "cortesia"}   # list_suscripciones
    union = _literales_de_la_union(FRONT / "lib/api.ts", "export type EstadoSuscripcion")
    assert desde_back <= union, desde_back - union
    cfg = _claves_del_mapa(FRONT / "app/admin/page.tsx", "ESTADO_CFG")
    assert desde_back <= cfg, desde_back - cfg


def test_mi_comercio_conoce_todos_los_estados_que_manda_el_backend():
    estados = _estados_que_ve_el_comercio()
    assert "cortesia" in estados
    texto = (FRONT / "lib/comercio.ts").read_text(encoding="utf-8")
    bloque = texto[texto.index("export type Suscripcion = {"):]
    union = set(re.findall(r'"([a-z_]+)"', re.search(r"estado:\s*([^;]+);", bloque).group(1)))
    mapa = _claves_del_mapa(FRONT / "app/mi-comercio/page.tsx", "ESTADO")
    # Fue BUG-QA-1: el back mandaba «cortesia» y el mapa ESTADO de mi-comercio no lo tenía
    # (ESTADO["cortesia"] undefined -> SuscripcionTab se caía en e.bg / e.color / e.label). Ya está.
    assert estados <= union and estados <= mapa, (estados - union, estados - mapa)


# ───────────────────────────────────────── estadísticas: lo que NO se tocó

# BUG-QA-2 (corregido): una cortesía con fecha futura no se cuenta como «pagando».
def test_kpi_pagando_no_cuenta_la_cortesia():
    fuente = inspect.getsource(SupabaseRepo)
    bloque = fuente[fuente.index("pagando = ("):]
    bloque = bloque[:bloque.index("\n")]
    assert "plan_cortesia" in bloque, bloque


# ───────────────────────────────────────── criterio 5: ningún precio al público (estático)

def test_ningun_archivo_publico_del_front_lee_precio_mes():
    permitidos = {"app/admin/page.tsx", "lib/api.ts", "components/planes-panel.tsx", "lib/data.ts"}
    ofensores = []
    for carpeta in ("app", "components", "lib"):
        for p in (FRONT / carpeta).rglob("*"):
            if p.suffix not in {".ts", ".tsx"} or "node_modules" in p.parts:
                continue
            rel = p.relative_to(FRONT).as_posix()
            if "precio_mes" in p.read_text(encoding="utf-8", errors="ignore") and rel not in permitidos:
                ofensores.append(rel)
    assert ofensores == []
    # lib/data.ts sólo lo nombra en un comentario («SIN precio_mes A PROPÓSITO»).
    for linea in (FRONT / "lib/data.ts").read_text(encoding="utf-8").splitlines():
        if "precio_mes" in linea:
            assert linea.lstrip().startswith("//"), linea


def test_en_0143_precio_mes_solo_se_lee_dentro_de_planes_orden():
    sql = (RAIZ / "supabase/migrations/0143_estrella_y_cortesia.sql").read_text(encoding="utf-8")
    sin_comentarios = chr(10).join(l.split("--")[0] for l in sql.splitlines())
    usos = [m.start() for m in re.finditer(r"precio_mes", sin_comentarios)]
    assert len(usos) == 2                                   # where pl.precio_mes > 0 + order by pl.precio_mes
    ini = sin_comentarios.index("create or replace function public.planes_orden")
    fin = sin_comentarios.index("create or replace function public.plan_orden_de")
    assert all(ini < u < fin for u in usos)
    assert "returns table (slug text, orden int)" in sin_comentarios
    assert "returns table (estrella boolean, plan_orden int)" in sin_comentarios


def test_la_migracion_0143_es_la_misma_en_las_dos_carpetas_y_ninguna_posterior_la_deshace():
    a = (RAIZ / "supabase/migrations/0143_estrella_y_cortesia.sql").read_bytes()
    b = (RAIZ / "selfhost/postgres-init/0143_estrella_y_cortesia.sql").read_bytes()
    assert a == b
    # Una migración POSTERIOR no puede redefinir estas funciones: pisaría la estrella.
    redefine = re.compile(r"create\s+(or\s+replace\s+)?function\s+(public\.)?(buscar_comercios|plan_orden_de|plan_publico|planes_orden|admin_resumen)\b", re.I)
    for carpeta in ("supabase/migrations", "selfhost/postgres-init"):
        for p in (RAIZ / carpeta).glob("01[4-9][0-9]_*.sql"):
            if p.name[:4] <= "0143":
                continue
            sin_comentarios = chr(10).join(l.split("--")[0] for l in p.read_text(encoding="utf-8").splitlines())
            assert not redefine.search(sin_comentarios), p.name


# ───────────────────────────────────────── criterio 3: la tilde ya no se ve en público

def test_ninguna_pantalla_publica_muestra_la_tilde_verificado():
    internos = {
        "app/admin/page.tsx", "app/mi-comercio/page.tsx", "app/publicar/page.tsx",   # admin / comercio / agente
        "components/icons.tsx", "components/ic.tsx", "lib/iconos-dibujos.ts",         # catálogo de íconos
    }
    patron = re.compile(r"\bVerified\b|uk-verif|comercio_verificado|n=[\"']verificado[\"']|Negocio verificado")
    ofensores = []
    for carpeta in ("app", "components"):
        for p in (FRONT / carpeta).rglob("*.tsx"):
            rel = p.relative_to(FRONT).as_posix()
            if rel in internos or rel.startswith("components/admin/") or "node_modules" in p.parts:
                continue
            for n, linea in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                if patron.search(linea) and not linea.lstrip().startswith(("//", "*", "{/*")):
                    ofensores.append(f"{rel}:{n}: {linea.strip()[:90]}")
    assert ofensores == [], ofensores


def test_los_resultados_publicos_solo_dibujan_la_estrella_con_estrella_true():
    buscador = (FRONT / "components/buscar-client.tsx").read_text(encoding="utf-8")
    assert "r.estrella === true && <EstrellaVerificado" in buscador          # estricto: undefined / null no pintan
    mapa = (FRONT / "components/map-results.tsx").read_text(encoding="utf-8")
    assert "r.verificado" not in mapa
    ficha = (FRONT / "app/comercios/[slug]/page.tsx").read_text(encoding="utf-8")
    assert "planPublico.estrella &&" in ficha and "comercio.verificado &&" not in ficha


def test_el_front_tolera_plan_publico_vacio_y_base_sin_migrar():
    data = (FRONT / "lib/data.ts").read_text(encoding="utf-8")
    cuerpo = data[data.index("export async function getPlanPublico"):]
    cuerpo = cuerpo[:cuerpo.index("\n}\n") + 3]
    assert "const SIN = { estrella: false, plan_orden: 0 }" in cuerpo
    assert "if (error) return SIN" in cuerpo and "if (!fila) return SIN" in cuerpo and "catch" in cuerpo
    assert "fila.estrella === true" in cuerpo
    orden = (FRONT / "lib/orden-cerca.ts").read_text(encoding="utf-8")
    assert "r.estrella === true" in orden and "r.plan_orden ?? 0" in orden
    tipos = (FRONT / "lib/types.ts").read_text(encoding="utf-8")
    assert re.search(r"estrella\?: boolean;", tipos) and re.search(r"plan_orden\?: number;", tipos)


# ───────────────────────────────────────── Postgres real (opcional)

@pytest.fixture(scope="module")
def pg():
    contenedor = os.environ.get("URUKU_PG_TEST_CONTAINER")
    if not contenedor or not shutil.which("docker"):
        pytest.skip("sin Postgres de Docker (URUKU_PG_TEST_CONTAINER)")
    base = "t0143qa_" + uuid.uuid4().hex[:8]

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
                                 nombre text, activo boolean not null default true);
            insert into planes (slug, precio_mes, nombre) values ('gratis',0,'B'),('publica',70,'P'),('pro',400,'Pro');
            create table comercios (id uuid primary key default gen_random_uuid(), plan text,
              plan_cortesia boolean not null default false, paga_hasta date,
              suspendido boolean not null default false, activo boolean not null default true);
            grant usage on schema public to anon, authenticated, service_role;
            revoke all on planes from anon, authenticated;
            grant select (slug, nombre, activo) on planes to anon, authenticated;
        """)
        sql = (RAIZ / "supabase/migrations/0143_estrella_y_cortesia.sql").read_text(encoding="utf-8")
        psql(sql[sql.index("create or replace function public.planes_orden"):
                 sql.index("-- ------------------------------------------------------- buscar_comercios")])
        yield psql
    finally:
        psql(f'drop database if exists "{base}" with (force)', db="postgres", check=False)


def _orden(pg, plan, cortesia, paga, suspendido):
    out = pg(f"set role anon; select public.plan_orden_de('{plan}', {cortesia}, {paga}, {suspendido});").stdout.strip().splitlines()
    return int(out[-1])


def test_pg_borde_de_la_fecha_en_hora_de_bolivia(pg):
    hoy_bo = "(now() at time zone 'America/La_Paz')::date"
    assert _orden(pg, "pro", "false", hoy_bo, "false") == 2          # vence hoy (pro = segundo plan pago): todavía al día
    assert _orden(pg, "pro", "false", f"{hoy_bo} - 1", "false") == 0  # venció ayer
    assert _orden(pg, "pro", "false", f"{hoy_bo} + 1", "true") == 0   # suspendido
    assert _orden(pg, "gratis", "true", "null", "false") == 0         # plan sin precio: sin estrella aunque sea cortesía


# Fue BUG-QA-3: plan_orden_de daba estrella a una cortesía SUSPENDIDA. Ya está (0143 revisada).
def test_pg_cortesia_suspendida_no_tiene_estrella(pg):
    assert _orden(pg, "pro", "true", "null", "true") == 0
