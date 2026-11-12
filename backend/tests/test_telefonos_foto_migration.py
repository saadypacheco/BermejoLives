"""La migración 0184 (teléfonos en las fotos): idéntica en las dos carpetas, todo o nada, las tablas y las funciones
sólo para service_role, y el check de `cost_switches` ampliado con el nombre real que le dio la 0183."""
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
NOMBRE = "0184_telefonos_en_fotos.sql"


def _sql(carpeta: str) -> str:
    return (RAIZ / carpeta / NOMBRE).read_text(encoding="utf-8")


def _sin_comentarios(sql: str) -> str:
    return re.sub(r"--[^\n]*", "", sql)


def _normal(sql: str) -> str:
    return re.sub(r"\s+", " ", _sin_comentarios(sql))


def test_es_identica_en_las_dos_carpetas_y_el_numero_es_unico():
    assert _sql("supabase/migrations").replace("\r\n", "\n") == _sql("selfhost/postgres-init").replace("\r\n", "\n")
    for carpeta in ("supabase/migrations", "selfhost/postgres-init"):
        assert sorted(p.name for p in (RAIZ / carpeta).glob("0184_*.sql")) == [NOMBRE]


def test_todo_o_nada_idempotente_y_recarga_el_esquema():
    sql = _sin_comentarios(_sql("supabase/migrations"))
    assert sql.count("begin;") == 1 and sql.count("commit;") == 1 and sql.index("begin;") < sql.index("commit;")
    assert sql.rstrip().endswith("notify pgrst, 'reload schema';")
    assert not re.search(r"create table(?! if not exists)", sql)
    assert not re.search(r"create index(?! if not exists)", sql)
    assert "create or replace function" in sql
    assert "delete from" not in sql and "drop table" not in sql and "drop column" not in sql


def test_las_dos_tablas_son_las_de_la_spec():
    sql = _normal(_sql("supabase/migrations"))
    assert "create table if not exists public.fotos_escaneadas" in sql
    assert "motor text not null check (motor in ('tesseract', 'gemini', 'gemini-relevamiento'))" in sql
    assert "comercio_id uuid not null references public.comercios(id)" in sql
    assert "primary key (foto_url, motor)" in sql
    assert "create table if not exists public.telefonos_detectados" in sql
    assert "tipo text not null check (tipo in ('celular', 'fijo'))" in sql
    assert "texto_leido text not null check (length(texto_leido) <= 60)" in sql
    assert ("estado text not null default 'pendiente' check (estado in ('pendiente', 'coincide', "
            "'aplicado_whatsapp', 'aplicado_telefono', 'descartado'))") in sql
    assert "compartido boolean not null default false" in sql
    assert "activo boolean not null default true" in sql
    assert "unique (comercio_id, numero)" in sql


def test_rls_revoke_y_grant_explicitos_sin_nada_para_anon():
    sql = _normal(_sql("supabase/migrations"))
    for tabla in ("fotos_escaneadas", "telefonos_detectados"):
        assert f"alter table public.{tabla} enable row level security;" in sql
        assert f"revoke all on public.{tabla} from public, anon, authenticated;" in sql
        assert f"grant all on public.{tabla} to service_role;" in sql
    assert not re.search(r"grant [^;]*\bto (anon|authenticated|public)\b", sql)
    for funcion in ("portadas_sin_escanear(text, integer, uuid)", "telefonos_resumen(text, uuid)"):
        assert f"revoke all on function public.{funcion} from public, anon, authenticated;" in sql
        assert f"grant execute on function public.{funcion} to service_role;" in sql


def test_amplia_el_check_de_cost_switches_con_el_nombre_real():
    base = (RAIZ / "supabase/migrations/0183_content_requests_and_cost_switches.sql").read_text(encoding="utf-8")
    assert "key         text primary key check (key in ('gemini_content'))" in base      # el check de COLUMNA de la 0183
    sql = _normal(_sql("supabase/migrations"))
    assert "drop constraint if exists cost_switches_key_check" in sql
    assert "add constraint cost_switches_key_check check (key in ('gemini_content', 'gemini_phone_scan'))" in sql
    assert sql.index("drop constraint if exists cost_switches_key_check") < sql.index("add constraint cost_switches_key_check")


def test_el_check_coincide_con_el_catalogo_del_codigo():
    """La ÚLTIMA migración que toca el check (la 0195 sumó `gemini_tarjetas`) coincide con el catálogo; la 0184
    conserva el suyo, histórico, con las dos claves de entonces."""
    from app.services.cost_switches import CATALOGO
    sql = _normal((RAIZ / "supabase/migrations/0195_importados_tarjetas.sql").read_text(encoding="utf-8"))
    m = re.search(r"add constraint cost_switches_key_check check \(key in \(([^)]*)\)\)", sql)
    assert m
    assert sorted(re.findall(r"'([a-z_]+)'", m.group(1))) == sorted(CATALOGO)


def test_las_funciones_no_tocan_columnas_privadas_de_comercios():
    """`comercios` se lee por columnas (regla 11): las funciones sólo usan estas."""
    sql = _normal(_sql("supabase/migrations"))
    usadas = set(re.findall(r"\bc\.([a-z_]+)", sql))
    assert usadas <= {"id", "activo", "portada_url", "whatsapp", "telefono", "ciudad_id", "created_at"}


def test_comprueba_los_permisos_al_final():
    sql = _sin_comentarios(_sql("supabase/migrations"))
    assert "has_table_privilege" in sql and "has_function_privilege" in sql
    assert sql.index("do $chk$") < sql.index("commit;")
