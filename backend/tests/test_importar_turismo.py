"""Importar negocios de la página de turismo (docs/importar-turismo.md): un test por criterio de terminado.

El HTML de ejemplo es CHICO y sintético: imita la estructura de Elementor de tarijaturismo.com (artículos con
nombre, lista de líneas y, en «Qué hacer», tarjetas con extracto) pero no copia nada de la página real. Nada sale a
la red: la descarga y Nominatim se reemplazan.
"""
import uuid

import pytest

from app.core import auth
from app.services import importar_turismo as it
from app.services import tarjetas

BASE = "https://tarijaturismo.com"
URL_DORMIR = f"{BASE}/donde-dormir/"
URL_COMER = f"{BASE}/donde-comer/"
URL_HACER = f"{BASE}/que-hacer/"
URL_OPERADORAS = f"{BASE}/operadoras-de-turismo/"
URL_AGENCIAS = f"{BASE}/agencias-de-viajes/"
URL_MOVERSE = f"{BASE}/como-moverse/"
URL_GUIAS = f"{BASE}/guias-de-turismo-autorizados/"


def h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def datos():
    return h(auth.make_token("datos@uruku.bo", rol="x", roles=["x"], permisos=["datos"]))


@pytest.fixture(autouse=True)
def _sin_red_ni_esperas(monkeypatch):
    """Nominatim NUNCA se llama de verdad y el segundo de espera no se duerme."""
    tarjetas.reiniciar_cache()
    monkeypatch.setattr(tarjetas, "_dormir", lambda s: None)

    def sin_red(params):
        raise AssertionError("Nominatim: un test salió a la red")

    monkeypatch.setattr(tarjetas, "_pedir_nominatim", sin_red)
    yield
    tarjetas.reiniciar_cache()


# ───────────────────────────────────────────────────────────── HTML sintético

def ficha(cats, nombre, lineas, *, extra_cabeza=""):
    """Un `<article>` de ficha completa. `lineas`: [(texto, href|None)]."""
    items = "".join(
        '<li class="elementor-icon-list-item">'
        + (f'<a href="{href}">' if href else "")
        + f'<span class="elementor-icon-list-icon"><svg><path d="M0 0"></path></svg></span>'
        f'<span class="elementor-icon-list-text">{texto}</span>'
        + ("</a>" if href else "") + "</li>"
        for texto, href in lineas)
    clases = " ".join(f"category-{c}" for c in cats)
    return (f'<article class="elementor-post elementor-grid-item post-1 post {clases}" role="listitem">'
            f'<div class="elementor-post__text"><div class="elementor-post__content">'
            f'<style>.x{{color:red}}</style>{extra_cabeza}'
            f'<div class="elementor-widget-container"><h2 class="elementor-heading-title elementor-size-default">'
            f'{nombre}</h2></div>'
            f'<ul class="elementor-icon-list-items">{items}</ul>'
            f'<iframe src="https://maps.google.com/maps?q=x" title="{nombre}"></iframe>'
            f'<img src="https://tarijaturismo.com/wp-content/uploads/foto.webp" alt="">'
            f'</div></div></article>')


def tarjeta(cats, nombre, extracto):
    clases = " ".join(f"category-{c}" for c in cats)
    return (f'<article class="elementor-post elementor-grid-item post-2 post {clases}" role="listitem">'
            f'<a class="elementor-post__thumbnail__link" href="{BASE}/detalle/"><img src="{BASE}/foto.webp"></a>'
            f'<div class="elementor-post__text"><h3 class="elementor-post__title">'
            f'<a href="{BASE}/detalle-{uuid.uuid4().hex[:6]}/"> {nombre} </a></h3>'
            f'<div class="elementor-post__excerpt"><p>{extracto}</p></div></div></article>')


#: Encabezado de subcategoría y pie de página: están FUERA de los artículos y no deben leerse.
SUBTITULO = '<div><h2 class="elementor-heading-title">Hostales</h2></div>'
PIE = ('<footer><h2 class="elementor-heading-title">Enlaces de Interés</h2><ul class="elementor-icon-list-items">'
       '<li><a href="/como-llegar/"><span class="elementor-icon-list-text">¿Cómo llegar a Tarija?</span></a></li></ul>'
       '</footer>')

HTML_DORMIR = (
    "<html><body>"
    + ficha(["donde-dormir", "hoteles"], "Hotel Los Parrales", [
        ("Urb. El Carmen de Aranjuez", None),
        ("Telefono: 466-48444 / +591 75111885", None),
        ("www.facebook.com/losparraleshotel", "http://www.facebook.com/losparraleshotel")])
    + SUBTITULO
    + ficha(["donde-dormir", "hostales"], "Hostal Bolívar", [
        ("Calle Bolívar No 256 entre Méndez y Suipacha", None),
        ("Telefono:+591 72995676", None)])
    + ficha(["donde-dormir", "residenciales"], "Residencial Guadalquivir", [
        ("Calle Ángel Calavi N° 127", None),
        ("Telefono: 73487166 - 46672229", None),
        ("residencial@gmail.com", None)])
    + ficha(["donde-dormir", "hoteles"], "Hotel Fantasma", [("Horarios: 06:00 – 19:00", None)])
    + PIE + "</body></html>")

HTML_COMER = (
    "<html><body>"
    + ficha(["donde-comer", "churrasquerias"], "El Asador Chaqueño", [
        ("Calle Ingavi entre Federico Avila y España", None),
        ("Telefono: +591 72968998", None),
        ("Sucursal # 2 B/Juan XXIII Av. Romero esq. Defensores del Chaco", None),
        ("Telefono: +591 466 54999 / +591 76185560", None)])
    + ficha(["donde-comer", "mercados-municipales"], "Mercado Avaroa", [("Horarios: 06:00 – 19:00", None)])
    + ficha(["donde-comer", "saltenerias"], "Salteñería Nanos", [
        ("Av. Las Américas esq. Junín", None),
        ("Telefono: +591 68741758", None),
        ("Av. Potosí # 732 pasando la calle O’connor", None)])
    + "</body></html>")

HTML_HACER = (
    "<html><body>"
    + tarjeta(["bodegas-y-vinotecas", "que-hacer"], "Bodega La Angostura",
              "Dirección Barrio Miraflores, Calle 4, Nº 333 Teléfono +591 72965171 Nuestras Redes:")
    + tarjeta(["plazas-parques-y-miradores", "que-hacer"], "Plaza Campero",
              "Dirección Calle Fray Manuel Mingo entre calle Campero y calle Gral. Trigo Horarios Abierto 24")
    + tarjeta(["museos-y-bibliotecas", "que-hacer"], "Museo San Roque",
              "Dirección Calle Gral. Trigo entre Fray M. Mingo Teléfono +591 70222889 Entrada")
    + tarjeta(["fuera-de-la-ciudad", "que-hacer"], "Cañón del Pilaya", "Información El Cañón del Pilaya es un")
    + "</body></html>")

HTML_OPERADORAS = (
    "<html><body>"
    + ficha(["agencias-de-viajes", "operadoras-de-turismo"], "Viva Tours", [
        ("Calle Bolivar, entre Sucre y Daniel Campos, Piso #2", None), ("Telefono: +591 65826498", None)])
    + "</body></html>")

HTML_AGENCIAS = HTML_OPERADORAS      # el mismo negocio aparece en las dos secciones

def tabla(cabecera, filas):
    """Una tabla de TablePress: `filas` = [[(columna, texto, rowspan|None), ...]]; las celdas llevan `column-N`."""
    th = "".join(f'<th class="column-{i}">{c}</th>' for i, c in enumerate(cabecera, 1))
    trs = ""
    for fila in filas:
        tds = "".join(f'<td{f" rowspan={chr(34)}{rs}{chr(34)}" if rs else ""} class="column-{col}">{txt}</td>'
                      for col, txt, rs in fila)
        trs += f'<tr class="row-2">{tds}</tr>'
    return (f'<table class="tablepress"><thead><tr class="row-1">{th}</tr></thead>'
            f'<tbody>{trs}</tbody></table>')


VACIA = [(1, "", None), (2, "", None), (3, "", None), (4, "", None)]

HTML_MOVERSE = (
    "<html><body>"
    + tabla(["<strong>Transporte</strong>", "<strong>Teléfono</strong>"], [
        [(1, "Radio Móvil Sol", None), (2, "+591 466 63030", None)],
        [(1, "Movil Test", None), (2, "+591 75114470 / +591 75114428", None)]])
    + tabla(["ASOCIACION", "DESTINO", "PRECIO REF.", "PUNTO DE SALIDA"], [
        [(1, "VALLE Telf. 66 - 48064", None), (2, "Valle de La Concepción", None), (3, "8,50Bs.", None),
         (4, "Av. Froilán Tejerina C/ Corrado", None)],
        VACIA,
        [(1, "AS. VIRGEN DEL ROSARIO Cel. 67373722", None), (2, "TOLOMOSA", None), (3, "7 Bs.", None),
         (4, "Av. Froilán Tejerina y C/ Pantoja", None)],
        VACIA,
        [(1, "BELLA VISTA", 2), (2, "BELLA VISTA", None), (3, "6 Bs.", None), (4, "Calle Pantoja", 2)],
        [(2, "SAN PEDRO DE SOLA", None), (3, "6 Bs.", None)]])
    + tabla(["LUGAR", "EMPRESA", "TELEFONO", "HORARIO"], [          # buses entre ciudades: no se leen
        [(1, "DE TARIJA A LA PAZ", 1), (2, "Villa del Norte", None), (3, "67370711/72941850", None),
         (4, "18:30", None)]])
    + "</body></html>")

HTML_GUIAS = (
    "<html><body>"
    + tabla(["Nombre", "Contacto", "Licencia"], [
        [(1, "Angela Tejerina Castro", None), (2, '<a href="tel:59176197685">76197685 <i class="fa"></i></a>', None),
         (3, "Vigente", None)],
        [(1, "Mariela Sanchez", None), (2, '<a href="tel:59160264560">60264560</a> - 78257882', None),
         (3, "Vigente", None)],
        [(1, "Pedro Vencido", None), (2, "70000001", None), (3, "Vencida", None)],
        [(1, "Sin Licencia", None), (2, "70000002", None), (3, "", None)]])
    + "</body></html>")


PAGINAS = {URL_DORMIR: HTML_DORMIR, URL_COMER: HTML_COMER, URL_HACER: HTML_HACER, URL_OPERADORAS: HTML_OPERADORAS,
           URL_AGENCIAS: HTML_AGENCIAS, URL_MOVERSE: HTML_MOVERSE, URL_GUIAS: HTML_GUIAS}


def todas_las_entradas():
    return [e for url, html in PAGINAS.items() for e in it.leer_pagina(html, url)]


@pytest.fixture
def ciudad(repo):
    repo.rubros["hospedaje"] = "rub-hosp"
    repo.rubros["comida-rapida"] = "rub-cr"
    repo.rubros["taxis"] = "rub-taxis"
    return repo.get_ciudad("tarija")


def por_nombre(entradas, nombre):
    return [e for e in entradas if e.nombre == nombre]


# ═══════════════════════════════════════════════════════ el parser

def test_lee_las_fichas_de_donde_dormir():
    es = it.leer_pagina(HTML_DORMIR, URL_DORMIR)
    assert [e.nombre for e in es] == ["Hotel Los Parrales", "Hostal Bolívar", "Residencial Guadalquivir", "Hotel Fantasma"]
    p = es[0]
    assert p.direccion == "Urb. El Carmen de Aranjuez"
    assert p.telefonos == ["466-48444 / +591 75111885"]
    assert p.enlace == "http://www.facebook.com/losparraleshotel"          # el href, no el texto sin esquema
    assert p.seccion == "donde-dormir" and p.subcategoria == "hoteles" and p.url == URL_DORMIR
    assert es[1].subcategoria == "hostales" and es[1].telefonos == ["+591 72995676"]


def test_el_encabezado_de_subcategoria_y_el_pie_de_pagina_no_son_negocios():
    nombres = [e.nombre for e in it.leer_pagina(HTML_DORMIR, URL_DORMIR)]
    assert "Hostales" not in nombres and "Enlaces de Interés" not in nombres
    assert all("llegar" not in " ".join(e.lineas) for e in it.leer_pagina(HTML_DORMIR, URL_DORMIR))


def test_un_correo_suelto_no_es_una_direccion():
    r = por_nombre(it.leer_pagina(HTML_DORMIR, URL_DORMIR), "Residencial Guadalquivir")
    assert len(r) == 1 and r[0].email == "residencial@gmail.com" and r[0].direccion == "Calle Ángel Calavi N° 127"


def test_una_sucursal_es_otra_entrada_con_su_propio_telefono():
    es = por_nombre(it.leer_pagina(HTML_COMER, URL_COMER), "El Asador Chaqueño")
    assert len(es) == 2
    assert es[0].sucursal is False and es[0].direccion == "Calle Ingavi entre Federico Avila y España"
    assert es[1].sucursal is True and es[1].direccion == "B/Juan XXIII Av. Romero esq. Defensores del Chaco"
    assert [t.numero for t in it.telefonos_de(es[0])] == ["+59172968998"]
    assert [t.numero for t in it.telefonos_de(es[1])] == ["+59146654999", "+59176185560"]


def test_una_direccion_suelta_despues_de_un_telefono_es_otra_sucursal_sin_telefono():
    es = por_nombre(it.leer_pagina(HTML_COMER, URL_COMER), "Salteñería Nanos")
    assert [(e.direccion, e.sucursal, it.telefonos_de(e) != []) for e in es] == [
        ("Av. Las Américas esq. Junín", False, True), ("Av. Potosí # 732 pasando la calle O’connor", True, False)]


def test_las_tarjetas_de_que_hacer_leen_direccion_y_telefono_del_extracto():
    es = it.leer_pagina(HTML_HACER, URL_HACER)
    assert [e.nombre for e in es] == ["Bodega La Angostura", "Plaza Campero", "Museo San Roque", "Cañón del Pilaya"]
    b = es[0]
    assert b.direccion == "Barrio Miraflores, Calle 4, Nº 333"       # corta donde empieza el otro rótulo
    assert [t.numero for t in it.telefonos_de(b)] == ["+59172965171"]
    assert b.subcategoria == "bodegas-y-vinotecas" and b.detalle.startswith(BASE)
    assert es[1].direccion.startswith("Calle Fray Manuel Mingo") and es[1].telefonos == []
    assert es[3].direccion is None and es[3].telefonos == []


def test_no_baja_ni_nombra_ninguna_imagen():
    texto = repr([e.__dict__ for e in todas_las_entradas()])
    assert ".webp" not in texto and "<img" not in texto and "uploads" not in texto


def test_html_vacio_o_sin_articulos_no_da_nada():
    assert it.leer_pagina("", URL_DORMIR) == []
    assert it.leer_pagina("<html><body><h2 class='elementor-heading-title'>Hola</h2></body></html>", URL_DORMIR) == []


def test_sin_telefono_ni_direccion_se_descarta():
    es = it.leer_pagina(HTML_DORMIR, URL_DORMIR) + it.leer_pagina(HTML_COMER, URL_COMER)
    descartadas = {e.nombre for e in es if not it.es_util(e)}
    assert descartadas == {"Hotel Fantasma", "Mercado Avaroa"}


def test_en_que_hacer_entra_lo_que_trae_telefono_o_direccion_y_queda_afuera_lo_que_no_trae_ninguno():
    es = {e.nombre: e for e in it.leer_pagina(HTML_HACER, URL_HACER)}
    assert it.es_util(es["Bodega La Angostura"]) and it.es_util(es["Museo San Roque"])
    assert it.es_util(es["Plaza Campero"])                 # una plaza con dirección entra
    assert not it.es_util(es["Cañón del Pilaya"])          # sólo «Información»: ni teléfono ni dirección


# ═══════════════════════════════════════════════════════ las tablas de «Cómo moverse» y las guías

def test_los_radio_moviles_son_taxis_sin_direccion():
    es = [e for e in it.leer_pagina(HTML_MOVERSE, URL_MOVERSE) if e.subcategoria == "radio-moviles"]
    assert [e.nombre for e in es] == ["Radio Móvil Sol", "Movil Test"]
    assert all(e.direccion is None and e.rubro == "taxis" and it.es_util(e) for e in es)
    assert [t.numero for t in it.telefonos_de(es[0])] == ["+59146663030"]
    assert [t.numero for t in it.telefonos_de(es[1])] == ["+59175114470", "+59175114428"]


def test_una_entrada_por_asociacion_con_el_punto_de_salida_y_los_destinos_en_el_texto():
    es = [e for e in it.leer_pagina(HTML_MOVERSE, URL_MOVERSE) if e.subcategoria == "transporte-alrededores"]
    assert [e.nombre for e in es] == ["Transporte Valle", "Asociación Virgen del Rosario", "Transporte Bella Vista"]
    valle, rosario, bella = es
    assert valle.direccion == "Av. Froilán Tejerina C/ Corrado" and rosario.direccion == "Av. Froilán Tejerina y C/ Pantoja"
    assert [t.numero for t in it.telefonos_de(valle)] == ["+59146648064"]        # «Telf. 66 - 48064»: fijo de Tarija
    assert [t.numero for t in it.telefonos_de(rosario)] == ["+59167373722"]      # «Cel. 67373722»
    assert it.telefonos_de(bella) == [] and bella.direccion == "Calle Pantoja"    # los rowspan no corren las columnas
    assert bella.notas[0] == "Destinos (precio ref.): BELLA VISTA 6 Bs.; SAN PEDRO DE SOLA 6 Bs."
    assert all(e.rubro == "taxis" for e in es) and all(it.es_util(e) for e in es)
    fila = it.armar_fila(bella, ciudad_id="c1", rubro_slug="taxis", punto=None, repetido=None)
    assert "Destinos (precio ref.): BELLA VISTA 6 Bs.; SAN PEDRO DE SOLA 6 Bs." in fila["texto_leido"]


def test_las_otras_tablas_de_la_pagina_no_se_leen():
    es = it.leer_pagina(HTML_MOVERSE, URL_MOVERSE)
    assert len(es) == 5 and "Villa del Norte" not in {e.nombre for e in es}


def test_una_guia_con_licencia_vigente_es_una_fila_y_las_otras_no():
    es = it.leer_pagina(HTML_GUIAS, URL_GUIAS)
    assert [e.nombre for e in es] == ["Angela Tejerina Castro · Guía de turismo", "Mariela Sanchez · Guía de turismo"]
    assert all(e.direccion is None and e.rubro is None and it.es_util(e) for e in es)
    assert [t.numero for t in it.telefonos_de(es[0])] == ["+59176197685"]
    assert [t.numero for t in it.telefonos_de(es[1])] == ["+59160264560", "+59178257882"]
    fila = it.armar_fila(es[0], ciudad_id="c1", rubro_slug=None, punto=None, repetido=None)
    assert "Guía autorizado (licencia vigente según la Secretaría de Turismo)" in fila["texto_leido"]
    assert fila["rubro_slug"] is None and fila["direccion"] is None and fila["ubicacion"] == "no_encontrada"


def test_el_nombre_de_una_asociacion_se_ordena():
    f = it._nombre_de_asociacion
    assert f("VALLE") == "Transporte Valle"
    assert f("AS. VIRGEN DEL ROSARIO") == "Asociación Virgen del Rosario"
    assert f("ASOCIACION DE TRANSPORTE SAN MIGUEL") == "Asociación de Transporte San Miguel"
    assert f("Calamuchita Norte") == "Transporte Calamuchita Norte"


# ═══════════════════════════════════════════════════════ los teléfonos

def entrada(*telefonos, direccion="Calle X"):
    return it.Entrada(nombre="N", direccion=direccion, telefonos=list(telefonos), enlace=None, subcategoria="hoteles",
                      seccion="donde-dormir", url=URL_DORMIR, categorias=("hoteles",))


@pytest.mark.parametrize("crudo,esperado", [
    ("466-48444", [("+59146648444", "fijo")]),
    ("466 75800", [("+59146675800", "fijo")]),
    ("+591 466 54999", [("+59146654999", "fijo")]),
    ("+591 466-38180", [("+59146638180", "fijo")]),
    ("4-66-40832", [("+59146640832", "fijo")]),
    ("4 6640206", [("+59146640206", "fijo")]),
    ("+591 46636929", [("+59146636929", "fijo")]),
    ("+591 71565942", [("+59171565942", "celular")]),
    ("70216566", [("+59170216566", "celular")]),
    ("+591 75111885", [("+59175111885", "celular")]),
    ("+591 72883846", [("+59172883846", "celular")]),
    ("+ 591 72968559", [("+59172968559", "celular")]),
    ("591 73495828", [("+59173495828", "celular")]),
    ("73487166 - 46672229", [("+59173487166", "celular"), ("+59146672229", "fijo")]),
    ("77290194 - 70223343 - 77177200", [("+59177290194", "celular"), ("+59170223343", "celular"),
                                         ("+59177177200", "celular")]),
    ("466-48444 / +591 75111885", [("+59146648444", "fijo"), ("+59175111885", "celular")]),
    ("46645320 / 59178223009", [("+59146645320", "fijo"), ("+59178223009", "celular")]),
    ("77173998 - 77173998", [("+59177173998", "celular")]),                    # repetido en la misma línea
    ("66 - 48064", [("+59146648064", "fijo")]),                                 # fijo sin el 4 de Tarija
    ("66-53691/66-53691/71341083", [("+59146653691", "fijo"), ("+59171341083", "celular")]),
    ("+591 4 66 62872 +591 70223441", [("+59146662872", "fijo"), ("+59170223441", "celular")]),
])
def test_telefonos_de_tarija(crudo, esperado):
    assert [(t.numero, t.tipo) for t in it.telefonos_de(entrada(crudo))] == esperado


@pytest.mark.parametrize("crudo", ["", "+591", "+591 466", "+591 6661333 /", "sin número", "12:00 - 18:00"])
def test_lo_que_no_es_un_telefono_no_inventa_nada(crudo):
    assert it.telefonos_de(entrada(crudo)) == []


def test_las_lineas_de_telefono_se_leen_por_separado():
    # «…591» al final de una línea y «71…» al principio de la otra no se pegan en un número inventado
    assert [t.numero for t in it.telefonos_de(entrada("466-48444 591", "71865038"))] == ["+59146648444", "+59171865038"]


def test_el_primer_celular_va_a_whatsapp_y_el_fijo_a_telefono():
    fila = it.armar_fila(entrada("466-48444 / +591 75111885"), ciudad_id="c1", rubro_slug=None, punto=None,
                         repetido=None)
    assert fila["whatsapp"] == "59175111885" and fila["telefono"] == "+591 4 664 8444"


# ═══════════════════════════════════════════════════════ fuente_id e idempotencia

def test_el_fuente_id_sale_del_host_el_nombre_y_la_direccion():
    e = it.leer_pagina(HTML_DORMIR, URL_DORMIR)[0]
    assert it.fuente_id_de(e) == "turismo:tarijaturismo.com:hotel-los-parrales|urb-el-carmen-de-aranjuez"
    assert it.fuente_id_de(entrada(direccion=None)).endswith("|-")


def test_una_sucursal_tiene_otro_fuente_id():
    a, b = por_nombre(it.leer_pagina(HTML_COMER, URL_COMER), "El Asador Chaqueño")
    assert it.fuente_id_de(a) != it.fuente_id_de(b)


def test_correrlo_dos_veces_no_duplica(repo, ciudad):
    r1 = it.cargar(repo, todas_las_entradas(), ciudad, mostrar=lambda s: None)
    cantidad = len(repo.importados)
    assert r1.nuevas == cantidad and r1.ya_existentes == 0 and cantidad > 0
    r2 = it.cargar(repo, todas_las_entradas(), ciudad, mostrar=lambda s: None)
    assert r2.nuevas == 0 and r2.ya_existentes == cantidad and len(repo.importados) == cantidad


def test_un_negocio_en_dos_secciones_se_carga_una_sola_vez(repo, ciudad):
    it.cargar(repo, todas_las_entradas(), ciudad)
    assert sum(1 for f in repo.importados.values() if f["nombre"] == "Viva Tours") == 1


def test_carga_lo_que_sirve_y_lo_descartado_no(repo, ciudad):
    r = it.cargar(repo, todas_las_entradas(), ciudad)
    nombres = {f["nombre"] for f in repo.importados.values()}
    assert {"Hotel Los Parrales", "Hostal Bolívar", "El Asador Chaqueño", "Salteñería Nanos", "Bodega La Angostura",
            "Museo San Roque", "Viva Tours"} <= nombres
    assert not nombres & {"Hotel Fantasma", "Mercado Avaroa", "Cañón del Pilaya", "Pedro Vencido · Guía de turismo"}
    assert {"Plaza Campero", "Radio Móvil Sol", "Transporte Valle", "Angela Tejerina Castro · Guía de turismo"} <= nombres
    assert r.leidas == 22 and r.descartadas == 3 and r.utiles == 18 and r.nuevas == 18


def test_la_fila_cumple_el_contrato_de_importados(repo, ciudad):
    it.cargar(repo, todas_las_entradas(), ciudad)
    f = next(x for x in repo.importados.values() if x["nombre"] == "Hotel Los Parrales")
    assert f["fuente"] == "turismo" and f["estado"] == "nuevo" and f["ciudad_id"] == ciudad["id"]
    assert f["fuente_id"] == "turismo:tarijaturismo.com:hotel-los-parrales|urb-el-carmen-de-aranjuez"
    assert f["direccion"] == "Urb. El Carmen de Aranjuez" and f["website"] == "http://www.facebook.com/losparraleshotel"
    assert f["whatsapp"] == "59175111885" and f["telefono"] == "+591 4 664 8444"
    assert f["rubro_slug"] == "hospedaje" and f["foto_ref"] is None and f["lector"] is None
    assert f["ubicacion"] == "no_encontrada" and f["lat"] is None            # sin mapa no hay punto
    assert "Origen: https://tarijaturismo.com/donde-dormir/" in f["texto_leido"]
    assert "Telefono: 466-48444 / +591 75111885" in f["texto_leido"]
    assert f["tags"]["turismo"]["subcategoria"] == "hoteles"
    r = next(x for x in repo.importados.values() if x["nombre"] == "Residencial Guadalquivir")
    assert r["email"] == "residencial@gmail.com"


# ═══════════════════════════════════════════════════════ el rubro

@pytest.mark.parametrize("cats,seccion,esperado", [
    (("hoteles",), "donde-dormir", "hospedaje"), (("hostels",), "donde-dormir", "hospedaje"),
    (("residenciales",), "donde-dormir", "hospedaje"), (("churrasquerias",), "donde-comer", "restaurantes"),
    (("saltenerias",), "donde-comer", "comida-rapida"), (("heladerias-dulces",), "donde-comer", "cafeteria"),
    (("bodegas-y-vinotecas",), "que-hacer", "bebidas"), (("diversion-nocturna",), "que-hacer", "nocturna"),
    (("complejos-deportivos-y-gimnasios",), "que-hacer", "gimnasios"),
    (("radio-moviles",), "como-moverse", "taxis"), (("transporte-alrededores",), "como-moverse", "taxis"),
    (("guias",), "guias-de-turismo-autorizados", None),
    (("cocina-italiana-pastas", "pizzeria"), "donde-comer", "restaurantes"),
    (("operadoras-de-turismo",), "operadoras-de-turismo", None), (("museos-y-bibliotecas",), "que-hacer", None),
    (("algo-nuevo",), "donde-dormir", "hospedaje"),                      # sin subcategoría conocida: la de la sección
    (("algo-nuevo",), "donde-comer", None),
])
def test_rubro_sugerido(cats, seccion, esperado):
    e = it.Entrada(nombre="N", direccion="x", telefonos=[], enlace=None, subcategoria=cats[0], seccion=seccion,
                   url=f"{BASE}/{seccion}/", categorias=cats)
    assert it.rubro_sugerido(e) == esperado


def test_los_rubros_del_mapeo_existen_en_las_migraciones():
    """Cada slug que sugiere el importador tiene que estar sembrado en alguna migración."""
    from pathlib import Path
    sql = "\n".join(p.read_text(encoding="utf-8", errors="ignore")
                    for p in (Path(__file__).resolve().parents[2] / "supabase" / "migrations").glob("*.sql"))
    for slug in set(it.RUBRO_POR_SUBCATEGORIA.values()) | set(it.RUBRO_POR_SECCION.values()):
        assert f"('{slug}'," in sql, slug


def test_un_rubro_que_no_existe_en_la_base_se_deja_vacio(repo):
    ciudad = repo.get_ciudad("tarija")                    # el repo falso no tiene `hospedaje` ni `restaurantes`
    it.cargar(repo, todas_las_entradas(), ciudad)
    assert {f["rubro_slug"] for f in repo.importados.values() if f["nombre"] == "Hotel Los Parrales"} == {None}
    repo.rubros["hospedaje"] = "rub-hosp"
    repo.importados.clear()
    repo._importados_por_clave.clear()
    it.cargar(repo, todas_las_entradas(), ciudad)
    assert {f["rubro_slug"] for f in repo.importados.values() if f["nombre"] == "Hotel Los Parrales"} == {"hospedaje"}


# ═══════════════════════════════════════════════════════ repetidos

def test_un_telefono_que_ya_tiene_un_comercio_marca_el_repetido(repo, ciudad):
    repo.comercios["com-1"] = {"id": "com-1", "nombre": "Otro Nombre Cualquiera", "activo": True,
                               "ciudad_id": ciudad["id"], "whatsapp": "59172995676", "telefono": None}
    it.cargar(repo, todas_las_entradas(), ciudad)
    f = next(x for x in repo.importados.values() if x["nombre"] == "Hostal Bolívar")
    assert f["duplicado_de"] == "com-1"


def test_un_nombre_parecido_en_la_misma_ciudad_marca_el_repetido(repo, ciudad):
    repo.comercios["com-2"] = {"id": "com-2", "nombre": "HOTEL LOS PARRALES Tarija", "activo": True,
                               "ciudad_id": ciudad["id"]}
    repo.comercios["com-3"] = {"id": "com-3", "nombre": "Hostal Bolívar", "activo": True, "ciudad_id": "otra-ciudad"}
    repo.comercios["com-4"] = {"id": "com-4", "nombre": "Viva Tours", "activo": False, "ciudad_id": ciudad["id"]}
    it.cargar(repo, todas_las_entradas(), ciudad)
    por = {x["nombre"]: x["duplicado_de"] for x in repo.importados.values()}
    assert por["Hotel Los Parrales"] == "com-2"
    assert por["Hostal Bolívar"] is None                   # el parecido es de otra ciudad
    assert por["Viva Tours"] is None                       # y el inactivo no cuenta


@pytest.mark.parametrize("a,b,esperado", [
    ("Hotel Los Parrales", "HOTEL LOS PARRALES", True), ("Hotel Los Parrales", "Los Parrales Tarija", True),
    ("Café Ñandú", "Cafe Nandu", True), ("Hotel Los Ceibos", "Resort Hotel Los Ceibos", True),
    ("Hotel Central", "Mercado Central", False), ("Hotel Los Parrales", "Hotel Las Panosas", False),
    ("Pizzería Sol", "Sol y Luna", False), ("", "Hotel X", False),
])
def test_mismo_nombre(a, b, esperado):
    assert it.mismo_nombre(a, b) is esperado


# ═══════════════════════════════════════════════════════ dry-run y línea de comandos

def descargador(pedidas):
    def d(url):
        pedidas.append(url)
        return PAGINAS[url]
    return d


def test_el_dry_run_no_escribe_ni_pregunta_al_mapa(repo, monkeypatch, capsys):
    llamadas = []

    def espia(params):
        llamadas.append(params)
        return []

    monkeypatch.setattr(tarjetas, "_pedir_nominatim", espia)
    pedidas = []
    code = it.main(["--ciudad", "tarija", "--dry-run"], repo=repo, descargar=descargador(pedidas),
                   pedir=espia, dormir=lambda s: None)
    salida = capsys.readouterr().out
    assert code == 0
    assert repo.importados == {} and llamadas == []
    assert "Hotel Los Parrales" in salida and "Simulación" in salida and "Hotel Fantasma" not in salida
    assert "Dónde dormir" in salida and "Qué hacer" in salida


def test_el_cli_baja_las_cinco_paginas_una_por_segundo_y_nada_mas(repo, capsys):
    pedidas, esperas = [], []
    code = it.main(["--ciudad", "tarija", "--dry-run"], repo=repo, descargar=descargador(pedidas),
                   dormir=esperas.append)
    assert code == 0
    assert pedidas == [URL_DORMIR, URL_COMER, URL_HACER, URL_OPERADORAS, URL_AGENCIAS, URL_MOVERSE, URL_GUIAS]
    assert esperas == [1.0] * 6                      # una por segundo, ni imágenes ni page/2


def test_el_cli_carga_y_cuenta_con_punto_sin_punto_y_repetidas(repo, capsys):
    repo.comercios["com-1"] = {"id": "com-1", "nombre": "X", "activo": True, "ciudad_id": "ciudad-tarija",
                               "whatsapp": "59172995676"}
    consultas = []

    def mapa(params):
        consultas.append(params["q"])
        if "Parrales" in params["q"] or "Aranjuez" in params["q"]:
            return [{"lat": "-22.7400", "lon": "-64.3400", "display_name": "x"}]
        return []

    code = it.main(["--ciudad", "tarija"], repo=repo, descargar=descargador([]), pedir=mapa, dormir=lambda s: None)
    salida = capsys.readouterr().out
    assert code == 0
    assert len(consultas) == 14 and all(q.endswith("Tarija") for q in consultas)
    con = [f for f in repo.importados.values() if f["lat"] is not None]
    assert [f["nombre"] for f in con] == ["Hotel Los Parrales"] and con[0]["ubicacion"] == "aproximada"
    assert "Nuevas:                 18" in salida and "Con punto en el mapa:   1" in salida
    assert "Sin punto:              17" in salida and "Marcadas como repetidas: 1" in salida
    # la segunda vez no hay nada nuevo ni se vuelve a preguntar al mapa
    consultas.clear()
    it.main(["--ciudad", "tarija"], repo=repo, descargar=descargador([]), pedir=mapa, dormir=lambda s: None)
    assert consultas == [] and len(repo.importados) == 18
    assert "Ya existentes:          18" in capsys.readouterr().out


def test_el_limite_corta_la_carga(repo, ciudad):
    r = it.cargar(repo, todas_las_entradas(), ciudad, limite=3)
    assert r.nuevas == 3 and len(repo.importados) == 3 and r.utiles == 18


def test_si_el_mapa_no_contesta_se_sigue_sin_punto_y_se_deja_de_insistir(repo, ciudad):
    llamadas = []

    def caido(params):
        llamadas.append(1)
        raise RuntimeError("sin red")

    r = it.cargar(repo, todas_las_entradas(), ciudad, pedir=caido)
    assert r.nuevas == 18 and r.sin_punto == 18 and r.con_punto == 0
    assert len(llamadas) == it.FALLAS_NOMINATIM_SEGUIDAS


def test_el_cli_con_ciudad_desconocida_o_sin_sitio_falla_con_codigo_2(repo, capsys):
    assert it.main(["--ciudad", "narnia"], repo=repo, descargar=descargador([])) == 2
    assert "No hay un lector" in capsys.readouterr().err
    assert it.main(["--ciudad", "tarija", "--limite", "0"], repo=repo, descargar=descargador([])) == 2


def test_si_una_pagina_no_se_puede_bajar_no_se_carga_nada(repo, capsys):
    def roto(url):
        raise RuntimeError("No se pudo leer la página")

    assert it.main(["--ciudad", "tarija"], repo=repo, descargar=roto, dormir=lambda s: None) == 1
    assert repo.importados == {}


# ═══════════════════════════════════════════════════════ el listado y «Promover»

def test_el_listado_filtra_por_fuente_turismo(client, repo, ciudad, datos):
    repo.upsert_importado({"fuente": "osm", "fuente_id": "node/1", "nombre": "De OSM", "lat": -22.7, "lng": -64.3})
    repo.importados["t1"] = {"id": "t1", "fuente": "tarjeta", "fuente_id": "tarjeta:1", "estado": "nuevo",
                             "nombre": "De tarjeta", "foto_ref": "privado:x"}
    it.cargar(repo, todas_las_entradas(), ciudad)
    todos = client.get("/admin/importados?limite=500", headers=datos).json()
    assert todos["total"] == 20
    t = client.get("/admin/importados?fuente=turismo&limite=500", headers=datos).json()["items"]
    assert len(t) == 18 and {i["fuente"] for i in t} == {"turismo"}
    assert all(i["tiene_foto"] is False and "foto_ref" not in i for i in t)
    p = next(i for i in t if i["nombre"] == "Hotel Los Parrales")
    assert p["texto_leido"].startswith("Sección: Dónde dormir") and p["lector"] is None
    assert p["ubicacion"] == "no_encontrada" and p["email"] is None and p["rubro_slug"] == "hospedaje"
    assert client.get("/admin/importados?fuente=otra", headers=datos).status_code == 422


def test_el_listado_muestra_el_nombre_del_repetido(client, repo, ciudad, datos):
    repo.comercios["com-2"] = {"id": "com-2", "nombre": "Hotel Los Parrales Tarija", "activo": True,
                               "ciudad_id": ciudad["id"]}
    it.cargar(repo, todas_las_entradas(), ciudad)
    p = next(i for i in client.get("/admin/importados?fuente=turismo&limite=500", headers=datos).json()["items"]
             if i["nombre"] == "Hotel Los Parrales")
    assert p["duplicado_de"] == "com-2" and p["duplicado_nombre"] == "Hotel Los Parrales Tarija"


def _id_de(repo, nombre):
    return next(i for i, f in repo.importados.items() if f["nombre"] == nombre)


def test_promover_de_turismo_copia_los_datos_y_no_sale_verificado_ni_confiable(client, repo, ciudad, datos):
    it.cargar(repo, todas_las_entradas(), ciudad)
    iid = _id_de(repo, "Hotel Los Parrales")
    # sin punto no se puede promover: la persona lo marca en el mapa (o «Buscar la dirección»)
    assert client.post(f"/admin/importados/{iid}/promover", json={}, headers=datos).status_code == 400
    r = client.patch(f"/admin/importados/{iid}", json={"lat": -21.535, "lng": -64.729}, headers=datos)
    assert r.status_code == 200 and r.json()["ubicacion"] == "confirmada"
    r = client.post(f"/admin/importados/{iid}/promover", json={}, headers=datos)
    assert r.status_code == 200, r.text
    com = repo.comercios[r.json()["comercio"]["id"]]
    assert com["nombre"] == "Hotel Los Parrales" and com["direccion"] == "Urb. El Carmen de Aranjuez"
    assert com["whatsapp"] == "59175111885" and com["telefono"] == "+591 4 664 8444"
    assert com["sitio_web"] == "http://www.facebook.com/losparraleshotel"
    assert com["lat"] == -21.535 and com["lng"] == -64.729 and com["ciudad_id"] == ciudad["id"]
    assert com["verificado"] is False and com["confiable"] is False and com["activo"] is True
    assert com["cargado_por"] == "import:turismo"
    assert "foto_ref" not in com and "texto_leido" not in com
    assert repo.importados[iid]["estado"] == "promovido" and repo.importados[iid]["comercio_id"] == com["id"]
    assert client.post(f"/admin/importados/{iid}/promover", json={}, headers=datos).status_code == 409


def test_promover_de_turismo_con_solo_fijo_no_lo_usa_como_whatsapp(client, repo, ciudad, datos):
    repo.importados["x"] = {"id": "x", "fuente": "turismo", "fuente_id": "turismo:t:x|-", "estado": "nuevo",
                            "ciudad_id": ciudad["id"], "nombre": "Solo Fijo", "telefono": "+591 4 664 8444",
                            "whatsapp": None, "lat": -21.5, "lng": -64.7, "direccion": "Calle 1", "email": "a@b.com"}
    com = repo.comercios[client.post("/admin/importados/x/promover", json={}, headers=datos).json()["comercio"]["id"]]
    assert com["whatsapp"] is None and com["telefono"] == "+591 4 664 8444" and com["email"] == "a@b.com"
    assert com["confiable"] is False and com["cargado_por"] == "import:turismo"


def test_el_patch_y_ubicar_sirven_para_turismo(client, repo, ciudad, datos, monkeypatch):
    it.cargar(repo, todas_las_entradas(), ciudad)
    iid = _id_de(repo, "Hostal Bolívar")
    r = client.patch(f"/admin/importados/{iid}", json={"telefono": "+591 4 664 8444", "rubro_slug": "hospedaje"},
                     headers=datos)
    assert r.status_code == 200 and r.json()["telefono"] == "+591 4 664 8444" and r.json()["rubro_slug"] == "hospedaje"
    monkeypatch.setattr(tarjetas, "_pedir_nominatim",
                        lambda p: [{"lat": "-22.7400", "lon": "-64.3400", "display_name": "x"}])
    u = client.post(f"/admin/importados/{iid}/ubicar", json={"direccion": "Calle Bolívar 256"}, headers=datos)
    assert u.status_code == 200 and u.json()["encontrado"] is True
    assert repo.importados[iid]["ubicacion"] == "aproximada" and repo.importados[iid]["lat"] == -22.74
