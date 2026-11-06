"""La migración 0193 (medición v2): CA-3 (el navegador ya no inserta), CA-11 (retención con piso, sin DELETE) y CA-12
(el resumen de 90 días con 300.000 filas, en menos de 1 s).

- Estáticas: la 0193 es idéntica en las dos carpetas, todo o nada, idempotente, sin permisos para anon/authenticated,
  con el piso de 13 meses adentro de la función de purga y sin tocar `cost_switches`.
- Contra un Postgres real de Docker (opcional, `URUKU_PG_TEST_CONTAINER=<contenedor postgres>`; sin él se saltean):
  anon y authenticated no pueden insertar ni leer; service_role no puede borrar ni vaciar ni modificar visitas;
  `purge_site_metrics(1)` falla y `purge_site_metrics(13)` borra sólo lo viejo; el resumen cuenta bien y rápido; la
  migración corre dos veces.
"""
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
NOMBRE = "0193_site_metrics_v2.sql"


def _sql(carpeta: str = "supabase/migrations") -> str:
    return (RAIZ / carpeta / NOMBRE).read_text(encoding="utf-8")


def _sin_comentarios(sql: str) -> str:
    return re.sub(r"--[^\n]*", "", sql)


def _normal(sql: str) -> str:
    return re.sub(r"\s+", " ", _sin_comentarios(sql))


# ═════════════════════════════════════ estáticas
def test_es_identica_en_las_dos_carpetas_y_el_numero_es_unico():
    assert _sql("supabase/migrations").replace("\r\n", "\n") == _sql("selfhost/postgres-init").replace("\r\n", "\n")
    for carpeta in ("supabase/migrations", "selfhost/postgres-init"):
        assert sorted(p.name for p in (RAIZ / carpeta).glob("0193_*.sql")) == [NOMBRE]
        nums = [p.name[:4] for p in (RAIZ / carpeta).glob("*.sql")]
        assert nums.count("0193") == 1


def test_todo_o_nada_idempotente_y_recarga_el_esquema():
    sql = _sin_comentarios(_sql())
    assert sql.count("begin;") == 1 and sql.count("commit;") == 1 and sql.index("begin;") < sql.index("commit;")
    assert sql.rstrip().endswith("notify pgrst, 'reload schema';")
    assert not re.search(r"create table(?! if not exists)", sql)
    assert not re.search(r"add column(?! if not exists)", sql)
    assert not re.search(r"create index(?! if not exists)", sql)
    assert not re.search(r"create function", sql) and not re.search(r"drop table|drop column", sql)


def test_CA3_el_navegador_no_inserta_ni_lee_ni_tiene_policy():
    sql = _normal(_sql())
    assert "drop policy if exists visitas_insert_public on public.visitas;" in sql
    assert "drop policy if exists leads_insert_public on public.leads;" in sql
    for t in ("visitas", "leads", "site_events"):
        assert f"revoke all on public.{t} from public, anon, authenticated;" in sql
    assert "alter table public.site_events enable row level security;" in sql
    # ningún grant para el navegador, en ningún lado
    assert not re.search(r"grant [^;]*\bto [^;]*\b(anon|authenticated|public)\b", sql)
    # las columnas nuevas no se dan por columna (nacen privadas: regla 11 de AGENTS.md)
    assert not re.search(r"grant (select|insert|update)? ?\(", sql)


def test_CA11_service_role_sin_delete_ni_vaciado_y_la_purga_con_piso():
    sql = _normal(_sql())
    assert "revoke update, delete, truncate on public.visitas from service_role;" in sql
    assert "revoke update, delete, truncate on public.site_events from service_role;" in sql
    assert "revoke delete, truncate on public.leads from service_role;" in sql
    assert "grant select, insert on public.visitas to service_role;" in sql
    assert "grant select, insert, update on public.leads to service_role;" in sql        # el «¿te contestó?» escribe `respondio`
    m = re.search(r"create or replace function public\.purge_site_metrics\(p_months int default 13\) (.*?) \$\$ (.*?) \$\$;", sql)
    assert m, "no encontré purge_site_metrics"
    cabecera, cuerpo = m.groups()
    assert "security definer" in cabecera and "set search_path = public, pg_temp" in cabecera
    assert "if p_months is null or p_months < 13 then raise exception 'retención mínima: 13 meses'" in cuerpo
    assert "delete from public.visitas where dia < v_corte" in cuerpo and "delete from public.site_events where day < v_corte" in cuerpo
    assert "leads" not in cuerpo and "busquedas" not in cuerpo                            # los contactos y las búsquedas no se purgan
    assert "revoke execute on function public.purge_site_metrics(int) from public, anon, authenticated;" in sql
    assert "grant execute on function public.purge_site_metrics(int) to service_role;" in sql


def test_los_resumenes_son_security_invoker_y_solo_del_backend():
    sql = _normal(_sql())
    for f, args in (("site_metrics_summary", "date, date, text"), ("comercio_origins", "uuid, date"),
                    ("comercio_lead_counts", "uuid, int")):
        assert f"revoke execute on function public.{f}({args}) from public, anon, authenticated;" in sql
        assert f"grant execute on function public.{f}({args}) to service_role;" in sql
        m = re.search(rf"create or replace function public\.{f}\(.*?\) returns jsonb language sql stable (.*?) as \$\$", sql)
        assert m and "security definer" not in m.group(1) and "set search_path = public, pg_temp" in m.group(1)


def test_el_resumen_trae_lo_que_dice_el_contrato():
    sql = _normal(_sql())
    cuerpo = sql[sql.index("function public.site_metrics_summary"):sql.index("function public.comercio_origins")]
    for clave in ("totals", "by_day", "top_paths", "referrers_raw", "origins", "devices", "standalone_share", "events",
                  "funnel", "leads_by_type", "ai_groups", "ai_routes"):
        assert f"'{clave}'" in cuerpo, clave
    for sub in ("'pageviews'", "'sessions'", "'first_pages'", "'sessions_with_ficha'", "'sessions_with_contact'"):
        assert sub in cuerpo
    assert "generate_series" in cuerpo                       # todos los días del rango, con ceros
    assert "limit 15" in cuerpo and "limit 300" in cuerpo    # top 15 de rutas, top 300 de referidos
    assert not re.search(r"\b(insert|update|delete)\b", cuerpo)


def test_site_events_tiene_el_catalogo_cerrado_y_sin_datos_personales():
    sql = _normal(_sql())
    m = re.search(r"create table if not exists public\.site_events \((.*?)\);", sql)
    assert m
    cuerpo = m.group(1)
    assert "event in ('share', 'pwa_install', 'video_play', 'video_network_click', 'uruku_whatsapp_click')" in cuerpo
    assert "char_length(detail) <= 40" in cuerpo and "char_length(path) <= 200" in cuerpo
    for prohibido in ("ip", "user_agent", "ua ", "cookie", "query"):
        assert not re.search(rf"\b{prohibido}\b", cuerpo.replace("session", "")), prohibido


def test_no_se_toca_cost_switches_ni_comercios_ni_publicaciones():
    sql = _normal(_sql())
    assert "cost_switches" not in sql and "umami" not in sql
    # las dos tablas con tests de columnas públicas (regla 11) no se tocan
    assert not re.search(r"(alter table|grant [^;]*on|revoke [^;]*on) (public\.)?(comercios|publicaciones)\b", sql)


def test_el_tablero_ya_no_cuenta_compartir_ni_red_como_contacto():
    sql = _normal(_sql())
    assert sql.count("coalesce(l.tipo, '') not in ('vista', 'compartir', 'red')") == 2
    assert "<> 'vista'" not in sql
    # mismo cuerpo que la 0143 salvo esas dos condiciones
    viejo = _normal((RAIZ / "supabase/migrations/0143_estrella_y_cortesia.sql").read_text(encoding="utf-8"))
    ini, fin = viejo.index("create or replace function public.admin_resumen"), viejo.index("$fn$; comment on function public.admin_resumen")
    cuerpo_viejo = viejo[ini:fin].replace("coalesce(l.tipo, '') <> 'vista'", "coalesce(l.tipo, '') not in ('vista', 'compartir', 'red')")
    assert cuerpo_viejo in sql


# ═════════════════════════════════════ contra un Postgres real
@pytest.fixture(scope="module")
def pg0193():
    """`psql(sql, rol=None, check=True, db=...)` contra una base descartable con el estado de ANTES de la 0193 y la
    migración ya corrida (dos veces: de paso prueba la idempotencia)."""
    contenedor = os.environ.get("URUKU_PG_TEST_CONTAINER")
    if not contenedor or not shutil.which("docker"):
        pytest.skip("sin Postgres de Docker (URUKU_PG_TEST_CONTAINER)")
    base = "t0193_" + uuid.uuid4().hex[:8]

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
        psql("""
            do $$ begin
              begin create role anon nologin; exception when duplicate_object then null; end;
              begin create role authenticated nologin; exception when duplicate_object then null; end;
              begin create role service_role nologin; exception when duplicate_object then null; end;
            end $$;
            alter role service_role bypassrls;            -- como el de Supabase
            grant usage on schema public to anon, authenticated, service_role;

            create table ciudades (id uuid primary key default gen_random_uuid(), slug text);
            create table comercios (id uuid primary key default gen_random_uuid(), slug text,
                                    ciudad_id uuid references ciudades(id), activo boolean not null default true);
            create table busquedas (id uuid primary key default gen_random_uuid());
            -- leads y visitas como las dejaron la 0011/0055/0114/0120/0187 y la 0130 (con los permisos y policies de entonces)
            create table leads (
              id uuid primary key default gen_random_uuid(),
              comercio_id uuid not null references comercios(id) on delete cascade,
              tipo text not null default 'whatsapp', created_at timestamptz not null default now(),
              busqueda_id uuid references busquedas(id) on delete set null, origen text,
              respondio boolean, respondio_en timestamptz, respondio_por text);
            grant select, insert on leads to anon, authenticated;
            grant all on leads to service_role;
            alter table leads enable row level security;
            create policy leads_insert_public on leads for insert to anon, authenticated with check (true);
            create policy leads_select_service on leads for select to service_role using (true);
            create table visitas (
              id uuid primary key default gen_random_uuid(),
              dia date not null default ((now() at time zone 'America/La_Paz')::date),
              ruta text not null, sesion text not null, origen text, referido text, ciudad_slug text,
              primera boolean not null default false, created_at timestamptz not null default now());
            create index idx_visitas_dia on visitas (dia desc);
            grant select, insert on visitas to anon, authenticated;
            grant all on visitas to service_role;
            alter table visitas enable row level security;
            create policy visitas_insert_public on visitas for insert to anon, authenticated with check (true);
            create policy visitas_select_service on visitas for select to service_role using (true);
        """)
        migracion = _sql()
        psql(migracion)
        psql(migracion)                                # idempotente
        yield psql
    finally:
        psql(f'drop database if exists "{base}" with (force)', db="postgres", check=False)


def _falla(p, texto="permission denied"):
    assert p.returncode != 0, "tendría que haber fallado"
    assert texto in p.stderr, p.stderr


@pytest.mark.parametrize("rol", ["anon", "authenticated"])
def test_CA3_pg_el_navegador_no_inserta_ni_lee_visitas_leads_ni_eventos(pg0193, rol):
    for tabla, cols, vals in (("visitas", "ruta, sesion", "'/', 'abcdef'"),
                              ("site_events", "event, path", "'share', '/'"),
                              ("leads", "comercio_id", "gen_random_uuid()")):
        _falla(pg0193(f"insert into {tabla} ({cols}) values ({vals});", rol=rol, check=False))
        _falla(pg0193(f"select count(*) from {tabla};", rol=rol, check=False))
    _falla(pg0193("select public.purge_site_metrics(13);", rol=rol, check=False))
    _falla(pg0193("select public.site_metrics_summary(current_date, current_date);", rol=rol, check=False))


def test_CA11_pg_service_role_escribe_pero_no_borra_ni_vacia_ni_modifica(pg0193):
    pg0193("insert into visitas (ruta, sesion) values ('/', 'abcdef'); "
           "insert into site_events (event, path, detail) values ('share', '/', 'copy');", rol="service_role")
    for sql in ("delete from visitas;", "truncate visitas;", "update visitas set ruta = '/x';",
                "delete from site_events;", "truncate site_events;", "delete from leads;", "truncate leads;"):
        _falla(pg0193(sql, rol="service_role", check=False))
    # leads conserva UPDATE (el «¿te contestó?»)
    pg0193("insert into comercios (slug) values ('c'); insert into leads (comercio_id) select id from comercios limit 1;")
    pg0193("update leads set respondio = true;", rol="service_role")


def test_CA11_pg_la_purga_tiene_piso_y_borra_solo_lo_viejo(pg0193):
    pg0193("delete from visitas; delete from site_events;")
    pg0193("""
        insert into visitas (dia, ruta, sesion) values
          (current_date - 500, '/viejo', 'sesion-1'), (current_date - 400, '/viejo2', 'sesion-2'),
          (current_date - 30, '/reciente', 'sesion-3'), (current_date, '/hoy', 'sesion-4');
        insert into site_events (day, event, path, detail) values
          (current_date - 500, 'share', '/', 'copy'), (current_date, 'share', '/', 'copy');
    """)
    for meses in ("1", "12", "null"):
        p = pg0193(f"select public.purge_site_metrics({meses});", rol="service_role", check=False)
        _falla(p, "retención mínima")
    assert pg0193("select count(*) from visitas;").stdout.strip() == "4"
    assert pg0193("select public.purge_site_metrics(13);", rol="service_role").stdout.strip() == "3"   # 2 visitas + 1 evento
    assert pg0193("select string_agg(ruta, ',' order by ruta) from visitas;").stdout.strip() == "/hoy,/reciente"
    assert pg0193("select count(*) from site_events;").stdout.strip() == "1"
    assert pg0193("select public.purge_site_metrics(13);", rol="service_role").stdout.strip() == "0"


def test_pg_el_resumen_cuenta_dias_sesiones_funnel_y_eventos(pg0193):
    pg0193("delete from visitas; delete from site_events; delete from leads; delete from comercios; delete from ciudades;")
    pg0193("""
        insert into ciudades (id, slug) values ('00000000-0000-4000-8000-000000000001', 'bermejo');
        insert into comercios (id, slug, ciudad_id) values ('00000000-0000-4000-8000-0000000000c1', 'rustico', '00000000-0000-4000-8000-000000000001');
        insert into visitas (dia, ruta, sesion, origen, referido, ciudad_slug, primera, device, standalone) values
          (current_date, '/', 'sa', null, 'l.facebook.com', 'bermejo', true, 'mobile', true),
          (current_date, '/comercios/rustico', 'sa', null, null, 'bermejo', false, 'mobile', true),
          (current_date, '/', 'sb', 'chatgpt.com', null, 'bermejo', true, 'desktop', false),
          (current_date - 2, '/', 'sc', null, null, 'tarija', true, null, false);
        insert into leads (comercio_id, tipo, sesion) values
          ('00000000-0000-4000-8000-0000000000c1', 'whatsapp', 'sa'),
          ('00000000-0000-4000-8000-0000000000c1', 'vista', 'sa'),
          ('00000000-0000-4000-8000-0000000000c1', 'compartir', 'sb');
        insert into site_events (event, path, detail, city_slug) values ('share', '/', 'copy', 'bermejo'), ('share', '/', 'copy', 'bermejo');
    """)
    r = pg0193("select public.site_metrics_summary(current_date - 4, current_date)::text;", rol="service_role").stdout.strip()
    import json
    d = json.loads(r)
    assert d["totals"] == {"pageviews": 4, "sessions": 3, "first_pages": 3}
    assert len(d["by_day"]) == 5 and sum(x["visitas"] for x in d["by_day"]) == 4
    assert [x["visitas"] for x in d["by_day"]] == [0, 0, 1, 0, 3]                       # los días sin nada, con cero
    assert d["funnel"] == {"sessions": 3, "sessions_with_ficha": 1, "sessions_with_contact": 1}
    assert d["leads_by_type"] == {"whatsapp": 1, "vista": 1, "compartir": 1}
    assert d["events"] == [{"event": "share", "detail": "copy", "n": 2}]
    assert d["standalone_share"] == 0.3333
    assert {x["device"]: x["n"] for x in d["devices"]} == {"mobile": 1, "desktop": 1, "unknown": 1}
    assert {(x["referido"], x["origen"]) for x in d["referrers_raw"]} == {("l.facebook.com", None), (None, "chatgpt.com"), (None, None)}
    assert d["top_paths"][0] == {"ruta": "/", "n": 3}
    ciudad = json.loads(pg0193("select public.site_metrics_summary(current_date - 4, current_date, 'bermejo')::text;",
                               rol="service_role").stdout.strip())
    assert ciudad["totals"] == {"pageviews": 3, "sessions": 2, "first_pages": 2}
    assert ciudad["leads_by_type"] == {"whatsapp": 1, "vista": 1, "compartir": 1}         # el comercio es de Bermejo
    origen = json.loads(pg0193("select public.comercio_origins('00000000-0000-4000-8000-0000000000c1', current_date - 30)::text;",
                               rol="service_role").stdout.strip())
    assert origen == []                                                                    # ninguna visita primera a /comercios/rustico
    cuentas = json.loads(pg0193("select public.comercio_lead_counts('00000000-0000-4000-8000-0000000000c1', 30)::text;",
                                rol="service_role").stdout.strip())
    assert cuentas["por_tipo"] == {"whatsapp": 1, "vista": 1, "compartir": 1} and cuentas["redes"] == {}


def test_CA12_pg_el_resumen_de_90_dias_con_300000_filas_tarda_menos_de_1_segundo(pg0193):
    pg0193("delete from visitas; delete from site_events; delete from leads;")
    pg0193("""
        insert into visitas (dia, ruta, sesion, origen, referido, ciudad_slug, primera, device, standalone)
        select current_date - (g % 90),
               (array['/', '/buscar', '/ofertas', '/comercios/uno', '/mapa'])[1 + g % 5],
               's' || (g / 3),
               case when g % 50 = 0 then 'volante-x' end,
               case when g % 7 = 0 then 'google.com' end,
               'bermejo', g % 3 = 0, (array['mobile', 'desktop', 'tablet'])[1 + g % 3], g % 10 = 0
          from generate_series(1, 300000) g;
        analyze visitas;
    """)
    p = pg0193("""
        do $$
        declare t0 timestamptz := clock_timestamp(); r jsonb; ms numeric;
        begin
          set local role service_role;
          r := public.site_metrics_summary(current_date - 89, current_date);
          ms := extract(epoch from clock_timestamp() - t0) * 1000;
          if (r->'totals'->>'pageviews')::int <> 300000 then raise exception 'cortó los totales: %', r->'totals'; end if;
          if ms > 1000 then raise exception 'tardó % ms', ms; end if;
        end $$;
    """)
    assert p.returncode == 0
