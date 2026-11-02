"""La migración 0181 (contenido para redes y cuidado de suscriptores).

Lo que se prueba, sin base de datos:
- idéntica en `supabase/migrations/` y en `selfhost/postgres-init/`, y con número único;
- todo o nada (`begin` / `commit`) y termina pidiendo a PostgREST que recargue el esquema;
- RLS activo + `revoke` + `grant` explícito de cada tabla y de la vista (lesson KB: sin GRANT, 42501);
- la columna nueva de `planes` NO entra en ningún `grant select (` a anon;
- ningún `create table` sin `if not exists` (se puede correr dos veces);
- no nombra el código del comercio (lo busca `test_ninguna_vista_ni_funcion_publica_expone_codigo`).

Con `URUKU_PG_TEST_CONTAINER` (un Postgres de Docker, opcional): como anon, un `select` sobre cada
tabla da «permission denied». Sin el contenedor esos tests se saltean, como los de la 0145.
"""
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
NOMBRE = "0181_content_and_subscribers.sql"
TABLAS = ("comercio_social_consents", "content_assets", "content_pieces", "content_piece_sources",
          "content_posts", "subscriber_profiles", "subscriber_reports", "subscriber_tasks")
VISTA = "comercio_social_consent_current"


def _sql(carpeta: str) -> str:
    return (RAIZ / carpeta / NOMBRE).read_text(encoding="utf-8")


def _sin_comentarios(sql: str) -> str:
    return "\n".join(l for l in sql.splitlines() if not l.lstrip().startswith("--"))


def test_es_identica_en_las_dos_carpetas():
    a, b = _sql("supabase/migrations"), _sql("selfhost/postgres-init")
    assert a.replace("\r\n", "\n") == b.replace("\r\n", "\n")


def test_el_numero_0181_es_unico_en_cada_carpeta():
    for carpeta in ("supabase/migrations", "selfhost/postgres-init"):
        con_0181 = sorted(p.name for p in (RAIZ / carpeta).glob("0181_*.sql"))
        assert con_0181 == [NOMBRE], (carpeta, con_0181)


def test_todo_o_nada_y_recarga_el_esquema():
    sql = _sin_comentarios(_sql("supabase/migrations"))
    assert sql.count("begin;") == 1 and sql.count("commit;") == 1
    assert sql.index("begin;") < sql.index("commit;")
    assert sql.rstrip().endswith("notify pgrst, 'reload schema';")
    assert sql.index("commit;") < sql.index("notify pgrst")


def test_cada_tabla_tiene_rls_revoke_y_grant_explicitos():
    sql = _sin_comentarios(_sql("supabase/migrations"))
    for t in TABLAS:
        assert f"alter table public.{t}" in sql and "enable row level security" in sql
        assert re.search(rf"alter table public\.{t}\s+enable row level security;", sql), t
        revoke = re.search(r"revoke all on(.*?)from public, anon, authenticated;", sql, re.S)
        grant = re.search(r"grant all on(.*?)to service_role;", sql, re.S)
        assert revoke and grant
        assert f"public.{t}" in revoke.group(1), t
        assert f"public.{t}" in grant.group(1), t
    assert f"public.{VISTA}" in re.search(r"revoke all on(.*?)from public, anon, authenticated;", sql, re.S).group(1)
    assert re.search(rf"grant select on public\.{VISTA} to service_role;", sql)
    # sólo service_role recibe permisos: nada para anon ni authenticated
    assert not re.search(r"\bgrant\b[^;]*\b(anon|authenticated)\b", sql, re.I)


def test_las_tablas_no_llevan_policies_ni_valvulas_de_escape():
    """RLS sin policies: sólo `service_role` (que la saltea) entra. Sin GUC ni rama OR."""
    sql = _sin_comentarios(_sql("supabase/migrations")).lower()
    assert "create policy" not in sql
    assert "current_setting" not in sql


def test_la_vista_es_security_invoker():
    sql = _sin_comentarios(_sql("supabase/migrations"))
    assert re.search(rf"create or replace view public\.{VISTA}\s+with \(security_invoker = true\)", sql)


def test_la_columna_nueva_de_planes_no_se_le_da_a_anon():
    """La 0134 y la 0144 dan `grant select (columnas)` a anon sobre `planes`; la nueva nace privada."""
    for carpeta in ("supabase/migrations", "selfhost/postgres-init"):
        for f in sorted((RAIZ / carpeta).glob("*.sql")):
            sql = _sin_comentarios(f.read_text(encoding="utf-8"))
            for grant in re.findall(r"grant select \(([^)]*)\)\s+on\s+(?:public\.)?planes", sql, re.I):
                assert "social_pieces_per_month" not in grant, f.name
    assert "social_pieces_per_month" in _sql("supabase/migrations")


def test_ningun_create_table_sin_if_not_exists():
    sql = _sin_comentarios(_sql("supabase/migrations"))
    assert not re.search(r"create table(?! if not exists)", sql)
    assert len(re.findall(r"create table if not exists", sql)) == len(TABLAS)


def test_las_fk_a_comercios_no_llevan_cascade_y_todo_baja_con_activo():
    sql = _sin_comentarios(_sql("supabase/migrations")).lower()
    assert "on delete cascade" not in sql
    assert "delete from" not in sql
    for t in ("content_assets", "content_pieces", "content_posts", "subscriber_tasks", "comercio_social_consents"):
        bloque = re.search(rf"create table if not exists public\.{t} \((.*?)\n\);", sql, re.S).group(1)
        assert "activo" in bloque, t


def test_no_nombra_el_codigo_del_comercio():
    sql = _sin_comentarios(_sql("supabase/migrations"))
    assert not re.search(r"\bcodigo\b", sql)


def test_no_toca_comercios():
    """No agrega columnas a `comercios` (regla 11 de AGENTS.md): así `PRIVADAS_EXTRA` no cambia."""
    sql = _sin_comentarios(_sql("supabase/migrations"))
    assert not re.search(r"alter table (public\.)?comercios\b", sql)


# ── contra un Postgres real (opcional) ───────────────────────────────────────

CONTENEDOR = os.environ.get("URUKU_PG_TEST_CONTAINER")
pg_real = pytest.mark.skipif(not CONTENEDOR or not shutil.which("docker"),
                             reason="sin URUKU_PG_TEST_CONTAINER (Postgres de Docker) o sin docker")


def _psql(sql: str, rol: str, check: bool = True) -> subprocess.CompletedProcess:
    cmd = ["docker", "exec", "-i", CONTENEDOR, "psql", "-U", "postgres", "-v", "ON_ERROR_STOP=1", "-c",
           f"set role {rol}; {sql}"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise AssertionError(r.stderr)
    return r


@pg_real
@pytest.mark.parametrize("tabla", TABLAS + (VISTA,))
@pytest.mark.parametrize("rol", ["anon", "authenticated"])
def test_en_postgres_anon_no_puede_leer_ninguna_tabla_nueva(tabla, rol):
    r = _psql(f"select count(*) from public.{tabla};", rol, check=False)
    assert r.returncode != 0 and "permission denied" in r.stderr, (tabla, rol, r.stderr)


@pg_real
@pytest.mark.parametrize("tabla", TABLAS)
def test_en_postgres_service_role_lee_y_escribe(tabla):
    assert _psql(f"select count(*) from public.{tabla};", "service_role").returncode == 0
