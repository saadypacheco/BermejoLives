"""El informe de catálogo: qué hay cargado y, sobre todo, qué falta.

Lo que se mide acá es que los huecos aparezcan. Un panel que sólo muestra lo que
existe se siente completo aunque falte la mitad del pueblo — el valor de esta
vista es exactamente el contrario.
"""
from app.services.catalogo import informe


def _ha(token):
    return {"Authorization": f"Bearer {token}"}


def test_un_rubro_sin_comercios_aparece_igual(client, repo, admin_token):
    """Es el punto de la vista: los vacíos tienen que verse, no desaparecer del
    listado por no tener filas asociadas."""
    r = client.get("/admin/catalogo", headers=_ha(admin_token))
    assert r.status_code == 200, r.text
    datos = r.json()

    slugs = {x["slug"] for x in datos["rubros"]}
    todos = {x["slug"] for x in repo.list_rubros()}
    assert slugs == todos          # ninguno se cae del informe


def test_cuenta_los_comercios_de_cada_rubro(client, repo, admin_token):
    datos = informe(repo)
    por_slug = {x["slug"]: x["comercios"] for x in datos["rubros"]}
    esperado = {}
    for rel in repo.list_comercio_rubros_todos():
        esperado[rel["slug"]] = esperado.get(rel["slug"], 0) + 1
    for slug, n in esperado.items():
        assert por_slug.get(slug) == n, slug


def test_los_inactivos_no_cuentan():
    class RepoFalso:
        def list_todos_comercios(self, *a, **k):
            return [
                {"id": "1", "activo": True,  "prod_det_ia": "remera, pantalon"},
                {"id": "2", "activo": False, "prod_det_ia": "remera"},
            ]
        def list_rubros(self):
            return [{"slug": "ropa", "nombre": "Moda y ropa"}]
        def list_comercio_rubros_todos(self):
            return [{"comercio_id": "1", "slug": "ropa"},
                    {"comercio_id": "2", "slug": "ropa"}]
        def kpis_admin(self):
            return {"sin_resultado": []}

    datos = informe(RepoFalso())
    assert datos["comercios"] == 1
    assert datos["rubros"][0]["comercios"] == 1        # no 2
    assert dict((p["termino"], p["comercios"]) for p in datos["productos"])["remera"] == 1


def test_los_productos_se_normalizan_antes_de_contar():
    """"Remeras" y "remera " son el mismo producto. Sin normalizar, el catálogo
    infla el vocabulario y ninguna variante junta comercios suficientes."""
    class RepoFalso:
        def list_todos_comercios(self, *a, **k):
            return [{"id": "1", "activo": True, "prod_det_ia": "Remera, remera ,  REMERA"}]
        def list_rubros(self):
            return []
        def list_comercio_rubros_todos(self):
            return []
        def kpis_admin(self):
            return {"sin_resultado": []}

    datos = informe(RepoFalso())
    # Dentro de un mismo comercio el producto se cuenta UNA vez, aunque esté
    # escrito de tres formas: si no, un local repetitivo pesaría como tres.
    assert datos["productos"] == [{"termino": "remera", "comercios": 1}]


def test_sin_busquedas_el_catalogo_igual_sirve():
    """El informe no puede caerse porque falten las búsquedas: son la parte
    opcional, el catálogo es la principal."""
    class RepoRoto:
        def list_todos_comercios(self, *a, **k):
            return [{"id": "1", "activo": True, "prod_det_ia": "olla"}]
        def list_rubros(self):
            return [{"slug": "bazar", "nombre": "Bazar"}]
        def list_comercio_rubros_todos(self):
            return []
        def kpis_admin(self):
            raise RuntimeError("PostgREST caído")

    datos = informe(RepoRoto())
    assert datos["buscado_sin_resultado"] == []
    assert datos["rubros"][0]["comercios"] == 0


def test_el_descarte_no_cuenta_como_hueco():
    """"Otros" siempre está vacío o casi, y no es una categoría que falte
    relevar: marcarlo como hueco sería ruido permanente."""
    class RepoFalso:
        def list_todos_comercios(self, *a, **k):
            return []
        def list_rubros(self):
            return [{"slug": "otros", "nombre": "Otros"}, {"slug": "optica", "nombre": "Óptica"}]
        def list_comercio_rubros_todos(self):
            return []
        def kpis_admin(self):
            return {"sin_resultado": []}

    assert informe(RepoFalso())["rubros_vacios"] == 1     # sólo óptica


def test_sin_token_no_se_ve(client, repo):
    assert client.get("/admin/catalogo").status_code in (401, 403)
