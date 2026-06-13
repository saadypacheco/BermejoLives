"""Registro self-service, login y publicación por chatbot."""
from tests.conftest import comercio_token


# ---------------- Registro ----------------
def _registro(**kw):
    base = {"nombre": "Mi Tienda", "email": "nuevo@x.com", "password": "secreto1", "whatsapp": "59170001111", "plan": "gratis"}
    base.update(kw)
    return base


def test_registro_crea_comercio_y_loguea(client, repo):
    r = client.post("/auth/comercio/registro", json=_registro())
    assert r.status_code == 200
    data = r.json()
    assert data["access_token"]
    assert data["comercio"]["slug"] == "mi-tienda"
    assert data["comercio"]["confiable"] is False  # nace NO confiable
    assert len(repo.comercios) == 1
    assert "nuevo@x.com" in repo.usuarios


def test_registro_slug_unico_ante_colision(client, repo):
    repo.seed_comercio(slug="mi-tienda", nombre="otra")
    r = client.post("/auth/comercio/registro", json=_registro())
    assert r.json()["comercio"]["slug"] == "mi-tienda-2"


def test_registro_email_duplicado_409(client, repo):
    client.post("/auth/comercio/registro", json=_registro())
    r = client.post("/auth/comercio/registro", json=_registro(nombre="Otra"))
    assert r.status_code == 409


def test_registro_password_corta_400(client):
    r = client.post("/auth/comercio/registro", json=_registro(password="123"))
    assert r.status_code == 400


def test_registro_plan_pago_marca_pendiente(client):
    r = client.post("/auth/comercio/registro", json=_registro(email="pro@x.com", plan="premium"))
    assert r.json()["pago_pendiente"] is True


def test_registro_guarda_modalidad_y_rubro(client, repo):
    r = client.post("/auth/comercio/registro", json=_registro(
        email="resto@x.com", nombre="Resto Bermejo", modalidad="minorista", rubro_slug="gastronomia"))
    assert r.status_code == 200
    com = next(c for c in repo.comercios.values() if c.get("slug") == "resto-bermejo")
    assert com["modalidad"] == "minorista"
    assert com["rubro_id"] == "rub-2"   # gastronomia


def test_registro_modalidad_invalida_400(client):
    r = client.post("/auth/comercio/registro", json=_registro(email="z@x.com", modalidad="revendedor"))
    assert r.status_code == 400


# ---------------- Login + publicar ----------------
def test_login_y_publicar_no_confiable_va_a_moderacion(client, repo):
    reg = client.post("/auth/comercio/registro", json=_registro(email="m@x.com")).json()
    token = reg["access_token"]
    r = client.post(
        "/comercio/publicar",
        headers={"Authorization": f"Bearer {token}"},
        json={"tipo": "oferta", "titulo": "Remera", "precio": 80, "moneda": "BOB"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["publicado_directo"] is False
    assert body["estado"] == "pendiente"


def test_publicar_confiable_publica_directo(client, repo):
    repo.seed_comercio(id="com-c", slug="conf", nombre="Conf", whatsapp="591700", confiable=True)
    token = comercio_token(comercio_id="com-c", email="c@x.com")
    r = client.post(
        "/comercio/publicar",
        headers={"Authorization": f"Bearer {token}"},
        json={"tipo": "novedad", "titulo": "Llegó stock"},
    )
    assert r.json()["estado"] == "aprobado"
    assert repo.publicaciones[0]["approved_at"] is not None


def test_publicar_tipo_invalido_400(client, repo):
    repo.seed_comercio(id="com-c", slug="conf", nombre="Conf", whatsapp="591700", confiable=True)
    token = comercio_token(comercio_id="com-c")
    r = client.post("/comercio/publicar", headers={"Authorization": f"Bearer {token}"}, json={"tipo": "spam"})
    assert r.status_code == 400


def test_publicar_sin_token_401(client):
    assert client.post("/comercio/publicar", json={"tipo": "oferta"}).status_code == 401
