"""Migración 0180: city_category_pages() (docs/visibilidad-buscadores-ia.md §3.2).

No hay un Postgres en la suite: se revisa el SQL como texto (igual que las demás
pruebas de migraciones del repo).
"""
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
NOMBRE = "0180_city_category_pages.sql"


def _sql(carpeta: str) -> str:
    return (RAIZ / carpeta / NOMBRE).read_text(encoding="utf-8")


def _sin_comentarios(sql: str) -> str:
    return "\n".join(re.sub(r"--.*$", "", linea) for linea in sql.splitlines())


def _columnas(sql: str) -> list[tuple[str, str]]:
    """(nombre, tipo) de cada columna del `returns table (...)`."""
    m = re.search(r"returns table \((.*?)\)\s*language", _sin_comentarios(sql), re.S | re.I)
    assert m, "no encontré el returns table"
    cols = []
    for trozo in m.group(1).split(","):
        if trozo.strip():
            nombre, tipo = trozo.split(None, 1)
            cols.append((nombre, tipo.strip().lower()))
    return cols


def test_espejada_en_supabase_y_selfhost_y_el_numero_no_choca():
    assert _sql("supabase/migrations") == _sql("selfhost/postgres-init")
    for carpeta in ("supabase/migrations", "selfhost/postgres-init"):
        nums = [p.name[:4] for p in (RAIZ / carpeta).glob("*.sql")]
        assert nums.count("0180") == 1


def test_es_security_invoker_con_search_path_fijo_y_grant_a_anon():
    sql = _sin_comentarios(_sql("supabase/migrations")).lower()
    assert "security invoker" in sql and "security definer" not in sql
    assert "set search_path = public" in sql
    assert re.search(r"grant\s+execute on function public\.city_category_pages\(\)\s+to anon", sql)
    assert "notify pgrst, 'reload schema'" in sql


def test_devuelve_exactamente_las_columnas_del_contrato():
    assert _columnas(_sql("supabase/migrations")) == [
        ("city_slug", "text"), ("city_name", "text"), ("region", "text"),
        ("category_slug", "text"), ("category_name", "text"),
        ("indexable", "boolean"), ("last_modified", "timestamptz"),
    ]


def test_no_devuelve_ninguna_columna_de_conteo():
    for nombre, tipo in _columnas(_sql("supabase/migrations")):
        assert nombre not in {"count", "n", "total", "cantidad"}
        assert tipo in {"text", "boolean", "timestamptz"}, f"{nombre}: {tipo}"


def test_filtros_de_la_regla_de_negocio():
    sql = _sin_comentarios(_sql("supabase/migrations")).lower()
    assert "ci.activa" in sql                                   # ciudades activas
    assert "ru.activo" in sql and "ru.slug <> 'otros'" in sql   # rubros activos, sin «otros»
    assert "c.activo" in sql and "not coalesce(c.suspendido, false)" in sql
    assert "comercio_rubros" in sql                             # N:M (incluye el principal)
    assert "having count(distinct c.id) >= 1" in sql
    assert ">= 5" in sql                                        # umbral de indexable
    # regla «fino» de §3.1
    for pedazo in ("'otros'", "subcategoria", "descripcion", "prod_obs_human",
                   "prod_det_ia", "a clasificar"):
        assert pedazo in sql


def test_sin_borrado_fisico_ni_columnas_privadas_de_comercios():
    sql = _sin_comentarios(_sql("supabase/migrations")).lower()
    assert "delete from" not in sql
    for privada in ("plan_cortesia", "paga_hasta", "cargado_por", "capturado_en",
                    "fotos_extra", "wa_jid", "rubro_revisado_por"):
        assert privada not in sql
