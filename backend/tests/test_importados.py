"""Comercios traídos de fuentes externas: normalización, revisión y promoción.

La regla que gobierna todo esto: **nada importado se publica solo**. Lo que
viene de OpenStreetMap es nombre, punto en el mapa y a veces teléfono — medido
sobre 19.861 negocios, el 0,5% traía foto y el 1% WhatsApp. Si eso entrara
mezclado con los 270 comercios que el equipo relevó caminando, el comprador
tocaría pines vacíos y dejaría de confiar en los que sí sirven.
"""
from app.services import importador


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _nodo(**tags):
    base = {"type": "node", "id": 12345, "lat": -22.7361, "lon": -64.3433}
    return {**base, "tags": {"name": "Panadería La Esquina", "shop": "bakery", **tags}}


# ─────────────────────────────────── normalización
def test_traduce_la_categoria_de_osm_a_la_taxonomia_de_uruku():
    fila = importador.normalizar(_nodo())
    assert fila["categoria"] == "bakery"
    assert fila["rubro_slug"] == "panaderia"
    assert fila["fuente_id"] == "node/12345"


def test_una_categoria_desconocida_queda_SIN_rubro_y_no_inventa_uno():
    """Preferir el hueco a la invención es la lección que costó limpiar
    `alimentos` y `hogar`: un rubro de más manda al comprador a un local que no
    tiene lo que busca, y eso es peor que no encontrar nada."""
    fila = importador.normalizar(_nodo(shop="funeral_directors"))
    assert fila["rubro_slug"] is None


def test_sin_nombre_no_entra():
    """Un punto sin nombre no se puede reconocer parado en la vereda, así que no
    sirve ni para el mapa ni para salir a buscarlo."""
    assert importador.normalizar({"type": "node", "id": 1, "lat": -22.7, "lon": -64.3,
                                  "tags": {"shop": "bakery"}}) is None


def test_sin_coordenadas_no_entra():
    assert importador.normalizar({"type": "node", "id": 1, "tags": {"name": "X", "shop": "bakery"}}) is None


def test_toma_las_coordenadas_del_center_cuando_es_un_way():
    """Un local mapeado como polígono (way) no tiene lat/lon sino un centro."""
    fila = importador.normalizar({"type": "way", "id": 9, "center": {"lat": -21.5, "lon": -64.7},
                                  "tags": {"name": "Mercado", "amenity": "marketplace"}})
    assert fila["lat"] == -21.5 and fila["fuente_id"] == "way/9"


def test_junta_el_telefono_de_las_variantes_de_osm():
    fila = importador.normalizar(_nodo(**{"contact:phone": "+591 71234567;+591 4444"}))
    assert fila["telefono"] == "+591 71234567"     # el primero, sin el resto de la lista


def test_arma_la_direccion_con_calle_y_numero():
    fila = importador.normalizar(_nodo(**{"addr:street": "Av. Costanera", "addr:housenumber": "440"}))
    assert fila["direccion"] == "Av. Costanera 440"


# ─────────────────────────────────── panel
def test_el_listado_arranca_en_los_sin_revisar(client, repo, admin_token):
    repo.upsert_importado({"fuente": "osm", "fuente_id": "node/1", "nombre": "A",
                           "lat": -22.7, "lng": -64.3})
    r = client.get("/admin/importados", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["estado"] == "nuevo"


def test_promover_crea_el_comercio_y_marca_el_importado(client, repo, admin_token):
    repo.upsert_importado({"fuente": "osm", "fuente_id": "node/1", "nombre": "Panadería La Esquina",
                           "rubro_slug": "panaderia", "lat": -22.7361, "lng": -64.3433,
                           "telefono": "59171234567"})
    imp_id = list(repo.importados)[0]

    r = client.post(f"/admin/importados/{imp_id}/promover", json={}, headers=_h(admin_token))
    assert r.status_code == 200, r.text
    com = r.json()["comercio"]
    assert com["nombre"] == "Panadería La Esquina"
    # Nace SIN verificar: nadie lo miró todavía, y el mapa distingue entre lo
    # que alguien caminó y lo que salió de una base abierta.
    assert repo.comercios[com["id"]]["verificado"] is False
    assert repo.comercios[com["id"]]["cargado_por"] == "import:osm"
    assert repo.importados[imp_id]["estado"] == "promovido"
    assert repo.importados[imp_id]["comercio_id"] == com["id"]


def test_no_se_promueve_dos_veces(client, repo, admin_token):
    repo.upsert_importado({"fuente": "osm", "fuente_id": "node/1", "nombre": "A",
                           "lat": -22.7, "lng": -64.3})
    imp_id = list(repo.importados)[0]
    client.post(f"/admin/importados/{imp_id}/promover", json={}, headers=_h(admin_token))
    r = client.post(f"/admin/importados/{imp_id}/promover", json={}, headers=_h(admin_token))
    assert r.status_code == 409


def test_sin_coordenadas_no_se_puede_promover(client, repo, admin_token):
    repo.upsert_importado({"fuente": "osm", "fuente_id": "node/2", "nombre": "A",
                           "lat": None, "lng": None})
    imp_id = list(repo.importados)[0]
    r = client.post(f"/admin/importados/{imp_id}/promover", json={}, headers=_h(admin_token))
    assert r.status_code == 400


def test_descartar_no_borra_la_fila(client, repo, admin_token):
    """Si se borrara, la próxima importación lo volvería a proponer y el trabajo
    de haberlo mirado se perdería en cada corrida."""
    repo.upsert_importado({"fuente": "osm", "fuente_id": "node/1", "nombre": "A",
                           "lat": -22.7, "lng": -64.3})
    imp_id = list(repo.importados)[0]
    r = client.post(f"/admin/importados/{imp_id}/descartar?motivo=cerrado", headers=_h(admin_token))
    assert r.status_code == 200
    assert repo.importados[imp_id]["estado"] == "descartado"
    assert repo.importados[imp_id]["motivo"] == "cerrado"


def test_reimportar_actualiza_los_datos_pero_no_resucita_lo_revisado(repo):
    """Lo que hace que reimportar una ciudad sea seguro de repetir."""
    fila = {"fuente": "osm", "fuente_id": "node/1", "nombre": "Viejo", "lat": -22.7, "lng": -64.3}
    assert repo.upsert_importado(fila) is True
    imp_id = list(repo.importados)[0]
    repo.marcar_importado(imp_id, {"estado": "descartado"})

    assert repo.upsert_importado({**fila, "nombre": "Nuevo", "telefono": "5917"}) is False
    assert repo.importados[imp_id]["nombre"] == "Nuevo"        # el dato se actualiza
    assert repo.importados[imp_id]["telefono"] == "5917"
    assert repo.importados[imp_id]["estado"] == "descartado"   # la revisión se respeta
