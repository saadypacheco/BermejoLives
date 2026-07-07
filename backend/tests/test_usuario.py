"""Cuenta de comprador/visitante: celular + código por WhatsApp, sin contraseña."""


def _codigo_del_comprador(repo, whatsapp):
    digitos = "".join(c for c in whatsapp if c.isdigit())
    for u in repo.compradores.values():
        if u["whatsapp"] == digitos:
            return u["reset_code"]
    return None


def test_solicitar_codigo_crea_usuario_y_devuelve_ok(client, repo):
    r = client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": "59171234567"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert len(repo.compradores) == 1
    assert _codigo_del_comprador(repo, "59171234567") is not None


def test_verificar_codigo_ok_devuelve_token(client, repo):
    client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": "59171234567"})
    codigo = _codigo_del_comprador(repo, "59171234567")

    r = client.post("/auth/usuario/verificar", json={"whatsapp": "59171234567", "codigo": codigo})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["access_token"]
    assert body["usuario"]["whatsapp"] == "59171234567"


def test_verificar_codigo_incorrecto_400(client):
    client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": "59171234567"})
    r = client.post("/auth/usuario/verificar", json={"whatsapp": "59171234567", "codigo": "000000"})
    assert r.status_code == 400


def test_favoritos_requiere_token_401(client):
    r = client.get("/usuario/favoritos")
    assert r.status_code == 401


def test_agregar_y_listar_favorito(client, repo):
    client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": "59171234567"})
    codigo = _codigo_del_comprador(repo, "59171234567")
    token = client.post("/auth/usuario/verificar", json={"whatsapp": "59171234567", "codigo": codigo}).json()["access_token"]

    comercio = repo.crear_comercio({"nombre": "Importadora ABC", "slug": "importadora-abc"})

    r = client.post("/usuario/favoritos", headers={"Authorization": f"Bearer {token}"}, json={"comercio_id": comercio["id"]})
    assert r.status_code == 200

    r2 = client.get("/usuario/favoritos", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    items = r2.json()["items"]
    assert len(items) == 1
    assert items[0]["slug"] == "importadora-abc"


def test_quitar_favorito(client, repo):
    client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": "59171234567"})
    codigo = _codigo_del_comprador(repo, "59171234567")
    token = client.post("/auth/usuario/verificar", json={"whatsapp": "59171234567", "codigo": codigo}).json()["access_token"]
    comercio = repo.crear_comercio({"nombre": "Importadora ABC", "slug": "importadora-abc"})
    client.post("/usuario/favoritos", headers={"Authorization": f"Bearer {token}"}, json={"comercio_id": comercio["id"]})

    r = client.delete(f"/usuario/favoritos/{comercio['id']}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert client.get("/usuario/favoritos", headers={"Authorization": f"Bearer {token}"}).json()["items"] == []
