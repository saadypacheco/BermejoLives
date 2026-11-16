"""Importar Overture Maps a Importados (docs/vigia-fuentes.md, fase 2). Nunca sale a S3: `leer` es un falso que
devuelve filas con la forma de las de DuckDB."""
import uuid

import pytest

from app.core import auth
from app.services import importar_overture as io
from app.services import tarjetas

LAT, LNG = -22.7361, -64.3433          # el centro de cualquier ciudad del repo falso


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


def cruda(i=1, **extra):
    base = {"id": f"08f{i:013d}", "nombre": f"Restaurante Prueba {i}", "categoria": "restaurant",
            "taxonomia": "restaurant", "confianza": 0.8, "lat": LAT + i * 0.001, "lng": LNG,
            "phones": ["+591 72957024"], "websites": ["https://prueba.com.bo"],
            "socials": ["https://www.facebook.com/123456"], "emails": ["hola@prueba.com.bo"],
            "addresses": [{"freeform": "Calle Sucre 123", "locality": "Bermejo", "postcode": None, "region": None,
                           "country": "BO"}],
            "operating_status": None, "fuentes": ["meta"], "licencias": ["CDLA-Permissive-2.0"]}
    return {**base, **extra}


def correr(repo, crudas, *args):
    salida: list[str] = []
    codigo = io.main(["--ciudad", "bermejo", *args], repo, leer=lambda *a, **k: crudas, mostrar=salida.append)
    return codigo, "\n".join(salida)


# ───────────────────────────────────────────── normalizar

def test_armar_fila_reparte_telefono_redes_y_web():
    f = io.armar_fila(cruda(), ciudad_id="c1", release=io.RELEASE, rubros_validos=lambda s: True)
    assert f["fuente"] == "overture" and f["fuente_id"] == "overture:08f0000000000001"
    assert f["whatsapp"] == "59172957024" and f["telefono"] is None          # un celular va a WhatsApp
    assert f["website"] == "https://prueba.com.bo"
    assert f["tags"]["overture"]["redes_por_red"] == {"facebook_url": "https://www.facebook.com/123456"}
    assert f["rubro_slug"] == "restaurantes" and f["estado"] == "nuevo" and f["ubicacion"] == "aproximada"
    assert f["direccion"] == "Calle Sucre 123" and f["email"] == "hola@prueba.com.bo"
    assert f["horario"] is None and f["duplicado_de"] is None
    assert "Overture Maps" in f["texto_leido"] and "confianza 0.80" in f["texto_leido"]


def test_facebook_en_websites_no_queda_como_sitio_web():
    f = io.armar_fila(cruda(websites=["https://facebook.com/milocal"], socials=[]), ciudad_id="c",
                      release=io.RELEASE, rubros_validos=lambda s: True)
    assert f["website"] is None
    assert f["tags"]["overture"]["redes_por_red"]["facebook_url"] == "https://facebook.com/milocal"


@pytest.mark.parametrize("url", ["http://dario.ugarte.54/", "https://www.google.com/maps/place/x", "nada"])
def test_web_que_no_es_un_sitio_se_descarta(url):
    assert io.web_propia(url) is None


def test_direccion_que_es_un_enlace_de_google_se_descarta():
    f = io.armar_fila(cruda(addresses=[{"freeform": "https://www.google.com/maps/place/Resto"}]), ciudad_id="c",
                      release=io.RELEASE, rubros_validos=lambda s: True)
    assert f["direccion"] is None


def test_rubro_que_no_existe_queda_vacio():
    f = io.armar_fila(cruda(), ciudad_id="c", release=io.RELEASE, rubros_validos=lambda s: False)
    assert f["rubro_slug"] is None


@pytest.mark.parametrize("extra,motivo", [
    ({"nombre": " "}, "sin_nombre"),
    ({"operating_status": "permanently_closed"}, "cerrado"),
    ({"categoria": "christian_place_of_worship"}, "no_comercio"),
    ({"categoria": "park"}, "no_comercio"),
    ({}, None),
])
def test_motivo_descarte(extra, motivo):
    assert io.motivo_descarte(cruda(**extra)) == motivo


def test_red_de():
    assert io.red_de("https://m.facebook.com/x") == "facebook_url"
    assert io.red_de("instagram.com/x") == "instagram_url"
    assert io.red_de("https://www.tiktok.com/@x") == "tiktok_url"
    assert io.red_de("https://notfacebook.com") is None


# ───────────────────────────────────────────── el comando

def test_simulacion_no_guarda_nada(repo):
    antes = len(repo.importados)
    codigo, salida = correr(repo, [cruda(1), cruda(2), cruda(3, categoria="park")], "--dry-run")
    assert codigo == 0
    assert len(repo.importados) == antes
    assert "Entrarían" in salida and "SIMULACIÓN" in salida and "no_comercio: 1" in salida


def test_carga_y_volver_a_correr_no_duplica(repo):
    codigo, salida = correr(repo, [cruda(1), cruda(2)])
    assert codigo == 0
    nuevos = [f for f in repo.importados.values() if f["fuente"] == "overture"]
    assert len(nuevos) == 2 and all(f["estado"] == "nuevo" for f in nuevos)
    codigo, salida = correr(repo, [cruda(1), cruda(2)])
    assert len([f for f in repo.importados.values() if f["fuente"] == "overture"]) == 2
    assert "Ya estaban:              2" in salida


def test_marca_repetido_por_nombre_y_distancia(repo):
    cid = str(uuid.uuid4())
    repo.comercios[cid] = {"id": cid, "nombre": "Restaurante Prueba 1", "lat": LAT + 0.001, "lng": LNG,
                           "ciudad_id": "ciudad-bermejo", "activo": True, "slug": "x", "whatsapp": None}
    correr(repo, [cruda(1, phones=[])])
    fila = next(f for f in repo.importados.values() if f["fuente"] == "overture")
    assert fila["duplicado_de"] == cid


def test_limite_carga_primero_los_mas_confiables(repo):
    correr(repo, [cruda(1, confianza=0.55), cruda(2, confianza=0.95)], "--limite", "1")
    filas = [f for f in repo.importados.values() if f["fuente"] == "overture"]
    assert len(filas) == 1 and filas[0]["nombre"] == "Restaurante Prueba 2"


def test_argumentos_invalidos(repo):
    assert io.main(["--ciudad", "bermejo", "--confianza", "2"], repo, leer=lambda *a, **k: []) == 2
    assert io.main(["--ciudad", "bermejo", "--release", "latest; drop"], repo, leer=lambda *a, **k: []) == 2


def test_si_s3_no_contesta_sale_con_error(repo):
    def caido(*a, **k):
        raise OSError("sin red")
    assert io.main(["--ciudad", "bermejo"], repo, leer=caido, mostrar=lambda _: None) == 1


# ───────────────────────────────────────────── promover

def test_promover_overture_lleva_las_redes_a_su_campo(client, repo, datos):
    correr(repo, [cruda(1)])
    iid = next(k for k, f in repo.importados.items() if f["fuente"] == "overture")
    r = client.post(f"/admin/importados/{iid}/promover", json={}, headers=datos)
    assert r.status_code == 200, r.text
    com = repo.comercios[r.json()["comercio"]["id"]]
    assert com["facebook_url"] == "https://www.facebook.com/123456"
    assert com["sitio_web"] == "https://prueba.com.bo"
    assert com["whatsapp"] == "59172957024" and com["confiable"] is False
    assert com["cargado_por"] == "import:overture"


def test_listado_filtra_por_overture(client, repo, datos):
    correr(repo, [cruda(1)])
    r = client.get("/admin/importados", params={"fuente": "overture"}, headers=datos)
    assert r.status_code == 200, r.text
    assert [i["fuente"] for i in r.json()["items"]] == ["overture"]
