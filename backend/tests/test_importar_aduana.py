"""Importar las oficinas de la Aduana Nacional a Importados (docs/vigia-fuentes.md). Nunca sale a la red: `leer` es un
falso. El HTML es sintético (escrito a mano, con la estructura de las páginas de la Aduana): el real no se sube al
repo, que es público."""
import uuid

import pytest

from app.core import auth
from app.services import importar_aduana as ia
from app.services import tarjetas, ubicar_direccion

CIUDADES = {
    "bermejo": {"id": "c-bermejo", "slug": "bermejo", "nombre": "Bermejo", "departamento": "Tarija",
                "lat": -22.7361, "lng": -64.3433},
    "tarija": {"id": "c-tarija", "slug": "tarija", "nombre": "Tarija", "departamento": "Tarija",
               "lat": -21.5355, "lng": -64.7296},
    "oruro": {"id": "c-oruro", "slug": "oruro", "nombre": "Oruro", "departamento": "Oruro",
              "lat": -17.9833, "lng": -67.15},
    "la-paz": {"id": "c-la-paz", "slug": "la-paz", "nombre": "La Paz", "departamento": "La Paz",
               "lat": -16.5, "lng": -68.15},
    "cochabamba": {"id": "c-cbba", "slug": "cochabamba", "nombre": "Cochabamba", "departamento": "Cochabamba",
                   "lat": -17.3895, "lng": -66.1568},
}
CIUDADES_LISTA = list(CIUDADES.values())


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

    def sin_aduana(url):
        raise AssertionError("Aduana: un test salió a la red")
    monkeypatch.setattr(ia, "_pedir", sin_aduana)


@pytest.fixture
def repo(repo):
    """El repo falso, con las ciudades del país (con su departamento y su centro) y el rubro."""
    repo.list_ciudades = lambda: [{"id": c["id"], "slug": k, "nombre": c["nombre"]} for k, c in CIUDADES.items()]
    repo.get_ciudad = lambda slug: CIUDADES.get(slug)
    repo.rubros["aduana"] = "rub-aduana"
    return repo


# ───────────────────────────────────────────── HTML sintético

def tarjeta(nombre, direccion, telefono, lat=None, lng=None):
    lat_s, lng_s = ("", "") if lat is None else (lat, lng)
    return f"""
        <div class="col-12 col-md-8 col-lg-10"><div class="container p-1"><div class="row"><div class="col">
          <div class="card"><div class="card-body"><div class="row">
            <div class="col-12 col-md-12 col-lg-6">
              <p class="text-start h6 mb-3" style="font-weight: bold;">Nombre de oficina:
                  {nombre}
              </p>
              <p class="text-start h7 mb-3"><i class="bi bi-geo-alt small"></i>Dirección:
                {direccion}
              <p class="text-start h7"><i class="bi bi-telephone small"></i>Teléfono:
                 {telefono}
              </p>
            </div>
            <div class="col-12 col-md-12 col-lg-6">
              <iframe width="100%" height="130" src="https://www.openstreetmap.org/export/embed.html?marker={lat_s}%2C{lng_s}"></iframe>
              <div class="d-grid gap-2"><a class="btn btn-secondary btn-sm" target="_blank"
                 href="https://www.openstreetmap.org/?mlat={lat_s}&mlon={lng_s}#map=19/{lat_s}/{lng_s}&layers=N">
                 Abrir mapa <i class="bi bi-box-arrow-up-right"></i></a></div>
            </div>
          </div></div></div></div></div></div></div>"""


PIE = ("<footer><h4>Contacto</h4><p>Teléfono: (591) - 2 - 5550000</p><p>Dirección: Calle del Pie 1</p></footer>")


def pagina_direcciones(*tarjetas, paginas=()):
    pager = "".join(f'<li><a href="?page={n}" class="page-link">{n + 1}</a></li>' for n in paginas)
    return (f"<html><body><h2>Direcciones</h2><div class='row gy-4'>{''.join(tarjetas)}</div>"
            f"<nav><ul class='pagination'>{pager}</ul></nav>{PIE}</body></html>")


def tabla_horarios(region, *filas, titulos=("Oficina", "Lugar de Atención", "Días Ordinarios", "Días Extraordinarios")):
    cab = "".join(f"<th>{t}</th>" for t in titulos)
    cuerpo = "".join("<tr>" + "".join(f"<td>{c or '&nbsp;'}</td>" for c in f) + "</tr>" for f in filas)
    return (f"<div class='tab-content'><h4>{region}</h4><table class='table' border='1'><thead><tr>{cab}</tr></thead>"
            f"<tbody>{cuerpo}</tbody></table></div>")


def pagina_horarios(*tablas):
    return "<html><body><table><tr><td>menú</td></tr></table>" + "".join(tablas) + "</body></html>"


BERMEJO = tarjeta("Aduana Frontera Bermejo", "Recinto Ficticio Frontera Bermejo - Porcelana", "(4) 6612345- 6612346 (Int. 6101)",
                  -22.7332, -64.3523)
TARIJA = tarjeta("Aduana Interior Tarija", "Direcci&oacute;n: Av. Demo S/N, Zona Aeropuerto", "(4) 6612345-6612346 (Int. 6061)",
                 -21.5455, -64.7092)
ORURO = tarjeta("Gerencia Regional Oruro", "Calle Falsa N° 123 entre A y B, Oruro",
                "(2) 5234567 - 5234568 - 5234569 - 5234560 Int. 4001", -17.982, -67.1289)
LA_PAZ = tarjeta("Oficina Central - La Paz", "Av. Ficticia N°2038", "(591) - 2 - 2123456", -16.5067, -68.1303)
EL_ALTO = tarjeta("Aduana Aeropuerto El Alto", "Aeropuerto Internacional, curva del Km7.", "Teléfonos: 2812345 Int. 3711  FAX: (591-2) 2812345",
                  -16.5081, -68.1779)
POSTAL = tarjeta("Aduana Postal - Cochabamba", "Calle Pasaje 1", "", None, None)
CANADA_ORURO = tarjeta("Aduana Frontera Cañada Oruro", "Hito BR94, frontera Bolivia - Paraguay", "(4) 6612345 (Int. 6131)",
                       -21.6716, -62.4614)
PATACAMAYA = tarjeta("Aduana Patacamaya", "Carretera a Oruro: Avenida Panamericana No.250.", "28392704",
                     -17.2465, -67.9030)
COPIA_1 = tarjeta("Aduana Arroyo", "Av. Bolivia Frontera Brasil", "(3) 3553937", -17.3959, -66.2252)
COPIA_2 = tarjeta("Gerencia Regional Cochabamba", "Av. Km 7", "(4) 4377777", -17.3959, -66.2252)
MAR = tarjeta("Aduana Del Mar", "Calle Mar S/N", "(2) 2333333", 0.0, 0.0)

HORARIOS = pagina_horarios(
    tabla_horarios("Gerencia Regional Tarija",
                   ("Administración de Aduana Frontera Bermejo", "Administración (Oficina)", "lunes - viernes 8:30 16:30", ""),
                   ("Administración de Aduana Frontera Bermejo", "Área de Control Integrado (24 Horas)",
                    "lunes - viernes 0:00 23:59", "sábado, domingo y feriados 00:00 23:59"),
                   ("Administración de Aduana Interior Tarija", "Administración (Oficina)", "lunes - viernes 8:30 16:30", "")),
    tabla_horarios("Gerencia Regional Oruro",
                   ("Administración de Aduana Interior Oruro", "Pasto Grande", "lunes - viernes 08:30 18:30", ""),
                   ("Gerencia Regional Oruro", "Atención Oficinas", "lunes - viernes 08:30 16:30", ""),
                   ("Administración de Aduana Frontera Sin Dirección", "Oficina", "lunes - viernes 08:00 12:00", "")),
)
DIRECCIONES = pagina_direcciones(BERMEJO, TARIJA, ORURO, LA_PAZ, EL_ALTO, POSTAL, CANADA_ORURO, PATACAMAYA,
                                 paginas=(1, 2))


def datos_de(direcciones_html=DIRECCIONES, horarios_html=HORARIOS):
    oficinas, _ = ia.parsear_direcciones(direcciones_html)
    return {"direcciones": oficinas, "horarios": ia.parsear_horarios(horarios_html)}


def correr(repo, datos_, *args):
    salida: list[str] = []
    codigo = ia.main([*args], repo, leer=lambda *a, **k: datos_, mostrar=salida.append)
    return codigo, "\n".join(salida)


def importados(repo):
    return [f for f in repo.importados.values() if f["fuente"] == "aduana"]


# ───────────────────────────────────────────── parseo

def test_parsear_direcciones_lee_las_tarjetas_y_el_punto():
    oficinas, paginas = ia.parsear_direcciones(DIRECCIONES)
    assert len(oficinas) == 8 and paginas == {1, 2}
    b = oficinas[0]
    assert b["nombre"] == "Aduana Frontera Bermejo" and b["direccion"].startswith("Recinto Ficticio")
    assert b["telefono"] == "(4) 6612345- 6612346 (Int. 6101)"
    assert (b["lat"], b["lng"]) == (-22.7332, -64.3523) and b["url"] == ia.URL_DIRECCIONES
    assert oficinas[5]["nombre"] == "Aduana Postal - Cochabamba"
    assert oficinas[5]["lat"] is None and oficinas[5]["telefono"] == ""         # el mapa vacío no es un punto


def test_el_pie_de_la_pagina_no_se_mezcla_con_la_ultima_tarjeta():
    oficinas, _ = ia.parsear_direcciones(pagina_direcciones(BERMEJO))
    assert "5550000" not in oficinas[0]["telefono"] and "Pie" not in oficinas[0]["direccion"]


def test_un_rotulo_repetido_se_limpia_y_las_entidades_se_decodifican():
    oficinas, _ = ia.parsear_direcciones(pagina_direcciones(TARIJA))      # «Dirección: Dirección: Av. …»
    assert oficinas[0]["direccion"] == "Av. Demo S/N, Zona Aeropuerto"
    assert ia.direccion_limpia("Dirección: Calle 1.") == "Calle 1"
    assert ia.direccion_limpia("https://x.com/mapa") is None


def test_un_punto_fuera_de_bolivia_se_ignora():
    oficinas, _ = ia.parsear_direcciones(pagina_direcciones(MAR))
    assert oficinas[0]["lat"] is None and oficinas[0]["lng"] is None


def test_sin_tarjetas_o_sin_tabla_lanza():
    with pytest.raises(ia.PaginaInesperada):
        ia.parsear_direcciones("<html><body><p>Mantenimiento</p></body></html>")
    with pytest.raises(ia.PaginaInesperada):
        ia.parsear_horarios("<html><body><table><tr><td>otra cosa</td></tr></table></body></html>")
    with pytest.raises(ia.PaginaInesperada):
        ia.parsear_horarios(pagina_horarios(tabla_horarios("X", ("a", "b"), titulos=("Algo", "Otro"))))


def test_parsear_horarios_lee_las_filas_de_todas_las_tablas():
    filas = ia.parsear_horarios(HORARIOS)
    assert len(filas) == 6
    assert filas[1] == {"oficina": "Administración de Aduana Frontera Bermejo",
                        "lugar": "Área de Control Integrado (24 Horas)", "ordinarios": "lunes - viernes 0:00 23:59",
                        "extraordinarios": "sábado, domingo y feriados 00:00 23:59"}
    assert filas[0]["extraordinarios"] == ""                       # el &nbsp; no es un horario


# ───────────────────────────────────────────── normalizar

@pytest.mark.parametrize("crudo,area,esperado", [
    ("(4) 6612345- 6612346 (Int. 6101)", "", ["+59146612345", "+59146612346"]),
    ("(591) - 2 - 2123456", "4", ["+59122123456"]),                          # el área que escribe la página manda
    ("2812345 Int. 3711  FAX: (591-2) 2812345", "2", ["+59122812345"]),        # sin el fax ni el interno
    ("Teléfonos: 2818050-2818358-2816863 Int. 3001 - 3007", "2", ["+59122818050", "+59122818358", "+59122816863"]),
    ("28392704", "", ["+59128392704"]),                                       # ocho dígitos: ya trae el área
    ("2136261", "2", ["+59122136261"]),                                       # siete: se le pone el del departamento
    ("(4) 4377777 – Interno 5061", "", ["+59144377777"]),
    ("", "4", []), (None, "4", []), ("sin teléfono", "4", []),
])
def test_telefonos_de(crudo, area, esperado):
    assert [t.numero for t in ia.telefonos_de(crudo, area)] == esperado


def test_tipo_de_oficina():
    assert [ia.tipo_de(n) for n in (
        "Aduana Frontera Bermejo", "Aduana Interior Tarija", "Aduana Aeropuerto El Alto", "Aduana Postal Santa Cruz",
        "Aduana Zona Franca Industrial Oruro", "Gerencia Regional Oruro", "Oficina Central - La Paz",
        "Puesto de Control Frontera Hito Cajones", "Agencia de Aduana Exterior Arica", "Aduana Cobija")] == [
        "Frontera", "Interior", "Aeropuerto", "Postal", "Zona franca", "Gerencia regional", "Oficina central",
        "Puesto de control", "Exterior", "Oficina"]


def test_horario_de_una_linea_con_cada_lugar_de_atencion():
    filas = ia.parsear_horarios(HORARIOS)[:2]
    assert ia.horario_de(filas) == (
        "Administración (Oficina): lunes a viernes 8:30 a 16:30 · "
        "Área de Control Integrado (24 Horas): lunes a viernes 0:00 a 23:59; sábado, domingo y feriados 00:00 a 23:59")
    assert ia.horario_de([]) is None
    assert ia.horario_de([{"lugar": "X", "ordinarios": "", "extraordinarios": ""}]) is None


def test_el_horario_no_pasa_de_su_tope():
    filas = [{"lugar": f"Lugar {i}", "ordinarios": "lunes - viernes 8:00 12:00", "extraordinarios": ""}
             for i in range(60)]
    assert len(ia.horario_de(filas)) <= ia.MAX_HORARIO


def test_unir_junta_direcciones_y_horarios_por_el_nombre_de_la_oficina():
    oficinas, sin_direccion = ia.unir(datos_de())
    por_nombre = {o["nombre"]: o for o in oficinas}
    assert len(por_nombre["Aduana Frontera Bermejo"]["horarios"]) == 2        # «Administración de Aduana …»
    assert len(por_nombre["Aduana Interior Tarija"]["horarios"]) == 1
    assert len(por_nombre["Gerencia Regional Oruro"]["horarios"]) == 1
    assert por_nombre["Aduana Postal - Cochabamba"]["horarios"] == []
    assert sin_direccion == 2                                                   # «Interior Oruro» y «Frontera Sin Dirección»


def test_unir_acepta_un_nombre_que_es_el_comienzo_del_otro():
    datos_ = {"direcciones": [{"nombre": "Aduana Interior Oruro - Pasto Grande", "direccion": "x", "telefono": ""}],
              "horarios": [{"oficina": "Administración de Aduana Interior Oruro", "lugar": "P",
                            "ordinarios": "lunes - viernes 8:00 9:00", "extraordinarios": ""}]}
    oficinas, sin = ia.unir(datos_)
    assert len(oficinas[0]["horarios"]) == 1 and sin == 0


def test_fuente_id_estable_por_el_nombre():
    assert ia.fuente_id_de("Aduana Frontera Cañada Oruro") == "aduana:aduana-frontera-canada-oruro"
    assert ia.fuente_id_de("  Aduana   Frontera BERMEJO ") == ia.fuente_id_de("Aduana Frontera Bermejo")


# ───────────────────────────────────────────── ciudad

def oficina(nombre, direccion="", lat=None, lng=None):
    return {"nombre": nombre, "direccion": direccion, "lat": lat, "lng": lng}


@pytest.mark.parametrize("o,esperada", [
    (oficina("Aduana Frontera Bermejo", "Recinto Porcelana", -22.7332, -64.3523), "bermejo"),   # la ciudad del nombre
    (oficina("Oficina Central - La Paz", "Av. 20 de Octubre", -16.5067, -68.1303), "la-paz"),
    (oficina("Gerencia Regional Potosí X", "Madrid 390 entre A y B, Oruro"), "oruro"),         # la localidad al final
    (oficina("Aduana Frontera Pisiga", "Oruro, carretera internacional"), "oruro"),            # y al comienzo
    (oficina("Aduana Patacamaya", "Carretera a Oruro: Avenida Panamericana", -17.2465, -67.9030), None),   # un camino
    (oficina("Aduana Frontera Cañada Oruro", "Hito BR94", -21.6716, -62.4614), None),         # el punto la contradice
    (oficina("Aduana Aeropuerto El Alto", "Aeropuerto Internacional", -16.5081, -68.1779), "la-paz"),     # por el punto
    (oficina("Aduana Sin Pistas", "Calle 1"), None),                                           # no se inventa una
    (oficina("Aduana Frontera Tambo Quemado", "Carretera Patacamaya Tambo Quemado", -18.2838, -69.0715), None),
])
def test_asignar_ciudad(o, esperada):
    assert (ia.asignar_ciudad(o, CIUDADES_LISTA) or {}).get("slug") == esperada


def test_un_punto_repetido_en_otra_oficina_no_sirve_para_elegir_ciudad():
    o = oficina("Aduana Arroyo", "Av. Bolivia", -17.3959, -66.2252)
    assert ia.asignar_ciudad(o, CIUDADES_LISTA)["slug"] == "cochabamba"
    assert ia.asignar_ciudad(o, CIUDADES_LISTA, punto_unico=False) is None


def test_las_ciudades_son_las_de_la_tabla_con_centro(repo):
    assert {c["slug"] for c in ia.ciudades_del_pais(repo)} == set(CIUDADES)


# ───────────────────────────────────────────── la fila

def _fila(o, ciudad="bermejo", **kw):
    oficinas, _ = ia.unir({"direcciones": [o], "horarios": ia.parsear_horarios(HORARIOS)})
    return ia.armar_fila(oficinas[0], ciudad=CIUDADES[ciudad], rubros_validos=lambda s: True, **kw)


def test_armar_fila_guarda_horario_y_telefono_sin_whatsapp():
    o = ia.parsear_direcciones(pagina_direcciones(BERMEJO))[0][0]
    f = _fila(o)
    assert f["fuente"] == "aduana" and f["fuente_id"] == "aduana:aduana-frontera-bermejo"
    assert f["ciudad_id"] == "c-bermejo" and f["estado"] == "nuevo" and f["rubro_slug"] == "aduana"
    assert f["nombre"] == "Aduana Frontera Bermejo" and f["subcategoria"] == "Frontera"
    assert f["horario"].startswith("Administración (Oficina): lunes a viernes 8:30 a 16:30")
    assert f["whatsapp"] is None and "661 2345" in f["telefono"] and "661 2346" in f["telefono"]
    assert (f["lat"], f["lng"]) == (-22.7332, -64.3523) and f["ubicacion"] == "aproximada"
    assert f["direccion"] == "Recinto Ficticio Frontera Bermejo - Porcelana"
    assert f["fuente_url"] == ia.URL_DIRECCIONES and f["duplicado_de"] is None and f["email"] is None
    t = f["tags"]["aduana"]
    assert t["tipo"] == "Frontera" and t["municipio"] == "Bermejo" and t["url"] == ia.URL_DIRECCIONES
    assert len(t["horarios"]) == 2 and t["url_horarios"] == ia.URL_HORARIOS
    assert f["texto_leido"].startswith("Aduana Nacional · oficinas · Bermejo")
    assert ia.URL_DIRECCIONES in f["texto_leido"] and "Horario: " in f["texto_leido"]


def test_un_celular_tambien_va_a_telefono_nunca_a_whatsapp():
    o = {"nombre": "Aduana Interior Tarija", "direccion": "X", "telefono": "(4) 72957024", "lat": None, "lng": None}
    f = ia.armar_fila({**o, "horarios": []}, ciudad=CIUDADES["tarija"], rubros_validos=lambda s: True)
    assert f["whatsapp"] is None and "7295" in (f["telefono"] or "")


def test_sin_punto_o_con_punto_lejos_queda_no_encontrada():
    o = ia.parsear_direcciones(pagina_direcciones(BERMEJO))[0][0]
    f = _fila(o, usar_punto=False)
    assert f["lat"] is None and f["ubicacion"] == "no_encontrada"
    assert f["tags"]["aduana"]["punto_aduana"] == {"lat": -22.7332, "lng": -64.3523}      # guardado, no usado
    lejos = {**o, "lat": -19.0, "lng": -65.0}
    assert _fila(lejos)["lat"] is None


def test_rubro_que_no_existe_queda_vacio():
    o = ia.parsear_direcciones(pagina_direcciones(BERMEJO))[0][0]
    assert ia.armar_fila({**o, "horarios": []}, ciudad=CIUDADES["bermejo"],
                         rubros_validos=lambda s: False)["rubro_slug"] is None


# ───────────────────────────────────────────── el comando

def test_simulacion_no_guarda_nada(repo):
    antes = len(repo.importados)
    codigo, salida = correr(repo, datos_de(), "--dry-run")
    assert codigo == 0 and len(repo.importados) == antes
    assert "Entrarían:    6" in salida and "SIMULACIÓN" in salida and "fuera_de_ciudad: 2" in salida
    assert "Leídas de la Aduana:     8" in salida and "2 oficinas de horarios sin dirección" in salida
    assert "Con horario:             3" in salida and "Por ciudad:" in salida


def test_carga_y_volver_a_correr_no_duplica(repo):
    d = datos_de()
    codigo, salida = correr(repo, d)
    assert codigo == 0
    nuevos = importados(repo)
    assert len(nuevos) == 6 and all(f["estado"] == "nuevo" and f["rubro_slug"] == "aduana" for f in nuevos)
    assert {f["ciudad_id"] for f in nuevos} == {"c-bermejo", "c-tarija", "c-oruro", "c-la-paz", "c-cbba"}
    codigo, salida = correr(repo, d)
    assert len(importados(repo)) == 6
    assert "Ya estaban:              6" in salida and "Nuevas en Importados:    0" in salida


def test_dry_run_despues_de_cargar_dice_que_ya_estaban(repo):
    d = datos_de()
    correr(repo, d)
    _, salida = correr(repo, d, "--dry-run")
    assert "Ya estaban:              6" in salida and "Entrarían:    0" in salida


def test_oficinas_de_ciudades_fuera_de_la_tabla_se_descartan(repo):
    correr(repo, datos_de())
    nombres = {f["nombre"] for f in importados(repo)}
    assert "Aduana Frontera Cañada Oruro" not in nombres and "Aduana Patacamaya" not in nombres
    assert "Aduana Aeropuerto El Alto" in nombres             # por el punto, dentro del radio de La Paz


def test_la_tarjeta_repetida_en_la_pagina_se_cuenta_una_vez(repo):
    d = datos_de()
    d["direcciones"] = d["direcciones"] + [d["direcciones"][0]]
    _, salida = correr(repo, d)
    assert len(importados(repo)) == 6 and "repetida_en_la_pagina: 1" in salida


def test_los_puntos_copiados_de_otra_oficina_no_deciden_la_ciudad(repo):
    d = {"direcciones": ia.parsear_direcciones(pagina_direcciones(COPIA_1, COPIA_2))[0], "horarios": []}
    _, salida = correr(repo, d)
    assert [f["nombre"] for f in importados(repo)] == ["Gerencia Regional Cochabamba"]
    assert "fuera_de_ciudad: 1" in salida


def test_sin_punto_ignora_el_de_la_aduana(repo):
    correr(repo, datos_de(), "--sin-punto")
    assert all(f["lat"] is None and f["ubicacion"] == "no_encontrada" for f in importados(repo))


def test_limite(repo):
    correr(repo, datos_de(), "--limite", "2")
    assert len(importados(repo)) == 2


def test_repetido_por_telefono(repo):
    cid = str(uuid.uuid4())
    repo.comercios[cid] = {"id": cid, "nombre": "Otro nombre", "ciudad_id": "c-tarija", "activo": True, "slug": "x",
                           "whatsapp": None, "telefono": "46612345"}
    correr(repo, datos_de())
    assert {f["nombre"]: f["duplicado_de"] for f in importados(repo)}["Aduana Interior Tarija"] == cid


def test_repetido_por_nombre_en_la_misma_ciudad(repo):
    cid = str(uuid.uuid4())
    repo.comercios[cid] = {"id": cid, "nombre": "Aduana Bermejo", "ciudad_id": "c-bermejo", "activo": True,
                           "slug": "x", "whatsapp": None}
    otra = str(uuid.uuid4())
    repo.comercios[otra] = {"id": otra, "nombre": "Aduana Frontera Bermejo", "ciudad_id": "c-tarija", "activo": True,
                            "slug": "y", "whatsapp": None}
    correr(repo, datos_de())
    assert {f["nombre"]: f["duplicado_de"] for f in importados(repo)}["Aduana Frontera Bermejo"] == cid


def test_argumentos_invalidos(repo):
    assert ia.main(["--limite", "0"], repo, leer=lambda *a, **k: {}, mostrar=lambda _: None) == 2


def test_sin_ciudades_en_la_tabla_sale_con_error(repo):
    repo.list_ciudades = lambda: []
    assert ia.main([], repo, leer=lambda *a, **k: {}, mostrar=lambda _: None) == 2


def test_si_la_aduana_no_contesta_sale_con_error(repo):
    def caido(*a, **k):
        raise OSError("sin red")
    assert ia.main([], repo, leer=caido, mostrar=lambda _: None) == 1


def test_si_la_aduana_cambio_la_pagina_sale_con_error(repo):
    def cambiada(*a, **k):
        return {"direcciones": ia.parsear_direcciones("<html></html>")[0], "horarios": []}
    assert ia.main([], repo, leer=cambiada, mostrar=lambda _: None) == 1
    assert importados(repo) == []


# ───────────────────────────────────────────── lectura

def test_leer_aduana_recorre_las_paginas_y_pide_los_horarios_con_pausa(monkeypatch):
    pedidos, pausas = [], []
    monkeypatch.setattr(ia.time, "sleep", pausas.append)

    def pedir(url):
        pedidos.append(url)
        if url == ia.URL_HORARIOS:
            return HORARIOS, url
        if url.endswith("page=1"):
            return pagina_direcciones(LA_PAZ, paginas=(0, 2)), url
        if url.endswith("page=2"):
            return pagina_direcciones(ORURO, paginas=(0, 1)), url
        return DIRECCIONES, url

    datos_ = ia.leer_aduana(pedir=pedir)
    assert pedidos == [ia.URL_DIRECCIONES, f"{ia.URL_DIRECCIONES}?page=1", f"{ia.URL_DIRECCIONES}?page=2",
                       ia.URL_HORARIOS]
    assert pausas == [ia.PAUSA_SEG] * 3
    assert len(datos_["direcciones"]) == 8 + 1 + 1 and len(datos_["horarios"]) == 6


# ───────────────────────────────────────────── ubicador

def test_el_ubicador_levanta_las_de_la_aduana_sin_punto_y_no_toca_las_que_traen_el_suyo(repo):
    correr(repo, datos_de())
    postal = next(f for f in importados(repo) if f["nombre"] == "Aduana Postal - Cochabamba")
    con_punto = next(f for f in importados(repo) if f["nombre"] == "Aduana Frontera Bermejo")
    assert postal["lat"] is None and con_punto["lat"] is not None
    punto = {"lat": "-17.39", "lon": "-66.15", "display_name": "Calle Pasaje", "place_rank": 26}
    salida: list[str] = []
    assert ubicar_direccion.main(["--ciudad", "cochabamba", "--rehacer"], repo, pedir=lambda p: [punto],
                                 mostrar=salida.append) == 0
    assert postal["lat"] == -17.39 and postal["ubicacion"] == "aproximada"
    assert ubicar_direccion.main(["--ciudad", "bermejo", "--rehacer"], repo, pedir=lambda p: [],
                                 mostrar=lambda s: None) == 0
    assert con_punto["lat"] == -22.7332 and con_punto["ubicacion"] == "aproximada"        # --rehacer no se lo saca


# ───────────────────────────────────────────── moderación

def _id_de(repo, nombre):
    return next(k for k, f in repo.importados.items() if f["fuente"] == "aduana" and f["nombre"] == nombre)


def test_listado_filtra_por_aduana(client, repo, datos):
    correr(repo, datos_de())
    repo.importados["otro"] = {"id": "otro", "fuente": "osm", "fuente_id": "node/1", "estado": "nuevo",
                               "nombre": "Otro", "ciudad_id": "c-tarija", "duplicado_de": None}
    r = client.get("/admin/importados", params={"fuente": "aduana"}, headers=datos)
    assert r.status_code == 200, r.text
    assert {i["fuente"] for i in r.json()["items"]} == {"aduana"} and len(r.json()["items"]) == 6
    assert r.json()["items"][0]["horario"] is not None or r.json()["items"][0]["texto_leido"]


def test_promover_una_oficina_crea_el_lugar_no_comercial(client, repo, datos):
    correr(repo, datos_de())
    iid = _id_de(repo, "Aduana Frontera Bermejo")
    repo.importados[iid]["whatsapp"] = "59170011122"              # aunque alguien lo hubiera dejado en la fila
    r = client.post(f"/admin/importados/{iid}/promover", json={}, headers=datos)
    assert r.status_code == 200, r.text
    com = repo.comercios[r.json()["comercio"]["id"]]
    assert com["nombre"] == "Aduana Frontera Bermejo" and com["subcategoria"] == "Frontera"
    assert com["horario"].startswith("Administración (Oficina): lunes a viernes 8:30 a 16:30")
    assert com["direccion"] == "Recinto Ficticio Frontera Bermejo - Porcelana"
    assert com["fuente_url"] == ia.URL_DIRECCIONES
    assert com["telefono"] and "661 2345" in com["telefono"] and com["whatsapp"] is None
    assert com["cargado_por"] == "import:aduana" and com["verificado"] is False and com["confiable"] is False
    assert com["activo"] is True and com["lat"] == -22.7332 and com["ciudad_id"] == "c-bermejo"
    assert com["rubro_revisado_por"] == "datos@uruku.bo" and com["rubro_revisado_at"]      # lo masivo no lo toca
    assert repo.comercios[com["id"]]["rubros"] == ["aduana"]
    assert repo.importados[iid]["estado"] == "promovido" and repo.importados[iid]["comercio_id"] == com["id"]


def test_promover_una_oficina_sin_punto_con_la_confirmacion_de_la_persona(client, repo, datos):
    correr(repo, datos_de())
    iid = _id_de(repo, "Aduana Postal - Cochabamba")
    assert client.post(f"/admin/importados/{iid}/promover", json={}, headers=datos).status_code == 400
    r = client.post(f"/admin/importados/{iid}/promover", json={"sin_ubicacion": True}, headers=datos)
    assert r.status_code == 200, r.text
    assert repo.comercios[r.json()["comercio"]["id"]]["lat"] is None
