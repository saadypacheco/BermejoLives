"""Importar los lugares para visitar de la página de turismo (docs/lugares-turismo.md): un test por criterio.

Los textos son INVENTADOS: imitan los rótulos y la estructura (bloques `box-body` con `<h3>` + `<p>`, el JSON de la
API de WordPress) pero no copian nada de la página real. Nada sale a la red: la descarga y Nominatim se reemplazan.
"""
import json

import pytest

from app.services import importar_turismo_lugares as lug
from app.services import tarjetas

BASE = "https://tarijaturismo.com"
PIE = (-21.534641, -64.734265)              # el enlace del pie del sitio: nunca puede ser el punto de un lugar
CENTRO = {"lat": -21.5355, "lng": -64.7296}
RESENA = "TEXTO-INVENTADO-DE-RESENA con autor y todo"
INFO = "TEXTO-INVENTADO-DE-INFORMACION"


@pytest.fixture(autouse=True)
def _sin_red_ni_esperas(monkeypatch):
    tarjetas.reiniciar_cache()
    monkeypatch.setattr(tarjetas, "_dormir", lambda s: None)

    def sin_red(params):
        raise AssertionError("Nominatim: un test salió a la red")

    monkeypatch.setattr(tarjetas, "_pedir_nominatim", sin_red)
    yield
    tarjetas.reiniciar_cache()


@pytest.fixture
def ciudad(repo):
    repo.rubros["para-visitar"] = "rub-pv"
    return {**repo.get_ciudad("tarija"), **CENTRO}


# ───────────────────────────────────────────────────────────── HTML y JSON sintéticos

def bloque(rotulo, valor):
    return (f'<div class="elementor-element"><div class="ekit-wid-con"><div class="elementskit-infobox">'
            f'<div class="elementskit-box-header"><i class="icon icon-google-map"></i></div>'
            f'<div class="box-body"><h3 class="elementskit-info-box-title">\n   {rotulo}   </h3>'
            f'<p>{valor}</p></div></div></div></div>')


def contenido(direccion=None, telefono=None, horario=None, extras=()):
    partes = []
    if direccion:
        partes.append(bloque("Dirección", direccion))
    if telefono:
        partes.append(bloque("Teléfono", telefono))
    if horario:
        partes.append(bloque("Horarios", horario))
    partes += [bloque(r, v) for r, v in extras]
    return '<div data-elementor-type="wp-post">' + "".join(partes) + '<img src="https://x/foto.webp"></div>'


def post(pid, titulo, cats, *, direccion=None, telefono=None, horario=None, link=None, extras=None):
    extras = [("Reseña", RESENA), ("Información", INFO), ("Entrada", "5 Bs"), ("Presentación", RESENA)] \
        if extras is None else extras
    return {"id": pid, "slug": f"lugar-{pid}", "link": link or f"{BASE}/lugar-{pid}/", "title": {"rendered": titulo},
            "categories": cats, "content": {"rendered": contenido(direccion, telefono, horario, extras)}}


IDS = {"plazas-parques-y-miradores": 80, "museos-y-bibliotecas": 81, "dentro-de-la-ciudad": 79,
       "centros-culturales": 88, "fuera-de-la-ciudad": 83, "fuera-del-municipio": 87, "que-hacer": 78}

POSTS = {
    "plazas-parques-y-miradores": [
        post(1001, "Plaza Mayor", [80, 78], direccion="Calle Ficticia 1 entre A y B", horario="Abierto 24 horas"),
        post(1002, "Parque Los Nogales", [80, 78], direccion="Av. Imaginaria"),
        post(1003, "Mirador El Lomo", [80, 78], direccion="Barrio Alto"),
    ],
    "museos-y-bibliotecas": [
        post(1101, "Museo del Telar", [81, 78], direccion="Calle Telar 10", telefono="+591 70011122",
             horario="Lunes a viernes 9:00 a 12:00"),
        post(1102, "Archivo Antiguo", [81, 78], direccion="Calle Papel 3", telefono="46640000 / 46650000"),
    ],
    "dentro-de-la-ciudad": [
        post(1201, "Iglesia de la Aldea", [79, 78], direccion="Esquina Fe"),
        post(1202, "Casona Vieja", [79, 78], direccion="Calle Vieja 5"),
    ],
    "centros-culturales": [
        post(1301, "Casa del Arte", [88, 78], direccion="Calle Arte 7", telefono="+591 71122334 / +591 72233445"),
    ],
    "fuera-de-la-ciudad": [
        post(1401, "Represa Lejana", [83, 78], direccion="San Nadie", horario="Todos los días 8:00 a 17:00"),
        post(1402, "Comunidad Perdida", [83, 78]),
    ],
    "fuera-del-municipio": [
        post(1501, "Valle Remoto", [87, 78], direccion="A 76 Km de Tarija, Zona Alta"),
    ],
}


def api(posts=None, categorias=None):
    """Un `descargar(url)` falso que contesta como la API de WordPress y apunta los pedidos."""
    posts = POSTS if posts is None else posts
    cats = [{"id": i, "slug": s} for s, i in IDS.items()] if categorias is None else categorias
    pedidos: list[str] = []

    def descargar(url):
        pedidos.append(url)
        if "/categories?" in url:
            return json.dumps(cats)
        cid = int(url.split("categories=")[1].split("&")[0])
        slug = next(s for s, i in IDS.items() if i == cid)
        return json.dumps(posts.get(slug, []))

    descargar.pedidos = pedidos
    return descargar


def lugares_de_prueba():
    return lug.leer_sitio(lug.SITIOS["tarija"], descargar_=api(), dormir=lambda s: None)


# ───────────────────────────────────────────────────────────── el lector de bloques

def test_toma_direccion_telefono_y_horario_y_descarta_el_resto():
    d = lug.leer_bloques(contenido("Calle Ficticia 1", "+591 70011122", "Abierto 24 horas",
                                   extras=[("Reseña", RESENA), ("Presentación", RESENA), ("Información", INFO),
                                           ("Entrada", "20 Bs")]))
    assert d == {"direccion": "Calle Ficticia 1", "telefonos": ["+591 70011122"], "horario": "Abierto 24 horas"}
    assert RESENA not in json.dumps(d) and INFO not in json.dumps(d) and "20 Bs" not in json.dumps(d)


def test_acepta_la_errata_horaios_y_varios_telefonos():
    d = lug.leer_bloques(bloque("Horaios", "De 8 a 12") + bloque("Teléfono", "1") + bloque("Telefono", "2"))
    assert d["horario"] == "De 8 a 12" and d["telefonos"] == ["1", "2"]


def test_bloques_con_div_anidado_y_br_no_pegan_palabras():
    html = ('<div class="box-body"><h3 class="elementskit-info-box-title">Horarios</h3>'
            '<div><p>Lunes a viernes</p><p>8:00<br>a 12:00</p></div></div>')
    assert lug.leer_bloques(html)["horario"] == "Lunes a viernes 8:00 a 12:00"


def test_un_html_sin_bloques_da_todo_vacio():
    assert lug.leer_bloques("") == {"direccion": None, "telefonos": [], "horario": None}
    assert lug.leer_bloques("<p>hola</p>") == {"direccion": None, "telefonos": [], "horario": None}


@pytest.mark.parametrize("cat,nombre,esperada", [
    ("plazas-parques-y-miradores", "Plaza Uno", "Plaza"),
    ("plazas-parques-y-miradores", "Plazuela Dos", "Plaza"),
    ("plazas-parques-y-miradores", "Parque Tres", "Parque"),
    ("plazas-parques-y-miradores", "Mirador Cuatro", "Mirador"),
    ("museos-y-bibliotecas", "Museo Cinco", "Museo"),
    ("museos-y-bibliotecas", "Biblioteca Seis", "Biblioteca o archivo"),
    ("museos-y-bibliotecas", "Archivo Siete", "Biblioteca o archivo"),
    ("dentro-de-la-ciudad", "Iglesia Ocho", "Iglesia"),
    ("dentro-de-la-ciudad", "Capilla Nueve", "Iglesia"),
    ("dentro-de-la-ciudad", "Catedral Diez", "Iglesia"),
    ("dentro-de-la-ciudad", "Casona Once", "Patrimonio"),
    ("centros-culturales", "Casa Doce", "Centro cultural"),
    ("fuera-de-la-ciudad", "Represa Trece", "Excursión"),
    ("fuera-del-municipio", "Valle Catorce", "Excursión"),
    ("areas-protegidas", "Reserva Quince", "Área protegida"),
])
def test_subcategoria_segun_categoria_y_primera_palabra(cat, nombre, esperada):
    assert lug.subcategoria_de(cat, nombre) == esperada
    assert esperada in lug.SUBCATEGORIAS


# ───────────────────────────────────────────────────────────── plan A: la API (criterio 1)

def test_la_api_da_los_lugares_con_sus_areas_en_siete_pedidos_a_un_segundo():
    desc = api()
    esperas: list[float] = []
    ls = lug.leer_sitio(lug.SITIOS["tarija"], descargar_=desc, dormir=esperas.append)
    assert len(ls) == sum(len(v) for v in POSTS.values()) + 3
    assert len(desc.pedidos) == 7                                   # 1 de categorías + 6 de posts
    assert esperas == [lug.INTERVALO_PEDIDOS] * 6                   # un segundo entre pedidos
    assert all(p.startswith(BASE + "/wp-json/wp/v2/") and "per_page=100" in p for p in desc.pedidos)
    assert all(l.nombre and l.subcategoria in lug.SUBCATEGORIAS for l in ls)
    assert sum(1 for l in ls if l.categoria == "areas-protegidas") == 3


def test_el_post_toma_nombre_direccion_telefono_horario_y_enlace():
    ls = {l.wp_id: l for l in lugares_de_prueba() if l.wp_id}
    m = ls[1101]
    assert (m.nombre, m.subcategoria, m.direccion, m.horario) == (
        "Museo del Telar", "Museo", "Calle Telar 10", "Lunes a viernes 9:00 a 12:00")
    assert m.telefonos == ["+591 70011122"] and m.url == f"{BASE}/lugar-1101/" and m.radio_km == 15
    assert m.categorias == ["museos-y-bibliotecas", "que-hacer"]
    assert ls[1401].radio_km == 120 and ls[1501].radio_km == 120 and ls[1301].radio_km == 15
    assert ls[1402].direccion is None and ls[1402].horario is None


def test_las_areas_tienen_nombre_fijo_url_de_su_pagina_y_caja_grande():
    areas = [l for l in lugares_de_prueba() if l.area]
    assert [a.area for a in areas] == ["sama", "tariquia", "aguarague"]
    assert all(a.url == BASE + "/areas-protegidas/" and a.radio_km == 120 and a.wp_id is None for a in areas)
    assert all(a.subcategoria == "Área protegida" and a.direccion is None for a in areas)


def test_un_enlace_de_otro_sitio_no_se_toma():
    p = {**POSTS, "museos-y-bibliotecas": [post(1101, "Museo X", [81], link="https://malo.example/x/"),
                                           post(1102, "Museo Y", [81], link="http://tarijaturismo.com/y/")]}
    ls = {l.wp_id: l for l in lug.leer_sitio(lug.SITIOS["tarija"], descargar_=api(p), dormir=lambda s: None)
          if l.wp_id}
    assert ls[1101].url is None and ls[1102].url is None            # otro host / sin https


def test_un_post_sin_id_o_sin_titulo_se_saltea_y_un_post_en_dos_categorias_cuenta_una_vez():
    rotos = [{"id": "x", "title": {"rendered": "Sin id"}, "content": {"rendered": ""}},
             {"id": 9, "title": {"rendered": "  "}, "content": {"rendered": ""}},
             {"id": 7, "title": {"rendered": "Doble"}, "categories": [80, 81], "content": {"rendered": ""}}]
    p = {"plazas-parques-y-miradores": rotos, "museos-y-bibliotecas": [rotos[2]]}
    ls = [l for l in lug.leer_sitio(lug.SITIOS["tarija"], descargar_=api(p), dormir=lambda s: None) if l.wp_id]
    assert [l.wp_id for l in ls] == [7] and ls[0].categoria == "plazas-parques-y-miradores"


# ───────────────────────────────────────────────────────────── plan B: el HTML

def tarjeta(cats, nombre, href):
    clases = " ".join(f"category-{c}" for c in cats)
    return (f'<article class="elementor-post {clases}"><h3 class="elementor-post__title">'
            f'<a href="{href}">{nombre}</a></h3><div class="elementor-post__excerpt"><p>Dirección corta…</p></div>'
            f'</article>')


def ficha_html(pid, direccion, telefono=None, horario=None):
    oficina = bloque("Dirección", "OFICINA-DEL-PIE")
    return (f'<html><div data-elementor-type="header">{oficina}</div>'
            f'<div data-elementor-type="wp-post" data-elementor-id="{pid}" class="elementor">'
            + bloque("Dirección", direccion) + (bloque("Teléfono", telefono) if telefono else "")
            + (bloque("Horarios", horario) if horario else "") + bloque("Reseña", RESENA)
            + f'</div><div data-elementor-type="footer">{oficina}</div></html>')


def test_si_la_api_no_sirve_se_leen_el_listado_y_las_fichas():
    fichas = {f"{BASE}/plaza-uno/": ficha_html(5001, "Calle HTML 1", horario="Abierto 24 horas"),
              f"{BASE}/museo-dos/": ficha_html(5002, "Calle HTML 2", telefono="+591 70011122"),
              f"{BASE}/negocio/": ficha_html(5003, "No es un lugar")}
    listado = ("<html>" + tarjeta(["que-hacer", "plazas-parques-y-miradores"], "Plaza Uno", f"{BASE}/plaza-uno/")
               + tarjeta(["que-hacer", "museos-y-bibliotecas"], "Museo Dos", f"{BASE}/museo-dos/")
               + tarjeta(["que-hacer", "bodegas-y-vinotecas"], "Bodega", f"{BASE}/negocio/") + "</html>")
    pedidos: list[str] = []

    def descargar(url):
        pedidos.append(url)
        if "/wp-json/" in url:
            raise RuntimeError("API cerrada")
        return listado if url == BASE + "/que-hacer/" else fichas[url]

    ls = lug.leer_sitio(lug.SITIOS["tarija"], descargar_=descargar, dormir=lambda s: None)
    por_id = {l.wp_id: l for l in ls if l.wp_id}
    assert set(por_id) == {5001, 5002}                                # la bodega no es un lugar
    assert por_id[5001].direccion == "Calle HTML 1" and por_id[5001].horario == "Abierto 24 horas"
    assert por_id[5002].telefonos == ["+591 70011122"] and por_id[5002].subcategoria == "Museo"
    assert por_id[5001].url == f"{BASE}/plaza-uno/" and por_id[5001].subcategoria == "Plaza"
    assert "OFICINA-DEL-PIE" not in json.dumps([l.direccion for l in ls if l.direccion])   # no se lee el encabezado ni el pie
    assert len([l for l in ls if l.area]) == 3
    assert not any(NEGRO in json.dumps(vars(l), default=str) for l in ls for NEGRO in (RESENA,))


def test_si_la_api_contesta_algo_raro_tambien_va_el_plan_b():
    def descargar(url):
        if "/wp-json/" in url:
            return "<html>no es json</html>"
        return "<html></html>"

    ls = lug.leer_sitio(lug.SITIOS["tarija"], descargar_=descargar, dormir=lambda s: None)
    assert [l.area for l in ls] == ["sama", "tariquia", "aguarague"]


# ───────────────────────────────────────────────────────────── la fila (criterio 3)

def test_la_fila_no_trae_resena_foto_ni_contenido_y_el_telefono_va_a_telefono(repo, ciudad):
    lug.cargar(repo, lugares_de_prueba(), ciudad, BASE, pedir=lambda p: [], mostrar=lambda s: None)
    f = next(x for x in repo.importados.values() if x["nombre"] == "Casa del Arte")
    assert f["fuente"] == "turismo" and f["fuente_id"] == "turismo:tarijaturismo.com:post:1301"
    assert f["rubro_slug"] == "para-visitar" and f["categoria"] == "centros-culturales"
    assert f["subcategoria"] == "Centro cultural"
    assert f["direccion"] == "Calle Arte 7" and f["fuente_url"] == f"{BASE}/lugar-1301/"
    assert f["telefono"] == "+591 7112 2334 / +591 7223 3445" and f["whatsapp"] is None    # nunca a WhatsApp
    assert f["website"] is None and f["email"] is None and f["foto_ref"] is None
    assert f["tags"] == {"wp_id": 1301, "categorias": ["centros-culturales", "que-hacer"]}
    assert f["estado"] == "nuevo"
    for fila in repo.importados.values():                  # ninguna fila lleva reseña ni información en ningún campo
        blob = json.dumps(fila, default=str, ensure_ascii=False)
        assert RESENA not in blob and INFO not in blob and "5 Bs" not in blob
    area = next(x for x in repo.importados.values() if x["fuente_id"].endswith(":area:tariquia"))
    assert area["subcategoria"] == "Área protegida" and area["fuente_url"] == BASE + "/areas-protegidas/"
    assert area["tags"] == {"wp_id": None, "categorias": ["areas-protegidas"]}


def test_los_numeros_de_un_museo_se_normalizan_y_los_repetidos_se_sacan(repo, ciudad):
    lug.cargar(repo, lugares_de_prueba(), ciudad, BASE, pedir=lambda p: [], mostrar=lambda s: None)
    f = next(x for x in repo.importados.values() if x["nombre"] == "Archivo Antiguo")
    assert f["telefono"] == "+591 4 664 0000 / +591 4 665 0000"


# ───────────────────────────────────────────────────────────── ubicación (criterios 3 y 4)

def nominatim(lat, lng, consultas=None):
    def pedir(params):
        if consultas is not None:
            consultas.append(params)
        return [{"lat": str(lat), "lon": str(lng), "display_name": "Algún lugar"}]
    return pedir


def uno(**kw):
    base = dict(nombre="Plaza Mayor", categoria="plazas-parques-y-miradores", subcategoria="Plaza",
                direccion="Calle Ficticia 1", telefonos=[], horario=None, url=f"{BASE}/x/", radio_km=15, wp_id=1)
    return lug.Lugar(**{**base, **kw})


def test_busca_primero_por_nombre_y_despues_por_direccion(ciudad):
    consultas: list[dict] = []

    def pedir(params):
        consultas.append(params)
        return [] if "Plaza Mayor" in params["q"] else [{"lat": "-21.536", "lon": "-64.730", "display_name": "x"}]

    p = lug.ubicar(uno(), ciudad, pedir=pedir)
    assert p and [c["q"] for c in consultas] == ["Plaza Mayor, Tarija", "Calle Ficticia 1, Tarija"]
    consultas.clear()
    assert lug.ubicar(uno(nombre="Otro Sitio"), ciudad, pedir=nominatim(-21.536, -64.73, consultas))
    assert [c["q"] for c in consultas] == ["Otro Sitio, Tarija"]          # con el nombre alcanzó: una sola consulta


def test_nunca_sale_el_punto_del_pie_del_sitio(repo, ciudad):
    """Criterio 3: aunque el mapa devolviera ESE punto, la fila queda sin punto (no_encontrada)."""
    lug.cargar(repo, lugares_de_prueba(), ciudad, BASE, pedir=nominatim(*PIE), mostrar=lambda s: None)
    assert repo.importados
    for f in repo.importados.values():
        assert not (f["lat"] is not None and abs(f["lat"] - PIE[0]) < 1e-4 and abs(f["lng"] - PIE[1]) < 1e-4)
        assert f["ubicacion"] == "no_encontrada" and f["lat"] is None
    # y armar_fila lo descarta aunque le llegue de otro lado
    fila = lug.armar_fila(uno(), base=BASE, ciudad_id="c", punto={"lat": PIE[0], "lng": PIE[1]}, repetido=None)
    assert fila["lat"] is None and fila["ubicacion"] == "no_encontrada"


def test_cada_fila_queda_aproximada_dentro_de_su_caja_o_no_encontrada(repo, ciudad):
    """Criterio 4: la caja es de 15 km (ciudad) o 120 km (lejos); un resultado de afuera de la caja no se acepta."""
    lejos = nominatim(-21.535 + 0.55, -64.7296)                 # a ~61 km del centro: sólo entra en la caja de 120 km
    lug.cargar(repo, lugares_de_prueba(), ciudad, BASE, pedir=lejos, mostrar=lambda s: None)
    por_nombre = {f["nombre"]: f for f in repo.importados.values()}
    assert por_nombre["Plaza Mayor"]["ubicacion"] == "no_encontrada" and por_nombre["Plaza Mayor"]["lat"] is None
    assert por_nombre["Represa Lejana"]["ubicacion"] == "aproximada" and por_nombre["Represa Lejana"]["lat"]
    assert por_nombre["Reserva Biológica de la Cordillera de Sama"]["ubicacion"] == "aproximada"
    assert {f["ubicacion"] for f in repo.importados.values()} <= {"aproximada", "no_encontrada"}
    assert all((f["lat"] is None) == (f["ubicacion"] == "no_encontrada") for f in repo.importados.values())


def test_el_radio_entra_en_la_cache_y_en_la_caja(ciudad):
    consultas: list[dict] = []
    p15 = tarjetas.buscar_direccion("Valle Remoto", ciudad, pedir=nominatim(-21.0, -64.7296, consultas), radio_km=15)
    p120 = tarjetas.buscar_direccion("Valle Remoto", ciudad, pedir=nominatim(-21.0, -64.7296, consultas), radio_km=120)
    assert p15 is None and p120 is not None                # la misma consulta con otra caja es otra respuesta
    assert len(consultas) == 2 and consultas[0]["viewbox"] != consultas[1]["viewbox"]
    tarjetas.buscar_direccion("Valle Remoto", ciudad, pedir=nominatim(-21.0, -64.7296, consultas), radio_km=120)
    assert len(consultas) == 2                              # ahora sí sale de la caché
    o, n, e, s = (float(v) for v in consultas[1]["viewbox"].split(","))
    assert 119 <= (n - s) * 111 / 2 * 1.0 <= 121


def test_el_mapa_sin_centro_no_se_acepta_para_cargar(repo):
    repo.rubros["para-visitar"] = "rub-pv"
    repo.get_ciudad = lambda slug: {"id": "c-x", "slug": slug, "nombre": "Tarija", "lat": None, "lng": None}
    assert lug.main(["--ciudad", "tarija"], repo, descargar_=api(), dormir=lambda s: None) == 2
    assert not repo.importados


def test_si_el_mapa_no_contesta_se_deja_de_insistir_y_las_filas_igual_se_cargan(repo, ciudad):
    llamadas = []

    def caido(params):
        llamadas.append(1)
        raise RuntimeError("caído")

    r = lug.cargar(repo, lugares_de_prueba(), ciudad, BASE, pedir=caido, mostrar=lambda s: None)
    assert r.nuevos == len(repo.importados) and r.no_encontradas == r.nuevos
    assert len(llamadas) == lug.FALLAS_NOMINATIM_SEGUIDAS          # después de 5 fallas seguidas no se pregunta más


# ───────────────────────────────────────────────────────────── idempotencia (criterio 2) y dry-run (criterio 1)

def test_correrlo_dos_veces_no_crea_filas_ni_pisa_lo_corregido(repo, ciudad):
    r1 = lug.cargar(repo, lugares_de_prueba(), ciudad, BASE, pedir=nominatim(-21.55, -64.75), mostrar=lambda s: None)
    cantidad = len(repo.importados)
    assert r1.nuevos == cantidad
    f = next(x for x in repo.importados.values() if x["nombre"] == "Plaza Mayor")
    repo.marcar_importado(f["id"], {"nombre": "Plaza Mayor (corregida)", "subcategoria": "Parque", "estado": "descartado",
                                    "lat": -21.6, "lng": -64.8, "ubicacion": "confirmada"})
    r2 = lug.cargar(repo, lugares_de_prueba(), ciudad, BASE, pedir=nominatim(-21.55, -64.75), mostrar=lambda s: None)
    assert r2.nuevos == 0 and r2.ya_existentes == cantidad and len(repo.importados) == cantidad
    assert repo.importados[f["id"]]["nombre"] == "Plaza Mayor (corregida)"
    assert repo.importados[f["id"]]["estado"] == "descartado" and repo.importados[f["id"]]["ubicacion"] == "confirmada"


def test_ya_existente_no_vuelve_a_consultar_el_mapa(repo, ciudad):
    lug.cargar(repo, lugares_de_prueba(), ciudad, BASE, pedir=nominatim(-21.55, -64.75), mostrar=lambda s: None)

    def prohibido(params):
        raise AssertionError("no debería consultar el mapa: ya existen")

    lug.cargar(repo, lugares_de_prueba(), ciudad, BASE, pedir=prohibido, mostrar=lambda s: None)


def test_dry_run_lista_todo_sin_escribir_ni_llamar_al_mapa(repo, ciudad, capsys):
    def prohibido(params):
        raise AssertionError("el dry-run no consulta el mapa")

    lineas: list[str] = []
    r = lug.cargar(repo, lugares_de_prueba(), ciudad, BASE, dry_run=True, pedir=prohibido, mostrar=lineas.append)
    esperados = sum(len(v) for v in POSTS.values()) + 3
    assert r.nuevos == esperados == len(lineas) and not repo.importados
    assert sum(r.por_categoria.values()) == esperados and r.por_categoria["areas-protegidas"] == 3
    assert r.por_subcategoria["Excursión"] == 3 and r.por_subcategoria["Área protegida"] == 3


def test_limite_corta_la_carga(repo, ciudad):
    lug.cargar(repo, lugares_de_prueba(), ciudad, BASE, limite=4, pedir=lambda p: [], mostrar=lambda s: None)
    assert len(repo.importados) == 4


# ───────────────────────────────────────────────────────────── repetidos

def test_repetido_por_nombre_y_distancia(ciudad):
    plaza = {"id": "c1", "nombre": "Plaza Mayor", "lat": -21.5355, "lng": -64.7296}
    cerca = {"lat": -21.5356, "lng": -64.7297}              # ~15 m
    lejos = {"lat": -21.60, "lng": -64.7297}                # ~7 km
    assert lug.buscar_repetido("Plaza Mayor", cerca, [plaza]) == {"id": "c1", "nombre": "Plaza Mayor"}
    assert lug.buscar_repetido("Plaza Mayor", lejos, [plaza]) is None
    assert lug.buscar_repetido("Plaza Mayor", None, [plaza])["id"] == "c1"           # sin punto, por nombre
    assert lug.buscar_repetido("Plaza Mayor", lejos, [{**plaza, "lat": None, "lng": None}])["id"] == "c1"
    assert lug.buscar_repetido("Mirador El Lomo", cerca, [plaza]) is None


def test_la_corrida_marca_el_repetido_de_un_comercio_activo(repo, ciudad):
    repo.comercios["com-1"] = {"id": "com-1", "nombre": "Plaza Mayor", "ciudad_id": ciudad["id"], "activo": True,
                               "lat": -21.5355, "lng": -64.7296}
    repo.comercios["com-2"] = {"id": "com-2", "nombre": "Mirador El Lomo", "ciudad_id": ciudad["id"], "activo": False}
    lug.cargar(repo, lugares_de_prueba(), ciudad, BASE, pedir=nominatim(-21.5356, -64.7297), mostrar=lambda s: None)
    por_nombre = {f["nombre"]: f for f in repo.importados.values()}
    assert por_nombre["Plaza Mayor"]["duplicado_de"] == "com-1"
    assert por_nombre["Mirador El Lomo"]["duplicado_de"] is None                    # el inactivo no cuenta


# ───────────────────────────────────────────────────────────── la línea de comandos

def test_main_dry_run(repo, capsys):
    assert lug.main(["--ciudad", "tarija", "--dry-run"], repo, descargar_=api(), dormir=lambda s: None) == 0
    salida = capsys.readouterr().out
    assert "SIMULACIÓN" in salida and "Cargaría (nuevos):      %d" % (sum(len(v) for v in POSTS.values()) + 3) in salida
    assert not repo.importados


def test_main_pide_el_rubro_y_valida_los_argumentos(repo, capsys):
    assert lug.main(["--ciudad", "tarija"], repo, descargar_=api(), dormir=lambda s: None) == 2   # el fake no tiene el rubro
    assert "0196" in capsys.readouterr().err
    assert lug.main(["--ciudad", "narnia", "--dry-run"], repo) == 2
    assert lug.main(["--ciudad", "tarija", "--limite", "0"], repo) == 2


def test_main_carga_de_verdad(repo):
    repo.rubros["para-visitar"] = "rub-pv"
    assert lug.main(["--ciudad", "tarija"], repo, descargar_=api(), pedir=nominatim(-21.55, -64.75),
                    dormir=lambda s: None) == 0
    assert len(repo.importados) == sum(len(v) for v in POSTS.values()) + 3
    assert {f["rubro_slug"] for f in repo.importados.values()} == {"para-visitar"}


def test_main_sin_sitio_devuelve_uno(repo, capsys):
    def roto(url):
        raise RuntimeError("sin conexión")
    assert lug.main(["--ciudad", "tarija", "--dry-run"], repo, descargar_=roto, dormir=lambda s: None) == 1


# ───────────────────────────────────────────────────────────── el importador de negocios no cambia

def test_importar_turismo_sigue_dejando_afuera_las_categorias_de_lugar():
    from app.services import importar_turismo as it
    assert set(lug.CATEGORIAS) == it.SUBCATEGORIAS_DE_LUGAR            # nada entra dos veces
