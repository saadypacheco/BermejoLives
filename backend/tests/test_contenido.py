"""Contenido de la home: publicador + cotizaciones + clima + videos promo."""
from io import BytesIO

from app.core import auth


def _pub_token():
    return auth.make_publicador_token("publicador@bermejolive.com")


def _h():
    return {"Authorization": f"Bearer {_pub_token()}"}


def test_publicador_login_ok(client):
    r = client.post("/auth/publicador/login", json={"email": "publicador@bermejolive.com", "password": "publicar1234"})
    assert r.status_code == 200 and r.json()["access_token"]


def test_publicador_login_bad(client):
    assert client.post("/auth/publicador/login", json={"email": "x", "password": "y"}).status_code == 401


def test_editar_cotizacion(client, repo):
    r = client.put("/contenido/cotizaciones/usd_bob", headers=_h(), json={"valor": 13.5})
    assert r.status_code == 200
    assert r.json()["cotizacion"]["valor"] == 13.5


def test_cotizacion_inexistente_404(client):
    assert client.put("/contenido/cotizaciones/nope", headers=_h(), json={"valor": 1}).status_code == 404


def test_cotizacion_sin_auth_401(client):
    assert client.put("/contenido/cotizaciones/usd_bob", json={"valor": 1}).status_code == 401


def test_override_clima(client, repo):
    r = client.put("/contenido/clima", headers=_h(), json={"temp_c": 30, "descripcion": "Calor", "horas": 6})
    assert r.status_code == 200
    assert repo.clima["temp_c"] == 30 and repo.clima["fuente"] == "manual" and repo.clima["override_hasta"]


def test_video_promo_upload_list_delete(client, repo):
    files = {"video": ("z.mp4", BytesIO(b"\x00\x00\x00\x18ftypmp42" + b"0" * 32), "video/mp4")}
    r = client.post("/contenido/videos-promo", headers=_h(), files=files, data={"titulo": "Centro"})
    assert r.status_code == 200
    vid = r.json()["video"]["id"]
    assert len(client.get("/contenido/videos-promo", headers=_h()).json()["items"]) == 1
    assert client.delete(f"/contenido/videos-promo/{vid}", headers=_h()).status_code == 200
    assert client.get("/contenido/videos-promo", headers=_h()).json()["items"] == []


def test_video_promo_no_es_video_400(client):
    files = {"video": ("z.jpg", BytesIO(b"no"), "image/jpeg")}
    assert client.post("/contenido/videos-promo", headers=_h(), files=files).status_code == 400


def test_admin_tambien_publica(client):
    tok = auth.make_token("admin@bermejolive.com", rol="admin")
    r = client.put("/contenido/cotizaciones/usd_bob", headers={"Authorization": f"Bearer {tok}"}, json={"valor": 14})
    assert r.status_code == 200


def test_editar_red(client, repo):
    r = client.put("/contenido/redes/tiktok", headers=_h(), json={"url": "https://tiktok.com/@encontralo"})
    assert r.status_code == 200
    assert r.json()["red"]["url"].endswith("encontralo")


def test_red_inexistente_404(client):
    assert client.put("/contenido/redes/nope", headers=_h(), json={"url": "x"}).status_code == 404
