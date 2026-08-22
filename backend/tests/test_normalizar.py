"""La normalización tiene que fusionar variantes SIN fusionar cosas distintas.

Los casos de este archivo no son inventados: salen del informe de producción
después de analizar 161 vidrieras con IA.
"""
from app.services.normalizar import normalizar_subcategoria, singular


def test_fusiona_los_casos_reales_de_produccion():
    """Los pares que aparecieron contados por separado en la base."""
    assert normalizar_subcategoria("bolsos y mochilas") == normalizar_subcategoria("mochilas y bolsos")
    assert normalizar_subcategoria("bazar y electrodomésticos") == normalizar_subcategoria("electrodomésticos y bazar")


def test_no_fusiona_el_local_con_el_producto():
    """"juguetería" y "juguetes" NO se fusionan, y está bien que no.

    Son palabras distintas (una deriva de la otra), no dos formas de la misma.
    Cualquier regla de sufijos que las una rompe otros casos: "librería" daría
    "libr" y "libros" daría "libro", que siguen sin coincidir. Normalizar de más
    fusiona categorías que no son la misma, y ese error es peor — no se nota y
    no se puede deshacer.

    El par juguetería/juguetes lo resuelve la capa de SINÓNIMOS, donde la IA
    escribe las dos palabras, y de acá en adelante el prompt pide singular y el
    término más común, así que las altas nuevas ya no se bifurcan."""
    assert normalizar_subcategoria("juguetería") != normalizar_subcategoria("juguetes")


def test_fusiona_tildes_mayusculas_y_plural():
    formas = ["Juguetería", "jugueteria", "JUGUETERIAS", "Juguetería "]
    assert len({normalizar_subcategoria(f) for f in formas}) == 1


def test_ignora_palabras_vacias():
    assert normalizar_subcategoria("ropa de bebé") == normalizar_subcategoria("ropa bebé")


def test_no_fusiona_categorias_distintas():
    """El riesgo real de normalizar de más: que "ropa femenina" y "ropa
    masculina" terminen siendo la misma cosa y el filtro deje de servir."""
    distintas = ["ropa femenina", "ropa masculina", "ropa de bebé",
                 "ropa deportiva", "ropa interior", "celulares", "ferretería",
                 "zapatillas", "bicicletas", "blanquería"]
    assert len({normalizar_subcategoria(d) for d in distintas}) == len(distintas)


def test_vacio_y_basura_no_rompen():
    assert normalizar_subcategoria(None) == ""
    assert normalizar_subcategoria("") == ""
    assert normalizar_subcategoria("   ") == ""
    assert normalizar_subcategoria("!!!") == ""


def test_solo_palabras_vacias_conserva_algo():
    """Preferimos un valor raro a perder el dato."""
    assert normalizar_subcategoria("de la") != ""


def test_singular_no_recorta_palabras_cortas():
    """"gas" o "pan" no son plurales; recortarlos crea colisiones peores."""
    for p in ("gas", "mes", "pan", "sal"):
        assert singular(p) == p


def test_singular_casos_del_espanol():
    assert singular("bolsos") == singular("bolso")
    assert singular("lapices") == singular("lapiz")
    assert singular("pantalones") == singular("pantalon")
