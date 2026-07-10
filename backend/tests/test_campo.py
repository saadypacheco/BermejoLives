"""Agente de campo: login + alta rápida de comercio."""
from io import BytesIO

from PIL import Image


def _agente_token(client):
    r = client.post("/auth/campo/login", json={"email": "agente@bermejolive.com", "password": "campo1234"})
    assert r.status_code == 200
    return r.json()["access_token"]


def _foto_test():
    """Imagen mínima válida para pasar la validación de _procesar_imagen."""
    buf = BytesIO()
    Image.new("RGB", (10, 10), color="red").save(buf, format="JPEG")
    buf.seek(0)
    return {"foto": ("test.jpg", buf, "image/jpeg")}


def test_campo_login_ok(client):
    assert _agente_token(client)


def test_campo_login_malo(client):
    r = client.post("/auth/campo/login", json={"email": "agente@bermejolive.com", "password": "x"})
    assert r.status_code == 401


def test_alta_campo_crea_comercio_pendiente(client, repo):
    token = _agente_token(client)
    r = client.post(
        "/campo/comercio",
        headers={"Authorization": f"Bearer {token}"},
        data={"nombre": "Gomería El Rápido", "whatsapp": "59170002222",
              "rubro_slugs": ["gomeria", "servicios"],
              "modalidad": "minorista", "lat": "-22.7361", "lng": "-64.3433",
              "descripcion": "Gomería y venta de repuestos de moto",
              "facebook_url": "https://facebook.com/gomeria"},
        files=_foto_test(),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["comercio"]["slug"] == "gomeria-el-rapido"
    assert body["comercio"]["gps"] is True
    assert body["comercio"]["rubros"] == 2
    com = repo.comercios[list(repo.comercios)[-1]]
    assert com["modalidad"] == "minorista"
    assert com["verificado"] is False
    assert com["rubro_id"] == "rub-3"          # gomeria (principal = primero)
    assert com["rubros"] == ["rub-3", "rub-4"]  # gomeria + servicios
    assert com["facebook_url"] == "https://facebook.com/gomeria"
    assert com["lat"] == -22.7361


def test_mis_comercios_lista_solo_los_del_agente(client, repo):
    token = _agente_token(client)
    client.post(
        "/campo/comercio",
        headers={"Authorization": f"Bearer {token}"},
        data={"nombre": "Gomería El Rápido", "whatsapp": "59170002222",
              "modalidad": "minorista", "lat": "-22.7361", "lng": "-64.3433",
              "descripcion": "Gomería y venta de repuestos de moto"},
        files=_foto_test(),
    )
    # Un comercio de otro origen (no cargado por este agente) no debe aparecer
    repo.crear_comercio({"nombre": "Otro", "slug": "otro", "cargado_por": "otro@x.com"})

    r = client.get("/campo/mis-comercios", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["nombre"] == "Gomería El Rápido"


def test_mis_comercios_sin_token_401(client):
    r = client.get("/campo/mis-comercios")
    assert r.status_code == 401


def _crear_comercio_propio(client, token):
    r = client.post(
        "/campo/comercio",
        headers={"Authorization": f"Bearer {token}"},
        data={"nombre": "Gomería El Rápido", "whatsapp": "59170002222",
              "modalidad": "minorista", "lat": "-22.7361", "lng": "-64.3433",
              "descripcion": "Gomería y venta de repuestos de moto"},
        files=_foto_test(),
    )
    return r.json()["comercio"]["id"]


def test_editar_mi_comercio_ok(client, repo):
    token = _agente_token(client)
    # crear_comercio no devuelve el id real usado internamente en /campo/comercio,
    # así que lo tomamos del repo (único comercio creado hasta acá)
    _crear_comercio_propio(client, token)
    comercio_id = list(repo.comercios)[-1]

    r = client.patch(
        f"/campo/mis-comercios/{comercio_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"nombre": "Gomería El Rápido (editado)", "rubro_slugs": ["servicios"]},
    )
    assert r.status_code == 200, r.text
    assert repo.comercios[comercio_id]["nombre"] == "Gomería El Rápido (editado)"
    assert repo.comercios[comercio_id]["rubros"] == ["servicios"]


def test_editar_comercio_ajeno_404(client, repo):
    token = _agente_token(client)
    otro = repo.crear_comercio({"nombre": "Otro", "slug": "otro", "cargado_por": "otro@x.com"})
    r = client.patch(
        f"/campo/mis-comercios/{otro['id']}",
        headers={"Authorization": f"Bearer {token}"},
        json={"nombre": "Hackeado"},
    )
    assert r.status_code == 404


def test_actualizar_foto_mi_comercio_ok(client, repo):
    token = _agente_token(client)
    _crear_comercio_propio(client, token)
    comercio_id = list(repo.comercios)[-1]
    url_original = repo.comercios[comercio_id]["portada_url"]

    r = client.post(
        f"/campo/mis-comercios/{comercio_id}/foto",
        headers={"Authorization": f"Bearer {token}"},
        files=_foto_test(),
    )
    assert r.status_code == 200, r.text
    assert repo.comercios[comercio_id]["portada_url"] != url_original


def test_actualizar_foto_comercio_ajeno_404(client, repo):
    token = _agente_token(client)
    otro = repo.crear_comercio({"nombre": "Otro", "slug": "otro", "cargado_por": "otro@x.com"})
    r = client.post(
        f"/campo/mis-comercios/{otro['id']}/foto",
        headers={"Authorization": f"Bearer {token}"},
        files=_foto_test(),
    )
    assert r.status_code == 404


def test_eliminar_mi_comercio_es_baja_logica(client, repo):
    token = _agente_token(client)
    _crear_comercio_propio(client, token)
    comercio_id = list(repo.comercios)[-1]

    r = client.delete(f"/campo/mis-comercios/{comercio_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    # Sigue existiendo el registro (baja lógica, no DELETE real)
    assert comercio_id in repo.comercios
    assert repo.comercios[comercio_id]["activo"] is False
    # Y ya no aparece en el listado del agente
    r2 = client.get("/campo/mis-comercios", headers={"Authorization": f"Bearer {token}"})
    assert all(i["id"] != comercio_id for i in r2.json()["items"])


def test_eliminar_comercio_ajeno_404(client, repo):
    token = _agente_token(client)
    otro = repo.crear_comercio({"nombre": "Otro", "slug": "otro", "cargado_por": "otro@x.com"})
    r = client.delete(f"/campo/mis-comercios/{otro['id']}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404
    assert repo.comercios[otro["id"]].get("activo", True) is True


def test_alta_campo_sin_token_401(client):
    r = client.post("/campo/comercio", data={"nombre": "X", "whatsapp": "1", "rubro_slug": "otros"})
    assert r.status_code == 401


def test_alta_campo_modalidad_invalida_400(client):
    token = _agente_token(client)
    r = client.post(
        "/campo/comercio",
        headers={"Authorization": f"Bearer {token}"},
        data={"nombre": "X", "whatsapp": "1", "rubro_slug": "otros", "modalidad": "revendedor"},
        files=_foto_test(),
    )
    assert r.status_code == 400
