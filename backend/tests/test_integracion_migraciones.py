"""Migraciones 0156–0158 (API de integración): iguales en las dos carpetas, con RLS y GRANTs explícitos.

Opcional, contra un Postgres real (Docker): `URUKU_PG_TEST_CONTAINER=<contenedor con la cadena aplicada>` verifica
los permisos reales de anon/authenticated/service_role y que las migraciones corren dos veces.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.pg_0149 import RAIZ, sin_comentarios_sql

NUEVAS = ("0156_integracion_tablas", "0157_publicaciones_updated_at_y_remitente", "0158_difusion_cola_integracion")
TABLAS = ("integracion_clientes", "integracion_comercios", "integracion_idempotencia", "integracion_eventos")


def _sql(nombre, carpeta="supabase/migrations"):
    return (RAIZ / carpeta / f"{nombre}.sql").read_text(encoding="utf-8")


@pytest.mark.parametrize("nombre", NUEVAS)
def test_la_migracion_es_identica_en_las_dos_carpetas(nombre):
    a = (RAIZ / "supabase/migrations" / f"{nombre}.sql").read_bytes()
    b = (RAIZ / "selfhost/postgres-init" / f"{nombre}.sql").read_bytes()
    assert a and a == b


def test_no_hay_huecos_ni_numeros_repetidos_desde_la_0155():
    nums = sorted(int(p.name[:4]) for p in (RAIZ / "supabase/migrations").glob("0*.sql") if int(p.name[:4]) >= 155)
    assert nums == list(range(155, nums[-1] + 1)) and nums[-1] >= 158


@pytest.mark.parametrize("nombre", NUEVAS)
def test_es_una_transaccion_idempotente_y_recarga_postgrest(nombre):
    sql = sin_comentarios_sql(_sql(nombre))
    assert sql.index("begin;") < sql.index("commit;")
    assert sql.rstrip().endswith("notify pgrst, 'reload schema';")
    assert not re.search(r"create table(?! if not exists)", sql, re.I)
    assert not re.search(r"\bdrop\s+(table|schema|database|column)\b", sql, re.I)
    assert not re.search(r"\bdelete\s+from\b|\btruncate\b", sql, re.I)
    assert "do $chk$" in sql                      # comprobación al final


def test_las_tablas_nuevas_tienen_rls_y_ningun_permiso_para_anon_ni_authenticated():
    sql = sin_comentarios_sql(_sql(NUEVAS[0]))
    for t in TABLAS:
        assert f"alter table public.{t}" in sql and "enable row level security" in sql
        assert re.search(rf"revoke all on public\.{t}\s+from public, anon, authenticated;", sql), t
        assert not re.search(rf"grant[^;]*on public\.{t}\s+to[^;]*(anon|authenticated|public)", sql, re.I), t
    # nada de policies: sin policy y con RLS, anon/authenticated no ven nada aunque alguien les diera un grant
    assert "create policy" not in sql


def test_service_role_recibe_solo_lo_que_necesita():
    """La 0090 deja `default privileges ... grant all` para service_role: la 0156 se lo quita y da lo mínimo."""
    sql = sin_comentarios_sql(_sql(NUEVAS[0]))
    for t in TABLAS:
        assert re.search(rf"revoke all on public\.{t}\s+from service_role;", sql), t
    assert re.search(r"grant select, insert\s+on public\.integracion_eventos\s+to service_role;", sql)         # append-only
    assert not re.search(r"grant[^;]*delete[^;]*integracion_(clientes|comercios|eventos)", sql, re.I)         # baja lógica


def test_las_columnas_nuevas_de_publicaciones_y_cola_no_se_dan_a_anon():
    sql = sin_comentarios_sql(_sql(NUEVAS[1]) + _sql(NUEVAS[2]))
    assert not re.search(r"grant[^;]*(updated_at|remitente_rol|texto_override|solicitado_por)[^;]*to[^;]*(anon|authenticated)", sql, re.I)
    assert "clock_timestamp()" in sql and "before update on public.publicaciones" in sql
    assert "'incierto'" in sql and "update public.publicaciones set updated_at = created_at" in sql      # backfill


def test_ninguna_migracion_nueva_toca_columnas_de_comercios():
    """El alcance vive en `integracion_comercios`: `comercios` (regla 11) no gana columnas."""
    for nombre in NUEVAS:
        assert not re.search(r"alter table (public\.)?comercios\b", sin_comentarios_sql(_sql(nombre)), re.I), nombre


# ───────────────────────────────────────────────────── contra un Postgres real (opcional)
CONTENEDOR = os.environ.get("URUKU_PG_TEST_CONTAINER")
pg = pytest.mark.skipif(not (CONTENEDOR and shutil.which("docker")), reason="sin URUKU_PG_TEST_CONTAINER / docker")


def _psql(consulta: str) -> str:
    out = subprocess.run(["docker", "exec", CONTENEDOR, "psql", "-U", "postgres", "-tAc", consulta],
                         capture_output=True, text=True, timeout=60, env={**os.environ, "MSYS_NO_PATHCONV": "1"})
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


@pg
@pytest.mark.parametrize("tabla", TABLAS)
def test_pg_anon_y_authenticated_no_tocan_las_tablas_de_integracion(tabla):
    for rol in ("anon", "authenticated"):
        for priv in ("select", "insert", "update", "delete"):
            assert _psql(f"select has_table_privilege('{rol}', 'public.{tabla}', '{priv}')") == "f", (rol, tabla, priv)
    assert _psql(f"select relrowsecurity from pg_class where oid = 'public.{tabla}'::regclass") == "t"


@pg
def test_pg_service_role_y_append_only():
    assert _psql("select has_table_privilege('service_role', 'public.integracion_clientes', 'update')") == "t"
    assert _psql("select has_table_privilege('service_role', 'public.integracion_clientes', 'delete')") == "f"
    assert _psql("select has_table_privilege('service_role', 'public.integracion_eventos', 'update')") == "f"
    assert _psql("select has_table_privilege('service_role', 'public.integracion_idempotencia', 'delete')") == "t"


@pg
def test_pg_las_columnas_nuevas_de_publicaciones_son_privadas_y_el_trigger_mueve_updated_at():
    for rol in ("anon", "authenticated"):
        for col in ("updated_at", "remitente_rol"):
            assert _psql(f"select has_column_privilege('{rol}', 'public.publicaciones', '{col}', 'select')") == "f"
    assert _psql("select count(*) from pg_trigger where tgname = 'publicaciones_updated_at' and not tgisinternal") == "1"
    assert _psql("select count(*) from public.publicaciones where updated_at is null") == "0"


@pg
@pytest.mark.parametrize("nombre", NUEVAS)
def test_pg_las_migraciones_corren_dos_veces(nombre):
    ruta = RAIZ / "selfhost/postgres-init" / f"{nombre}.sql"
    subprocess.run(["docker", "cp", str(ruta), f"{CONTENEDOR}:/tmp/{nombre}.sql"], check=True, capture_output=True,
                   env={**os.environ, "MSYS_NO_PATHCONV": "1"})
    for _ in range(2):
        out = subprocess.run(["docker", "exec", CONTENEDOR, "psql", "-U", "postgres", "-v", "ON_ERROR_STOP=1", "-q", "-f",
                              f"/tmp/{nombre}.sql"], capture_output=True, text=True, timeout=120,
                             env={**os.environ, "MSYS_NO_PATHCONV": "1"})
        assert out.returncode == 0, out.stderr
