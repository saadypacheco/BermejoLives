"""El diccionario de rubros no repite palabras.

Apareció mirando el panel: "artículo de limpieza" se veía dos veces. Buscándolo
en serio salieron siete términos repetidos dentro del mismo rubro —incluido un
`licoreria|licoreria` en el mismo patrón— y, peor, seis que estaban en DOS
rubros a la vez.

Los segundos no son cosméticos: `carniceria` estaba en `alimentos` y en
`carniceria`, `gimnasio` en `deportes` y en `gimnasios`. Siempre la misma
historia — se creó el rubro específico y la palabra se quedó también en el
genérico viejo, así que el genérico sigue ganando. De ahí salía la pollería
clasificada como "Supermercado y alimentos".

Este test reconstruye el estado FINAL de `rubro_palabras` aplicando las
migraciones en orden. Contar por archivo miente: la 0061 y la 0062 borran y
reescriben patrones enteros.

No cubre las palabras agregadas desde el panel —ésas viven sólo en la base—,
pero sí todo lo que entra por migración, que es donde se acumuló el problema.
"""
import re
from collections import defaultdict
from pathlib import Path

MIGRACIONES = Path(__file__).resolve().parents[2] / "supabase" / "migrations"

RE_DELETE = re.compile(
    r"delete from rubro_palabras\s+where rubro_slug\s*=\s*'([a-z0-9-]+)'\s*"
    r"and patron like '%([^']+)%'", re.I)
RE_INSERT = re.compile(r"\('([a-z0-9-]+)',\s*'(\\m\([^']+\))'")

# Solapamientos reales, no olvidos: dos negocios distintos que de verdad hacen
# lo mismo. Se listan acá para que agregar uno nuevo sea una decisión escrita y
# no un descuido que pasa silencioso.
SOLAPES_ACEPTADOS = {
    "alineacion": {"gomeria-servicio", "taller-mecanico"},
    "balanceo": {"gomeria-servicio", "taller-mecanico"},
    "cambio de aceite": {"neumaticos", "taller-mecanico"},
    "feria americana": {"ropa-americana", "usados"},
}


def _estado_final() -> dict[str, set[str]]:
    estado: dict[str, set[str]] = defaultdict(set)
    for f in sorted(MIGRACIONES.glob("*.sql")):
        t = f.read_text(encoding="utf-8")
        for m in RE_DELETE.finditer(t):
            slug, frag = m.group(1), m.group(2)
            estado[slug] = {p for p in estado[slug] if frag not in p}
        for m in RE_INSERT.finditer(t):
            estado[m.group(1)].add(m.group(2))
    return estado


def _terminos() -> dict[tuple[str, str], int]:
    veces: dict[tuple[str, str], int] = defaultdict(int)
    for slug, patrones in _estado_final().items():
        for p in patrones:
            for termino in p[p.index("(") + 1:-1].split("|"):
                termino = termino.strip().replace("\\M", "").replace("\\m", "")
                if termino:
                    veces[(slug, termino)] += 1
    return veces


def test_el_audit_ve_el_diccionario_entero():
    """Sin esto, los dos tests de abajo podrían estar pasando sobre cero filas —
    que es la forma en que una guarda se lee como protección y no protege."""
    veces = _terminos()
    assert len(veces) > 400, f"sólo se leyeron {len(veces)} términos; el parser se rompió"


def test_ninguna_palabra_repetida_dentro_del_mismo_rubro():
    repetidas = [f"{slug}: {t}" for (slug, t), n in sorted(_terminos().items()) if n > 1]
    assert not repetidas, (
        "Palabras que aparecen dos veces en el mismo rubro. No cambian la "
        "clasificación —`rubros_sugeridos` hace array_agg(distinct)— pero se ven "
        f"en el panel y esconden las que sí importan: {repetidas}")


def test_ninguna_palabra_clasifica_en_dos_rubros_sin_estar_declarada():
    """La que sí rompe: el genérico viejo se queda con la palabra del específico
    nuevo y le gana el principal por ser más antiguo en la taxonomía."""
    por_termino: dict[str, set[str]] = defaultdict(set)
    for slug, termino in _terminos():
        por_termino[termino].add(slug)

    chocan = {t: sorted(s) for t, s in por_termino.items()
              if len(s) > 1 and s != SOLAPES_ACEPTADOS.get(t)}
    assert not chocan, (
        "La misma palabra clasifica en dos rubros. Si el solapamiento es real "
        "—dos negocios que de verdad hacen lo mismo— agregalo a "
        f"SOLAPES_ACEPTADOS con el motivo; si no, sacala del genérico: {chocan}")
