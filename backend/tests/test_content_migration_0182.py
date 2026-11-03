"""La migración 0182 (textos del video v2): idéntica en las dos carpetas, todo o nada y sin permisos nuevos."""
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
NOMBRE = "0182_content_video_texts.sql"


def _sql(carpeta: str) -> str:
    return (RAIZ / carpeta / NOMBRE).read_text(encoding="utf-8")


def _sin_comentarios(sql: str) -> str:
    # Ni los comentarios de línea completa ni los del final de una línea (llevan `;` y cortarían los regex de abajo).
    return re.sub(r"--[^\n]*", "", sql)


def test_es_identica_en_las_dos_carpetas_y_el_numero_es_unico():
    assert _sql("supabase/migrations").replace("\r\n", "\n") == _sql("selfhost/postgres-init").replace("\r\n", "\n")
    for carpeta in ("supabase/migrations", "selfhost/postgres-init"):
        assert sorted(p.name for p in (RAIZ / carpeta).glob("0182_*.sql")) == [NOMBRE]


def test_todo_o_nada_idempotente_y_recarga_el_esquema():
    sql = _sin_comentarios(_sql("supabase/migrations"))
    assert sql.count("begin;") == 1 and sql.count("commit;") == 1 and sql.index("begin;") < sql.index("commit;")
    assert sql.rstrip().endswith("notify pgrst, 'reload schema';")
    assert not re.search(r"add column(?! if not exists)", sql)
    assert "delete from" not in sql and "drop " not in sql


def test_agrega_las_columnas_del_contrato():
    sql = _sin_comentarios(_sql("supabase/migrations"))
    pieces = re.search(r"alter table public\.content_pieces(.*?);", sql, re.S).group(1)
    sources = re.search(r"alter table public\.content_piece_sources(.*?);", sql, re.S).group(1)
    for col in ("video_texts", "video_texts_engine", "video_texts_checks", "photo_flags_ok"):
        assert col in pieces, col
    for col in ("chip_text", "photo_flags", "focus_y"):
        assert col in sources, col
    assert "default false" in pieces and "default '[]'::jsonb" in pieces and "default '{}'" in sources


def test_sin_grants_nuevos_las_columnas_nacen_privadas():
    """La 0181 dejó las dos tablas sólo para service_role, a nivel de tabla: la columna nueva lo hereda."""
    sql = _sin_comentarios(_sql("supabase/migrations"))
    assert not re.search(r"\bgrant\b|\brevoke\b", sql, re.I)
    base = _sin_comentarios((RAIZ / "supabase/migrations/0181_content_and_subscribers.sql").read_text(encoding="utf-8"))
    assert "revoke all on" in base and "public.content_pieces" in base and "public.content_piece_sources" in base
    assert not re.search(r"grant select \(", base, re.I)                       # sin grants por columna en la 0181
    assert "has_column_privilege" in sql                                         # y la 0182 lo comprueba


def test_no_toca_comercios_ni_nombra_el_codigo():
    sql = _sin_comentarios(_sql("supabase/migrations"))
    assert not re.search(r"alter table (public\.)?comercios\b", sql) and not re.search(r"\bcodigo\b", sql)
