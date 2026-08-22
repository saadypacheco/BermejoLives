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


# ── Nombres genéricos ───────────────────────────────────────────────────────
# Después de dos salidas al campo hay 100 comercios sobre 203 sin nombre real.
# De esta función depende poder ponerles el del cartel SIN pisar los que sí
# tienen uno escrito por una persona.
from app.services.normalizar import es_nombre_generico  # noqa: E402

RUBROS = {"🏬 Moda y ropa", "👟 Calzado", "Ferretería y construcción"}


def test_detecta_los_que_quedaron_sin_nombre():
    for n in ("Comercio", "comercio", "COMERCIO", "Comercio 3", "comercio-2",
              "local", "Tienda", "  ", "", None):
        assert es_nombre_generico(n, RUBROS), n


def test_un_rubro_no_es_un_nombre():
    """Apareció en los datos: un comercio llamado "🏬 Moda y ropa". No distingue
    ese local de los otros 110 que venden lo mismo."""
    assert es_nombre_generico("🏬 Moda y ropa", RUBROS)
    assert es_nombre_generico("moda y ropa", RUBROS)
    assert es_nombre_generico("Calzado", RUBROS)


def test_no_pisa_un_nombre_de_verdad():
    """El riesgo real: que una lectura de foto reemplace lo que tipeó alguien
    parado en la puerta del local."""
    for n in ("COMERCIAL MARIA", "Bazar Lidia", "ZAPATILLERIA CRUZ", "HJ",
              "Comercial Vásquez", "Comercio Fidel", "El mundo de lana"):
        assert not es_nombre_generico(n, RUBROS), n


def test_sin_lista_de_rubros_igual_funciona():
    """Los rubros son opcionales: el caso común es sólo "Comercio"."""
    assert es_nombre_generico("Comercio")
    assert not es_nombre_generico("Bazar Lidia")
