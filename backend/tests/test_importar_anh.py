"""Importar las estaciones de servicio de la ANH a Importados (docs/vigia-fuentes.md). Nunca sale a la red: `leer` es
un falso. El HTML es sintético (escrito a mano, con la estructura de la página de la ANH): el real no se sube al repo,
que es público."""
import uuid

import pytest

from app.core import auth
from app.services import importar_anh as ia
from app.services import tarjetas, ubicar_direccion

TARIJA = ia.DEPARTAMENTOS["tarija"]
CIUDADES = {
    "tarija": {"id": "c-tarija", "slug": "tarija", "nombre": "Tarija", "departamento": "Tarija",
               "lat": -21.5355, "lng": -64.7296},
    "yacuiba": {"id": "c-yacuiba", "slug": "yacuiba", "nombre": "Yacuiba", "departamento": "Tarija",
                "lat": -22.0146, "lng": -63.6775},
    "sucre": {"id": "c-sucre", "slug": "sucre", "nombre": "Sucre", "departamento": "Chuquisaca",
              "lat": -19.0333, "lng": -65.2627},
}
URL = "https://www.anh.gob.bo/w2026/contenido.php?s=40&R=1&D=6"


def h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def datos():
    return h(auth.make_token("datos@uruku.bo", rol="x", roles=["x"], permisos=["datos"]))


@pytest.fixture(autouse=True)
def _sin_red(monkeypatch):
    tarjetas.reiniciar_cache()
    monkeypatch.setattr(tarjetas, "_dormir", lambda s: None)

    def sin_red(params):
        raise AssertionError("Nominatim: un test salió a la red")
    monkeypatch.setattr(tarjetas, "_pedir_nominatim", sin_red)

    def sin_anh(url):
        raise AssertionError("ANH: un test salió a la red")
    monkeypatch.setattr(ia, "_pedir", sin_anh)


@pytest.fixture
def repo(repo):
    """El repo falso, con las ciudades del departamento (con su departamento y su centro) y el rubro."""
    repo.list_ciudades = lambda: [{"id": c["id"], "slug": k, "nombre": c["nombre"]} for k, c in CIUDADES.items()]
    repo.get_ciudad = lambda slug: CIUDADES.get(slug)
    repo.rubros["estacion-servicio"] = "rub-es"
    return repo


# ───────────────────────────────────────────── HTML sintético

def fila_html(nombre, direccion, telefono, licencia, productos, lat=None, lng=None, depto="TARIJA"):
    marca = (f"<br/><a class='btn btn-default' data-toggle='modal' data-target='#modal' "
             f"onclick=\"setMark({lat},{lng},'{nombre}');\">Mostrar Ubicación</a>") if lat is not None else ""
    return (f"<tr>\n<td style='width: 100%; font-size: 12px;'>{nombre}</td>\n"
            f"<td style='width: 100%; font-size: 12px;'><b>DIRECCIÓN: </b>{direccion}<br/>"
            f"<b>TELÉFONO: </b>{telefono}</td>\n"
            f"<td style='width: 100%; font-size: 12px;'>{licencia}</td>\n"
            f"<td style='width: 100%; font-size: 12px;'>{productos} </td>\n"
            f"<td style='width: 100%; font-size: 12px;'>{depto}{marca}</td>\n</tr>")


def pagina(*filas, titulos=True, con_tabla=True):
    cabeza = ("<thead><tr><th class='r'>RAZÓN SOCIAL</th><th class='r'>CONTACTO</th><th class='r'>LICENCIA</th>"
              "<th class='r'>PRODUCTOS</th><th class='r'>UBICACIÓN</th></tr></thead>") if titulos else ""
    tabla = (f"<table class='table' id='search_table'>{cabeza}<tbody>{''.join(filas)}</tbody></table>"
             if con_tabla else "<p>Sin resultados</p>")
    return ("<html><head><script>var x = 1;</script></head><body><select><option>Otra actividad</option></select>"
            f"<div class='row'>{tabla}</div></body></html>")


ALAMOS = fila_html('ESTACION DE SERVICIO "LOS ALAMOS" S.R.L.', "AV. DEMO 123 ZONA EL CENTRO", "6600001",
                   "ANH09001-CLES01-LIC09/2026", "DIESEL OIL GASOLINA ESPECIAL GASOLINA ESPECIAL (+)",
                   -21.5400, -64.7300)
ALAMOS_GNV = fila_html('ESTACIÓN DE SERVICIO "LOS ALAMOS" S.R.L.', "AVENIDA DEMO NRO 123", "6600001",
                       "ANH09001-CGNES01-LIC08/2025", "GAS NATURAL VEHICULAR", -21.5401, -64.7301)
SAN_LORENZO = fila_html("EL MOLLE DE PRUEBA S.R.L.", "CARRETERA TARIJA - SAN LORENZO KM.11 ZONA: EL RANCHO",
                        "6600002", "ANH09002-CLES01-LIC09/2026", "DIESEL OIL", -21.4531, -64.7533)
YACUIBA = fila_html("SURTIDOR PRUEBA YACUIBA", "YACUIBA, AVDA. LOS DEMOS, ESQ. INDEPENDENCIA", "71012345 - 6820000",
                    "ANH09003-CLES01-LIC09/2026", "DIESEL OIL SUPER ETANOL 92", -22.0094, -63.6810)
SIN_PUNTO = fila_html("GASOLINERA SIN MAPA", "TARIJA - AV. SIN PUNTO N° S/N", "6600004",
                      "ANH09004-CLES01-LIC09/2026", "GASOLINA ESPECIAL")
VILLAMONTES = fila_html("ESTACION DE PRUEBA VILLAMONTES", "VILLAMONTES - CARR. A SANTA CRUZ KM 1", "46700000",
                        "ANH09005-CLES01-LIC09/2026", "DIESEL OIL", -21.2569, -63.4559)
LIQUIDOS = pagina(ALAMOS, SAN_LORENZO, YACUIBA, SIN_PUNTO, VILLAMONTES)
GNV = pagina(ALAMOS_GNV)


def crudas_de(*paginas):
    out = []
    for html, actividad in paginas:
        out += ia.parsear_pagina(html, url=URL, actividad=actividad)
    return out


def correr(repo, crudas, *args):
    salida: list[str] = []
    codigo = ia.main(["--departamento", "tarija", *args], repo, leer=lambda *a, **k: crudas, mostrar=salida.append)
    return codigo, "\n".join(salida)


def importados(repo):
    return [f for f in repo.importados.values() if f["fuente"] == "anh"]


# ───────────────────────────────────────────── parseo

def test_parsear_pagina_lee_las_columnas_el_punto_y_el_origen():
    filas = ia.parsear_pagina(LIQUIDOS, url=URL, actividad="liquidos")
    assert len(filas) == 5
    f = filas[0]
    assert f["nombre"] == 'ESTACION DE SERVICIO "LOS ALAMOS" S.R.L.'
    assert f["direccion"] == "AV. DEMO 123 ZONA EL CENTRO" and f["telefono"] == "6600001"
    assert f["licencia"] == "ANH09001-CLES01-LIC09/2026"
    assert f["productos"] == "DIESEL OIL GASOLINA ESPECIAL GASOLINA ESPECIAL (+)"
    assert f["ubicacion_texto"] == "TARIJA"                 # el texto del botón no se mezcla con la celda
    assert (f["lat"], f["lng"]) == (-21.54, -64.73)
    assert f["url"] == URL and f["actividad"] == "liquidos"
    assert filas[3]["lat"] is None and filas[3]["lng"] is None      # sin botón de ubicación


def test_parsear_pagina_sin_titulos_usa_el_orden_de_siempre():
    filas = ia.parsear_pagina(pagina(ALAMOS, titulos=False), url=URL)
    assert filas[0]["nombre"].startswith("ESTACION") and filas[0]["telefono"] == "6600001"


def test_parsear_pagina_con_las_columnas_en_otro_orden():
    html = ("<table id='search_table'><thead><tr><th>CONTACTO</th><th>RAZÓN SOCIAL</th></tr></thead><tbody>"
            "<tr><td><b>DIRECCIÓN: </b>CALLE A<br/><b>TELÉFONO: </b>6611111</td><td>ALFA S.R.L.</td></tr>"
            "</tbody></table>")
    f = ia.parsear_pagina(html)[0]
    assert f["nombre"] == "ALFA S.R.L." and f["direccion"] == "CALLE A" and f["telefono"] == "6611111"


def test_un_punto_fuera_de_bolivia_se_ignora():
    html = pagina(fila_html("A S.R.L.", "TARIJA - X", "6600000", "ANH1111-CLES01", "DIESEL", 0, 0),
                  fila_html("B S.R.L.", "TARIJA - X", "6600000", "ANH1112-CLES01", "DIESEL", 21.5, 64.7))
    assert [(f["lat"], f["lng"]) for f in ia.parsear_pagina(html)] == [(None, None), (None, None)]


def test_pagina_sin_tabla_o_sin_columnas_lanza():
    with pytest.raises(ia.PaginaInesperada):
        ia.parsear_pagina(pagina(con_tabla=False))
    with pytest.raises(ia.PaginaInesperada):
        ia.parsear_pagina("<table id='search_table'><thead><tr><th>OTRA COSA</th></tr></thead></table>")


def test_tabla_vacia_no_es_un_error():
    assert ia.parsear_pagina(pagina()) == []


# ───────────────────────────────────────────── normalizar

def test_combustibles_de():
    assert ia.combustibles_de("DIESEL OIL GASOLINA ESPECIAL GASOLINA ESPECIAL (+) ") == [
        "Diesel oil", "Gasolina especial", "Gasolina especial (+)"]
    assert ia.combustibles_de("GAS NATURAL VEHICULAR") == ["Gas natural vehicular"]
    assert ia.combustibles_de("DIESEL OIL BIODIESEL X") == ["Diesel oil", "Biodiesel x"]       # lo nuevo no se pierde
    assert ia.combustibles_de("") == []


def test_telefonos_de_antepone_el_area_a_los_fijos_de_siete_digitos():
    fijos = ia.telefonos_de("6600001", "4")
    assert [t.numero for t in fijos] == ["+59146600001"] and fijos[0].tipo == "fijo"
    varios = ia.telefonos_de("71012345 - 6820000", "4")
    assert [t.numero for t in varios] == ["+59171012345", "+59146820000"]
    assert varios[0].tipo == "celular"
    assert ia.telefonos_de("sin teléfono", "4") == [] and ia.telefonos_de(None, "4") == []
    assert [t.numero for t in ia.telefonos_de("6600001 / 6600001", "4")] == ["+59146600001"]       # sin repetir


def test_codigo_de_licencia_sin_la_renovacion():
    assert ia.codigo_licencia("ANH00804-CLES02-LIC09/2026") == "ANH00804-CLES02"
    assert ia.codigo_licencia("anh00804-cles02") == "ANH00804-CLES02"
    assert ia.codigo_licencia("lo que sea") is None and ia.codigo_licencia(None) is None


def test_fuente_id_estable_entre_renovaciones_y_con_hash_si_no_hay_codigo():
    a = {"licencia": "ANH00804-CLES01-LIC09/2026", "nombre": "X", "direccion": "Y"}
    b = {"licencia": "ANH00804-CLES01-LIC03/2027", "nombre": "X", "direccion": "Y"}
    assert ia.fuente_id_de(TARIJA, a) == ia.fuente_id_de(TARIJA, b) == "anh:tarija:ANH00804-CLES01"
    sin = {"licencia": "", "nombre": 'Estación "Z"', "direccion": "Av. 1"}
    igual = {"licencia": "", "nombre": "ESTACION Z", "direccion": "AV 1"}
    otra = {"licencia": "", "nombre": "ESTACION Z", "direccion": "AV 2"}
    assert ia.fuente_id_de(TARIJA, sin) == ia.fuente_id_de(TARIJA, igual) != ia.fuente_id_de(TARIJA, otra)
    assert ia.fuente_id_de(TARIJA, sin).startswith("anh:tarija:")


def test_legible_pasa_las_mayusculas_y_respeta_las_siglas():
    assert ia.legible('ESTACION DE SERVICIO "EL TERO TERO" S.R.L.') == "Estación de Servicio El Tero Tero S.R.L."
    assert ia.legible('ESTACIÓN "EL PUENTE - Y.P.F.B."') == "Estación El Puente - Y.P.F.B."
    assert ia.legible("J.A.M.E. SUCURSAL BERMEJO") == "J.A.M.E. Sucursal Bermejo"
    assert ia.legible("AV. CIRCUNVALACION S/N") == "Av. Circunvalación S/N"
    assert ia.legible("Ya Viene Bien Escrito") == "Ya Viene Bien Escrito"
    assert ia.legible(None) == ""


def test_unir_actividades_junta_liquidos_y_gnv_de_la_misma_estacion():
    crudas = crudas_de((LIQUIDOS, "liquidos"), (GNV, "gnv"))
    assert len(crudas) == 6
    estaciones = ia.unir_actividades(crudas)
    assert len(estaciones) == 5
    alamos = estaciones[0]
    assert alamos["actividades"] == ["liquidos", "gnv"]
    assert alamos["licencias"] == ["ANH09001-CLES01-LIC09/2026", "ANH09001-CGNES01-LIC08/2025"]
    assert alamos["direccion"] == "AV. DEMO 123 ZONA EL CENTRO"            # manda la de líquidos
    assert alamos["unidas"] == 1


def test_unir_no_junta_sin_codigo_de_licencia():
    sin = [{"nombre": "X", "licencia": "", "actividad": "liquidos"}, {"nombre": "X", "licencia": "", "actividad": "gnv"}]
    assert len(ia.unir_actividades(sin)) == 2


# ───────────────────────────────────────────── ciudad

CIUDADES_TARIJA = [CIUDADES["tarija"], CIUDADES["yacuiba"]]


@pytest.mark.parametrize("direccion,lat,lng,esperada", [
    ("YACUIBA, AVDA. LOS DEMOS", None, None, "yacuiba"),                       # el municipio que nombra la dirección
    ("TARIJA- AV. PANAMERICANA", -21.60, -64.60, "tarija"),                   # gana el nombre, aunque el punto quede lejos
    ("AV. SIN CIUDAD S/N", -21.5400, -64.7300, "tarija"),                      # por el punto
    ("ZONA MORROS BLANCOS-AV. PANAMERICANA", -22.0094, -63.6810, "yacuiba"),
    ("CARRETERA TARIJA - SAN LORENZO KM.11", -21.4531, -64.7533, None),        # el camino no es la ciudad: afuera
    ("VILLAMONTES - CARR. SANTA CRUZ", -21.2569, -63.4559, None),              # sin ciudad en la tabla
    ("AV. SIN CIUDAD S/N", None, None, None),                                  # sin pistas: no se inventa
])
def test_asignar_ciudad(direccion, lat, lng, esperada):
    ciudad = ia.asignar_ciudad({"direccion": direccion, "lat": lat, "lng": lng}, CIUDADES_TARIJA)
    assert (ciudad or {}).get("slug") == esperada


def test_las_ciudades_son_solo_las_del_departamento(repo):
    assert [c["slug"] for c in ia.ciudades_del_departamento(repo, TARIJA)] == ["tarija", "yacuiba"]
    assert [c["slug"] for c in ia.ciudades_del_departamento(repo, ia.DEPARTAMENTOS["chuquisaca"])] == ["sucre"]


def test_los_nueve_departamentos_con_su_codigo():
    assert {d.slug: d.codigo for d in ia.DEPARTAMENTOS.values()} == {
        "chuquisaca": 1, "la-paz": 2, "cochabamba": 3, "oruro": 4, "potosi": 5, "tarija": 6, "santa-cruz": 7,
        "beni": 8, "pando": 9}
    assert ia.resolver_departamento("Potosí").slug == "potosi"
    assert ia.resolver_departamento("santa cruz").slug == "santa-cruz"
    assert ia.resolver_departamento("narnia") is None


# ───────────────────────────────────────────── la fila

def test_armar_fila_de_una_estacion_unida():
    estacion = ia.unir_actividades(crudas_de((LIQUIDOS, "liquidos"), (GNV, "gnv")))[0]
    f = ia.armar_fila(estacion, depto=TARIJA, ciudad=CIUDADES["tarija"], rubros_validos=lambda s: True)
    assert f["fuente"] == "anh" and f["fuente_id"] == "anh:tarija:ANH09001-CLES01"
    assert f["ciudad_id"] == "c-tarija" and f["estado"] == "nuevo" and f["rubro_slug"] == "estacion-servicio"
    assert f["nombre"] == "Estación de Servicio Los Alamos S.R.L." and f["direccion"] == "Av. Demo 123 Zona El Centro"
    assert "660 0001" in f["telefono"]
    assert f["whatsapp"] is None                                           # un fijo no abre un chat
    assert (f["lat"], f["lng"]) == (-21.54, -64.73) and f["ubicacion"] == "aproximada"
    assert f["horario"] is None and f["duplicado_de"] is None and f["fuente_url"] == URL
    anh = f["tags"]["anh"]
    assert anh["departamento"] == "Tarija" and anh["municipio"] == "Tarija" and anh["url"] == URL
    assert anh["combustibles"] == ["Diesel oil", "Gasolina especial", "Gasolina especial (+)",
                                   "Gas natural vehicular"]
    assert f["texto_leido"].startswith("ANH · estaciones de servicio · Tarija")
    assert URL in f["texto_leido"] and "Los Alamos" not in f["texto_leido"].splitlines()[0]


def test_armar_fila_celular_va_a_whatsapp_y_sin_punto_queda_no_encontrada():
    c = ia.parsear_pagina(pagina(YACUIBA), url=URL)[0]
    f = ia.armar_fila(c, depto=TARIJA, ciudad=CIUDADES["yacuiba"], rubros_validos=lambda s: True, usar_punto=False)
    assert f["whatsapp"] == "59171012345" and "682" in f["telefono"]
    assert f["lat"] is None and f["lng"] is None and f["ubicacion"] == "no_encontrada"
    assert f["tags"]["anh"]["punto_anh"] == {"lat": -22.0094, "lng": -63.681}        # queda guardado, no usado


def test_un_punto_lejos_de_su_ciudad_no_se_usa():
    c = {**ia.parsear_pagina(pagina(ALAMOS), url=URL)[0], "lat": -19.0, "lng": -65.0}
    f = ia.armar_fila(c, depto=TARIJA, ciudad=CIUDADES["tarija"], rubros_validos=lambda s: True)
    assert f["lat"] is None and f["ubicacion"] == "no_encontrada"


def test_rubro_que_no_existe_queda_vacio():
    c = ia.parsear_pagina(pagina(ALAMOS), url=URL)[0]
    assert ia.armar_fila(c, depto=TARIJA, ciudad=CIUDADES["tarija"], rubros_validos=lambda s: False)["rubro_slug"] is None


# ───────────────────────────────────────────── el comando

def test_simulacion_no_guarda_nada(repo):
    antes = len(repo.importados)
    codigo, salida = correr(repo, crudas_de((LIQUIDOS, "liquidos"), (GNV, "gnv")), "--dry-run")
    assert codigo == 0
    assert len(repo.importados) == antes
    assert "Entrarían" in salida and "SIMULACIÓN" in salida and "fuera_de_ciudad: 2" in salida
    assert "Leídos de la ANH:        6" in salida and "Unidos (misma estación en líquidos y GNV): 1" in salida
    assert "Por ciudad: Tarija 2, Yacuiba 1" in salida
    assert "Con WhatsApp (celular):  1" in salida


def test_carga_y_volver_a_correr_no_duplica(repo):
    crudas = crudas_de((LIQUIDOS, "liquidos"), (GNV, "gnv"))
    codigo, salida = correr(repo, crudas)
    assert codigo == 0
    nuevos = importados(repo)
    assert len(nuevos) == 3 and all(f["estado"] == "nuevo" for f in nuevos)
    assert {f["ciudad_id"] for f in nuevos} == {"c-tarija", "c-yacuiba"}
    codigo, salida = correr(repo, crudas)
    assert len(importados(repo)) == 3
    assert "Ya estaban:              3" in salida and "Nuevos en Importados:    0" in salida


def test_dry_run_despues_de_cargar_dice_que_ya_estaban(repo):
    crudas = crudas_de((LIQUIDOS, "liquidos"))
    correr(repo, crudas)
    _, salida = correr(repo, crudas, "--dry-run")
    assert "Ya estaban:              3" in salida and "Entrarían:    0" in salida


def test_sin_punto_ignora_el_de_la_anh(repo):
    correr(repo, crudas_de((LIQUIDOS, "liquidos")), "--sin-punto")
    assert all(f["lat"] is None and f["ubicacion"] == "no_encontrada" for f in importados(repo))
    assert all(f["tags"]["anh"]["punto_anh"] or f["nombre"].startswith("Gasolinera") for f in importados(repo))


def test_limite(repo):
    correr(repo, crudas_de((LIQUIDOS, "liquidos")), "--limite", "1")
    assert len(importados(repo)) == 1


def test_repetido_por_telefono(repo):
    cid = str(uuid.uuid4())
    repo.comercios[cid] = {"id": cid, "nombre": "Otro nombre", "ciudad_id": "c-tarija", "activo": True, "slug": "x",
                           "whatsapp": None, "telefono": "46600001"}
    correr(repo, crudas_de((pagina(ALAMOS), "liquidos")))
    assert importados(repo)[0]["duplicado_de"] == cid


def test_repetido_por_nombre_y_cercania(repo):
    cid = str(uuid.uuid4())
    repo.comercios[cid] = {"id": cid, "nombre": "Los Alamos", "lat": -21.5402, "lng": -64.7301,
                           "ciudad_id": "c-tarija", "activo": True, "slug": "x", "whatsapp": None}
    correr(repo, crudas_de((pagina(ALAMOS), "liquidos")))
    assert importados(repo)[0]["duplicado_de"] == cid


def test_con_punto_no_marca_repetido_a_un_homonimo_lejano(repo):
    cid = str(uuid.uuid4())
    repo.comercios[cid] = {"id": cid, "nombre": "Los Alamos", "lat": -21.60, "lng": -64.60,
                           "ciudad_id": "c-tarija", "activo": True, "slug": "x", "whatsapp": None}
    correr(repo, crudas_de((pagina(ALAMOS), "liquidos")))
    assert importados(repo)[0]["duplicado_de"] is None


def test_repetido_sin_punto_por_nombre_en_la_misma_ciudad(repo):
    cid = str(uuid.uuid4())
    repo.comercios[cid] = {"id": cid, "nombre": "Gasolinera Sin Mapa", "ciudad_id": "c-tarija", "activo": True,
                           "slug": "x", "whatsapp": None}
    otra = str(uuid.uuid4())
    repo.comercios[otra] = {"id": otra, "nombre": "Gasolinera Sin Mapa", "ciudad_id": "c-yacuiba", "activo": True,
                            "slug": "y", "whatsapp": None}
    correr(repo, crudas_de((pagina(SIN_PUNTO), "liquidos")))
    assert importados(repo)[0]["duplicado_de"] == cid


def test_argumentos_invalidos(repo):
    assert ia.main(["--departamento", "narnia"], repo, leer=lambda *a, **k: [], mostrar=lambda _: None) == 2
    assert ia.main(["--departamento", "tarija", "--limite", "0"], repo, leer=lambda *a, **k: []) == 2


def test_departamento_sin_ciudades_en_la_tabla_sale_con_error(repo):
    assert ia.main(["--departamento", "pando"], repo, leer=lambda *a, **k: [], mostrar=lambda _: None) == 2


def test_si_la_anh_no_contesta_sale_con_error(repo):
    def caido(*a, **k):
        raise OSError("sin red")
    assert ia.main(["--departamento", "tarija"], repo, leer=caido, mostrar=lambda _: None) == 1


def test_si_la_anh_cambio_la_pagina_sale_con_error(repo):
    def cambiada(*a, **k):
        return ia.parsear_pagina(pagina(con_tabla=False))
    assert ia.main(["--departamento", "tarija"], repo, leer=cambiada, mostrar=lambda _: None) == 1
    assert importados(repo) == []


# ───────────────────────────────────────────── lectura

def test_leer_anh_pide_las_dos_actividades_con_pausa(monkeypatch):
    pedidos, pausas = [], []
    monkeypatch.setattr(ia.time, "sleep", pausas.append)

    def pedir(url):
        pedidos.append(url)
        return (GNV if "R=2" in url else LIQUIDOS), url.replace("w2019", "w2026")

    filas = ia.leer_anh(TARIJA, pedir=pedir)
    assert pedidos == [ia.BASE_URL.format(actividad=1, codigo=6), ia.BASE_URL.format(actividad=2, codigo=6)]
    assert "D=6" in pedidos[0] and pausas == [ia.PAUSA_SEG]
    assert [f["actividad"] for f in filas] == ["liquidos"] * 5 + ["gnv"]
    assert all("/w2026/" in f["url"] for f in filas)                      # la URL de origen es la final


# ───────────────────────────────────────────── ubicador

def test_el_ubicador_levanta_las_filas_de_la_anh_sin_punto(repo):
    correr(repo, crudas_de((pagina(SIN_PUNTO), "liquidos")))
    assert importados(repo)[0]["lat"] is None
    antes = len(importados(repo))
    salida: list[str] = []
    punto = {"lat": "-21.5400", "lon": "-64.7300", "display_name": "Av. Sin Punto", "place_rank": 26}
    codigo = ubicar_direccion.main(["--ciudad", "tarija"], repo, pedir=lambda p: [punto], mostrar=salida.append)
    assert codigo == 0 and len(importados(repo)) == antes
    assert "1 importados sin punto" in "\n".join(salida)
    assert importados(repo)[0]["lat"] == -21.54 and importados(repo)[0]["ubicacion"] == "aproximada"


def test_rehacer_no_le_saca_a_la_anh_el_punto_que_trajo(repo):
    correr(repo, crudas_de((pagina(ALAMOS), "liquidos")))
    fila = importados(repo)[0]
    assert fila["lat"] == -21.54 and fila["ubicacion"] == "aproximada"
    codigo = ubicar_direccion.main(["--ciudad", "tarija", "--rehacer"], repo, pedir=lambda p: [],
                                   mostrar=lambda s: None)
    assert codigo == 0 and fila["lat"] == -21.54 and fila["ubicacion"] == "aproximada"


# ───────────────────────────────────────────── moderación

def test_listado_filtra_por_anh(client, repo, datos):
    correr(repo, crudas_de((pagina(ALAMOS), "liquidos")))
    repo.importados["otro"] = {"id": "otro", "fuente": "osm", "fuente_id": "node/1", "estado": "nuevo",
                               "nombre": "Otro", "ciudad_id": "c-tarija", "duplicado_de": None}
    r = client.get("/admin/importados", params={"fuente": "anh"}, headers=datos)
    assert r.status_code == 200, r.text
    assert [i["fuente"] for i in r.json()["items"]] == ["anh"]
    assert r.json()["items"][0]["texto_leido"].startswith("ANH · estaciones de servicio")


def test_promover_una_estacion_de_la_anh(client, repo, datos):
    correr(repo, crudas_de((LIQUIDOS, "liquidos"), (GNV, "gnv")))
    iid = next(k for k, f in repo.importados.items() if f["fuente"] == "anh" and f["nombre"].startswith("Estación"))
    r = client.post(f"/admin/importados/{iid}/promover", json={}, headers=datos)
    assert r.status_code == 200, r.text
    com = repo.comercios[r.json()["comercio"]["id"]]
    assert com["nombre"] == "Estación de Servicio Los Alamos S.R.L." and com["cargado_por"] == "import:anh"
    assert com["lat"] == -21.54 and com["ciudad_id"] == "c-tarija" and com["confiable"] is False
    assert com["telefono"] and com["whatsapp"] is None
    assert repo.importados[iid]["estado"] == "promovido"


def test_promover_sin_punto_no_se_puede_para_la_anh(client, repo, datos):
    correr(repo, crudas_de((pagina(SIN_PUNTO), "liquidos")))
    iid = next(k for k, f in repo.importados.items() if f["fuente"] == "anh")
    r = client.post(f"/admin/importados/{iid}/promover", json={"sin_ubicacion": True}, headers=datos)
    assert r.status_code == 400, r.text           # una estación tiene que tener punto
    assert repo.importados[iid]["estado"] == "nuevo"
