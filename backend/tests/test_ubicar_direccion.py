"""Ubicar direcciones por esquina o cuadra (docs/importar-turismo.md, «Ubicar por esquinas»).

Nada sale a la red: Nominatim se reemplaza por un `pedir` falso (y por uno que falla si algún test se escapa). Las
calles son una grilla inventada de 4 x 4 calles (3 x 3 cuadras de ~100 m) con la forma de las filas de `calles_tramos`.
"""
import math
import uuid

import pytest

from app.core import auth
from app.services import tarjetas, ubicar_direccion as ub
from app.services.ubicar_direccion import Partes, partir_direccion

LAT0, LNG0 = -22.7361, -64.3433          # el centro que devuelve el repo falso (`get_ciudad`)
PASO_LAT, PASO_LNG = 0.0009, 0.00098     # ~100 m
CIUDAD = {"id": "ciudad-tarija", "slug": "tarija", "nombre": "Tarija", "lat": LAT0, "lng": LNG0}

#: Calles de la grilla. E-O (la latitud cambia con la fila): filas 0..3. N-S (la longitud con la columna): 0..3.
CALLES_EO = ["Calle Sucre", "Calle Bolívar", "Calle Méndez", "Calle Suipacha"]
CALLES_NS = ["Calle La Madrid", "Calle Ingavi", "Calle General Trigo", "Calle O'Connor"]


@pytest.fixture(autouse=True)
def _sin_red_ni_esperas(monkeypatch):
    tarjetas.reiniciar_cache()
    monkeypatch.setattr(tarjetas, "_dormir", lambda s: None)

    def sin_red(params):
        raise AssertionError("Nominatim: un test salió a la red")

    monkeypatch.setattr(tarjetas, "_pedir_nominatim", sin_red)
    yield
    tarjetas.reiniciar_cache()


def esquina_de(fila: float, col: float) -> tuple[float, float]:
    return (LAT0 + fila * PASO_LAT, LNG0 + col * PASO_LNG)


def grilla(ciudad_id="ciudad-tarija", eo=CALLES_EO, ns=CALLES_NS, nombres_extra=None) -> list[dict]:
    """Filas de `calles_tramos`: una por cuadra. Los extremos de cada cuadra son esquinas."""
    filas, way = [], 1
    for i, nombre in enumerate(eo):
        for c in range(3):
            filas.append({"ciudad_id": ciudad_id, "osm_way_id": way, "parte": c, "nombre": nombre, "tipo": "residential",
                          "geom": [list(esquina_de(i, c)), list(esquina_de(i, c + 1))], "longitud_m": 100,
                          "activo": True, "id": str(uuid.uuid4())})
        way += 1
    for j, nombre in enumerate(ns):
        for r in range(3):
            filas.append({"ciudad_id": ciudad_id, "osm_way_id": way, "parte": r, "nombre": nombre, "tipo": "residential",
                          "geom": [list(esquina_de(r, j)), list(esquina_de(r + 1, j))], "longitud_m": 100,
                          "activo": True, "id": str(uuid.uuid4())})
        way += 1
    return filas + list(nombres_extra or [])


def cerca(punto, esperado, tol_m=3.0) -> bool:
    return ub.distancia_m((punto["lat"], punto["lng"]), esperado) <= tol_m


def nominatim_falso(lat=LAT0, lng=LNG0, llamadas=None):
    def pedir(params):
        if llamadas is not None:
            llamadas.append(params)
        return [{"lat": str(lat), "lon": str(lng), "display_name": "Calle de prueba, Tarija, Bolivia"}]
    return pedir


# ═══════════════════════════════════════════════════════ partir la dirección

@pytest.mark.parametrize("texto, calle, numero, esquina, entre", [
    ("B. Las Panosas, Calle La Madrid #316 entre M…", "la madrid", "316", None, None),
    ("Z/Central, Calle La Madrid #282 esq. Sucre", "la madrid", "282", "sucre", None),
    ("Z/Central, B/Las Panosas, calle Colón entre …", "colon", None, None, None),
    ("Z/Central, calle Sucre esq. Bolívar #782", "sucre", "782", "bolivar", None),
    ("B. FatimaAv. La Paz #251 entre C/Avaroa y C/…", "la paz", "251", "avaroa", None),
    ("C/Ingavi entre Junín y O'Connor", "ingavi", None, None, ("junin", "o'connor")),
    ("Z/Central, B/San Roque C/Sucre #920 entre Do…", "sucre", "920", None, None),
    ("Calle Bolívar No 256 entre Méndez y Suipacha", "bolivar", "256", None, ("mendez", "suipacha")),
    ("C/Sucre entre Corrado y Domingo Paz #0966", "sucre", "966", None, ("corrado", "domingo paz")),
    ("Av. Jaime Paz Zamora, pasando la Av. Fuerza…", "jaime paz zamora", None, None, None),
    ("Av. La Paz entre Rosendo Estensoro y Membrillos", "la paz", None, None, ("rosendo estensoro", "membrillos")),
    ("B/Senac, Av. Julio Arce entre Av. Los Ceibos y …", "julio arce", None, "los ceibos", None),
    ("Calle Virginio Lema, esquina calle Sucre", "virginio lema", None, "sucre", None),
    ("Calle 15 de abril esq. Sucre", "15 de abril", None, "sucre", None),
    ("Calle La Madrid entre Sucre y Gral. Trigo", "la madrid", None, None, ("sucre", "general trigo")),
    ("Calle Santa Cruz Esquina Bolivar", "santa cruz", None, "bolivar", None),
    ("Calle Colon Nº 536, entre 15 de Abril y La Madrid", "colon", "536", None, ("15 de abril", "la madrid")),
    ("Calle Sucre # 856 casi Domingo Paz", "sucre", "856", "domingo paz", None),
    ("Calle Corrado No 0220 entre Sucre y Daniel Campos", "corrado", "220", None, ("sucre", "daniel campos")),
    ("Calle Méndez esquina Bolívar", "mendez", None, "bolivar", None),
    ("C/Virginio Lema esq. Suipacha", "virginio lema", None, "suipacha", None),
    ("Calle General Trigo # 670 entre Ingavi y Madrid", "general trigo", "670", None, ("ingavi", "madrid")),
    ("C/Madrid entre Suipacha y Méndez", "madrid", None, None, ("suipacha", "mendez")),
    ("Calle 15 de Abril esquina O´connor", "15 de abril", None, "o'connor", None),
    ("C/La Madrid # 616 entre Junín y O’connor Gal…", "la madrid", "616", None, ("junin", "o'connor")),
    ("Av.Las Américas Esq. Attie Frente al Avión", "las americas", None, "attie", None),
    ("Av. Circunvalación esq. 6 de junio # 1920", "circunvalacion", "1920", "6 de junio", None),
    ("Ex terminal de Buses (Av. Las Américas)", "las americas", None, None, None),
    ("Parque Bolivar, Calle Oruro", "oruro", None, None, None),
    # sin «Calle»: lo que usa el panel y las tarjetas
    ("Sucre 100", "sucre", "100", None, None),
    ("Calle La Madrid 282", "la madrid", "282", None, None),
    ("Calle 15 de Abril", "15 de abril", None, None, None),
])
def test_parte_las_direcciones_reales_de_tarija(texto, calle, numero, esquina, entre):
    p = partir_direccion(texto)
    assert (p.calle, p.numero, p.esquina, p.entre) == (calle, numero, esquina, entre), texto


def test_parte_tipo_y_nombre_con_su_escritura():
    p = partir_direccion("Z/Central, Calle Méndez #12 esq. Sucre")
    assert p.tipo == "calle" and p.calle_texto == "Méndez"
    assert partir_direccion("Av.Las Américas Esq. Attie").tipo == "avenida"
    assert partir_direccion("Sucre 100").tipo is None


def test_partir_vacio_o_basura_no_revienta():
    assert partir_direccion(None) == Partes()
    assert partir_direccion("") == Partes()
    assert partir_direccion("   ,  ; ") == Partes()
    assert partir_direccion("Z/Central").calle is None
    assert partir_direccion("x" * 5000).calle is not None          # no hay explosión de tiempo ni de memoria


# ═══════════════════════════════════════════════════════ nombres

def test_normalizar_tildes_abreviaturas_y_apostrofes():
    assert ub.normalizar("Gral. Trigo") == "general trigo"
    assert ub.normalizar("Mcal. Sucre") == "mariscal sucre"
    assert ub.normalizar("Bolívar") == ub.normalizar("BOLIVAR") == "bolivar"
    assert ub.normalizar("O'Connor") == ub.normalizar("O´connor") == ub.normalizar("O’connor") == "o'connor"


def test_claves_ignoran_tipo_articulos_y_titulos():
    assert ub.clave_exacta("Calle La Madrid") == ub.clave_exacta("Madrid") == ("madrid",)
    assert ub.clave_exacta("Avenida Las Américas") == ub.clave_exacta("Av. Américas")
    assert ub.clave_exacta("Calle 15 de Abril") == ("15", "abril")
    assert ub.clave_sin_titulos("General Trigo") == ("trigo",)
    assert ub.clave_exacta("O'Connor") == ub.clave_exacta("O´connor") == ("oconnor",)


def test_buscar_calle_tolerante_pero_sin_adivinar():
    calles = ub.Calles(grilla(eo=CALLES_EO + ["Calle Rosendo Estenssoro"]))
    assert calles.buscar("Madrid")[1]["nombre"] == "Calle La Madrid"          # artículo
    assert calles.buscar("Gral. Trigo")[1]["nombre"] == "Calle General Trigo"  # abreviatura
    assert calles.buscar("Trigo")[1]["nombre"] == "Calle General Trigo"        # sin título
    assert calles.buscar("bolivar")[1]["nombre"] == "Calle Bolívar"            # tilde
    assert calles.buscar("Rosendo Estensoro")[1]["nombre"] == "Calle Rosendo Estenssoro"   # una letra de más
    assert calles.buscar("Calle Inexistente") is None
    assert calles.buscar("") is None and calles.buscar(None) is None


def test_dos_calles_distintas_que_empatan_no_dan_match():
    calles = ub.Calles(grilla(ns=["Calle General Trigo", "Calle Coronel Trigo", "Calle Ingavi", "Calle Junín"]))
    assert calles.buscar("Trigo") is None                                       # empate: no se elige
    assert calles.buscar("General Trigo") is not None                           # exacta: sin dudas


def test_los_numeros_no_se_confunden_por_una_letra():
    calles = ub.Calles(grilla(eo=["Calle 15 de Abril", "Calle Sucre", "Calle Méndez", "Calle Suipacha"]))
    assert calles.buscar("16 de Abril") is None


def test_una_cuadra_sin_nombre_o_inactiva_no_entra():
    filas = grilla()
    filas.append({"ciudad_id": "x", "nombre": None, "geom": [[0, 0], [1, 1]], "activo": True})
    filas.append({"ciudad_id": "x", "nombre": "Calle Fantasma", "geom": [[0, 0], [1, 1]], "activo": False})
    filas.append({"ciudad_id": "x", "nombre": "Calle Rota", "geom": [[0, 0]], "activo": True})
    calles = ub.Calles(filas)
    assert calles.buscar("Fantasma") is None and calles.buscar("Rota") is None


# ═══════════════════════════════════════════════════════ geometría

def test_esquina_es_el_extremo_compartido_de_dos_calles():
    calles = ub.Calles(grilla())
    a, b = calles.buscar("Sucre")[1]["cuadras"], calles.buscar("La Madrid")[1]["cuadras"]
    pts = ub.esquinas_entre(a, b)
    assert len(pts) == 1 and ub.distancia_m(pts[0], esquina_de(0, 0)) < 1
    assert ub.punto_de_esquina(a, b) == pts[0]
    # dos calles paralelas no se tocan
    assert ub.esquinas_entre(a, calles.buscar("Bolívar")[1]["cuadras"]) == []


def test_extremos_a_mas_de_20_metros_no_son_esquina():
    a = [[[0.0, 0.0], [0.0, 0.001]]]
    cerca_ = [[[0.00010, 0.001], [0.001, 0.001]]]       # ~11 m
    lejos = [[[0.00030, 0.001], [0.001, 0.001]]]        # ~33 m
    assert len(ub.esquinas_entre(a, cerca_)) == 1
    assert ub.esquinas_entre(a, lejos) == []


def test_avenida_de_doble_mano_da_una_sola_esquina():
    """Dos vías paralelas a 12 m (cada mano) cruzan a una calle: sus extremos se juntan en un punto."""
    av = [[[0.0, 0.0], [0.0, 0.001]], [[0.0001, 0.0], [0.0001, 0.001]]]
    calle = [[[-0.001, 0.001], [0.0, 0.001]], [[0.0001, 0.001], [0.001, 0.001]]]
    assert len(ub.esquinas_entre(av, calle)) == 1


def test_cuadra_es_el_medio_entre_las_dos_esquinas():
    calles = ub.Calles(grilla())
    a = calles.buscar("Sucre")[1]["cuadras"]
    b, c = calles.buscar("La Madrid")[1]["cuadras"], calles.buscar("Ingavi")[1]["cuadras"]
    p = ub.punto_de_cuadra(a, b, c)
    assert ub.distancia_m(p, esquina_de(0, 0.5)) < 1


def test_cuadra_con_esquinas_a_mas_de_600_m_no_se_ubica():
    calles = ub.Calles(grilla())
    a = calles.buscar("Sucre")[1]["cuadras"]
    b, c = calles.buscar("La Madrid")[1]["cuadras"], calles.buscar("O'Connor")[1]["cuadras"]   # 3 cuadras = ~300 m
    assert ub.punto_de_cuadra(a, b, c) is not None
    assert ub.punto_de_cuadra(a, b, c, max_m=200) is None


def test_esquina_en_dos_lugares_lejanos_es_ambigua():
    """A cruza a B en dos puntos distintos: no se adivina cuál."""
    a = [[[0.0, 0.0], [0.0, 0.01]], [[0.0, 0.01], [0.0, 0.02]]]
    b = [[[-0.001, 0.0], [0.0, 0.0]], [[0.0, 0.02], [0.001, 0.02]]]
    assert len(ub.esquinas_entre(a, b)) == 2
    assert ub.punto_de_esquina(a, b) is None


# ═══════════════════════════════════════════════════════ ubicar

def test_ubicar_por_esquina_sin_tocar_nominatim():
    r = ub.ubicar(None, "Z/Central, Calle La Madrid #282 esq. Sucre", CIUDAD, tramos=grilla(), pedir=None)
    assert r["metodo"] == "esquina" and cerca(r, esquina_de(0, 0))
    assert "La Madrid" in r["display_name"] and "Sucre" in r["display_name"] and "Tarija" in r["display_name"]


def test_ubicar_por_cuadra():
    r = ub.ubicar(None, "C/Sucre entre La Madrid y Ingavi #0966", CIUDAD, tramos=grilla())
    assert r["metodo"] == "cuadra" and cerca(r, esquina_de(0, 0.5))


def test_ubicar_con_tildes_abreviaturas_y_articulos():
    t = grilla()
    r = ub.ubicar(None, "Calle Bolivar esq. Gral. Trigo", CIUDAD, tramos=t)
    assert r["metodo"] == "esquina" and cerca(r, esquina_de(1, 2))
    r = ub.ubicar(None, "C/Madrid entre Mendez y Suipacha", CIUDAD, tramos=t)         # «La Madrid» = «Madrid»
    assert r["metodo"] == "cuadra" and cerca(r, esquina_de(2.5, 0))
    # Ingavi y O'Connor son paralelas: no se tocan; sin Nominatim no hay punto
    assert ub.ubicar(None, "Calle Ingavi esquina O´connor", CIUDAD, tramos=t, usar_mapas=False) is None
    r = ub.ubicar(None, "Calle Sucre casi O´connor", CIUDAD, tramos=t)               # «casi» = esquina
    assert r["metodo"] == "esquina" and cerca(r, esquina_de(0, 3))


def test_la_misma_calle_como_esquina_no_se_ubica():
    assert ub.ubicar(None, "Calle Sucre esq. Sucre", CIUDAD, tramos=grilla(), usar_mapas=False) is None


def test_entre_con_una_calle_que_no_esta_cae_a_nominatim_y_se_marca_calle():
    llamadas = []
    r = ub.ubicar(None, "C/Sucre entre Corrado y Domingo Paz #0966", CIUDAD, tramos=grilla(),
                  pedir=nominatim_falso(llamadas=llamadas))
    assert r["metodo"] == "calle" and len(llamadas) == 1
    assert llamadas[0]["q"] == "Calle Sucre 966, Tarija"                      # la dirección limpia, sin «entre»


def test_empate_de_calles_no_da_punto_por_geometria():
    t = grilla(ns=["Calle General Trigo", "Calle Coronel Trigo", "Calle Ingavi", "Calle Junín"])
    assert ub.ubicar(None, "Calle Sucre esq. Trigo", CIUDAD, tramos=t, usar_mapas=False) is None


def test_fuera_de_la_caja_de_la_ciudad_no_hay_punto():
    otra = {**CIUDAD, "lat": -17.78, "lng": -63.18}                           # el centro está a cientos de km
    assert ub.ubicar(None, "Calle Sucre esq. La Madrid", otra, tramos=grilla(), usar_mapas=False) is None
    # la esquina Suipacha-O'Connor está a ~320 m del centro: entra en una caja de 1 km y no en una de 100 m
    lejana = "Calle Suipacha esq. O'Connor"
    assert ub.ubicar(None, lejana, CIUDAD, tramos=grilla(), radio_km=1)["metodo"] == "esquina"
    assert ub.ubicar(None, lejana, CIUDAD, tramos=grilla(), radio_km=0.1, usar_mapas=False) is None


def test_ciudad_sin_centro_no_acota_las_esquinas():
    r = ub.ubicar(None, "Calle Sucre esq. La Madrid", {"id": "x", "nombre": "Tarija"}, tramos=grilla())
    assert r["metodo"] == "esquina"


def test_respaldo_nominatim_con_la_direccion_limpia():
    llamadas = []
    r = ub.ubicar(None, "Z/Central, Calle La Madrid #282 esq. Sucre", CIUDAD, tramos=[],
                  pedir=nominatim_falso(llamadas=llamadas))
    assert r == {"lat": LAT0, "lng": LNG0, "display_name": "Calle de prueba, Tarija, Bolivia", "metodo": "calle"}
    assert llamadas[0]["q"] == "Calle La Madrid 282, Tarija" and llamadas[0]["bounded"] == 1


def test_direccion_sin_calle_entendible_va_tal_cual_a_nominatim():
    llamadas = []
    ub.ubicar(None, "Z/Central", CIUDAD, tramos=[], pedir=nominatim_falso(llamadas=llamadas))
    assert llamadas[0]["q"] == "Z/Central, Tarija"


def test_nominatim_sin_resultado_o_caido():
    assert ub.ubicar(None, "Calle Falsa 123", CIUDAD, tramos=[], pedir=lambda p: []) is None

    def caido(p):
        raise ConnectionError("sin red")

    with pytest.raises(tarjetas.UbicacionNoDisponible):
        ub.ubicar(None, "Calle Inventada 456", CIUDAD, tramos=[], pedir=caido)
    assert ub.ubicar(None, "Calle Inventada 456", CIUDAD, tramos=[], pedir=caido, usar_mapas=False) is None


def test_nominatim_fuera_de_la_caja_se_descarta():
    assert ub.ubicar(None, "Calle Falsa 123", CIUDAD, tramos=[], pedir=nominatim_falso(lat=-17.0, lng=-63.0)) is None


def test_si_la_esquina_se_encuentra_nunca_se_llama_a_nominatim():
    def prohibido(p):
        raise AssertionError("no tenía que pedir")

    assert ub.ubicar(None, "Calle Sucre esq. Ingavi", CIUDAD, tramos=grilla(), pedir=prohibido)["metodo"] == "esquina"


def test_direccion_vacia_o_muy_corta():
    assert ub.ubicar(None, "", CIUDAD, tramos=[]) is None
    assert ub.ubicar(None, None, CIUDAD, tramos=[]) is None
    assert ub.ubicar(None, "ab", CIUDAD, tramos=[]) is None


def test_las_calles_se_leen_del_repo_solo_si_hay_esquina_o_entre(repo):
    llamadas = []
    original = repo.list_calles_tramos
    repo.list_calles_tramos = lambda cid: (llamadas.append(cid), original(cid))[1]
    repo.upsert_calles_tramos([{k: v for k, v in f.items() if k not in ("id", "activo")} for f in grilla()])
    pedir = nominatim_falso()
    assert ub.ubicar(repo, "Calle Sucre 100", CIUDAD, pedir=pedir)["metodo"] == "calle"
    assert llamadas == []                                                     # sin esquina no se leen las calles
    assert ub.ubicar(repo, "Calle Sucre esq. La Madrid", CIUDAD, pedir=pedir)["metodo"] == "esquina"
    assert llamadas == [CIUDAD["id"]]
    assert ub.ubicar(repo, "Calle Sucre esq. La Madrid", {"nombre": "Sin id"}, pedir=pedir)["metodo"] == "calle"


def test_si_el_repo_falla_al_leer_las_calles_se_sigue_con_nominatim(repo):
    def roto(cid):
        raise RuntimeError("base caída")

    repo.list_calles_tramos = roto
    assert ub.ubicar(repo, "Calle Sucre esq. La Madrid", CIUDAD, pedir=nominatim_falso())["metodo"] == "calle"


# ═══════════════════════════════════════════════════════ el comando

def _importado(repo, i, direccion, **extra):
    fila = {"fuente": "turismo", "fuente_id": f"turismo:{i}", "ciudad_id": CIUDAD["id"], "nombre": f"Negocio {i}",
            "direccion": direccion, "lat": None, "lng": None, "ubicacion": "no_encontrada", "estado": "nuevo", **extra}
    return repo.crear_importado(fila)["id"]


def _cargar_grilla(repo):
    repo.upsert_calles_tramos([{k: v for k, v in f.items() if k not in ("id", "activo")} for f in grilla()])


def test_comando_en_dry_run_cuenta_y_no_guarda_nada(repo):
    _cargar_grilla(repo)
    e = _importado(repo, 1, "Z/Central, Calle La Madrid #282 esq. Sucre")
    c = _importado(repo, 2, "C/Sucre entre La Madrid y Ingavi")
    k = _importado(repo, 3, "Calle Bolívar 100", fuente="tarjeta")
    n = _importado(repo, 4, "Z/Central")
    # no entran: ya tiene punto, ya revisado, otra fuente, sin dirección
    _importado(repo, 5, "Calle Sucre esq. Ingavi", lat=-22.7, lng=-64.3)
    _importado(repo, 6, "Calle Sucre esq. Ingavi", estado="promovido")
    _importado(repo, 7, "Calle Sucre esq. Ingavi", fuente="osm")
    _importado(repo, 8, None)
    antes = {i: dict(f) for i, f in repo.importados.items()}
    salida = []
    pedidos = []

    def pedir(params):
        pedidos.append(params["q"])
        return [] if "Z/Central" in params["q"] else [
            {"lat": str(LAT0), "lon": str(LNG0), "display_name": "Calle Bolívar, Tarija"}]

    assert ub.main(["--ciudad", "tarija", "--dry-run"], repo, pedir=pedir, mostrar=salida.append) == 0
    assert {i: dict(f) for i, f in repo.importados.items()} == antes            # dry-run: nada guardado
    texto = "\n".join(salida)
    assert "4 importados sin punto" in texto and "SIMULACIÓN" in texto
    assert "Por esquina:     1" in texto and "Por cuadra:      1" in texto
    assert "Por calle:       1" in texto and "Sin encontrar:   1" in texto
    assert "Negocio 4" in texto.split("Sin encontrar:")[1]                       # lista los que no encontró
    assert pedidos == ["Z/Central, Tarija", "Calle Bolívar 100, Tarija"]         # sólo lo que las calles no resolvieron
    assert e and c and k and n


def test_comando_guarda_punto_aproximado(repo):
    _cargar_grilla(repo)
    e = _importado(repo, 1, "Calle La Madrid #282 esq. Sucre")
    c = _importado(repo, 2, "C/Sucre entre La Madrid y Ingavi", ubicacion="no_encontrada")
    salida = []
    assert ub.main(["--ciudad", "tarija"], repo, pedir=lambda p: [], mostrar=salida.append) == 0
    fe, fc = repo.importados[e], repo.importados[c]
    assert fe["ubicacion"] == fc["ubicacion"] == "aproximada"
    assert ub.distancia_m((fe["lat"], fe["lng"]), esquina_de(0, 0)) < 1
    assert ub.distancia_m((fc["lat"], fc["lng"]), esquina_de(0, 0.5)) < 1
    assert fe["direccion"] == "Calle La Madrid #282 esq. Sucre" and fe["estado"] == "nuevo"   # sólo toca el punto
    assert "SIMULACIÓN" not in "\n".join(salida)


def test_comando_sin_calles_lo_avisa_y_sigue_con_nominatim(repo):
    i = _importado(repo, 1, "Calle La Madrid 282")
    salida = []
    assert ub.main(["--ciudad", "tarija"], repo, pedir=nominatim_falso(), mostrar=salida.append) == 0
    assert "no tiene calles cargadas" in "\n".join(salida)
    assert repo.importados[i]["lat"] == LAT0 and repo.importados[i]["ubicacion"] == "aproximada"


def test_comando_deja_de_pedirle_a_nominatim_tras_5_fallas_pero_sigue_con_las_esquinas(repo):
    _cargar_grilla(repo)
    for n in range(8):
        _importado(repo, n, f"Calle Falsa {n}00")                                # 8 que sólo Nominatim podría resolver
    esq = _importado(repo, 99, "Calle Sucre esq. Ingavi")
    pedidos = []

    def caido(params):
        pedidos.append(params["q"])
        raise ConnectionError("sin red")

    salida = []
    assert ub.main(["--ciudad", "tarija"], repo, pedir=caido, mostrar=salida.append) == 0
    assert len(pedidos) == 5                                                       # a la sexta ya no lo intenta
    texto = "\n".join(salida)
    assert "se deja de pedirle" in texto and "Por esquina:     1" in texto and "Sin encontrar:   8" in texto
    assert repo.importados[esq]["ubicacion"] == "aproximada"


def test_comando_limite_y_validaciones(repo):
    _cargar_grilla(repo)
    for n in range(3):
        _importado(repo, n, "Calle Sucre esq. Ingavi")
    salida = []
    assert ub.main(["--ciudad", "tarija", "--limite", "2"], repo, pedir=lambda p: [], mostrar=salida.append) == 0
    assert sum(1 for f in repo.importados.values() if f["lat"] is not None) == 2
    assert ub.main(["--ciudad", "tarija", "--limite", "0"], repo) == 2


def test_comando_ciudad_inexistente(repo, monkeypatch):
    monkeypatch.setattr(repo, "get_ciudad", lambda slug: None)
    assert ub.main(["--ciudad", "nada"], repo) == 2


# ═══════════════════════════════════════════════════════ el botón «Buscar la dirección» del panel

def test_el_endpoint_ubicar_usa_la_esquina(client, repo, monkeypatch):
    repo.upsert_calles_tramos([{k: v for k, v in f.items() if k not in ("id", "activo")} for f in grilla()])
    monkeypatch.setattr(repo, "get_ciudad_por_id", lambda cid: CIUDAD if cid else None)
    iid = _importado(repo, 1, "x")
    token = auth.make_token("datos@uruku.bo", rol="x", roles=["x"], permisos=["datos"])
    r = client.post(f"/admin/importados/{iid}/ubicar", headers={"Authorization": f"Bearer {token}"},
                    json={"direccion": "Z/Central, Calle La Madrid #282 esq. Sucre"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["metodo"] == "esquina" and j["encontrado"] is True and j["aproximada"] is True
    f = repo.importados[iid]
    assert f["ubicacion"] == "aproximada" and ub.distancia_m((f["lat"], f["lng"]), esquina_de(0, 0)) < 1
    assert f["direccion"] == "Z/Central, Calle La Madrid #282 esq. Sucre"


def test_el_importador_de_turismo_usa_el_mismo_ubicador(repo):
    from app.services import importar_turismo as it

    _cargar_grilla(repo)
    e = it.Entrada(seccion="donde-comer", subcategoria="restaurantes", nombre="Fogón del Valle",
                   direccion="Z/Central, Calle La Madrid #282 esq. Sucre", telefonos=["4 6648444"],
                   enlace=None, url="https://tarijaturismo.com/donde-comer/")
    r = it.cargar(repo, [e], {"id": CIUDAD["id"], "nombre": "Tarija", "lat": LAT0, "lng": LNG0}, pedir=lambda p: [])
    assert r.nuevas == 1 and r.con_punto == 1 and r.por_metodo["esquina"] == 1
    fila = next(iter(repo.importados.values()))
    assert fila["ubicacion"] == "aproximada" and ub.distancia_m((fila["lat"], fila["lng"]), esquina_de(0, 0)) < 1
