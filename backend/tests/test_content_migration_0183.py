"""La migración 0183 (pedidos a mano e interruptores de costo): idéntica en las dos carpetas, todo o nada, la
tabla nueva sólo para service_role y los checks de la 0181 reemplazados con el nombre real."""
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
NOMBRE = "0183_content_requests_and_cost_switches.sql"


def _sql(carpeta: str) -> str:
    return (RAIZ / carpeta / NOMBRE).read_text(encoding="utf-8")


def _sin_comentarios(sql: str) -> str:
    # Ni los comentarios de línea completa ni los del final de una línea (llevan `;` y cortarían los regex de abajo).
    return re.sub(r"--[^\n]*", "", sql)


def _normal(sql: str) -> str:
    return re.sub(r"\s+", " ", _sin_comentarios(sql))


def test_es_identica_en_las_dos_carpetas_y_el_numero_es_unico():
    assert _sql("supabase/migrations").replace("\r\n", "\n") == _sql("selfhost/postgres-init").replace("\r\n", "\n")
    for carpeta in ("supabase/migrations", "selfhost/postgres-init"):
        assert sorted(p.name for p in (RAIZ / carpeta).glob("0183_*.sql")) == [NOMBRE]


def test_todo_o_nada_idempotente_y_recarga_el_esquema():
    sql = _sin_comentarios(_sql("supabase/migrations"))
    assert sql.count("begin;") == 1 and sql.count("commit;") == 1 and sql.index("begin;") < sql.index("commit;")
    assert sql.rstrip().endswith("notify pgrst, 'reload schema';")
    assert not re.search(r"create table(?! if not exists)", sql)
    assert not re.search(r"add column(?! if not exists)", sql)
    assert not re.search(r"create index(?! if not exists)(?! uq_content_pieces_slot)", sql)
    assert "delete from" not in sql and "drop table" not in sql and "drop column" not in sql


def test_cost_switches_rls_revoke_y_grant_explicitos_como_la_0181():
    sql = _normal(_sql("supabase/migrations"))
    assert "create table if not exists public.cost_switches" in sql
    assert "key text primary key check (key in ('gemini_content'))" in sql
    assert "enabled boolean not null default false" in sql
    assert "updated_by text not null" in sql and "updated_at timestamptz not null default now()" in sql
    assert "alter table public.cost_switches enable row level security;" in sql
    assert "revoke all on public.cost_switches from public, anon, authenticated;" in sql
    assert "grant all on public.cost_switches to service_role;" in sql
    assert not re.search(r"grant [^;]*\bto (anon|authenticated|public)\b", sql)


def test_columnas_origin_y_rubro_id_en_content_pieces():
    sql = _normal(_sql("supabase/migrations"))
    assert "add column if not exists origin text not null default 'selector'" in sql
    assert "add column if not exists rubro_id uuid references public.rubros(id)" in sql
    assert "check (origin in ('selector', 'pedido'))" in sql


def test_reemplaza_el_check_del_pilar_por_su_nombre_real_y_exige_rubro_y_ciudad():
    """El check de columna de la 0181 (`pillar text ... check (pillar in (...))`) se llama `<tabla>_<columna>_check`."""
    base = (RAIZ / "supabase/migrations/0181_content_and_subscribers.sql").read_text(encoding="utf-8")
    assert re.search(r"pillar\s+text not null check \(pillar in \('comercio_del_dia', 'ofertas'\)\)", base)
    sql = _normal(_sql("supabase/migrations"))
    assert "drop constraint if exists content_pieces_pillar_check" in sql
    assert "add constraint content_pieces_pillar_check check (pillar in ('comercio_del_dia', 'ofertas', 'rubro'))" in sql
    assert "check (pillar <> 'rubro' or (rubro_id is not null and ciudad_id is not null))" in sql
    assert sql.index("drop constraint if exists content_pieces_pillar_check") < sql.index("add constraint content_pieces_pillar_check")


def test_el_lugar_del_calendario_pasa_a_valer_solo_para_el_selector():
    sql = _normal(_sql("supabase/migrations"))
    assert "drop index if exists public.uq_content_pieces_slot;" in sql
    assert re.search(r"create unique index uq_content_pieces_slot on public\.content_pieces \(scheduled_for, pillar\) "
                     r"where activo and origin = 'selector' and status not in \('skipped', 'failed'\);", sql)
    assert sql.index("drop index if exists public.uq_content_pieces_slot") < sql.index("create unique index uq_content_pieces_slot")


def test_sin_grants_por_columna_y_comprueba_los_permisos():
    """Las columnas nuevas de content_pieces heredan el permiso de la tabla (sólo service_role): nacen privadas."""
    sql = _sin_comentarios(_sql("supabase/migrations"))
    assert not re.search(r"grant select \(", sql, re.I)
    assert "has_column_privilege" in sql and "has_table_privilege" in sql


def test_no_toca_comercios_ni_nombra_el_codigo():
    sql = _sin_comentarios(_sql("supabase/migrations"))
    assert not re.search(r"alter table (public\.)?comercios\b", sql) and not re.search(r"\bcodigo\b", sql)
