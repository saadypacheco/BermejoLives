"""Deducción de rubros desde lo que se cargó del negocio.

El caso real: en el campo se anota lo principal que se ve, no se eligen rubros de
una lista de 42. El rubro tiene que salir de ese texto — y un local que vende
cosas de distintos rubros tiene que quedar en todos, para aparecer en todas las
búsquedas.
"""
from app.services.rubros import SLUG_DESCARTE, aplicar_rubros, resolver_rubros, texto_para_rubros


def test_el_texto_junta_los_campos_que_dicen_QUE_VENDE():
    """Da igual en cuál de ellos escribió el agente la palabra que importa."""
    t = texto_para_rubros({"nombre": "Casa Pepe", "prod_obs_human": "zapatillas",
                           "prod_det_ia": "chinelas", "subcategoria": "calzado"})
    assert all(x in t for x in ("Casa Pepe", "zapatillas", "chinelas", "calzado"))


def test_la_descripcion_y_los_sinonimos_NO_clasifican():
    """La regla que faltaba, y la que causó 194 comercios "mal clasificados".

    El alta miraba seis campos y el clasificador masivo tres: los rubros que un
    comercio TENÍA se calcularon con un texto más ancho que el que después los
    juzgaba. De ahí salían las carnicerías en talleres de motos.

    La descripción es prosa libre sobre el local —la cuadra, los vecinos, cómo
    llegar— y los sinónimos existen para que el comprador ENCUENTRE, no para
    clasificar: "ciclismo indoor" hacía de un gimnasio una bicicletería.
    """
    t = texto_para_rubros({
        "nombre": "Taller Rey",
        "descripcion": "Al lado de la carniceria de la esquina",
        "sinonimos": "ciclismo indoor",
    })
    assert t == "Taller Rey"


def test_texto_tolera_campos_vacios():
    assert texto_para_rubros({"nombre": "Pepe", "prod_obs_human": None, "descripcion": ""}) == "Pepe"


def test_deduce_de_los_productos(repo):
    c = repo.seed_comercio(slug="x", nombre="Casa Pepe", prod_obs_human="zapatillas, chinelas")
    assert resolver_rubros(repo, c) == ["calzado"]


def test_un_local_amplio_queda_en_todos_sus_rubros(repo):
    """El caso que motivó todo: se cargan los productos principales y el negocio
    tiene que aparecer buscando cualquiera de ellos."""
    c = repo.seed_comercio(slug="x", nombre="Multirubro",
                           prod_obs_human="neumaticos, zapatillas, televisores")
    assert resolver_rubros(repo, c) == ["calzado", "electronica", "neumaticos"]


def test_deduce_del_nombre_cuando_no_hay_productos(repo):
    """El cartel es dato: muchas veces es lo único cargado."""
    c = repo.seed_comercio(slug="x", nombre="Tornillos del Sur", prod_obs_human=None)
    assert "ferreteria" in resolver_rubros(repo, c)


def test_sin_nada_reconocible_cae_a_otros(repo):
    c = repo.seed_comercio(slug="x", nombre="Comercio",
                           descripcion="Tienda de artículos varios para la familia")
    assert resolver_rubros(repo, c) == [SLUG_DESCARTE]


def test_lo_elegido_a_mano_no_se_pisa(repo):
    """Si alguien curó los rubros en la segunda pasada, la deducción SUMA."""
    c = repo.seed_comercio(slug="x", nombre="Casa Pepe", prod_obs_human="zapatillas")
    assert resolver_rubros(repo, c, elegidos=["ropa"]) == ["calzado", "ropa"]


def test_otros_elegido_a_mano_no_sobrevive_si_hay_deduccion(repo):
    """"otros" es un descarte, no una elección: si se dedujo algo real, sobra."""
    c = repo.seed_comercio(slug="x", nombre="Casa Pepe", prod_obs_human="zapatillas")
    assert SLUG_DESCARTE not in resolver_rubros(repo, c, elegidos=[SLUG_DESCARTE])


def test_aplicar_persiste_y_saca_otros(repo):
    # El fake guarda SLUGS: `set_comercio_rubros` traduce los ids que le llegan.
    # Antes guardaba lo que le mandaran, así que `list_comercio_rubros_todos`
    # devolvía 'rub-cal' como si fuera un slug y eso escondía errores reales.
    c = repo.seed_comercio(slug="x", nombre="Casa Pepe", prod_obs_human="zapatillas",
                           rubros=["otros"])
    aplicar_rubros(repo, c)
    quedaron = repo.comercios[c["id"]]["rubros"]
    assert "calzado" in quedaron
    assert "otros" not in quedaron


def test_aplicar_setea_el_rubro_principal_si_estaba_vacio(repo):
    """Sin esto el comercio se clasifica bien para el buscador pero en pantalla
    se sigue viendo como "Otros"."""
    c = repo.seed_comercio(slug="x", nombre="Casa Pepe", prod_obs_human="zapatillas", rubro_id=None)
    aplicar_rubros(repo, c)
    assert repo.comercios[c["id"]]["rubro_id"] == repo.rubros["calzado"]


def test_reemplaza_el_principal_cuando_es_el_descarte(repo):
    """En el alta TODOS reciben rubro_id = otros. Si sólo se mirara NULL, la
    condición no se cumpliría nunca y el comercio quedaría clasificado por
    dentro pero mostrándose como "Otros" — que fue justo lo que pasó con los 160
    del primer análisis por fotos."""
    c = repo.seed_comercio(slug="x", nombre="Casa Pepe", prod_obs_human="zapatillas",
                           rubro_id=repo.rubros["otros"])
    aplicar_rubros(repo, c)
    assert repo.comercios[c["id"]]["rubro_id"] == repo.rubros["calzado"]


def test_no_pisa_el_rubro_principal_ya_elegido(repo):
    c = repo.seed_comercio(slug="x", nombre="Casa Pepe", prod_obs_human="zapatillas",
                           rubro_id=repo.rubros["ropa"])
    aplicar_rubros(repo, c)
    assert repo.comercios[c["id"]]["rubro_id"] == repo.rubros["ropa"]


# ------------------------------------------------- reclasificación masiva
def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_reclasificar_previsualiza_sin_escribir(client, repo, admin_token):
    c = repo.seed_comercio(slug="x", nombre="Casa Pepe", prod_obs_human="zapatillas",
                           rubros=[repo.rubros["otros"]], activo=True)

    r = client.post("/admin/rubros/reclasificar", headers=_headers(admin_token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["aplicado"] is False
    assert any(x["slug"] == "x" for x in body["cambios"])
    # No tocó nada.
    assert repo.comercios[c["id"]]["rubros"] == [repo.rubros["otros"]]


def test_reclasificar_aplica_cuando_se_pide(client, repo, admin_token):
    c = repo.seed_comercio(slug="x", nombre="Casa Pepe", prod_obs_human="zapatillas",
                           rubros=[repo.rubros["otros"]], activo=True)

    r = client.post("/admin/rubros/reclasificar?aplicar=true", headers=_headers(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["aplicado"] is True
    assert "calzado" in repo.comercios[c["id"]]["rubros"]


def test_reclasificar_reporta_los_que_no_matchean(client, repo, admin_token):
    """Esa lista es la que dice qué palabras le faltan al diccionario."""
    repo.seed_comercio(slug="y", nombre="Comercio", descripcion="artículos varios", activo=True)

    r = client.post("/admin/rubros/reclasificar", headers=_headers(admin_token))
    assert any(x["slug"] == "y" for x in r.json()["sin_match"])


def test_reclasificar_requiere_admin(client, repo):
    assert client.post("/admin/rubros/reclasificar").status_code in (401, 403)
