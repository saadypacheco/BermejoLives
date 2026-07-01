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
