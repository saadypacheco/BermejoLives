"""Migración 0194 (enmascarar las búsquedas ya guardadas): el SQL aplica LA MISMA regla que el backend.

No hay Postgres en los tests normales, así que acá se comprueba lo que se puede sin él:
- la migración es idéntica en `supabase/migrations/` y `selfhost/postgres-init/`, con número único, sin DELETE, sin
  DROP y con UPDATE sólo de las filas que cambian (idempotente);
- las dos expresiones regulares del SQL son EXACTAMENTE `PATRON_MAIL` y `PATRON_DIGITOS` de `core/text.py`;
- ejecutando en Python, en el mismo orden, los `regexp_replace` que están en el SQL, el resultado es igual a
  `enmascarar_busqueda` para un corpus de entradas (teléfonos con separadores, mails, variantes, basura).
"""
import re
from pathlib import Path

import pytest

from app.core import text
from app.services import site_metrics

RAIZ = Path(__file__).resolve().parents[2]
NOMBRE = "0194_busquedas_enmascarar.sql"


def _sql(carpeta="supabase/migrations") -> str:
    return (RAIZ / carpeta / NOMBRE).read_text(encoding="utf-8").replace("\r\n", "\n")


def _sin_comentarios(sql: str) -> str:
    return re.sub(r"--[^\n]*", "", sql)


def _reemplazos_del_sql() -> list[tuple[str, str, str]]:
    """Los `regexp_replace(x, 'patron', 'reemplazo', 'flags')` del UPDATE, en el orden en que se aplican (de adentro
    hacia afuera: es el orden en que aparecen sus argumentos de texto)."""
    sql = _sin_comentarios(_sql())
    cuerpo = sql[sql.index("update public.busquedas"):sql.index("comercio_origins")]
    return re.findall(r"'((?:[^']|'')*)',\s*'((?:[^']|'')*)',\s*'([gi]+)'", cuerpo)


def test_la_migracion_es_identica_en_las_dos_carpetas_y_tiene_numero_unico():
    assert _sql("supabase/migrations") == _sql("selfhost/postgres-init")
    for carpeta in ("supabase/migrations", "selfhost/postgres-init"):
        assert sorted(p.name for p in (RAIZ / carpeta).glob("0194_*.sql")) == [NOMBRE]


def test_es_un_update_idempotente_nunca_un_delete():
    sql = _sin_comentarios(_sql()).lower()
    assert "delete" not in sql and "drop " not in sql and "truncate" not in sql
    assert "update public.busquedas" in sql and "is distinct from" in sql
    assert sql.count("begin;") == 1 and sql.count("commit;") == 1
    assert "grant execute on function public.comercio_origins(uuid, date) to service_role" in re.sub(r"\s+", " ", sql)
    assert "anon" in sql and "revoke execute" in sql                      # los permisos de la función no se abren


def test_las_regex_del_sql_son_las_del_backend():
    reemplazos = _reemplazos_del_sql()
    assert [(r, f) for _p, r, f in reemplazos] == [(" ", "g"), ("[mail]", "gi"), ("#", "g")]
    espacios, mail, digitos = (p for p, _r, _f in reemplazos)
    assert espacios == r"\s+"
    assert mail == text.PATRON_MAIL
    assert digitos == text.PATRON_DIGITOS


def _como_el_sql(q: str) -> str:
    """Los mismos pasos que el UPDATE, con `re` de Python: juntar espacios → mails (sin distinguir mayúsculas) →
    dígitos → `btrim` (espacios) → `left(…, 100)`."""
    for patron, reemplazo, flags in _reemplazos_del_sql():
        q = re.sub(patron, reemplazo, q, flags=re.IGNORECASE if "i" in flags else 0)
    return q.strip(" ")[:100]


CORPUS = [
    "", "zapatos", "71234567 zapatos", "zapatos 71234567", "+591 712-34567", "+591 712-34567 pan", "(591) 71.234.567",
    "71 23 45 67", "llamame al 71 23 45 67 gracias", "tel 712 34", "tel 712 345", "talle 38 y 40", "12345", "123456", "1234567890123",
    "juan.perez@gmail.com", "escribime a juan.perez@gmail.com por favor", "JUAN@GMAIL.COM", "juan (at) gmail (dot) com",
    "juan [at] gmail [dot] com", "juan @ gmail . com", "juan(at)gmail.com", "juan AT gmail dot com", "a@b.co 71234567 c@d.org",
    "  mucho    espacio  ", "tab\tsalto\nlinea 71234567", "a" * 150, "1 " * 80, "x@y.com " * 20, "ñandú 71234567 café",
    "pan 2x1 y 6 de leche", "5917 1234567", "$ 1.500.000 casa", "(at)", "@", "a@", "@b.com", "a@b", "a@b.c.d.e",
]


@pytest.mark.parametrize("entrada", CORPUS)
def test_el_sql_y_el_backend_enmascaran_igual(entrada):
    assert _como_el_sql(entrada) == site_metrics.enmascarar_busqueda(entrada)


def test_el_enmascarado_es_idempotente():
    """Correr la migración dos veces (o enmascarar algo ya enmascarado) no cambia nada."""
    for entrada in CORPUS:
        uno = site_metrics.enmascarar_busqueda(entrada)
        assert site_metrics.enmascarar_busqueda(uno) == uno
