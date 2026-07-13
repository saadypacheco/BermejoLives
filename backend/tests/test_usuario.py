"""Cuenta de comprador/visitante: celular + código por WhatsApp, sin contraseña.

Login por mensaje ENTRANTE (2026-07-13): solicitar-codigo ya no manda nada
por WhatsApp — devuelve el código + un link wa.me, y hace falta que el
webhook confirme (simulado acá con repo.confirmar_reset_code_usuario, que
es exactamente lo que hace ingest.py al recibir "CONFIRMAR-XXXXXX") antes
de que /verificar acepte el código.
"""


def _codigo_del_comprador(repo, whatsapp):
    digitos = "".join(c for c in whatsapp if c.isdigit())
    for u in repo.compradores.values():
        if u["whatsapp"] == digitos:
            return u["reset_code"]
    return None


def test_solicitar_codigo_crea_usuario_y_devuelve_codigo_y_link(client, repo):
    r = client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": "59171234567"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["codigo"]
    assert body["wa_link"].startswith("https://wa.me/")
    assert f"CONFIRMAR-{body['codigo']}" in body["wa_link"]
    assert len(repo.compradores) == 1
    assert _codigo_del_comprador(repo, "59171234567") == body["codigo"]


def test_verificar_sin_confirmar_por_whatsapp_400(client, repo):
    """Conocer el código no alcanza — el código viaja en la respuesta HTTP,
    así que si esto no fallara, cualquiera podría loguearse sin mandar nada."""
    client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": "59171234567"})
    codigo = _codigo_del_comprador(repo, "59171234567")

    r = client.post("/auth/usuario/verificar", json={"whatsapp": "59171234567", "codigo": codigo})
    assert r.status_code == 400
    assert "confirmaste" in r.json()["detail"].lower()


def test_verificar_codigo_ok_devuelve_token(client, repo):
    client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": "59171234567"})
    codigo = _codigo_del_comprador(repo, "59171234567")
    assert repo.confirmar_reset_code_usuario("59171234567", codigo) is True

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


def _token_comprador(client, repo, whatsapp):
    client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": whatsapp})
    codigo = _codigo_del_comprador(repo, whatsapp)
    repo.confirmar_reset_code_usuario(whatsapp, codigo)
    return client.post("/auth/usuario/verificar", json={"whatsapp": whatsapp, "codigo": codigo}).json()["access_token"]


def test_agregar_y_listar_favorito(client, repo):
    token = _token_comprador(client, repo, "59171234567")
    comercio = repo.crear_comercio({"nombre": "Importadora ABC", "slug": "importadora-abc"})

    r = client.post("/usuario/favoritos", headers={"Authorization": f"Bearer {token}"}, json={"comercio_id": comercio["id"]})
    assert r.status_code == 200

    r2 = client.get("/usuario/favoritos", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    items = r2.json()["items"]
    assert len(items) == 1
    assert items[0]["slug"] == "importadora-abc"


def test_quitar_favorito(client, repo):
    token = _token_comprador(client, repo, "59171234567")
    comercio = repo.crear_comercio({"nombre": "Importadora ABC", "slug": "importadora-abc"})
    client.post("/usuario/favoritos", headers={"Authorization": f"Bearer {token}"}, json={"comercio_id": comercio["id"]})

    r = client.delete(f"/usuario/favoritos/{comercio['id']}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert client.get("/usuario/favoritos", headers={"Authorization": f"Bearer {token}"}).json()["items"] == []
