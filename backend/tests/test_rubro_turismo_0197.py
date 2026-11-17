"""Migración 0197: el rubro comercial `turismo` que sugiere el importador de la página de turismo."""
import re
from pathlib import Path

from app.services.importar_turismo import RUBRO_TURISMO

RAIZ = Path(__file__).resolve().parents[2]
SQL = RAIZ / "supabase" / "migrations" / "0197_rubro_turismo.sql"
COPIA = RAIZ / "selfhost" / "postgres-init" / "0197_rubro_turismo.sql"


def test_copias_identicas():
    assert SQL.read_bytes() == COPIA.read_bytes()


def test_crea_el_rubro_que_sugiere_el_importador_como_negocio():
    sql = SQL.read_text(encoding="utf-8")
    m = re.search(r"values \('(?P<slug>[a-z-]+)', 'Turismo', null, \d+, (?P<comercial>true|false)\)", sql)
    assert m and m.group("slug") == RUBRO_TURISMO
    assert m.group("comercial") == "true"
    assert "on conflict (slug) do update" in sql


def test_palabras_solo_compuestas():
    sql = SQL.read_text(encoding="utf-8")
    marca = r"('turismo', '\m("
    inicio = sql.index(marca) + len(marca)
    patron = sql[inicio:sql.index(")')", inicio)]
    alternativas = patron.split("|")
    assert "agencia de viajes" in alternativas and "guia de turismo" in alternativas
    # «turismo» o «viaje» solos clasificarían mal hoteles y bolsos de viaje.
    assert all(" " in a for a in alternativas)
    assert patron == patron.lower() and not re.search(r"[áéíóú]", patron)


def test_sin_borrado_fisico():
    sql = SQL.read_text(encoding="utf-8").lower()
    assert "delete from" not in sql and "truncate" not in sql and "drop " not in sql
