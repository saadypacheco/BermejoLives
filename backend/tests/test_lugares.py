"""Mercados y galerías: los crea el agente en la calle y los cura el admin.

Son la dirección real de la mayoría de los comercios cargados (74 de 84 en el
primer recorrido estaban dentro de un lugar), así que un fallo acá deja sin
ubicación utilizable a casi todo el catálogo.
"""


def _ha(token):
    return {"Authorization": f"Bearer {token}"}


# ═══════════════════════════════════════════════ agente de campo
def test_agente_crea_un_lugar_en_el_momento(client, repo, agente_token):
    """La primera vez que encuentra un mercado lo da de alta ahí mismo."""
    r = client.post("/campo/lugares",
                    json={"nombre": "Mercado Central", "tipo": "mercado",
                          "ciudad_slug": "bermejo", "lat": -22.73, "lng": -64.34},
                    headers=_ha(agente_token))
    assert r.status_code == 200, r.text
    assert r.json()["lugar"]["nombre"] == "Mercado Central"


def test_no_se_crea_un_lugar_sin_nombre(client, repo, agente_token):
    r = client.post("/campo/lugares", json={"nombre": "   "}, headers=_ha(agente_token))
    assert r.status_code == 400


def test_el_agente_lista_los_lugares_para_el_selector(client, repo, agente_token):
    client.post("/campo/lugares", json={"nombre": "Galería Cortez"}, headers=_ha(agente_token))
    items = client.get("/campo/lugares", headers=_ha(agente_token)).json()["items"]
    assert any(l["nombre"] == "Galería Cortez" for l in items)


def test_el_agente_corrige_el_nombre_de_un_lugar(client, repo, agente_token):
    """Se cargan mal seguido: se tipean rápido y parado en la calle."""
    lugar = client.post("/campo/lugares", json={"nombre": "Galeria cortes"},
                        headers=_ha(agente_token)).json()["lugar"]

    r = client.patch(f"/campo/lugares/{lugar['id']}",
                     json={"nombre": "Galería Cortez"}, headers=_ha(agente_token))
    assert r.status_code == 200, r.text
    assert r.json()["lugar"]["nombre"] == "Galería Cortez"


def test_editar_sin_cambios_es_un_error_explicito(client, repo, agente_token):
    lugar = client.post("/campo/lugares", json={"nombre": "Mercado"},
                        headers=_ha(agente_token)).json()["lugar"]
    r = client.patch(f"/campo/lugares/{lugar['id']}", json={}, headers=_ha(agente_token))
    assert r.status_code == 400


def test_lugares_de_campo_requieren_agente(client, repo):
    assert client.get("/campo/lugares").status_code in (401, 403)
    assert client.post("/campo/lugares", json={"nombre": "X"}).status_code in (401, 403)


# ═══════════════════════════════════════════════════════ admin
def test_admin_lista_lugares(client, repo, admin_token, agente_token):
    client.post("/campo/lugares", json={"nombre": "Mercado Central"}, headers=_ha(agente_token))
    r = client.get("/admin/lugares", headers=_ha(admin_token))
    assert r.status_code == 200, r.text
    assert any(l["nombre"] == "Mercado Central" for l in r.json()["items"])


def test_admin_crea_lugar(client, repo, admin_token):
    r = client.post("/admin/lugares",
                    json={"nombre": "Paseo Comercial", "tipo": "galeria"},
                    headers=_ha(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["lugar"]["nombre"] == "Paseo Comercial"


def test_admin_no_crea_lugar_sin_nombre(client, repo, admin_token):
    r = client.post("/admin/lugares", json={"nombre": ""}, headers=_ha(admin_token))
    assert r.status_code == 400


def test_admin_edita_lugar(client, repo, admin_token):
    lugar = client.post("/admin/lugares", json={"nombre": "Mercado"},
                        headers=_ha(admin_token)).json()["lugar"]

    r = client.put(f"/admin/lugares/{lugar['id']}",
                   json={"nombre": "Mercado Central", "lat": -22.73, "lng": -64.34},
                   headers=_ha(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["lugar"]["nombre"] == "Mercado Central"


def test_borrar_un_lugar_es_darlo_de_baja_no_borrarlo(client, repo, admin_token):
    """Hay comercios apuntando al lugar: borrarlo de verdad los dejaría huérfanos."""
    lugar = client.post("/admin/lugares", json={"nombre": "Mercado"},
                        headers=_ha(admin_token)).json()["lugar"]

    r = client.delete(f"/admin/lugares/{lugar['id']}", headers=_ha(admin_token))
    assert r.status_code == 200, r.text
    assert repo.get_lugar(lugar["id"])["activo"] is False


def test_lugares_de_admin_requieren_admin(client, repo):
    assert client.get("/admin/lugares").status_code in (401, 403)
    assert client.post("/admin/lugares", json={"nombre": "X"}).status_code in (401, 403)
