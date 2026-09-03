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


# ── La vista previa: el arreglo que vale más que la IA ────────────────────────

def _comercio(repo, cid, nombre, vende, rubros=()):
    # El fake guarda los rubros del comercio en `rubros`, que es de donde los
    # lee `list_comercio_rubros_todos`.
    return repo.seed_comercio(id=cid, nombre=nombre, prod_det_ia=vende,
                              activo=True, rubros=list(rubros))


def test_la_vista_previa_avisa_cuando_la_palabra_arrastra(client, admin_token, repo):
    """El caso "papa frita": describe bien la comida rápida y está en todos los
    kioscos. La palabra es correcta y el alcance es el problema."""
    _comercio(repo, "k1", "Kiosko", "galletita, papa frita, caramelo", ["kiosco"])
    _comercio(repo, "k2", "Kiosko dos", "papa frita, chicle", ["kiosco"])
    _comercio(repo, "cr", "Snack", "hamburguesa, papa frita", ["comida-rapida"])

    r = client.post("/admin/rubros/previsualizar",
                    json={"palabras": "papa frita", "rubro_slug": "comida-rapida"},
                    headers=_h(admin_token))
    d = r.json()

    assert d["alcanza"] == 3
    assert d["ya_lo_tienen"] == 1          # el snack, que ya es comida rápida
    assert d["nuevos"] == 2                # los dos kioscos, que NO deberían entrar
    # Y dice con qué rubro conviven, que es la señal de que arrastra.
    assert {"slug": "kiosco", "comercios": 2} in d["conviven_con"]


def test_la_vista_previa_de_una_palabra_limpia(client, admin_token, repo):
    _comercio(repo, "f1", "Funeraria San José", "cajon mortuorio, corona")
    _comercio(repo, "k1", "Kiosko", "galletita, caramelo", ["kiosco"])

    d = client.post("/admin/rubros/previsualizar",
                    json={"palabras": "cajon mortuorio"}, headers=_h(admin_token)).json()

    assert d["alcanza"] == 1 and d["nuevos"] == 1
    assert d["conviven_con"] == []          # no arrastra a nadie de otro rubro


def test_la_vista_previa_usa_el_patron_real(client, admin_token, repo):
    """Tiene que probar EXACTAMENTE lo que se va a guardar. Una vista previa que
    mira otra cosa que el clasificador tranquiliza sobre algo que no se probó."""
    d = client.post("/admin/rubros/previsualizar",
                    json={"palabras": "cajon mortuorio, velatorio"},
                    headers=_h(admin_token)).json()
    assert d["patron"] == _patron_de("cajon mortuorio, velatorio")


def test_sin_palabras_no_previsualiza(client, admin_token):
    r = client.post("/admin/rubros/previsualizar", json={"palabras": "  "},
                    headers=_h(admin_token))
    assert r.status_code == 400


# ── Aplicar la palabra a los comercios que alcanza, sin paso aparte ──────────

def test_aplicar_patron_le_agrega_el_rubro_a_los_que_alcanza(client, admin_token, repo):
    """Cierra el hueco entre crear un rubro y que los comercios lo tengan.
    Antes había que acordarse de correr 'Completar rubros' despues; si nadie lo
    hacia, el rubro quedaba con cero comercios y parecia roto."""
    repo.rubros.setdefault("funeraria", repo._id("rub"))
    _comercio(repo, "f1", "San José", "cajon mortuorio, corona")
    _comercio(repo, "k1", "Kiosko", "galletita", ["kiosco"])

    r = client.post("/admin/rubros/aplicar-patron",
                    json={"rubro_slug": "funeraria", "palabras": "cajon mortuorio"},
                    headers=_h(admin_token))

    assert r.json()["agregados"] == 1
    suyos = {x["slug"] for x in repo.list_comercio_rubros_todos() if x["comercio_id"] == "f1"}
    assert "funeraria" in suyos
    # Y no toca al que no alcanza.
    ajenos = {x["slug"] for x in repo.list_comercio_rubros_todos() if x["comercio_id"] == "k1"}
    assert ajenos == {"kiosco"}


def test_aplicar_patron_no_pisa_los_rubros_que_ya_tenia(client, admin_token, repo):
    """Sólo SUMA: mandar únicamente el nuevo borraría los que ya tenía, porque
    `set_comercio_rubros` reemplaza el conjunto entero."""
    repo.rubros.setdefault("funeraria", repo._id("rub"))
    _comercio(repo, "f1", "San José", "cajon mortuorio", ["regaleria", "floreria"])

    client.post("/admin/rubros/aplicar-patron",
                json={"rubro_slug": "funeraria", "palabras": "cajon mortuorio"},
                headers=_h(admin_token))

    suyos = {x["slug"] for x in repo.list_comercio_rubros_todos() if x["comercio_id"] == "f1"}
    assert suyos == {"regaleria", "floreria", "funeraria"}


def test_aplicar_patron_saltea_a_los_que_quedarian_con_demasiados(client, admin_token, repo):
    """Un comercio en siete categorías no filtra en ninguna, y agregarle una
    más lo empeora. Se saltea Y se informa: saltear en silencio deja al usuario
    creyendo que se aplicó a todos."""
    repo.rubros.setdefault("funeraria", repo._id("rub"))
    muchos = ["ropa", "calzado", "bazar", "hogar", "regaleria", "floreria"]
    for s in muchos:
        repo.rubros.setdefault(s, repo._id("rub"))
    _comercio(repo, "f1", "Polirubro", "cajon mortuorio", muchos)

    d = client.post("/admin/rubros/aplicar-patron",
                    json={"rubro_slug": "funeraria", "palabras": "cajon mortuorio"},
                    headers=_h(admin_token)).json()

    assert d["agregados"] == 0
    assert d["salteados"][0]["nombre"] == "Polirubro"


def test_aplicar_patron_a_un_rubro_inexistente(client, admin_token):
    r = client.post("/admin/rubros/aplicar-patron",
                    json={"rubro_slug": "no-existe", "palabras": "x"}, headers=_h(admin_token))
    assert r.status_code == 400
