"""Chalanas y lapachos del mapa: decoración ubicada a mano.

Son datos que alguien puso caminando la ciudad y mirando dónde queda bien. Se
rehacen a mano si se pierden, así que las validaciones y la baja lógica importan
más de lo que sugiere el hecho de que sean adornos.
"""


def _ha(token):
    return {"Authorization": f"Bearer {token}"}


def test_se_crea_una_chalana_donde_se_toco_el_mapa(client, repo, admin_token):
    r = client.post("/admin/adornos",
                    json={"tipo": "chalana", "lat": -22.748, "lng": -64.346},
                    headers=_ha(admin_token))
    assert r.status_code == 200, r.text
    adorno = r.json()["adorno"]
    assert adorno["tipo"] == "chalana"
    assert adorno["lat"] == -22.748


def test_solo_existen_chalanas_y_lapachos(client, repo, admin_token):
    """El tipo decide qué dibujo se usa. Uno desconocido no rompería nada
    visible —caería en el dibujo por defecto— y por eso conviene rechazarlo
    acá: un adorno que no es lo que dice ser es imposible de encontrar después."""
    r = client.post("/admin/adornos",
                    json={"tipo": "helicoptero", "lat": -22.7, "lng": -64.3},
                    headers=_ha(admin_token))
    assert r.status_code == 400


def test_no_se_crea_un_adorno_sin_ubicacion(client, repo, admin_token):
    r = client.post("/admin/adornos", json={"tipo": "lapacho"}, headers=_ha(admin_token))
    assert r.status_code == 400


def test_arrastrar_lo_mueve(client, repo, admin_token):
    creado = client.post("/admin/adornos",
                         json={"tipo": "lapacho", "lat": -22.73, "lng": -64.34},
                         headers=_ha(admin_token)).json()["adorno"]
    r = client.put(f"/admin/adornos/{creado['id']}",
                   json={"lat": -22.74, "lng": -64.35}, headers=_ha(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["adorno"]["lat"] == -22.74


def test_el_tamano_y_el_giro_se_ajustan(client, repo, admin_token):
    creado = client.post("/admin/adornos",
                         json={"tipo": "chalana", "lat": -22.74, "lng": -64.34},
                         headers=_ha(admin_token)).json()["adorno"]
    r = client.put(f"/admin/adornos/{creado['id']}",
                   json={"escala": 1.4, "giro": -12}, headers=_ha(admin_token))
    assert r.status_code == 200
    assert r.json()["adorno"]["escala"] == 1.4
    assert r.json()["adorno"]["giro"] == -12


def test_un_put_vacio_no_pasa(client, repo, admin_token):
    creado = client.post("/admin/adornos",
                         json={"tipo": "lapacho", "lat": -22.73, "lng": -64.34},
                         headers=_ha(admin_token)).json()["adorno"]
    assert client.put(f"/admin/adornos/{creado['id']}", json={},
                      headers=_ha(admin_token)).status_code == 400


def test_borrar_es_baja_logica_y_lo_saca_del_listado(client, repo, admin_token):
    """Un adorno borrado por error se rehace caminando la ciudad de nuevo, así
    que se desactiva en vez de eliminarse."""
    creado = client.post("/admin/adornos",
                         json={"tipo": "chalana", "lat": -22.74, "lng": -64.34},
                         headers=_ha(admin_token)).json()["adorno"]
    assert client.delete(f"/admin/adornos/{creado['id']}",
                         headers=_ha(admin_token)).status_code == 200

    listado = client.get("/admin/adornos", headers=_ha(admin_token)).json()["items"]
    assert creado["id"] not in [a["id"] for a in listado]
    assert repo.adornos[creado["id"]]["activo"] is False


def test_el_listado_devuelve_lo_puesto(client, repo, admin_token):
    for tipo in ("chalana", "chalana", "lapacho"):
        client.post("/admin/adornos", json={"tipo": tipo, "lat": -22.74, "lng": -64.34},
                    headers=_ha(admin_token))
    items = client.get("/admin/adornos", headers=_ha(admin_token)).json()["items"]
    assert len([a for a in items if a["tipo"] == "chalana"]) == 2
    assert len([a for a in items if a["tipo"] == "lapacho"]) == 1


def test_sin_token_no_se_tocan(client, repo):
    assert client.post("/admin/adornos",
                       json={"tipo": "chalana", "lat": -22.7, "lng": -64.3}).status_code in (401, 403)
