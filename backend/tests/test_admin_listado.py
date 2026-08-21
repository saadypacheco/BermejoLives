"""El listado del panel tiene que traer lo que el panel usa para buscar.

Nace de un bug real: se agregó la búsqueda por código y por productos en el
frontend, pero list_todos_comercios seleccionaba columnas explícitas y no los
incluía. Buscar "URUKU-TCHE" no devolvía nada aunque el comercio existiera, y no
había forma de notarlo desde el código del frontend.
"""

# Campos que el panel de Comercios necesita sí o sí: son los que usa el buscador
# multi-campo y los que muestra en cada fila.
CAMPOS_QUE_USA_EL_PANEL = [
    "nombre", "slug", "descripcion", "prod_obs_human", "codigo",
    "direccion", "whatsapp", "telefono", "verificado", "lat", "lng",
]


def test_listado_admin_trae_los_campos_del_buscador(client, repo, admin_token):
    repo.seed_comercio(slug="comercio-24", nombre="Comercio", codigo="TCHE",
                       prod_obs_human="medias, ropa interior", activo=True)

    r = client.get("/moderacion/comercios?todos=true",
                   headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200, r.text
    item = next(c for c in r.json()["items"] if c.get("slug") == "comercio-24")

    faltantes = [k for k in CAMPOS_QUE_USA_EL_PANEL if k not in item]
    assert not faltantes, f"el panel busca por estos campos y no llegan: {faltantes}"


def test_el_codigo_llega_para_poder_buscarlo(client, repo, admin_token):
    repo.seed_comercio(slug="comercio-24", nombre="Comercio", codigo="TCHE", activo=True)
    r = client.get("/moderacion/comercios?todos=true",
                   headers={"Authorization": f"Bearer {admin_token}"})
    item = next(c for c in r.json()["items"] if c.get("slug") == "comercio-24")
    assert item["codigo"] == "TCHE"
