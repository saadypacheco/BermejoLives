"""Lugares para visitar (docs/lugares-turismo.md): la parte de API del backend.

- `GET /admin/importados?rubro=` y los campos `subcategoria` / `fuente_url` de cada item.
- `PATCH /admin/importados/{id}` con `subcategoria` (lista fija) y `horario`.
- `POST /admin/importados/{id}/promover` con un rubro NO comercial (criterio 5).
- `GET /campo/mis-comercios` suma `comercial`.
"""
import pytest

from app.core import auth
from app.services import importar_turismo_lugares as lug
from app.services import que_hay_aca, tarjetas


LUGAR_ID = "00000000-0000-4000-8000-000000000001"
NEGOCIO_ID = "00000000-0000-4000-8000-000000000002"


def h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def datos():
    return h(auth.make_token("datos@uruku.bo", rol="x", roles=["x"], permisos=["datos"]))


@pytest.fixture(autouse=True)
def _sin_red(monkeypatch):
    tarjetas.reiniciar_cache()

    def sin_red(params):
        raise AssertionError("Nominatim: un test salió a la red")

    monkeypatch.setattr(tarjetas, "_pedir_nominatim", sin_red)
    yield
    tarjetas.reiniciar_cache()


@pytest.fixture
def lugar(repo):
    """Un lugar en la sala de espera, como lo deja `importar_turismo_lugares`."""
    repo.rubros["para-visitar"] = "rub-pv"
    repo.rubros["hospedaje"] = "rub-hosp"
    repo.importados[LUGAR_ID] = {
        "id": LUGAR_ID, "fuente": "turismo", "fuente_id": "turismo:tarijaturismo.com:post:1", "estado": "nuevo",
        "ciudad_id": "ciudad-tarija", "nombre": "Plaza Mayor", "categoria": "plazas-parques-y-miradores",
        "rubro_slug": "para-visitar", "subcategoria": "Plaza", "lat": -21.5355, "lng": -64.7296,
        "telefono": "+591 4 663 6680", "whatsapp": None, "website": None, "email": None,
        "direccion": "Calle Ficticia 1", "horario": "Abierto 24 horas",
        "fuente_url": "https://tarijaturismo.com/plaza-mayor/", "ubicacion": "aproximada", "foto_ref": None,
        "tags": {"wp_id": 1, "categorias": []}, "duplicado_de": None,
    }
    repo.importados[NEGOCIO_ID] = {
        "id": NEGOCIO_ID, "fuente": "turismo", "fuente_id": "turismo:tarijaturismo.com:negocio", "estado": "nuevo",
        "ciudad_id": "ciudad-tarija", "nombre": "Hotel X", "rubro_slug": "hospedaje", "lat": -21.5, "lng": -64.7,
        "telefono": "+591 4 664 8444", "whatsapp": "59175111885", "direccion": "Calle 2", "tags": {},
    }
    return LUGAR_ID


# ───────────────────────────────────────────────────────────── el listado

def test_el_listado_filtra_por_rubro_y_trae_subcategoria_y_fuente_url(client, repo, datos, lugar):
    r = client.get("/admin/importados?fuente=turismo&rubro=para-visitar", headers=datos)
    assert r.status_code == 200
    items = r.json()["items"]
    assert [i["nombre"] for i in items] == ["Plaza Mayor"]
    assert items[0]["subcategoria"] == "Plaza" and items[0]["fuente_url"] == "https://tarijaturismo.com/plaza-mayor/"
    assert items[0]["categoria"] == "plazas-parques-y-miradores" and "foto_ref" not in items[0]
    # sin el filtro salen los dos; con otro rubro, sólo ése; con uno que no existe, ninguno
    assert len(client.get("/admin/importados?fuente=turismo", headers=datos).json()["items"]) == 2
    solo_hotel = client.get("/admin/importados?rubro=hospedaje", headers=datos).json()["items"]
    assert [i["nombre"] for i in solo_hotel] == ["Hotel X"]
    assert client.get("/admin/importados?rubro=nada", headers=datos).json()["items"] == []


def test_el_listado_exige_el_permiso_datos(client, lugar):
    sin = h(auth.make_token("otro@uruku.bo", rol="x", roles=["x"], permisos=["comercios"]))
    assert client.get("/admin/importados?rubro=para-visitar", headers=sin).status_code == 403
    assert client.get("/admin/importados?rubro=para-visitar").status_code in (401, 403)


# ───────────────────────────────────────────────────────────── el PATCH

def test_el_patch_corrige_subcategoria_y_horario(client, repo, datos, lugar):
    r = client.patch(f"/admin/importados/{lugar}", json={"subcategoria": "Parque", "horario": "  Lunes a viernes  "},
                     headers=datos)
    assert r.status_code == 200, r.text
    assert r.json()["subcategoria"] == "Parque" and r.json()["horario"] == "Lunes a viernes"
    assert repo.importados[lugar]["subcategoria"] == "Parque"
    # vacío los borra
    r = client.patch(f"/admin/importados/{lugar}", json={"subcategoria": "", "horario": None}, headers=datos)
    assert r.status_code == 200 and r.json()["subcategoria"] is None and r.json()["horario"] is None


@pytest.mark.parametrize("tipo", lug.SUBCATEGORIAS)
def test_el_patch_acepta_cada_tipo_de_la_lista(client, datos, lugar, tipo):
    assert client.patch(f"/admin/importados/{lugar}", json={"subcategoria": tipo}, headers=datos).status_code == 200


def test_el_patch_rechaza_un_tipo_fuera_de_la_lista_y_horario_demasiado_largo(client, repo, datos, lugar):
    r = client.patch(f"/admin/importados/{lugar}", json={"subcategoria": "Discoteca"}, headers=datos)
    assert r.status_code == 400 and "Plaza" in r.json()["detail"]
    assert repo.importados[lugar]["subcategoria"] == "Plaza"
    assert client.patch(f"/admin/importados/{lugar}", json={"horario": "x" * 301}, headers=datos).status_code == 422


def test_el_patch_sigue_siendo_solo_para_los_nuevos(client, repo, datos, lugar):
    repo.importados[lugar]["estado"] = "descartado"
    assert client.patch(f"/admin/importados/{lugar}", json={"subcategoria": "Parque"}, headers=datos).status_code == 409


# ───────────────────────────────────────────────────────────── promover (criterio 5)

def test_promover_un_lugar_crea_el_comercio_no_comercial_y_marca_el_rubro_revisado(client, repo, datos, lugar):
    r = client.post(f"/admin/importados/{lugar}/promover", json={}, headers=datos)
    assert r.status_code == 200, r.text
    com = repo.comercios[r.json()["comercio"]["id"]]
    assert com["nombre"] == "Plaza Mayor" and com["subcategoria"] == "Plaza"
    assert com["horario"] == "Abierto 24 horas" and com["direccion"] == "Calle Ficticia 1"
    assert com["fuente_url"] == "https://tarijaturismo.com/plaza-mayor/"
    assert com["telefono"] == "+591 4 663 6680" and com["whatsapp"] is None
    assert com["cargado_por"] == "import:turismo" and com["verificado"] is False and com["confiable"] is False
    assert com["activo"] is True and com["lat"] == -21.5355 and com["ciudad_id"] == "ciudad-tarija"
    assert com["rubro_revisado_por"] == "datos@uruku.bo" and com["rubro_revisado_at"]      # lo masivo no lo toca
    assert repo.comercios[com["id"]]["rubros"] == ["para-visitar"]
    assert repo.importados[lugar]["estado"] == "promovido" and repo.importados[lugar]["comercio_id"] == com["id"]


def test_promover_un_lugar_no_pasa_el_whatsapp_del_importado_pero_si_el_del_body(client, repo, datos, lugar):
    repo.importados[lugar]["whatsapp"] = "59170011122"              # aunque alguien lo hubiera dejado en la fila
    com = repo.comercios[client.post(f"/admin/importados/{lugar}/promover", json={}, headers=datos)
                         .json()["comercio"]["id"]]
    assert com["whatsapp"] is None
    repo.importados[lugar]["estado"] = "nuevo"
    com2 = repo.comercios[client.post(f"/admin/importados/{lugar}/promover", json={"whatsapp": "70099988"},
                                      headers=datos).json()["comercio"]["id"]]
    assert com2["whatsapp"] == "59170099988"


def test_si_la_persona_le_cambia_el_rubro_a_comercial_se_promueve_como_negocio(client, repo, datos, lugar):
    """Un centro cultural que resulta ser un hotel: mismo botón, comercio común (sin subcategoría ni enlace)."""
    r = client.post(f"/admin/importados/{lugar}/promover", json={"rubro_slug": "hospedaje", "nombre": "Hotel Plaza"},
                    headers=datos)
    com = repo.comercios[r.json()["comercio"]["id"]]
    assert com["nombre"] == "Hotel Plaza" and "subcategoria" not in com and "fuente_url" not in com
    assert "rubro_revisado_at" not in com and com["whatsapp"] is None and com["confiable"] is False


def test_promover_un_negocio_de_turismo_no_cambia(client, repo, datos, lugar):
    r = client.post(f"/admin/importados/{NEGOCIO_ID}/promover", json={}, headers=datos)
    com = repo.comercios[r.json()["comercio"]["id"]]
    assert com["whatsapp"] == "59175111885" and com["telefono"] == "+591 4 664 8444"
    assert "fuente_url" not in com and "rubro_revisado_at" not in com and com["confiable"] is False


def test_promover_un_lugar_sin_punto_sigue_dando_400(client, repo, datos, lugar):
    repo.importados[lugar].update(lat=None, lng=None)
    assert client.post(f"/admin/importados/{lugar}/promover", json={}, headers=datos).status_code == 400


# ───────────────────────────────────────────────────────────── «Qué hay acá»: comercial

def test_comercial_de():
    no = {"rubros": {"slug": "para-visitar", "nombre": "Para visitar", "comercial": False}}
    assert que_hay_aca.comercial_de(no) is False
    assert que_hay_aca.comercial_de({"rubros": {"slug": "ropa", "nombre": "Ropa", "comercial": True}}) is True
    assert que_hay_aca.comercial_de({"rubros": {"slug": "ropa", "nombre": "Ropa"}}) is True     # sin la marca = comercio
    assert que_hay_aca.comercial_de({"rubros": None}) is True and que_hay_aca.comercial_de({}) is True


def test_mis_comercios_suma_comercial(client, repo):
    agente = auth.make_agente_token("agente@uruku.bo", ciudad_slug="bermejo")
    base = {"whatsapp": None, "activo": True, "plan": "gratis", "ciudad_id": "ciu-1", "cargado_por": "o@uruku.bo"}
    repo.crear_comercio({**base, "nombre": "Un museo", "slug": "museo",
                         "rubros": {"slug": "para-visitar", "nombre": "Para visitar", "comercial": False}})
    repo.crear_comercio({**base, "nombre": "Una tienda", "slug": "tienda",
                         "rubros": {"slug": "ropa", "nombre": "Ropa", "comercial": True}})
    repo.crear_comercio({**base, "nombre": "Sin rubro", "slug": "sin"})
    r = client.get("/campo/mis-comercios", headers=h(agente))
    assert r.status_code == 200
    items = {i["nombre"]: i for i in r.json()["items"]}
    assert items["Un museo"]["comercial"] is False and items["Un museo"]["rubro_slug"] == "para-visitar"
    assert items["Una tienda"]["comercial"] is True and items["Sin rubro"]["comercial"] is True
    uno = client.get(f"/campo/mis-comercios/{items['Un museo']['id']}", headers=h(agente))
    assert uno.status_code == 200 and uno.json()["comercio"]["comercial"] is False
