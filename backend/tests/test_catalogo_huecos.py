"""El catálogo tiene que mostrar lo que FALTA, no sólo lo que hay."""
from app.services.catalogo import informe


def _c(repo, **kw):
    return repo.seed_comercio(activo=True, **kw)


def test_subcategorias_van_aparte_de_los_productos(repo):
    """Responden preguntas distintas: los productos dicen qué se vende en la
    ciudad; la subcategoria es la que arma los chips del buscador."""
    _c(repo, id="a", nombre="A", subcategoria="zapatilla urbana",
       prod_det_ia="zapatilla, botin, chinela")

    r = informe(repo)
    subs = [s["subcategoria"] for s in r["subcategorias"]]
    assert subs == ["zapatilla urbana"]
    assert "botin" in [p["termino"] for p in r["productos"]]
    assert "botin" not in subs


def test_cuenta_los_que_no_tienen_subcategoria(repo):
    """Un comercio sin subcategoria no aparece en ningun chip de refinamiento:
    es trabajo pendiente, no un comercio sano."""
    _c(repo, id="a", nombre="A", subcategoria="bazar")
    _c(repo, id="b", nombre="B", subcategoria=None)
    _c(repo, id="c", nombre="C", subcategoria="   ")

    assert informe(repo)["sin_subcategoria"] == 2


def test_las_subcategorias_salen_de_menor_a_mayor(repo):
    """Del top ya se sabe todo. Lo que hay que ver es la cola: las que tienen un
    solo comercio son chips que no refinan nada."""
    for i in range(3):
        _c(repo, id=f"m{i}", nombre=f"M{i}", subcategoria="bazar")
    _c(repo, id="u", nombre="U", subcategoria="rara")

    subs = informe(repo)["subcategorias"]
    assert [s["subcategoria"] for s in subs] == ["rara", "bazar"]
    assert subs[0]["comercios"] == 1


def test_cuenta_las_subcategorias_de_un_solo_comercio(repo):
    _c(repo, id="a", nombre="A", subcategoria="unica")
    _c(repo, id="b", nombre="B", subcategoria="bazar")
    _c(repo, id="c", nombre="C", subcategoria="bazar")

    r = informe(repo)
    assert r["subcategorias_distintas"] == 2
    assert r["subcategorias_unicas"] == 1


def test_las_subcategorias_no_se_recortan(repo):
    """Los productos se recortan al top 120 porque son cientos y la cola no
    aporta. Las subcategorias van ENTERAS: la cola es justamente lo que se
    viene a buscar."""
    for i in range(150):
        _c(repo, id=f"s{i}", nombre=f"S{i}", subcategoria=f"sub {i}")

    assert len(informe(repo)["subcategorias"]) == 150
