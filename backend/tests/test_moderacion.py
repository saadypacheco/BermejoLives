"""Panel de moderación: listar pendientes y transicionar estado."""


def _seed_pendiente(repo):
    repo.publicaciones.append(
        {"id": "pub-1", "activo": True, "estado": "pendiente", "comercio_id": "com-1",
         "tipo": "oferta", "titulo": "X"}
    )


def test_listar_pendientes(client, repo, admin_token):
    _seed_pendiente(repo)
    r = client.get("/moderacion/publicaciones?estado=pendiente", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert r.json()["total"] == 1


def test_aprobar_cambia_estado(client, repo, admin_token):
    _seed_pendiente(repo)
    r = client.post(
        "/moderacion/publicaciones/pub-1",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"estado": "aprobado"},
    )
    assert r.status_code == 200
    assert repo.publicaciones[0]["estado"] == "aprobado"
    assert repo.publicaciones[0]["moderado_por"] == "admin@bermejolive.com"


def test_rechazar_con_motivo(client, repo, admin_token):
    _seed_pendiente(repo)
    r = client.post(
        "/moderacion/publicaciones/pub-1",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"estado": "rechazado", "motivo": "Foto borrosa"},
    )
    assert r.status_code == 200
    assert repo.publicaciones[0]["motivo_moderacion"] == "Foto borrosa"


def test_estado_invalido_400(client, repo, admin_token):
    _seed_pendiente(repo)
    r = client.post(
        "/moderacion/publicaciones/pub-1",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"estado": "publicado_ya"},
    )
    assert r.status_code == 400


def test_publicacion_inexistente_404(client, admin_token):
    r = client.post(
        "/moderacion/publicaciones/no-existe",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"estado": "aprobado"},
    )
    assert r.status_code == 404


# ---- Moderación de comercios (alta de campo) ----
def test_listar_comercios_por_verificar(client, repo, admin_token):
    repo.seed_comercio(id="cm-1", slug="campo1", nombre="Campo 1", whatsapp="591", verificado=False)
    repo.seed_comercio(id="cm-2", slug="ver1", nombre="Verif", whatsapp="591", verificado=True)
    r = client.get("/moderacion/comercios?verificado=false", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert [c["id"] for c in items] == ["cm-1"]


def test_verificar_comercio(client, repo, admin_token):
    repo.seed_comercio(id="cm-1", slug="campo1", nombre="Campo 1", whatsapp="591", verificado=False)
    r = client.post("/moderacion/comercios/cm-1/verificar", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert repo.comercios["cm-1"]["verificado"] is True


def test_rechazar_comercio_lo_desactiva(client, repo, admin_token):
    repo.seed_comercio(id="cm-1", slug="campo1", nombre="Campo 1", whatsapp="591", verificado=False)
    r = client.post("/moderacion/comercios/cm-1/rechazar", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert repo.comercios["cm-1"]["activo"] is False


def test_comercios_requiere_admin(client):
    from tests.conftest import comercio_token
    r = client.get("/moderacion/comercios", headers={"Authorization": f"Bearer {comercio_token()}"})
    assert r.status_code == 403
