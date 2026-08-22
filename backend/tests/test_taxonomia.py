"""La evidencia que se le muestra al modelo tiene que ser fiel.

Si la evidencia está mal armada, la propuesta va a ser convincente y equivocada
— que es el peor resultado posible, porque cambiar la taxonomía reordena el mapa
y los filtros de todos los comercios a la vez.
"""
import json

from app.services.taxonomia import armar_evidencia, revisar

RUBROS = [
    {"slug": "moda", "nombre": "Moda y ropa"},
    {"slug": "calzado", "nombre": "Calzado"},
    {"slug": "nautica", "nombre": "Náutica"},
    {"slug": "otros", "nombre": "Otros (a clasificar)"},
]


def comercio(cid, productos, sub="", activo=True):
    return {"id": cid, "prod_det_ia": productos, "subcategoria": sub, "activo": activo}


def test_cuenta_los_rubros_por_comercio():
    comercios = [comercio("1", "remera, pantalon"), comercio("2", "remera")]
    rel = [{"comercio_id": "1", "slug": "moda"}, {"comercio_id": "2", "slug": "moda"}]
    ev = armar_evidencia(comercios, rel, RUBROS)
    moda = next(r for r in ev["rubros"] if r["slug"] == "moda")
    assert moda["comercios"] == 2
    assert "remera" in moda["productos"]          # 2 veces
    assert "pantalon" not in moda["productos"]    # 1 sola vez, no concluye nada


def test_los_rubros_vacios_se_detectan():
    ev = armar_evidencia([comercio("1", "remera")],
                         [{"comercio_id": "1", "slug": "moda"}], RUBROS)
    vacios = {v["slug"] for v in ev["vacios"]}
    assert "nautica" in vacios
    assert "otros" not in vacios      # el descarte no es un rubro vacío


def test_los_sin_rubro_alimentan_los_candidatos():
    """Un comercio que sólo tiene "otros" no tiene rubro real, y su vocabulario
    es la evidencia más directa de qué categoría falta."""
    comercios = [comercio("1", "sartén, olla"), comercio("2", "sartén, olla")]
    rel = [{"comercio_id": "1", "slug": "otros"}]     # 2 no tiene ninguno
    ev = armar_evidencia(comercios, rel, RUBROS)
    sueltos = {h["termino"]: h["veces"] for h in ev["sin_rubro"]}
    assert sueltos.get("sarten") == 2 or sueltos.get("sartén") == 2


def test_los_inactivos_no_cuentan():
    comercios = [comercio("1", "remera"), comercio("2", "remera", activo=False)]
    rel = [{"comercio_id": "1", "slug": "moda"}, {"comercio_id": "2", "slug": "moda"}]
    ev = armar_evidencia(comercios, rel, RUBROS)
    assert ev["total_comercios"] == 1
    assert next(r for r in ev["rubros"] if r["slug"] == "moda")["comercios"] == 1


def test_un_comercio_multirubro_cuenta_en_todos():
    """Es el caso que motivó comercio_rubros: un local vende neumáticos Y
    zapatillas, y tiene que aparecer buscando cualquiera de las dos."""
    rel = [{"comercio_id": "1", "slug": "moda"}, {"comercio_id": "1", "slug": "calzado"}]
    ev = armar_evidencia([comercio("1", "remera")], rel, RUBROS)
    assert {r["slug"] for r in ev["rubros"]} == {"moda", "calzado"}


def test_la_evidencia_va_entera_al_prompt():
    ev = armar_evidencia([comercio("1", "remera, remera")],
                         [{"comercio_id": "1", "slug": "moda"}], RUBROS)
    visto = {}

    def post(prompt):
        visto["p"] = prompt
        return json.dumps({"crear": [], "dividir": [], "fusionar": [],
                           "eliminar": [], "renombrar": []})

    revisar(ev, post)
    assert "Moda y ropa" in visto["p"]
    assert "Náutica" in visto["p"]          # los vacíos también son evidencia


def test_respuesta_rota_no_explota():
    ev = armar_evidencia([], [], RUBROS)
    assert "error" in revisar(ev, lambda p: "no es json")


def test_devuelve_las_cinco_listas_siempre():
    ev = armar_evidencia([], [], RUBROS)
    prop = revisar(ev, lambda p: json.dumps({"crear": [{"nombre": "Náutica"}]}))
    assert set(prop) == {"crear", "dividir", "fusionar", "eliminar", "renombrar"}
    assert prop["dividir"] == []
