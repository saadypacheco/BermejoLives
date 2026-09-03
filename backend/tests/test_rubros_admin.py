"""Alta de rubros y diccionario desde el panel."""
from app.api.moderacion import _patron_de


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_el_patron_escapa_lo_que_romperia_la_regex():
    """Alguien va a escribir un parentesis alguna vez. Sin escapar no da error:
    cambia lo que el patron matchea, que es peor."""
    p = _patron_de("bar (nocturno)")
    assert r"\(" in p and r"\)" in p


def test_el_patron_junta_y_deduplica():
    assert _patron_de("lubricentro, engrase, lubricentro, ,") == r"\m(lubricentro|engrase)"


def test_slug_invalido_se_rechaza(client, admin_token):
    r = client.post("/admin/rubros",
                    json={"slug": "Taller Mecánico", "nombre": "Taller"}, headers=_h(admin_token))
    assert r.status_code == 400
    assert "minúsculas" in r.json()["detail"]


def test_crear_rubro_guarda_palabras_y_saca_la_propuesta(client, admin_token, repo):
    repo.rubros_propuestos.append({"normalizado": "funeraria", "texto": "funeraria",
                                   "comercio_id": None})
    r = client.post("/admin/rubros", json={
        "slug": "funeraria", "nombre": "Funeraria", "icono": "🕯️",
        "palabras": "funeraria, servicio funebre", "resolver": "funeraria",
    }, headers=_h(admin_token))

    assert r.status_code == 200
    assert "funeraria" in repo.rubros
    assert any(p["rubro_slug"] == "funeraria" for p in repo.rubro_palabras)
    # La propuesta se va de la cola: si no, sigue apareciendo para siempre y una
    # cola que no baja se deja de mirar.
    assert repo.rubros_propuestos == []


def test_palabras_a_un_rubro_que_no_existe_se_rechaza(client, admin_token):
    r = client.post("/admin/rubros/palabras",
                    json={"rubro_slug": "inventado", "palabras": "x"}, headers=_h(admin_token))
    assert r.status_code == 400


def test_palabras_a_un_rubro_existente(client, admin_token, repo):
    """El caso 'no es un rubro nuevo, es otra forma de decir uno que existe'."""
    repo.rubros_propuestos.append({"normalizado": "lubricentro", "texto": "lubricentro",
                                   "comercio_id": None})
    r = client.post("/admin/rubros/palabras", json={
        "rubro_slug": "neumaticos", "palabras": "lubricentro, engrase",
        "resolver": "lubricentro",
    }, headers=_h(admin_token))

    assert r.status_code == 200
    assert any(p["rubro_slug"] == "neumaticos" and "lubricentro" in p["patron"]
               for p in repo.rubro_palabras)
    assert repo.rubros_propuestos == []
