"""El diccionario de sinónimos: que traiga lo que corresponde y NADA más.

El riesgo de esta capa no es quedarse corta, es pasarse. Un sinónimo de más hace
que el comprador reciba locales que no tienen lo que busca, y eso destruye la
confianza en el buscador mucho más rápido que un resultado faltante.
"""
import json

from app.services.sinonimos import (
    MAX_SINONIMOS,
    _limpiar,
    _normalizar_termino,
    generar_diccionario,
    sinonimos_para,
    terminos_de_comercio,
)


def post_falso(respuesta: dict):
    """Reemplaza la llamada al modelo. Guarda los prompts para poder mirarlos."""
    vistos = []

    def _post(prompt: str) -> str:
        vistos.append(prompt)
        return json.dumps(respuesta)

    _post.prompts = vistos
    return _post


def test_el_caso_de_frontera():
    """Lo que motiva todo: las dos formas tienen que llevar al mismo local."""
    dicc = generar_diccionario(["remeras"], post_falso({"remera": "polera, camiseta"}))
    assert "polera" in dicc["remera"]
    assert "camiseta" in dicc["remera"]


def test_el_termino_no_se_repite_en_sus_sinonimos():
    dicc = generar_diccionario(["remera"], post_falso({"remera": "remera, remeras, polera"}))
    assert dicc["remera"] == "polera"


def test_corta_en_el_maximo():
    """Muchos sinónimos = el modelo se fue por las ramas."""
    largo = ", ".join(f"palabra{i}" for i in range(20))
    dicc = generar_diccionario(["remera"], post_falso({"remera": largo}))
    assert len(dicc["remera"].split(",")) == MAX_SINONIMOS


def test_los_terminos_se_normalizan_antes_de_preguntar():
    """"Zapatillas", "zapatilla" y "ZAPATILLAS" son una sola pregunta, no tres:
    cada término repetido es plata gastada dos veces."""
    post = post_falso({"zapatilla": "tenis"})
    generar_diccionario(["Zapatillas", "zapatilla", "ZAPATILLAS "], post)
    # Se cuenta sólo la lista de términos: el prompt nombra "zapatilla" en sus
    # ejemplos, y eso no tiene nada que ver con lo que se está preguntando.
    lista = post.prompts[0].split("Términos:")[1]
    assert lista.count("zapatilla") == 1
    assert len(post.prompts) == 1


def test_un_lote_que_falla_no_tumba_los_demas():
    llamadas = {"n": 0}

    def post(prompt: str) -> str:
        llamadas["n"] += 1
        if llamadas["n"] == 1:
            raise RuntimeError("503 del modelo")
        return json.dumps({"campera": "casaca"})

    muchos = [f"producto{i}" for i in range(45)]           # fuerza 2 lotes
    dicc = generar_diccionario(muchos + ["campera"], post)
    assert dicc.get("campera") == "casaca"


def test_respuesta_rota_no_explota():
    def post(prompt: str) -> str:
        return "esto no es json"

    assert generar_diccionario(["remera"], post) == {}


def test_acepta_lista_ademas_de_texto():
    """El modelo a veces devuelve ["a","b"] en vez de "a, b"."""
    dicc = generar_diccionario(["remera"], post_falso({"remera": ["polera", "camiseta"]}))
    assert dicc["remera"] == "polera, camiseta"


def test_terminos_de_comercio_junta_productos_y_subcategoria():
    c = {"prod_det_ia": "remeras, pantalones", "subcategoria": "ropa femenina"}
    t = terminos_de_comercio(c)
    assert "remera" in t and "pantalon" in t and "ropa femenina" in t


def test_aplica_por_palabra_suelta():
    """El comercio dice "remera de algodon" y el diccionario sólo conoce
    "remera": tiene que matchear igual, porque el texto es libre."""
    c = {"prod_det_ia": "remera de algodon"}
    assert "polera" in sinonimos_para(c, {"remera": "polera"})


def test_no_inventa_sinonimos_sin_diccionario():
    assert sinonimos_para({"prod_det_ia": "remeras"}, {}) == ""


def test_no_repite_sinonimos_entre_productos():
    """Dos productos que comparten sinónimo no lo escriben dos veces."""
    c = {"prod_det_ia": "remera, camiseta"}
    salida = sinonimos_para(c, {"remera": "polera", "camiseta": "polera"})
    assert salida == "polera"


def test_normalizar_termino_es_estable():
    for variantes in (["Remeras", "remera", "REMERA "], ["Zapatillas", "zapatilla"]):
        assert len({_normalizar_termino(v) for v in variantes}) == 1


def test_limpiar_descarta_basura():
    assert _limpiar("remera", "") == ""
    assert _limpiar("remera", "a, de, !!!") == ""
