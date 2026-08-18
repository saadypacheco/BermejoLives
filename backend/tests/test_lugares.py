from app.services.lugares import elegir_lugar


def test_punto_dentro_del_poligono():
    lugares = [{"id": "l1", "poligono": [[0, 0], [0, 1], [1, 1], [1, 0]], "lat": None, "lng": None}]
    assert elegir_lugar(lugares, 0.5, 0.5) == "l1"     # dentro del cuadrado
    assert elegir_lugar(lugares, 2, 2) is None          # afuera


def test_cercania_al_punto_sin_poligono():
    lugares = [{"id": "l1", "poligono": None, "lat": -22.7361, "lng": -64.3433}]
    assert elegir_lugar(lugares, -22.7361, -64.3433) == "l1"   # mismo punto (dentro del radio)
    assert elegir_lugar(lugares, -22.70, -64.30) is None       # lejos


def test_poligono_gana_a_cercania():
    lugares = [
        {"id": "cerca", "poligono": None, "lat": 0.5001, "lng": 0.5001},
        {"id": "poly", "poligono": [[0, 0], [0, 1], [1, 1], [1, 0]], "lat": None, "lng": None},
    ]
    assert elegir_lugar(lugares, 0.5, 0.5) == "poly"   # el polígono que contiene el punto manda


def test_sin_gps_devuelve_none():
    assert elegir_lugar([{"id": "l1", "poligono": [[0, 0], [0, 1], [1, 1], [1, 0]]}], None, None) is None
