"""El cartel del horario dice CUÁNDO abre, con el día si no es hoy.

El caso que lo motivó (12/10): un local que no abre los lunes figuraba el lunes
como «Cerrado · abre 9:30», y parecía que abría ese mismo día. Y el «+» del
horario cargado no separaba los días: el domingo heredaba los de la semana.
"""
from datetime import datetime

import pytest

from app.services.horario import abierto_ahora, etiqueta

DUENIO = "Mar-Sab 9:30-13:00 16-20 + Dom 9:30-13 14:30-20"


def _et(horario: str, cuando: datetime) -> str | None:
    return etiqueta(abierto_ahora(horario, cuando), cuando)


# 12/10/2026 es lunes.
@pytest.mark.parametrize("cuando,esperado", [
    (datetime(2026, 10, 12, 10, 0), "Cerrado hoy · abre mañana 9:30"),
    (datetime(2026, 10, 13, 8, 0), "Cerrado · abre 9:30"),
    (datetime(2026, 10, 13, 12, 15), "Abierto · cierra 13:00"),
    (datetime(2026, 10, 13, 14, 0), "Cerrado · abre 16:00"),
    (datetime(2026, 10, 17, 15, 0), "Cerrado · abre 16:00"),        # sábado: sin la tarde del domingo
    (datetime(2026, 10, 17, 21, 0), "Cerrado · abre mañana 9:30"),
    (datetime(2026, 10, 18, 13, 30), "Cerrado · abre 14:30"),
    (datetime(2026, 10, 18, 15, 0), "Abierto ahora"),
    (datetime(2026, 10, 18, 21, 0), "Cerrado · abre el martes 9:30"),
])
def test_horario_del_duenio(cuando, esperado):
    assert _et(DUENIO, cuando) == esperado


def test_un_tramo_sin_dias_hereda_los_del_anterior():
    """«Lun a Sáb 8-12 · 14:30-20»: la tarde es de lunes a sábado, no del domingo."""
    assert _et("Lun a Sáb 8-12 · 14:30-20", datetime(2026, 10, 18, 10, 0)) == "Cerrado hoy · abre mañana 8:00"
    assert _et("Lun a Sáb 8-12 · 14:30-20", datetime(2026, 10, 17, 15, 0)) == "Abierto ahora"


def test_sin_dias_en_ningun_tramo_son_todos_los_dias():
    assert _et("9-18", datetime(2026, 10, 18, 10, 0)) == "Abierto ahora"


def test_la_madrugada_sigue_siendo_de_la_noche_anterior():
    assert _et("Vie-Sab 22-4", datetime(2026, 10, 17, 3, 0)) == "Abierto · cierra 4:00"
