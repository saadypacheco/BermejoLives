"""Migración 0199: el rubro NO comercial `aduana` de las oficinas que trae importar_aduana."""
import re
from pathlib import Path

from app.services.importar_aduana import RUBRO

RAIZ = Path(__file__).resolve().parents[2]
SQL = RAIZ / "supabase" / "migrations" / "0199_rubro_aduana.sql"
COPIA = RAIZ / "selfhost" / "postgres-init" / "0199_rubro_aduana.sql"


def test_copias_identicas():
    assert SQL.read_bytes() == COPIA.read_bytes()


def test_crea_el_rubro_del_importador_como_servicio_publico():
    sql = SQL.read_text(encoding="utf-8")
    m = re.search(r"values \('(?P<slug>[a-z-]+)', 'Aduana', null, \d+, (?P<comercial>true|false)\)", sql)
    assert m and m.group("slug") == RUBRO
    assert m.group("comercial") == "false"
    assert "on conflict (slug) do update" in sql and "comercial = false" in sql


def test_palabras_solo_compuestas():
    sql = SQL.read_text(encoding="utf-8")
    marca = r"('aduana', '\m("
    inicio = sql.index(marca) + len(marca)
    patron = sql[inicio:sql.index(")')", inicio)]
    alternativas = patron.split("|")
    assert "aduana nacional" in alternativas and "aduana frontera" in alternativas
    # «aduana» sola pasaría a los despachantes y agencias de aduana (negocios) a un rubro sin WhatsApp.
    assert all(" " in a for a in alternativas)
    assert patron == patron.lower() and not re.search(r"[áéíóú]", patron)


def test_sin_borrado_fisico():
    sql = SQL.read_text(encoding="utf-8").lower()
    assert "delete from" not in sql and "truncate" not in sql and "drop " not in sql
