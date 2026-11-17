"""Completar el existente, «no es el mismo», promover sin ubicación y subcategoría legible
(docs/turismo-home-y-repetidos.md §1 y §2; criterios 1 a 4).

- `GET  /admin/importados/{id}/comparar`
- `POST /admin/importados/{id}/completar`
- `POST /admin/importados/{id}/no-es-repetido`
- `POST /admin/importados/{id}/promover` con `sin_ubicacion` y la subcategoría legible de turismo.
"""
import pytest

from app.core import auth
from app.services import calles_mapa, completar_importado as ci, importar_turismo as it, tarjetas
from app.services import subcategorias_turismo as sub


IMP = "00000000-0000-4000-8000-0000000000a1"
IMP2 = "00000000-0000-4000-8000-0000000000a2"


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
def invalidadas(monkeypatch):
    """Las ciudades a las que se les invalidó el mapa de calles."""
    vistas = []
    monkeypatch.setattr(calles_mapa, "invalidar", lambda ciudad_id: vistas.append(ciudad_id))
    return vistas


@pytest.fixture
def existente(repo):
    """El comercio que cargó alguien en la calle: con punto exacto, foto, y casi nada más."""
    for slug in ("otros", "turismo", "para-visitar", "hospedaje", "taxis"):
        repo.rubros.setdefault(slug, f"rub-{slug}")
    return repo.seed_comercio(
        id="com-exist", nombre="Hotel Los Parrales", slug="hotel-los-parrales", ciudad_id="ciudad-tarija",
        activo=True, lat=-21.5301, lng=-64.7302, direccion=None, telefono=None, whatsapp=None, sitio_web=None,
        email=None, horario=None, fuente_url=None, subcategoria=None, portada_url="https://x/foto.jpg",
        verificado=True, confiable=True, cargado_por="agente:ana", rubros=["hospedaje"])


def _importado(repo, **kw):
    fila = {
        "id": IMP, "fuente": "turismo", "fuente_id": "turismo:tarijaturismo.com:hotel-los-parrales|calle-1",
        "estado": "nuevo", "ciudad_id": "ciudad-tarija", "nombre": "Hotel Los Parrales", "categoria": "hoteles",
        "rubro_slug": "hospedaje", "lat": -21.5312, "lng": -64.7311, "telefono": "+591 4 664 8444",
        "whatsapp": "59175111885", "website": "https://parrales.example.com", "email": "info@parrales.example.com",
        "direccion": "Calle Ficticia 123", "horario": "Todos los días", "fuente_url": "https://tarijaturismo.com/p/",
        "subcategoria": None, "tags": {"turismo": {"seccion": "donde-dormir", "subcategoria": "hoteles"}},
        "ubicacion": "aproximada", "foto_ref": None, "duplicado_de": "com-exist", "comercio_id": None,
        "motivo": None, **kw,
    }
    repo.importados[fila["id"]] = fila
    return fila


@pytest.fixture
def imp(repo, existente):
    return _importado(repo)


def completar(client, datos, importado=IMP, **body):
    body.setdefault("comercio_id", "com-exist")
    return client.post(f"/admin/importados/{importado}/completar", json=body, headers=datos)


# ───────────────────────────────────────────────────────────── comparar

def test_comparar_trae_los_dos_lado_a_lado_con_la_forma_del_contrato(client, datos, imp):
    r = client.get(f"/admin/importados/{IMP}/comparar", headers=datos)      # sin comercio_id: usa duplicado_de
    assert r.status_code == 200, r.text
    j = r.json()
    assert set(j) == {"comercio", "campos", "rubro_sugerido", "rubros_actuales"}
    assert set(j["comercio"]) == {"id", "nombre", "slug", "direccion", "telefono", "whatsapp", "sitio_web", "email",
                                  "horario", "lat", "lng", "tiene_foto", "fuente_url", "subcategoria", "verificado"}
    assert j["comercio"]["id"] == "com-exist" and j["comercio"]["tiene_foto"] is True
    assert j["comercio"]["verificado"] is True and "codigo" not in j["comercio"] and "confiable" not in j["comercio"]
    assert [c["campo"] for c in j["campos"]] == list(ci.CAMPOS)
    assert all(set(c) == {"campo", "actual", "nuevo", "sugerido"} for c in j["campos"])
    por = {c["campo"]: c for c in j["campos"]}
    assert por["horario"] == {"campo": "horario", "actual": None, "nuevo": "Todos los días", "sugerido": "completar"}
    assert por["nombre"]["sugerido"] == "igual"
    assert por["punto"]["actual"] == {"lat": -21.5301, "lng": -64.7302}
    assert por["punto"]["nuevo"] == {"lat": -21.5312, "lng": -64.7311} and por["punto"]["sugerido"] == "conservar"
    assert por["whatsapp"]["nuevo"] == "59175111885" and por["subcategoria"]["nuevo"] == "Hotel"
    assert j["rubro_sugerido"] == "hospedaje" and j["rubros_actuales"] == ["hospedaje"]


def test_comparar_con_otro_comercio_por_query(client, repo, datos, imp):
    repo.seed_comercio(id="com-otro", nombre="Otro", activo=True, direccion="Calle Otra 9")
    r = client.get(f"/admin/importados/{IMP}/comparar?comercio_id=com-otro", headers=datos)
    por = {c["campo"]: c for c in r.json()["campos"]}
    assert r.json()["comercio"]["id"] == "com-otro"
    assert por["direccion"] == {"campo": "direccion", "actual": "Calle Otra 9", "nuevo": "Calle Ficticia 123",
                                "sugerido": "conservar"}


def test_comparar_marca_igual_lo_que_ya_esta_aunque_se_escriba_distinto(client, repo, datos, imp, existente):
    existente.update(telefono="466-48444", sitio_web="parrales.example.com/", email="INFO@parrales.example.com",
                     whatsapp="75111885", horario="todos los  días")
    por = {c["campo"]: c["sugerido"] for c in client.get(f"/admin/importados/{IMP}/comparar", headers=datos)
           .json()["campos"]}
    assert por["telefono"] == "igual" and por["sitio_web"] == "igual" and por["email"] == "igual"
    assert por["whatsapp"] == "igual" and por["horario"] == "igual"


def test_comparar_404_400_y_permiso(client, repo, datos, imp, existente):
    assert client.get("/admin/importados/nada/comparar", headers=datos).status_code == 404
    assert client.get(f"/admin/importados/{IMP}/comparar?comercio_id=nada", headers=datos).status_code == 404
    existente["activo"] = False
    assert client.get(f"/admin/importados/{IMP}/comparar", headers=datos).status_code == 404     # inactivo
    imp["duplicado_de"] = None
    r = client.get(f"/admin/importados/{IMP}/comparar", headers=datos)                           # sin con quién
    assert r.status_code == 400 and "repetido" in r.json()["detail"]
    sin = h(auth.make_token("otro@uruku.bo", rol="x", roles=["x"], permisos=["comercios"]))
    assert client.get(f"/admin/importados/{IMP}/comparar", headers=sin).status_code == 403
    assert client.get(f"/admin/importados/{IMP}/comparar").status_code in (401, 403)


# ───────────────────────────────────────────────────────────── completar: campos

def test_completa_lo_vacio_solo_y_deja_el_importado_promovido_apuntando_al_existente(client, repo, datos, imp,
                                                                                    existente, invalidadas):
    r = completar(client, datos)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] is True and j["comercio"]["id"] == "com-exist"
    assert j["cambiados"] == ["direccion", "telefono", "whatsapp", "sitio_web", "email", "horario", "fuente_url",
                              "subcategoria"]
    c = repo.comercios["com-exist"]
    assert c["direccion"] == "Calle Ficticia 123" and c["telefono"] == "+591 4 664 8444"
    assert c["whatsapp"] == "59175111885" and c["sitio_web"] == "https://parrales.example.com"
    assert c["email"] == "info@parrales.example.com" and c["horario"] == "Todos los días"
    assert c["fuente_url"] == "https://tarijaturismo.com/p/" and c["subcategoria"] == "Hotel"
    i = repo.importados[IMP]
    assert i["estado"] == "promovido" and i["comercio_id"] == "com-exist"
    assert i["motivo"] == "completó el existente" and i["revisado_por"] == "datos@uruku.bo" and i["revisado_at"]
    assert len(repo.comercios) == 1                                  # no creó un comercio nuevo


def test_nunca_toca_foto_verificado_confiable_cargado_por_codigo_ni_slug(client, repo, datos, imp, existente):
    existente["codigo"] = "ABCD"
    antes = {k: existente[k] for k in ("portada_url", "verificado", "confiable", "cargado_por", "codigo", "slug",
                                       "nombre")}
    imp.update(nombre="Hotel Parrales S.R.L.", foto_ref="privada/tarjetas/x.jpg")
    # aunque la persona lo pida: esos campos ni siquiera se pueden nombrar
    todo = {c: "nuevo" for c in ci.CAMPOS}
    assert completar(client, datos, usar=todo).status_code == 200
    despues = repo.comercios["com-exist"]
    assert {k: despues[k] for k in antes if k != "nombre"} == {k: v for k, v in antes.items() if k != "nombre"}
    assert despues["nombre"] == "Hotel Parrales S.R.L."             # el nombre sólo cambia porque vino en `usar`
    assert despues["slug"] == "hotel-los-parrales"                  # y aun así el slug no se mueve
    for malo in ("slug", "foto", "verificado", "confiable", "codigo", "cargado_por"):
        assert completar(client, datos, importado=IMP, usar={malo: "nuevo"}).status_code == 400


def test_con_los_dos_datos_distintos_conserva_el_existente_salvo_usar_nuevo(client, repo, datos, imp, existente):
    existente.update(direccion="Av. Real 1", horario="Lunes a viernes", email="viejo@x.com")
    r = completar(client, datos, usar={"horario": "nuevo"})
    assert r.status_code == 200
    c = repo.comercios["com-exist"]
    assert c["direccion"] == "Av. Real 1" and c["email"] == "viejo@x.com"      # conservados
    assert c["horario"] == "Todos los días"                                    # lo que se pidió
    assert "direccion" not in r.json()["cambiados"] and "horario" in r.json()["cambiados"]


def test_sin_usar_nada_no_se_cambia_el_nombre(client, repo, datos, imp, existente):
    imp["nombre"] = "Otro Nombre"
    completar(client, datos)
    assert repo.comercios["com-exist"]["nombre"] == "Hotel Los Parrales"


def test_usar_rechaza_campos_desconocidos_y_valores_que_no_son_nuevo(client, datos, imp):
    r = completar(client, datos, usar={"inventado": "nuevo"})
    assert r.status_code == 400 and "inventado" in r.json()["detail"]
    assert completar(client, datos, usar={"horario": "actual"}).status_code == 422


# ───────────────────────────────────────────────────────────── completar: punto, whatsapp y teléfono

def test_el_punto_del_existente_gana_siempre(client, repo, datos, imp, existente, invalidadas):
    r = completar(client, datos, usar={"punto": "nuevo"})
    assert r.status_code == 200
    c = repo.comercios["com-exist"]
    assert (c["lat"], c["lng"]) == (-21.5301, -64.7302) and "punto" not in r.json()["cambiados"]
    assert invalidadas == []                                          # no cambió el mapa


def test_el_punto_se_copia_solo_si_el_existente_no_tiene_e_invalida_el_mapa(client, repo, datos, imp, existente,
                                                                            invalidadas):
    existente.update(lat=None, lng=None)
    r = completar(client, datos)
    c = repo.comercios["com-exist"]
    assert (c["lat"], c["lng"]) == (-21.5312, -64.7311) and "punto" in r.json()["cambiados"]
    assert invalidadas == ["ciudad-tarija"]


def test_el_whatsapp_solo_se_completa_si_el_importado_trae_un_celular_y_el_existente_no_tiene(client, repo, datos,
                                                                                            imp, existente):
    imp["whatsapp"] = "4664 8444"                                      # un fijo no abre un chat
    completar(client, datos)
    assert repo.comercios["com-exist"]["whatsapp"] is None
    imp.update(estado="nuevo", whatsapp="59175111885")
    existente["whatsapp"] = "59170000001"
    completar(client, datos, usar={"whatsapp": "nuevo"})               # ni pidiéndolo se reemplaza
    assert repo.comercios["com-exist"]["whatsapp"] == "59170000001"


def test_un_telefono_distinto_se_reemplaza_solo_con_usar_nuevo(client, repo, datos, imp, existente):
    existente["telefono"] = "+591 4 600 0000"
    completar(client, datos)
    assert repo.comercios["com-exist"]["telefono"] == "+591 4 600 0000"
    imp.update(estado="nuevo", comercio_id=None)
    completar(client, datos, usar={"telefono": "nuevo"})
    assert repo.comercios["com-exist"]["telefono"] == "+591 4 664 8444"


def test_un_telefono_que_el_existente_ya_tiene_como_whatsapp_no_se_copia(client, repo, datos, imp, existente):
    existente["whatsapp"] = "59146648444"
    imp.update(telefono="466-48444", whatsapp=None)
    r = completar(client, datos)
    assert repo.comercios["com-exist"]["telefono"] is None and "telefono" not in r.json()["cambiados"]


# ───────────────────────────────────────────────────────────── completar: rubro

def test_sumar_rubro_agrega_el_sugerido(client, repo, datos, imp, existente):
    imp["rubro_slug"] = "turismo"
    r = completar(client, datos, sumar_rubro=True)
    assert r.status_code == 200 and "rubro" in r.json()["cambiados"]
    assert repo.get_comercio_rubros("com-exist") == ["hospedaje", "turismo"]
    assert r.json()["rubros"] == ["hospedaje", "turismo"]


def test_sin_sumar_rubro_no_toca_los_rubros(client, repo, datos, imp, existente):
    imp["rubro_slug"] = "turismo"
    r = completar(client, datos)
    assert repo.get_comercio_rubros("com-exist") == ["hospedaje"] and "rubro" not in r.json()["cambiados"]


def test_si_el_unico_rubro_es_otros_el_sugerido_lo_reemplaza(client, repo, datos, imp, existente):
    existente["rubros"] = ["otros"]
    completar(client, datos, sumar_rubro=True)
    assert repo.get_comercio_rubros("com-exist") == ["hospedaje"]


def test_el_rubro_respeta_el_tope_de_seis(client, repo, datos, imp, existente):
    llenos = ["a1", "a2", "a3", "a4", "a5", "hospedaje"]
    for s in llenos:
        repo.rubros.setdefault(s, f"rub-{s}")
    existente["rubros"] = list(llenos)
    imp["rubro_slug"] = "turismo"
    r = completar(client, datos, sumar_rubro=True)
    assert r.status_code == 200 and "rubro" not in r.json()["cambiados"]
    assert repo.get_comercio_rubros("com-exist") == llenos


def test_un_rubro_ya_puesto_no_se_duplica():
    assert ci.rubro_a_aplicar(["hospedaje"], "hospedaje") == ("igual", ["hospedaje"])
    assert ci.rubro_a_aplicar([], "turismo") == ("reemplazar", ["turismo"])
    assert ci.rubro_a_aplicar(["a", "b"], None) == ("igual", ["a", "b"])


def test_un_rubro_no_comercial_marca_el_rubro_como_revisado(client, repo, datos, imp, existente):
    imp["rubro_slug"] = "para-visitar"
    completar(client, datos, sumar_rubro=True)
    c = repo.comercios["com-exist"]
    assert "para-visitar" in repo.get_comercio_rubros("com-exist")
    assert c["rubro_revisado_por"] == "datos@uruku.bo" and c["rubro_revisado_at"]


def test_un_rubro_comercial_no_marca_revisado(client, repo, datos, imp, existente):
    imp["rubro_slug"] = "turismo"
    completar(client, datos, sumar_rubro=True)
    assert "rubro_revisado_at" not in repo.comercios["com-exist"]


# ───────────────────────────────────────────────────────────── completar: errores

def test_completar_404_409_y_permiso(client, repo, datos, imp, existente):
    assert completar(client, datos, importado="nada").status_code == 404
    assert completar(client, datos, comercio_id="nada").status_code == 404
    existente["activo"] = False
    assert completar(client, datos).status_code == 404                  # comercio inactivo
    existente["activo"] = True
    sin = h(auth.make_token("otro@uruku.bo", rol="x", roles=["x"], permisos=["comercios"]))
    assert client.post(f"/admin/importados/{IMP}/completar", json={"comercio_id": "com-exist"},
                       headers=sin).status_code == 403
    assert completar(client, datos).status_code == 200
    assert completar(client, datos).status_code == 409                  # ya está promovido
    for estado in ("descartado", "promovido"):
        imp["estado"] = estado
        assert completar(client, datos).status_code == 409
    assert client.post(f"/admin/importados/{IMP}/completar", json={}, headers=datos).status_code == 422


def test_un_409_o_404_no_cambia_nada_del_comercio(client, repo, datos, imp, existente):
    imp["estado"] = "descartado"
    completar(client, datos)
    assert repo.comercios["com-exist"]["horario"] is None and imp["comercio_id"] is None


# ───────────────────────────────────────────────────────────── no es repetido (criterio 2)

def test_no_es_repetido_limpia_el_aviso_y_deja_promover_como_nuevo(client, repo, datos, imp, existente):
    r = client.post(f"/admin/importados/{IMP}/no-es-repetido", headers=datos)
    assert r.status_code == 200, r.text
    assert r.json()["duplicado_de"] is None and r.json()["estado"] == "nuevo" and r.json()["id"] == IMP
    assert "foto_ref" not in r.json() and repo.importados[IMP]["duplicado_de"] is None
    antes = len(repo.comercios)
    p = client.post(f"/admin/importados/{IMP}/promover", json={}, headers=datos)
    assert p.status_code == 200 and len(repo.comercios) == antes + 1


def test_no_es_repetido_404_409_y_permiso(client, repo, datos, imp):
    assert client.post("/admin/importados/nada/no-es-repetido", headers=datos).status_code == 404
    sin = h(auth.make_token("otro@uruku.bo", rol="x", roles=["x"], permisos=["comercios"]))
    assert client.post(f"/admin/importados/{IMP}/no-es-repetido", headers=sin).status_code == 403
    imp["estado"] = "promovido"
    assert client.post(f"/admin/importados/{IMP}/no-es-repetido", headers=datos).status_code == 409
    assert imp["duplicado_de"] == "com-exist"                           # no se tocó


def test_la_salida_del_listado_trae_el_nombre_del_repetido(client, repo, datos, imp, existente):
    item = client.get("/admin/importados?fuente=turismo", headers=datos).json()["items"][0]
    assert item["duplicado_de"] == "com-exist" and item["duplicado_nombre"] == "Hotel Los Parrales"
    assert item["subcategoria_legible"] == "Hotel"


# ───────────────────────────────────────────────────────────── promover sin ubicación (criterio 3)

def test_sin_el_flag_un_importado_sin_punto_sigue_dando_400(client, repo, datos, imp):
    imp.update(lat=None, lng=None, duplicado_de=None)
    r = client.post(f"/admin/importados/{IMP}/promover", json={}, headers=datos)
    assert r.status_code == 400 and "coordenadas" in r.json()["detail"]
    assert client.post(f"/admin/importados/{IMP}/promover", json={"sin_ubicacion": False},
                       headers=datos).status_code == 400


@pytest.mark.parametrize("fuente", ["turismo", "tarjeta"])
def test_con_el_flag_tarjetas_y_turismo_se_promueven_sin_punto(client, repo, datos, imp, fuente):
    imp.update(fuente=fuente, lat=None, lng=None, duplicado_de=None, nombre="Juan Pérez · Guía de turismo",
               categoria="guias", rubro_slug="turismo", telefono=None, whatsapp="59170011122")
    r = client.post(f"/admin/importados/{IMP}/promover", json={"sin_ubicacion": True}, headers=datos)
    assert r.status_code == 200, r.text
    c = repo.comercios[r.json()["comercio"]["id"]]
    assert c["lat"] is None and c["lng"] is None and c["activo"] is True and c["confiable"] is False
    assert c["whatsapp"] == "59170011122" and repo.importados[IMP]["estado"] == "promovido"
    assert repo.get_comercio_rubros(c["id"]) == ["turismo"]


def test_con_el_flag_las_de_osm_siguen_dando_400(client, repo, datos, imp):
    imp.update(fuente="osm", lat=None, lng=None, duplicado_de=None)
    r = client.post(f"/admin/importados/{IMP}/promover", json={"sin_ubicacion": True}, headers=datos)
    assert r.status_code == 400 and "sin ubicación" in r.json()["detail"]
    assert len(repo.comercios) == 1


def test_con_el_flag_y_con_punto_se_usa_el_punto(client, repo, datos, imp):
    imp["duplicado_de"] = None
    r = client.post(f"/admin/importados/{IMP}/promover", json={"sin_ubicacion": True}, headers=datos)
    c = repo.comercios[r.json()["comercio"]["id"]]
    assert (c["lat"], c["lng"]) == (-21.5312, -64.7311)


# ───────────────────────────────────────────────────────────── subcategoría legible (criterio 4)

def test_las_etiquetas_que_usa_la_home_estan_escritas_exactamente_asi():
    assert sub.SUB_GUIA == "Guía de turismo"
    assert sub.SUB_RADIO_MOVIL == "Radio móvil"
    assert sub.SUB_TRANSPORTE_ALREDEDORES == "Transporte a los alrededores"
    assert sub.ETIQUETAS_DE_LA_HOME == ("Guía de turismo", "Radio móvil", "Transporte a los alrededores")
    assert sub.ETIQUETA_POR_SLUG["guias"] == "Guía de turismo"
    assert sub.ETIQUETA_POR_SLUG["radio-moviles"] == "Radio móvil"
    assert sub.ETIQUETA_POR_SLUG["transporte-alrededores"] == "Transporte a los alrededores"


def test_la_tabla_cubre_las_subcategorias_que_el_importador_conoce():
    conocidas = set(it.RUBRO_POR_SUBCATEGORIA) | set(it.SUBCATEGORIAS_TURISMO) | set(it.SECCIONES_TURISMO)
    assert conocidas - set(sub.ETIQUETA_POR_SLUG) == set()
    assert all(v and v == v.strip() and "-" not in v for v in sub.ETIQUETA_POR_SLUG.values())


@pytest.mark.parametrize("categoria,rubro,esperada", [
    ("guias", "turismo", "Guía de turismo"),
    ("radio-moviles", "taxis", "Radio móvil"),
    ("transporte-alrededores", "taxis", "Transporte a los alrededores"),
    ("agencias-de-viajes", "turismo", "Agencia de viajes"),
    ("operadoras-de-turismo", "turismo", "Operadora de turismo"),
    ("hoteles", "hospedaje", "Hotel"), ("hostales", "hospedaje", "Hostal"),
    ("bodegas-y-vinotecas", "bebidas", "Bodega"), ("complejos-turisticos", "turismo", "Complejo turístico"),
    ("balneareos-privados", "turismo", "Balneario"), ("churrasquerias", "restaurantes", "Churrasquería"),
    ("saltenerias", "comida-rapida", "Salteñería"),
])
def test_al_promover_un_importado_de_turismo_la_subcategoria_queda_legible(client, repo, datos, imp, categoria,
                                                                          rubro, esperada):
    repo.rubros.setdefault(rubro, f"rub-{rubro}")
    imp.update(categoria=categoria, rubro_slug=rubro, duplicado_de=None, lat=None, lng=None)
    r = client.post(f"/admin/importados/{IMP}/promover", json={"sin_ubicacion": True}, headers=datos)
    assert r.status_code == 200, r.text
    assert repo.comercios[r.json()["comercio"]["id"]]["subcategoria"] == esperada


def test_una_categoria_que_no_esta_en_la_tabla_queda_sin_subcategoria(client, repo, datos, imp):
    imp.update(categoria="algo-nuevo-de-la-pagina", duplicado_de=None, tags={})
    r = client.post(f"/admin/importados/{IMP}/promover", json={}, headers=datos)
    assert "subcategoria" not in repo.comercios[r.json()["comercio"]["id"]]


def test_una_agencia_con_categoria_rara_usa_la_de_su_seccion(client, repo, datos, imp):
    imp.update(categoria="turismo-receptivo", rubro_slug="turismo", duplicado_de=None,
               tags={"turismo": {"seccion": "agencias-de-viajes"}})
    r = client.post(f"/admin/importados/{IMP}/promover", json={}, headers=datos)
    assert repo.comercios[r.json()["comercio"]["id"]]["subcategoria"] == "Agencia de viajes"


def test_las_otras_fuentes_no_reciben_subcategoria_de_la_tabla(client, repo, datos, imp):
    imp.update(fuente="tarjeta", categoria="guias", duplicado_de=None)
    r = client.post(f"/admin/importados/{IMP}/promover", json={}, headers=datos)
    assert "subcategoria" not in repo.comercios[r.json()["comercio"]["id"]]


def test_un_lugar_para_visitar_conserva_su_tipo(client, repo, datos, imp):
    imp.update(categoria="plazas-parques-y-miradores", rubro_slug="para-visitar", subcategoria="Mirador",
               duplicado_de=None)
    r = client.post(f"/admin/importados/{IMP}/promover", json={}, headers=datos)
    assert repo.comercios[r.json()["comercio"]["id"]]["subcategoria"] == "Mirador"


def test_completar_pone_la_subcategoria_legible_si_el_existente_no_tiene(client, repo, datos, imp, existente):
    imp.update(categoria="guias", rubro_slug="turismo")
    completar(client, datos)
    assert repo.comercios["com-exist"]["subcategoria"] == "Guía de turismo"


def test_completar_conserva_la_subcategoria_del_existente_si_tiene(client, repo, datos, imp, existente):
    existente["subcategoria"] = "Hostal familiar"
    completar(client, datos)
    assert repo.comercios["com-exist"]["subcategoria"] == "Hostal familiar"
    imp.update(estado="nuevo")
    completar(client, datos, usar={"subcategoria": "nuevo"})
    assert repo.comercios["com-exist"]["subcategoria"] == "Hotel"
