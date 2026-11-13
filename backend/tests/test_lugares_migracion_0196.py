"""Migración 0196 (docs/lugares-turismo.md): el rubro `para-visitar`, `fuente_url` pública y la sala de espera.

Pruebas estáticas sobre el archivo (como las de la 0145/0195). El efecto en Postgres lo comprueba el bloque `do $chk$`
de la propia migración al aplicarla (si algo queda mal, no se aplica nada).
"""
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ARCHIVO = "0196_lugares_para_visitar.sql"


def _sql(carpeta="supabase/migrations") -> str:
    return (RAIZ / carpeta / ARCHIVO).read_text(encoding="utf-8")


def _sin_comentarios(sql: str) -> str:
    return "\n".join(l for l in sql.splitlines() if not l.lstrip().startswith("--"))


def test_esta_igual_en_supabase_y_en_selfhost():
    a = (RAIZ / "supabase/migrations" / ARCHIVO).read_bytes()
    b = (RAIZ / "selfhost/postgres-init" / ARCHIVO).read_bytes()
    assert a == b and a


def test_es_la_siguiente_a_la_0195():
    nombres = sorted(p.name for p in (RAIZ / "supabase/migrations").glob("0*.sql"))
    assert nombres.index(ARCHIVO) == nombres.index("0195_importados_tarjetas.sql") + 1


def test_crea_el_rubro_no_comercial_sin_emoji_y_lo_deja_activo():
    sql = _sin_comentarios(_sql())
    m = re.search(r"insert into public\.rubros \(slug, nombre, icono, orden, comercial\)\s+values \((.*?)\)\s+on conflict",
                  sql, re.S)
    assert m, "no inserta el rubro"
    assert re.fullmatch(r"'para-visitar', 'Para visitar', null, 62, false", m.group(1).strip())
    assert "on conflict (slug) do update set nombre = excluded.nombre, comercial = false, activo = true;" in sql
    assert not re.search(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", _sql()), "sin emojis"


def test_las_palabras_son_solo_las_inequivocas():
    sql = _sin_comentarios(_sql())
    m = re.search(r"insert into public\.rubro_palabras \(rubro_slug, patron\) values\s+\('para-visitar', '(.*?)'\)\s+"
                  r"on conflict \(rubro_slug, patron\) do nothing;", sql, re.S)
    assert m, "no inserta las palabras (con la constraint única de la 0045)"
    patron = m.group(1)
    for palabra in ("area protegida", "reserva biologica", "parque nacional"):
        assert palabra in patron
    # «plaza», «parque» e «iglesia» a secas clasificarían mal a «Comercial Plaza» o «Parque Industrial»
    alternativas = set(re.search(r"\\m\((.*)\)", patron).group(1).split("|"))
    assert not alternativas & {"plaza", "parque", "iglesia"}
    # «museo», «mirador», «centro cultural»: nombres de hoteles y restaurantes («Hotel El Mirador»)
    assert not alternativas & {"museo", "mirador", "centro cultural"}
    assert patron == patron.lower()                      # las palabras van en minúsculas y sin acentos
    assert not re.search(r"[áéíóúñ]", patron)


def test_fuente_url_es_publica_por_columna_y_nunca_por_tabla():
    sql = _sin_comentarios(_sql())
    assert "alter table public.comercios add column if not exists fuente_url text;" in sql
    assert "grant select (fuente_url) on public.comercios to anon, authenticated;" in sql
    assert not re.search(r"grant\s+select\s+on\s+(public\.)?comercios\s+to\s+[^;]*anon", sql, re.I)


def test_la_sala_de_espera_sigue_privada():
    sql = _sin_comentarios(_sql())
    assert "alter table public.comercios_importados add column if not exists subcategoria text;" in sql
    assert "alter table public.comercios_importados add column if not exists fuente_url   text;" in sql
    assert "revoke all on public.comercios_importados from public, anon, authenticated;" in sql
    assert "grant all on public.comercios_importados to service_role;" in sql
    assert not re.search(r"grant[^;]*comercios_importados[^;]*\b(anon|authenticated)\b", sql, re.I)


def test_es_una_transaccion_con_comprobacion_y_recarga_postgrest():
    sql = _sin_comentarios(_sql())
    assert "begin;" in sql and "commit;" in sql and sql.index("begin;") < sql.index("do $chk$") < sql.index("commit;")
    assert sql.rstrip().endswith("notify pgrst, 'reload schema';")
    chk = sql[sql.index("do $chk$"):sql.rindex("$chk$;")]
    assert "has_column_privilege(v_rol, 'public.comercios', 'fuente_url', 'select')" in chk
    assert "has_any_column_privilege(v_rol, 'public.comercios_importados', 'select')" in chk
    assert "comercial = false" in chk
    assert chk.count("raise exception") >= 4


def test_es_idempotente_y_sin_borrado_fisico():
    sql = _sin_comentarios(_sql()).lower()
    assert not re.search(r"create table(?! if not exists)", sql)
    assert not re.search(r"\bdelete\b|\btruncate\b|\bdrop\s+(table|column)\b", sql)
    assert all("if not exists" in l for l in sql.splitlines() if "add column" in l)
