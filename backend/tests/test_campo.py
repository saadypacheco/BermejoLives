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
    # El fake guarda SLUGS (`set_comercio_rubros` traduce los ids que recibe):
    # antes guardaba lo que le mandaran y `list_comercio_rubros_todos` devolvía
    # 'rub-3' como si fuera un slug, escondiendo errores reales.
    assert com["rubros"] == ["gomeria", "servicios"]
    assert com["facebook_url"] == "https://facebook.com/gomeria"
    assert com["lat"] == -22.7361


def test_lat_vacia_y_lat_ausente_son_lo_mismo_para_el_backend(client):
    """La trampa que retuvo seis altas de campo en la cola offline.

    El agente veía las coordenadas guardadas en el detalle de la cola y el
    servidor igual respondía "Falta la ubicación": para el backend, un `lat`
    VACÍO y un `lat` que no vino son indistinguibles. Queda fijado acá para que
    nadie "arregle" el mensaje sin darse cuenta de que son dos casos distintos
    del lado del cliente — uno es un dato perdido y el otro un dato mal enviado.
    """
    token = _agente_token(client)
    h = {"Authorization": f"Bearer {token}"}
    base = {"nombre": "X", "modalidad": "minorista", "lng": "-64.3433"}

    vacia = client.post("/campo/comercio", headers=h, data={**base, "lat": ""})
    ausente = client.post("/campo/comercio", headers=h, data=base)
    assert vacia.status_code == 400 and ausente.status_code == 400
    assert vacia.json()["detail"] == ausente.json()["detail"] == "Falta la ubicación"

    # Y con coma decimal no es 400 sino 422, con el detalle como LISTA — que en
    # la pantalla del agente llegaba como "[object Object]".
    coma = client.post("/campo/comercio", headers=h, data={**base, "lat": "-22,7361"})
    assert coma.status_code == 422
    assert isinstance(coma.json()["detail"], list)


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


def test_editar_mi_comercio_actualiza_email(client, repo):
    token = _agente_token(client)
    _crear_comercio_propio(client, token)
    comercio_id = list(repo.comercios)[-1]

    r = client.patch(
        f"/campo/mis-comercios/{comercio_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "contacto@negocio.com"},
    )
    assert r.status_code == 200, r.text
    assert repo.comercios[comercio_id]["email"] == "contacto@negocio.com"


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


# ---------------- Galería (fotos / videos) ----------------
def _video_file():
    return {"video": ("clip.mp4", BytesIO(b"\x00\x00\x00\x18ftypmp42" + b"0" * 64), "video/mp4")}


def test_agregar_y_listar_foto(client, repo):
    token = _agente_token(client)
    cid = _crear_comercio_propio(client, token)
    h = {"Authorization": f"Bearer {token}"}
    r = client.post(f"/campo/mis-comercios/{cid}/fotos", headers=h, files=_foto_test())
    assert r.status_code == 200
    assert r.json()["foto"]["comercio_id"] == cid
    assert r.json()["foto"]["thumb_url"]
    assert len(client.get(f"/campo/mis-comercios/{cid}/fotos", headers=h).json()["items"]) == 1


def test_borrar_foto(client, repo):
    token = _agente_token(client)
    cid = _crear_comercio_propio(client, token)
    h = {"Authorization": f"Bearer {token}"}
    fid = client.post(f"/campo/mis-comercios/{cid}/fotos", headers=h, files=_foto_test()).json()["foto"]["id"]
    assert client.delete(f"/campo/mis-comercios/{cid}/fotos/{fid}", headers=h).status_code == 200
    assert client.get(f"/campo/mis-comercios/{cid}/fotos", headers=h).json()["items"] == []


def test_limite_10_fotos(client, repo):
    token = _agente_token(client)
    cid = _crear_comercio_propio(client, token)
    h = {"Authorization": f"Bearer {token}"}
    for _ in range(10):
        assert client.post(f"/campo/mis-comercios/{cid}/fotos", headers=h, files=_foto_test()).status_code == 200
    assert client.post(f"/campo/mis-comercios/{cid}/fotos", headers=h, files=_foto_test()).status_code == 409


def test_foto_comercio_ajeno_404(client, repo):
    token = _agente_token(client)
    otro = repo.crear_comercio({"nombre": "Otro", "slug": "otro-gal", "cargado_por": "otro@x.com"})
    r = client.post(f"/campo/mis-comercios/{otro['id']}/fotos", headers={"Authorization": f"Bearer {token}"}, files=_foto_test())
    assert r.status_code == 404


def test_agregar_video_ok(client, repo):
    token = _agente_token(client)
    cid = _crear_comercio_propio(client, token)
    h = {"Authorization": f"Bearer {token}"}
    r = client.post(f"/campo/mis-comercios/{cid}/videos", headers=h, files=_video_file(), data={"duracion_seg": "45"})
    assert r.status_code == 200
    assert r.json()["video"]["duracion_seg"] == 45
    assert len(client.get(f"/campo/mis-comercios/{cid}/videos", headers=h).json()["items"]) == 1


def test_video_no_es_video_400(client, repo):
    token = _agente_token(client)
    cid = _crear_comercio_propio(client, token)
    r = client.post(f"/campo/mis-comercios/{cid}/videos", headers={"Authorization": f"Bearer {token}"},
                    files={"video": ("x.jpg", BytesIO(b"nope"), "image/jpeg")})
    assert r.status_code == 400


def test_limite_5_videos(client, repo):
    token = _agente_token(client)
    cid = _crear_comercio_propio(client, token)
    h = {"Authorization": f"Bearer {token}"}
    for _ in range(5):
        assert client.post(f"/campo/mis-comercios/{cid}/videos", headers=h, files=_video_file()).status_code == 200
    assert client.post(f"/campo/mis-comercios/{cid}/videos", headers=h, files=_video_file()).status_code == 409
