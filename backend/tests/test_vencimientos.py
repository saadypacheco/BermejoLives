"""Vencimientos: el estado y el orden, que es lo que decide si el panel sirve."""
from datetime import timedelta

from app.services.vencimientos import con_estado, estado_de, hoy_local


def _en(dias):
    # Contra el calendario de Bermejo, no el de la máquina que corre el test:
    # el servidor está en UTC y Bolivia en UTC-4, así que `date.today()` daba
    # un día de diferencia durante cuatro horas al día.
    return (hoy_local() + timedelta(days=dias)).isoformat()


def test_sin_fecha_no_es_ok():
    """Es la distinción que hace útil al panel.

    Una fila sin fecha no está tranquila: está sin vigilar. Contarla como `ok`
    convierte el tablero en un semáforo que siempre da verde.
    """
    assert estado_de(None, 30) == "sin_fecha"


def test_los_umbrales():
    assert estado_de(-1, 30) == "vencido"
    assert estado_de(0, 30) == "critico"
    assert estado_de(7, 30) == "critico"
    assert estado_de(8, 30) == "por_vencer"
    assert estado_de(30, 30) == "por_vencer"
    assert estado_de(31, 30) == "ok"


def test_el_aviso_es_por_fila():
    """Un dominio .bo necesita más aire que un chip: renovarlo puede requerir un
    trámite y esperar a alguien."""
    assert estado_de(45, 30) == "ok"
    assert estado_de(45, 60) == "por_vencer"


def test_orden_lo_que_arde_primero():
    filas = [
        {"nombre": "ok", "vence_el": _en(200), "aviso_dias": 30},
        {"nombre": "sin fecha", "vence_el": None, "aviso_dias": 30},
        {"nombre": "vencido", "vence_el": _en(-3), "aviso_dias": 30},
        {"nombre": "critico", "vence_el": _en(2), "aviso_dias": 30},
        {"nombre": "por vencer", "vence_el": _en(20), "aviso_dias": 30},
    ]
    assert [f["nombre"] for f in con_estado(filas)] == [
        "vencido", "critico", "por vencer", "sin fecha", "ok"]


def test_las_sin_fecha_van_antes_que_las_sanas():
    """Son trabajo pendiente, no calma: enterradas al final no las carga nadie."""
    filas = [{"nombre": "ok", "vence_el": _en(300), "aviso_dias": 30},
             {"nombre": "pendiente", "vence_el": None, "aviso_dias": 30}]
    assert [f["nombre"] for f in con_estado(filas)] == ["pendiente", "ok"]


def test_fecha_invalida_no_revienta():
    """Una fecha escrita a mano puede venir con cualquier cosa; que el panel
    entero se caiga por una fila mal cargada sería peor que no tenerlo."""
    filas = [{"nombre": "rara", "vence_el": "mañana", "aviso_dias": 30}]
    assert con_estado(filas)[0]["estado"] == "sin_fecha"


def test_dias_se_calcula_bien():
    f = con_estado([{"nombre": "x", "vence_el": _en(10), "aviso_dias": 30}])[0]
    assert f["dias"] == 10


def test_zona_horaria_de_bolivia():
    """Lo que motivó el arreglo: entre las 20:00 y la medianoche de Bermejo, en
    UTC ya es el día siguiente. Algo que vence HOY aparecía como vencido durante
    las últimas cuatro horas del día en que todavía se podía renovar."""
    from datetime import datetime, timezone

    from app.services.vencimientos import TZ_BOLIVIA, hoy_local

    assert TZ_BOLIVIA.utcoffset(None).total_seconds() == -4 * 3600
    # Nunca por delante del calendario UTC.
    assert hoy_local() <= datetime.now(timezone.utc).date()
    assert estado_de(0, 30) == "critico"      # vence hoy: urgente, no vencido
