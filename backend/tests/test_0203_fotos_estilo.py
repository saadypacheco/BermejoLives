"""La migración 0203 (fotos con estilo URUKU, docs/fotos-estilo-uruku.md §4): pruebas ESTÁTICAS sobre el SQL.

Idéntica en las dos carpetas, en transacción, idempotente, sin borrado físico; `comercio_fotos` por columnas (tres nuevas:
dos públicas y una privada); `photo_style_uses` sólo insert; el interruptor `gemini_fotos` en el check y nacido apagado; y una
comprobación final que hace fallar la migración si algo quedó mal.

(No hay Postgres en este entorno de pruebas: lo que se prueba acá es el texto. La corrida real, dos veces, es parte del
«terminado» de la spec y se hace en QA: `psql -f` dos veces sobre una base con las migraciones anteriores.)
"""
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
NOMBRE = "0203_fotos_estilo_uruku.sql"
PUBLICAS = ["id", "comercio_id", "url", "thumb_url", "orden", "created_at", "diseno_url", "diseno_thumb_url"]
PRIVADAS = ["diseno_propuesta_url"]


def _sql(carpeta: str = "supabase/migrations") -> str:
    return (RAIZ / carpeta / NOMBRE).read_text(encoding="utf-8")


def _sin_comentarios(sql: str) -> str:
    return re.sub(r"--[^\n]*", "", sql)


def _normal(sql: str = "") -> str:
    return re.sub(r"\s+", " ", _sin_comentarios(sql or _sql())).lower()


def _fuera_del_chequeo(sql: str) -> str:
    """El SQL sin el bloque `do $chk$ ... $chk$` (la comprobación nombra privilegios que NO tiene que haber)."""
    return re.sub(r"do \$chk\$.*?\$chk\$;", "", sql, flags=re.S)


def _bloque_chk() -> str:
    m = re.search(r"do \$chk\$(.*?)\$chk\$;", _normal(), re.S)
    assert m, "la 0203 tiene que terminar con un bloque do $chk$"
    return m.group(1)


# ══════════════════════════════════════════ forma

def test_las_dos_copias_son_identicas_y_el_numero_es_unico():
    a = (RAIZ / "supabase/migrations" / NOMBRE).read_bytes()
    b = (RAIZ / "selfhost/postgres-init" / NOMBRE).read_bytes()
    assert a == b and a
    for carpeta in ("supabase/migrations", "selfhost/postgres-init"):
        assert sorted(p.name for p in (RAIZ / carpeta).glob("0203_*.sql")) == [NOMBRE]


def test_es_la_siguiente_a_la_0202():
    nombres = sorted(p.name for p in (RAIZ / "supabase/migrations").glob("02*.sql"))
    assert nombres[nombres.index(NOMBRE) - 1].startswith("0202_")


def test_en_transaccion_y_recarga_el_esquema_de_postgrest():
    sql = _sin_comentarios(_sql())
    assert sql.count("begin;") == 1 and sql.count("commit;") == 1 and sql.index("begin;") < sql.index("commit;")
    assert sql.rstrip().endswith("notify pgrst, 'reload schema';")
    assert sql.index("commit;") < sql.index("notify pgrst")


def test_es_idempotente():
    sql = _normal()
    assert not re.search(r"create table(?! if not exists)", sql)
    assert not re.search(r"add column(?! if not exists)", sql)
    assert not re.search(r"create index(?! if not exists)", sql)
    assert "drop constraint if exists cost_switches_key_check" in sql
    assert "on conflict (key) do nothing" in sql
    assert re.findall(r"add column if not exists (\w+) text", sql) == ["diseno_url", "diseno_thumb_url", "diseno_propuesta_url"]


def test_sin_borrado_fisico():
    fuera = _fuera_del_chequeo(_normal())
    assert "delete from" not in fuera and "truncate" not in fuera
    assert "drop table" not in fuera and "drop column" not in fuera
    assert re.findall(r"\bdrop \w+", fuera) == ["drop constraint"]          # sólo el check de cost_switches


# ══════════════════════════════════════════ comercio_fotos: por columnas

def test_revoke_de_tabla_y_grant_por_columna_en_ese_orden():
    sql = _fuera_del_chequeo(_normal())
    assert "revoke select on public.comercio_fotos from anon, authenticated;" in sql
    m = re.search(r"grant select \(([^)]*)\) on public\.comercio_fotos to anon, authenticated;", sql)
    assert m, "falta el grant select (columnas)"
    assert [c.strip() for c in m.group(1).split(",")] == PUBLICAS
    # el revoke de tabla borra también los grants por columna: tiene que ir ANTES
    assert sql.index("revoke select on public.comercio_fotos") < sql.index("grant select (")
    assert "grant all on public.comercio_fotos to service_role;" in sql
    assert not re.search(r"grant\s+select\s+on\s+(public\.)?comercio_fotos", sql)       # nunca la tabla entera


def test_la_propuesta_es_privada_y_no_figura_en_ningun_grant():
    fuera = _fuera_del_chequeo(_normal())
    for g in re.findall(r"grant[^;]*;", fuera):
        for privada in PRIVADAS:
            assert privada not in g, g
    assert "add column if not exists diseno_propuesta_url text" in fuera


def test_las_publicas_del_grant_son_todas_las_columnas_de_comercio_fotos_menos_la_privada():
    """Las columnas de `comercio_fotos` según las migraciones (0030 + las que sumen) = públicas + privadas. Si alguien
    agrega una, esto (y la comprobación final de la migración) obligan a decidir si es pública o privada."""
    sql0030 = _sin_comentarios((RAIZ / "supabase/migrations/0030_galeria_comercio.sql").read_text(encoding="utf-8"))
    cuerpo = re.search(r"create table if not exists comercio_fotos \((.*?)\n\);", sql0030, re.S).group(1)
    cols = [ln.strip().split()[0] for ln in cuerpo.splitlines() if ln.strip()]
    for f in sorted((RAIZ / "supabase/migrations").glob("*.sql")):
        sql = _sin_comentarios(f.read_text(encoding="utf-8"))
        for alt in re.finditer(r"alter\s+table\s+(?:if exists\s+)?(?:public\.)?comercio_fotos\b(.*?);", sql, re.S | re.I):
            cols += re.findall(r"\badd\s+column\s+(?:if not exists\s+)?(\w+)", alt.group(1), re.I)
    assert sorted(cols) == sorted(PUBLICAS + PRIVADAS)


def test_la_comprobacion_final_cubre_los_privilegios_de_comercio_fotos():
    chk = _bloque_chk()
    assert "has_table_privilege(v_rol, 'public.comercio_fotos', 'select')" in chk               # sin select de tabla
    assert "has_column_privilege(v_rol, 'public.comercio_fotos', v_col, 'select')" in chk
    assert "array['id', 'comercio_id', 'url', 'thumb_url', 'orden', 'created_at', 'diseno_url', 'diseno_thumb_url']" in chk
    assert "array['diseno_propuesta_url']" in chk
    # toda columna decidida: si aparece una nueva, la migración falla
    assert "information_schema.columns" in chk and "table_name = 'comercio_fotos'" in chk
    assert "no está decidida" in chk
    # RLS prendida y anon ve exactamente las fotos de los comercios activos
    assert "relrowsecurity" in chk and "comercio_fotos sin rls" in chk
    assert "set local role anon" in chk and "select count(id) into v_visible from public.comercio_fotos" in chk
    assert "join public.comercios c on c.id = f.comercio_id and c.activo" in chk
    assert "has_table_privilege('service_role', 'public.comercio_fotos', 'update')" in chk


# ══════════════════════════════════════════ photo_style_uses

def test_photo_style_uses_columnas_y_checks_de_la_spec():
    sql = _normal()
    m = re.search(r"create table if not exists public\.photo_style_uses \((.*?)\); comment on table", sql)
    assert m
    cuerpo = m.group(1)
    for trozo in ("id uuid primary key default gen_random_uuid()", "comercio_id uuid not null references public.comercios(id)",
                  "foto_id uuid,", "target text not null check (target in ('cover', 'gallery'))",
                  "method text not null check (method in ('free', 'gemini', 'external'))", "model text,", "prompt_version text,",
                  "cost_usd numeric(8, 4) not null default 0", "result text not null check (result in ('ok', 'error', 'timeout'))",
                  "error text,", "result_url text,", "actor text not null", "created_at timestamptz not null default now()"):
        assert trozo in cuerpo, trozo
    assert "foto_id uuid references" not in cuerpo                                    # sin FK: comercio_fotos borra físico
    assert "create index if not exists idx_photo_style_uses_dia on public.photo_style_uses (method, created_at);" in sql
    assert "create index if not exists idx_photo_style_uses_comercio on public.photo_style_uses (comercio_id, created_at);" in sql


def test_photo_style_uses_rls_y_solo_select_e_insert_para_service_role():
    sql = _fuera_del_chequeo(_normal())
    assert "alter table public.photo_style_uses enable row level security;" in sql
    assert "revoke all on public.photo_style_uses from public, anon, authenticated;" in sql
    assert "revoke all on public.photo_style_uses from service_role;" in sql
    assert "grant select, insert on public.photo_style_uses to service_role;" in sql
    # el revoke general va antes del grant mínimo
    assert sql.index("revoke all on public.photo_style_uses from service_role") < sql.index("grant select, insert on public.photo_style_uses")
    grants = [g for g in re.findall(r"grant[^;]*;", sql) if "photo_style_uses" in g]
    assert grants == ["grant select, insert on public.photo_style_uses to service_role;"]     # sin update, delete ni all


def test_la_comprobacion_exige_que_photo_style_uses_sea_solo_insert():
    chk = _bloque_chk()
    for priv in ("select", "insert", "update", "delete"):
        assert f"has_table_privilege(v_rol, 'public.photo_style_uses', '{priv}')" in chk     # anon y authenticated: nada
    assert "photo_style_uses sin rls" in chk
    assert "has_table_privilege('service_role', 'public.photo_style_uses', 'select')" in chk
    assert "has_table_privilege('service_role', 'public.photo_style_uses', 'insert')" in chk
    for priv in ("update", "delete", "truncate"):
        assert f"has_table_privilege('service_role', 'public.photo_style_uses', '{priv}')" in chk
    assert "es sólo insert" in chk


def test_no_hay_ningun_delete_ni_update_sobre_el_registro_en_el_codigo():
    """El registro de costos es historia: el backend sólo inserta y lee (la base no le da más)."""
    repo = (RAIZ / "backend/app/db/repository.py").read_text(encoding="utf-8")
    trozos = re.findall(r'table\("photo_style_uses"\)\.(\w+)', repo)
    assert trozos and set(trozos) <= {"insert", "select"}


# ══════════════════════════════════════════ el interruptor

def test_el_check_de_cost_switches_coincide_con_el_catalogo_y_el_interruptor_nace_apagado():
    from app.services.cost_switches import CATALOGO
    sql = _normal()
    m = re.search(r"add constraint cost_switches_key_check check \(key in \(([^)]*)\)\)", sql)
    assert m and sorted(re.findall(r"'([a-z_]+)'", m.group(1))) == sorted(CATALOGO)
    assert "gemini_fotos" in CATALOGO
    assert "insert into public.cost_switches (key, enabled, updated_by) values ('gemini_fotos', false, 'migracion 0203') on conflict (key) do nothing;" in sql
    assert sql.index("drop constraint if exists cost_switches_key_check") < sql.index("add constraint cost_switches_key_check")


def test_la_comprobacion_cubre_el_check_y_la_fila_pero_no_exige_apagado_para_poder_correrse_de_nuevo():
    chk = _bloque_chk()
    assert "conname = 'cost_switches_key_check'" in chk and "like '%gemini_fotos%'" in chk
    assert "where key = 'gemini_fotos'" in chk
    # Si el dueño ya lo prendió, volver a correr la migración no puede fallar: nace apagada por el insert, no por la comprobación.
    assert "and enabled" not in chk


def test_el_interruptor_de_la_api_es_el_mismo_que_el_de_la_migracion_y_el_default_es_apagado(crepo):
    from app.services import cost_switches
    assert cost_switches.GEMINI_FOTOS == "gemini_fotos"
    c = cost_switches.CATALOGO["gemini_fotos"]
    assert c["label"] == "Fotos con IA (Gemini)"
    assert c["cost"] == "aprox. US$ 0,03-0,04 por imagen, tope 20 por día, sin nivel gratis"
    assert c["off_means"] == "quedan la plantilla gratis y ChatGPT a mano"
    assert cost_switches.esta_prendido(crepo, "gemini_fotos") is False                  # sin fila = apagado


def test_la_0203_no_aparece_en_ninguna_lista_de_columnas_de_comercios():
    """Es de `comercio_fotos`: no toca `comercios` (su lista pública es la de la 0145, regla 11)."""
    sql = _normal()
    assert not re.search(r"alter table public\.comercios\b", sql)
    assert "grant select (" in sql and sql.count("grant select (") == 1
