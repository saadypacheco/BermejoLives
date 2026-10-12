"""Un Postgres real (Docker) con lo mínimo para probar la migración 0149.

Opcional: variable `URUKU_PG_TEST_CONTAINER=<contenedor postgres>`. Sin ella (o sin
`docker`) los tests que usan `pg0149` se saltean. Cada módulo de test arma su propia base
(`create database`) y la borra al terminar: no toca nada más del servidor.

Arma las tablas que la 0149 necesita con las columnas REALES (las que suman las
migraciones), pero con tipos simples: lo que se prueba son los permisos, no los datos.
  - publicaciones (todas las columnas de las migraciones; `id` uuid, `activo` boolean) con
    la policy de la 0002 y el `grant select` de TABLA entera de la 0002 (el estado de antes),
  - comercios (id, slug, nombre, activo, codigo + índice único, cargado_por) con el grant
    de columnas de la 0148,
  - comercio_usuarios (id, comercio_id, clave_hash) sin permisos para anon,
  - feed_publico (una vista como la real: corre con su dueño),
  - previsualizar_patron(text, text) y rubros_a_revisar(text, integer): ejecutables por
    PUBLIC, como las deja la 0087/0089.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
MIGRACIONES = RAIZ / "supabase/migrations"


def sin_comentarios_sql(sql: str) -> str:
    return "\n".join(l for l in sql.splitlines() if not l.lstrip().startswith("--"))


def leer_0149(carpeta: str = "supabase/migrations") -> str:
    return (RAIZ / carpeta / "0149_publicaciones_columnas_y_codigos.sql").read_text(encoding="utf-8")


def columnas_de_tabla(tabla: str) -> list[str]:
    """Las columnas de `tabla` según las migraciones, en orden (create table de la 0001 +
    cada `alter table ... add/drop/rename column`)."""
    cols: list[str] = []
    init = (MIGRACIONES / "0001_init.sql").read_text(encoding="utf-8")
    m = re.search(rf"create table(?: if not exists)? (?:public\.)?{tabla}\s*\((.*?)\n\);", init, re.S | re.I)
    assert m, f"no encontré el create table {tabla} en la 0001"
    for linea in m.group(1).splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("--") or re.match(r"(primary|unique|constraint|check|foreign)\b", linea, re.I):
            continue
        cols.append(linea.split()[0].strip('",'))
    for f in sorted(MIGRACIONES.glob("*.sql")):
        sql = sin_comentarios_sql(f.read_text(encoding="utf-8"))
        for alt in re.finditer(rf"alter\s+table\s+(?:if exists\s+)?(?:only\s+)?(?:public\.)?{tabla}\b(.*?);", sql, re.S | re.I):
            cuerpo = alt.group(1)
            for add in re.finditer(r"\badd\s+column\s+(?:if not exists\s+)?(\w+)", cuerpo, re.I):
                if add.group(1) not in cols:
                    cols.append(add.group(1))
            for ren in re.finditer(r"\brename\s+(?:column\s+)?(\w+)\s+to\s+(\w+)", cuerpo, re.I):
                if ren.group(1) in cols:
                    cols.remove(ren.group(1))
                cols.append(ren.group(2))
            for drop in re.finditer(r"\bdrop\s+column\s+(?:if exists\s+)?(\w+)", cuerpo, re.I):
                if drop.group(1) in cols:
                    cols.remove(drop.group(1))
    return cols


@pytest.fixture(scope="module")
def pg0149():
    """`psql(sql, rol=None, check=True)` contra una base descartable con el estado de ANTES de la 0149."""
    contenedor = os.environ.get("URUKU_PG_TEST_CONTAINER")
    if not contenedor or not shutil.which("docker"):
        pytest.skip("sin Postgres de Docker (URUKU_PG_TEST_CONTAINER)")
    base = "t0149_" + uuid.uuid4().hex[:8]

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
        pub = columnas_de_tabla("publicaciones")
        assert "raw" in pub and "codigo_recibido" in pub and "ia_veredicto" in pub
        columnas_pub = ", ".join(
            f'"{c}" ' + {"id": "uuid primary key default gen_random_uuid()", "activo": "boolean not null default true",
                                                          "comercio_id": "uuid", "producto_ref_id": "uuid"}.get(c, "text")
            for c in pub)
        psql(f"""
            do $$ begin
              begin create role anon nologin; exception when duplicate_object then null; end;
              begin create role authenticated nologin; exception when duplicate_object then null; end;
              begin create role service_role nologin; exception when duplicate_object then null; end;
            end $$;
            alter role service_role bypassrls;            -- como el de Supabase: bypassa RLS
            grant usage on schema public to anon, authenticated, service_role;

            create table comercios (
              id uuid primary key default gen_random_uuid(), slug text, nombre text,
              activo boolean not null default true, codigo text, cargado_por text,
              created_at timestamptz not null default now());
            create unique index idx_comercios_codigo on comercios (codigo) where codigo is not null;
            grant select (id, slug, nombre, activo, created_at) on comercios to anon, authenticated;
            grant all on comercios to service_role;

            create table comercio_usuarios (
              id uuid primary key default gen_random_uuid(),
              comercio_id uuid not null references comercios(id),
              clave_hash text, activo boolean not null default true);
            alter table comercio_usuarios enable row level security;
            grant all on comercio_usuarios to service_role;

            create table publicaciones ({columnas_pub});
            -- Como la 0002: tabla entera para anon + la policy de aprobadas y activas.
            grant select on publicaciones to anon, authenticated;
            grant all on publicaciones to service_role;
            alter table publicaciones enable row level security;
            create policy publicaciones_public_read on publicaciones for select to anon, authenticated
              using (estado = 'aprobado' and activo);

            create view feed_publico as
              select p.id, p.tipo, p.titulo, p.descripcion, c.slug as comercio_slug
                from publicaciones p join comercios c on c.id = p.comercio_id and c.activo
               where p.estado = 'aprobado' and p.activo;
            grant select on feed_publico to anon, authenticated;

            -- Las funciones del panel nacen ejecutables por PUBLIC (0087/0089/0091).
            create function previsualizar_patron(p_patron text, p_rubro text default null)
              returns table (codigo text) language sql as $f$ select 'K7M2'::text $f$;
            create function rubros_a_revisar(p_estado text default 'dudosos', p_limite int default 100)
              returns table (codigo text) language sql as $f$ select 'K7M2'::text $f$;
            grant execute on function previsualizar_patron(text, text) to service_role;
            grant execute on function rubros_a_revisar(text, int) to service_role;
        """)
        yield psql
    finally:
        psql(f'drop database if exists "{base}" with (force)', db="postgres", check=False)
