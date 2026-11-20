"""Platos típicos (docs/home-ciudades.md §15): Admin › Platos típicos (listar y editar), el importador de
gastronomía con HTTP y Gemini simulados (interruptor apagado / prendido, texto original, sin copias) y el
interruptor `gemini_gastronomia`. Sin red y sin gastar nada."""
import json

import pytest

from app.core import auth
from app.core.config import settings
from app.services import content_captions, cost_switches, importar_gastronomia as ig, importar_turismo

CIUDAD = {"id": "6f1c1c1e-1b1a-4c55-9d3a-0a6c2f9a7b10", "slug": "tarija", "nombre": "Tarija"}
OTRA_CIUDAD = "9a2b8d6e-3c4d-4e5f-8a7b-1c2d3e4f5a6b"
BASE = "https://tarijaturismo.com"


def h(token):
    return {"Authorization": f"Bearer {token}"}


def _token(permisos):
    return h(auth.make_token("x@uruku.bo", rol="x", roles=["x"], permisos=permisos))


@pytest.fixture
def contenido():
    return _token(["contenido"])


@pytest.fixture(autouse=True)
def _interruptores_limpios():
    cost_switches.reiniciar_cache()
    yield
    cost_switches.reiniciar_cache()


@pytest.fixture(autouse=True)
def _sin_red(monkeypatch):
    def no(*a, **k):
        raise AssertionError("los tests no pueden salir a la red")

    monkeypatch.setattr(importar_turismo, "descargar_pagina", no)
    monkeypatch.setattr(content_captions, "llamar_gemini_partes", no)


@pytest.fixture
def repo(repo):
    repo.ciudades = getattr(repo, "ciudades", {})
    repo.get_ciudad = lambda slug: dict(CIUDAD) if slug == "tarija" else None
    return repo


def _plato(repo, **kw):
    return repo.crear_plato({"ciudad_id": CIUDAD["id"], "tipo": "plato", "nombre": "Saice", "descripcion": "Un guiso.",
                             "fuente_url": f"{BASE}/saice/", **kw})


# ══════════════════════════════════════════ los endpoints del admin

def test_sin_token_no_entra(client):
    assert client.get("/admin/platos").status_code in (401, 403)
    assert client.patch("/admin/platos/x", json={"estado": "aprobado"}).status_code in (401, 403)


def test_sin_el_permiso_contenido_es_403(client, repo):
    p = _plato(repo)
    sin = _token(["pagos", "datos"])
    assert client.get("/admin/platos", headers=sin).status_code == 403
    assert client.patch(f"/admin/platos/{p['id']}", json={"estado": "aprobado"}, headers=sin).status_code == 403
    assert repo.get_plato(p["id"])["estado"] == "pendiente"


def test_el_admin_y_el_rol_publicador_entran(client, repo, admin_token):
    assert client.get("/admin/platos", headers=h(admin_token)).status_code == 200
    publicador = h(auth.make_token("p@uruku.bo", rol="publicador"))
    assert client.get("/admin/platos", headers=publicador).status_code == 200


def test_listar_devuelve_una_lista_con_los_campos_del_contrato(client, repo, contenido):
    _plato(repo)
    r = client.get("/admin/platos", headers=contenido)
    assert r.status_code == 200
    filas = r.json()
    assert isinstance(filas, list) and len(filas) == 1
    assert set(filas[0]) == {"id", "ciudad_id", "tipo", "nombre", "descripcion", "fuente_url", "estado", "activo",
                             "updated_at"}
    assert filas[0]["estado"] == "pendiente" and filas[0]["activo"] is True


def test_listar_filtra_por_ciudad_y_estado_y_muestra_todos_los_estados(client, repo, contenido):
    _plato(repo, nombre="A")
    p = _plato(repo, nombre="B", tipo="bebida")
    repo.update_plato(p["id"], {"estado": "aprobado"})
    r_ = _plato(repo, nombre="C", tipo="reposteria")
    repo.update_plato(r_["id"], {"estado": "rechazado", "activo": False})
    _plato(repo, nombre="D", ciudad_id=OTRA_CIUDAD)
    todos = client.get("/admin/platos", params={"ciudad_id": CIUDAD["id"]}, headers=contenido).json()
    assert sorted(x["nombre"] for x in todos) == ["A", "B", "C"]
    assert [x["nombre"] for x in client.get("/admin/platos", params={"ciudad_id": CIUDAD["id"], "estado": "aprobado"},
                                             headers=contenido).json()] == ["B"]
    assert [x["nombre"] for x in client.get("/admin/platos", params={"estado": "pendiente"},
                                             headers=contenido).json()] == ["A", "D"]
    assert client.get("/admin/platos", params={"estado": "borrado"}, headers=contenido).status_code == 422


def test_editar_nombre_y_texto_con_los_espacios_parejos(client, repo, contenido):
    p = _plato(repo)
    r = client.patch(f"/admin/platos/{p['id']}", json={"nombre": "  Saice   tarijeño ", "descripcion": " Un guiso\n de carne. "},
                     headers=contenido)
    assert r.status_code == 200, r.text
    assert r.json()["nombre"] == "Saice tarijeño" and r.json()["descripcion"] == "Un guiso de carne."
    assert set(r.json()) == {"id", "ciudad_id", "tipo", "nombre", "descripcion", "fuente_url", "estado", "activo", "updated_at"}
    assert repo.get_plato(p["id"])["nombre"] == "Saice tarijeño"


def test_aprobar_rechazar_y_dar_de_baja(client, repo, contenido):
    p = _plato(repo)
    url = f"/admin/platos/{p['id']}"
    assert client.patch(url, json={"estado": "aprobado"}, headers=contenido).json()["estado"] == "aprobado"
    assert client.patch(url, json={"estado": "rechazado"}, headers=contenido).json()["estado"] == "rechazado"
    r = client.patch(url, json={"activo": False}, headers=contenido).json()
    assert r["activo"] is False and r["estado"] == "rechazado"
    assert client.patch(url, json={"activo": True, "estado": "aprobado"}, headers=contenido).json()["activo"] is True


def test_el_texto_vacio_lo_deja_sin_descripcion(client, repo, contenido):
    p = _plato(repo)
    r = client.patch(f"/admin/platos/{p['id']}", json={"descripcion": "   "}, headers=contenido)
    assert r.status_code == 200 and r.json()["descripcion"] is None


def test_no_cambia_ni_la_ciudad_ni_el_tipo_ni_el_enlace(client, repo, contenido):
    p = _plato(repo)
    r = client.patch(f"/admin/platos/{p['id']}", json={"ciudad_id": "otra", "tipo": "bebida", "fuente_url": "https://x.com",
                                                          "estado": "aprobado"}, headers=contenido)
    assert r.status_code == 200
    fila = repo.get_plato(p["id"])
    assert fila["ciudad_id"] == CIUDAD["id"] and fila["tipo"] == "plato" and fila["fuente_url"] == f"{BASE}/saice/"
    assert fila["estado"] == "aprobado"


def test_errores_404_400_422_409(client, repo, contenido):
    p = _plato(repo)
    otro = _plato(repo, nombre="Chancho a la cruz")
    url = f"/admin/platos/{p['id']}"
    assert client.patch("/admin/platos/3d8e1f52-7a40-4b8f-9c11-5e2a6b7c8d90", json={"estado": "aprobado"},
                        headers=contenido).status_code == 404
    assert client.patch(url, json={}, headers=contenido).status_code == 400
    assert client.patch(url, json={"nombre": "   "}, headers=contenido).status_code == 400
    assert client.patch(url, json={"estado": "publicado"}, headers=contenido).status_code == 422
    assert client.patch(url, json={"nombre": "x" * 200}, headers=contenido).status_code == 422
    assert client.patch(url, json={"descripcion": "x" * 900}, headers=contenido).status_code == 422
    # el único (ciudad, nombre): sin mirar mayúsculas ni tildes
    assert client.patch(url, json={"nombre": "chancho A la cruz"}, headers=contenido).status_code == 409
    assert client.patch(f"/admin/platos/{otro['id']}", json={"nombre": "CHANCHO a la cruz"}, headers=contenido).status_code == 200


def test_editar_deja_registro_con_structlog(client, repo, contenido):
    import structlog
    p = _plato(repo)
    with structlog.testing.capture_logs() as logs:
        client.patch(f"/admin/platos/{p['id']}", json={"estado": "aprobado"}, headers=contenido)
    ev = next(l for l in logs if l["event"] == "admin.plato_editado")
    assert ev["plato"] == p["id"] and ev["estado"] == "aprobado" and ev["by"] == "x@uruku.bo"


def test_un_id_que_no_es_uuid_es_400_y_no_un_500(client, repo, contenido):
    for malo in ("no-existe", "123", "x" * 80, "1; drop"):
        r = client.patch(f"/admin/platos/{malo}", json={"estado": "aprobado"}, headers=contenido)
        assert r.status_code == 400 and "no es válido" in r.json()["detail"], malo
    r = client.get("/admin/platos", params={"ciudad_id": "tarija"}, headers=contenido)
    assert r.status_code == 400 and "ciudad" in r.json()["detail"].lower()


def test_aprobar_exige_texto_el_que_ya_tiene_o_el_del_mismo_cuerpo(client, repo, contenido):
    sin = _plato(repo, descripcion=None)
    url = f"/admin/platos/{sin['id']}"
    r = client.patch(url, json={"estado": "aprobado"}, headers=contenido)
    assert r.status_code == 400 and r.json()["detail"] == "No se puede aprobar un plato sin texto."
    assert client.patch(url, json={"estado": "aprobado", "descripcion": "   "}, headers=contenido).status_code == 400
    assert repo.get_plato(sin["id"])["estado"] == "pendiente"
    # con el texto en el mismo cuerpo, sí
    r = client.patch(url, json={"estado": "aprobado", "descripcion": "Un guiso de carne y ají."}, headers=contenido)
    assert r.status_code == 200 and r.json()["estado"] == "aprobado"
    # y una vez aprobado no se le puede vaciar el texto
    r = client.patch(url, json={"descripcion": ""}, headers=contenido)
    assert r.status_code == 400 and repo.get_plato(sin["id"])["descripcion"] == "Un guiso de carne y ají."
    # rechazar o pendiente no necesitan texto
    assert client.patch(url, json={"estado": "rechazado", "descripcion": ""}, headers=contenido).status_code == 200
    con = _plato(repo, nombre="Con texto")
    assert client.patch(f"/admin/platos/{con['id']}", json={"estado": "aprobado"}, headers=contenido).status_code == 200


# ══════════════════════════════════════════ el interruptor de costo

def test_gemini_gastronomia_esta_en_el_catalogo_y_apagado(crepo):
    c = cost_switches.CATALOGO["gemini_gastronomia"]
    assert set(c) == {"label", "what", "cost", "off_means"} and all(c.values())
    assert cost_switches.GEMINI_GASTRONOMIA == "gemini_gastronomia"
    assert cost_switches.esta_prendido(crepo, "gemini_gastronomia") is False
    assert next(i for i in cost_switches.listar(crepo) if i["key"] == "gemini_gastronomia")["enabled"] is False


# ══════════════════════════════════════════ el sitio: HTML y la API de WordPress (sin red)

def test_sin_html_saca_etiquetas_scripts_y_entidades():
    crudo = "<style>p{x:1}</style><p>Sopa de&nbsp;ma&#237;z</p><script>var a=1</script><ul><li>Ma&iacute;z</li><li>Cebolla</li></ul>"
    assert ig.sin_html(crudo) == "Sopa de maíz Maíz Cebolla"
    assert ig.sin_html(None) == "" and ig.sin_html("<p></p>") == ""


def test_clave_nombre_no_mira_mayusculas_ni_tildes():
    assert ig.clave_nombre("  Chancho  a la CRUZ ") == ig.clave_nombre("chancho a la cruz")
    assert ig.clave_nombre("Ají de fideo") == ig.clave_nombre("aji de fideo")


def _post(titulo, link, contenido="<p>texto</p>"):
    return {"id": 1, "link": link, "title": {"rendered": titulo}, "content": {"rendered": contenido}}


SITIO = ig.SITIOS["tarija"]


def test_notas_de_posts_toma_nombre_enlace_y_texto_y_descarta_lo_raro():
    notas = ig.notas_de_posts([
        _post("Saice &#8211; Tarija", f"{BASE}/saice/", "<p>Carne picada con ají.</p>"),
        _post("", f"{BASE}/vacio/"),
        _post("Con enlace ajeno", "https://otro-sitio.com/x/"),
        _post("Con http", "http://tarijaturismo.com/x/"),
        "no soy un post", None,
    ], "plato", SITIO)
    assert [(n.nombre, n.url, n.tipo) for n in notas] == [
        ("Saice – Tarija", f"{BASE}/saice/", "plato"), ("Con enlace ajeno", None, "plato"), ("Con http", None, "plato")]
    assert notas[0].texto == "Carne picada con ají."


class _Sitio:
    """Contesta las URLs de la API de WordPress con lo que se le cargue y recuerda lo que se pidió."""

    def __init__(self, posts_por_id):
        self.pedidas: list[str] = []
        self.posts = posts_por_id

    def __call__(self, url):
        self.pedidas.append(url)
        if "/categories?" in url:
            return json.dumps([{"id": 11, "slug": "platos"}, {"id": 12, "slug": "reposteria-tradicional"},
                               {"id": 13, "slug": "bebidas-tipicas"}])
        cid = int(url.split("categories=")[1].split("&")[0])
        return json.dumps(self.posts.get(cid, []))


def test_leer_notas_pide_las_categorias_y_los_posts_con_solo_los_campos_necesarios():
    sitio = _Sitio({11: [_post("Saice", f"{BASE}/saice/")], 12: [_post("Alfajores", f"{BASE}/alf/")],
                    13: [_post("Singani", f"{BASE}/sing/"), _post("Saice", f"{BASE}/saice-otra/")]})
    notas = ig.leer_notas(SITIO, sitio)
    assert [(n.nombre, n.tipo) for n in notas] == [("Saice", "plato"), ("Alfajores", "reposteria"), ("Singani", "bebida")]
    assert sitio.pedidas[0] == f"{BASE}/wp-json/wp/v2/categories?per_page=100&slug=platos,reposteria-tradicional,bebidas-tipicas&_fields=id,slug"
    assert sitio.pedidas[1:] == [f"{BASE}/wp-json/wp/v2/posts?categories={c}&per_page=100&_fields=id,link,title,content"
                                 for c in (11, 12, 13)]


def test_leer_notas_falla_en_español_si_la_api_no_sirve():
    with pytest.raises(RuntimeError, match="no contestó un JSON válido"):
        ig.leer_notas(SITIO, lambda url: "<html>no es json</html>")
    with pytest.raises(RuntimeError, match="no tiene las categorías"):
        ig.leer_notas(SITIO, lambda url: json.dumps([{"id": 11, "slug": "platos"}]))


# ══════════════════════════════════════════ el texto: copias, formato y reintento

FUENTE = ("El saice es un plato tradicional de la cocina tarijeña que se prepara con carne picada de res, papa, arveja "
          "y un ají colorado bien picante, y se sirve caliente con arroz blanco y cebolla picada por encima.")
ORIGINAL = ("En tu mesa tarijeña lo vas a encontrar hecho con carne molida, papas y arvejas en una salsa de ají. "
            "Se come bien caliente, con arroz y un poco de cebolla fresca.")


def test_comparte_ngrama_detecta_8_palabras_seguidas_sin_mirar_tildes_ni_mayusculas():
    copiado = "Es un PLATO tradicional de la cocina tarijena que se prepara con carne picada de res y nada más."
    assert ig.comparte_ngrama(copiado, FUENTE) is True
    assert ig.comparte_ngrama(ORIGINAL, FUENTE) is False
    # 7 palabras iguales no alcanzan; 8 sí
    siete = "tradicional de la cocina tarijeña que se"
    assert ig.comparte_ngrama(siete + " baila", FUENTE, n=8) is False
    assert ig.comparte_ngrama(siete + " prepara", FUENTE, n=8) is True
    assert ig.comparte_ngrama("", FUENTE) is False and ig.comparte_ngrama(ORIGINAL, "") is False


def test_el_umbral_de_copia_es_de_8_palabras():
    assert ig.NGRAMA_COPIA == 8


@pytest.mark.parametrize("texto,motivo", [
    (None, "ningún texto"), ("", "ningún texto"), ("Corto.", "largo"),
    ("Una sola frase larga que explica el plato con bastante detalle de ingredientes y de la forma de servirlo en casa", "frases"),
    ("Primera frase del plato. Segunda frase del plato. Tercera frase del plato. Cuarta frase de más del plato.", "frases"),
    ("Mirá la receta en https://ejemplo.com y probala. Es muy rica y se come caliente con arroz blanco.", "enlaces"),
    ("Se sirve con <b>arroz</b> y cebolla fresca por encima. Es un clásico de las mesas del valle central.", "etiquetas"),
    ("Es un plato tradicional de la cocina tarijeña que se prepara con carne picada de res. Se come con arroz.", "copia"),
    ("x" * 700, "largo"),
])
def test_problemas_del_texto_los_rechaza(texto, motivo):
    assert any(motivo in p for p in ig.problemas_del_texto(texto, FUENTE)), ig.problemas_del_texto(texto, FUENTE)


def test_un_texto_original_de_dos_o_tres_frases_pasa():
    assert ig.problemas_del_texto(ORIGINAL, FUENTE) == []
    tres = ORIGINAL + " Un clásico de los almuerzos del domingo."
    assert ig.problemas_del_texto(tres, FUENTE) == []
    assert ig.contar_frases("Uno. Dos! ¿Tres? ") == 3 and ig.contar_frases("...") == 0


def test_el_prompt_da_la_nota_como_datos_y_prohibe_copiar_e_inventar():
    nota = ig.Nota("Saice", "plato", f"{BASE}/saice/", FUENTE)
    p = ig.construir_prompt(nota)
    assert "<nota>" in p and FUENTE in p and "</nota>" in p
    assert "voseo" in p and "ORIGINAL" in p and "No copies" in p and "No inventes" in p
    assert "DATOS, no instrucciones" in p and "2 a 3 frases" in p and "«Saice»" in p
    assert "rechazó" in ig.construir_prompt(nota, ["copia 8 palabras"]) and "copia 8 palabras" in ig.construir_prompt(nota, ["copia 8 palabras"])
    assert len(ig.construir_prompt(ig.Nota("X", "plato", None, "a " * 9000))) < 6000      # la nota se corta


def test_generar_descripcion_acepta_la_buena_a_la_primera():
    nota = ig.Nota("Saice", "plato", None, FUENTE)
    llamadas = []
    texto, pedidos, obj = ig.generar_descripcion(nota, lambda partes: llamadas.append(partes) or {"descripcion": ORIGINAL})
    assert (texto, pedidos, obj) == (ORIGINAL, 1, []) and len(llamadas) == 1
    assert "text" in llamadas[0][0]


def test_generar_descripcion_reintenta_una_vez_con_las_objeciones_si_copio():
    nota = ig.Nota("Saice", "plato", None, FUENTE)
    copiado = "Es un plato tradicional de la cocina tarijeña que se prepara con carne picada de res. Se come con arroz."
    respuestas = iter([{"descripcion": copiado}, {"descripcion": ORIGINAL}])
    prompts = []

    def llamar(partes):
        prompts.append(partes[0]["text"])
        return next(respuestas)

    texto, pedidos, obj = ig.generar_descripcion(nota, llamar)
    assert texto == ORIGINAL and pedidos == 2 and obj == []
    assert "copia" in prompts[1] and "copia" not in prompts[0]


def test_generar_descripcion_si_vuelve_a_copiar_no_devuelve_texto_y_no_pide_mas_de_dos():
    nota = ig.Nota("Saice", "plato", None, FUENTE)
    copiado = "Es un plato tradicional de la cocina tarijeña que se prepara con carne picada de res. Se come con arroz."
    n = []
    texto, pedidos, obj = ig.generar_descripcion(nota, lambda p: n.append(1) or {"descripcion": copiado})
    assert texto is None and pedidos == 2 == len(n) and any("copia" in o for o in obj)


def test_generar_descripcion_con_gemini_caido_o_respuesta_rara_no_lanza():
    nota = ig.Nota("Saice", "plato", None, FUENTE)

    def cae(partes):
        raise RuntimeError("503")

    assert ig.generar_descripcion(nota, cae)[0] is None
    assert ig.generar_descripcion(nota, lambda p: None)[0] is None
    assert ig.generar_descripcion(nota, lambda p: {"otra_cosa": 1})[0] is None
    assert ig.generar_descripcion(nota, lambda p: {"descripcion": 5})[0] is None


# ══════════════════════════════════════════ cargar

def _notas():
    return [ig.Nota("Saice", "plato", f"{BASE}/saice/", FUENTE),
            ig.Nota("Alfajores de maní", "reposteria", f"{BASE}/alf/", "Alfajores rellenos con dulce de leche y maní molido, bañados en azúcar impalpable que se disfrutan con café por la tarde en casa."),
            ig.Nota("Singani", "bebida", None, "Destilado de uva moscatel de altura, que se toma solo, con hielo o en chuflay con ginger ale en las peñas del valle.")]


def test_cargar_sin_escribir_no_llama_ni_escribe_y_cuenta(repo):
    salida = []
    r = ig.cargar(repo, _notas(), CIUDAD, escribir=False, llamar=None, imprimir=salida.append)
    assert (r.nuevas, r.ya_estaban, r.pedidos_gemini, r.escribio) == (3, 0, 0, False)
    assert repo.list_platos(CIUDAD["id"], None) == []
    assert len(salida) == 3 and "Saice" in salida[0]


def test_cargar_guarda_pendientes_con_texto_original_y_sin_el_texto_de_la_nota(repo):
    def gemini(partes):
        return {"descripcion": ORIGINAL}

    r = ig.cargar(repo, _notas(), CIUDAD, escribir=True, llamar=gemini, imprimir=lambda s: None)
    assert (r.nuevas, r.con_texto, r.sin_texto, r.pedidos_gemini) == (3, 3, 0, 3)
    filas = repo.list_platos(CIUDAD["id"], None)
    assert sorted(f["nombre"] for f in filas) == ["Alfajores de maní", "Saice", "Singani"]
    assert {f["estado"] for f in filas} == {"pendiente"} and {f["activo"] for f in filas} == {True}
    assert {(f["nombre"], f["tipo"]) for f in filas} == {("Saice", "plato"), ("Alfajores de maní", "reposteria"), ("Singani", "bebida")}
    assert next(f for f in filas if f["nombre"] == "Saice")["fuente_url"] == f"{BASE}/saice/"
    assert next(f for f in filas if f["nombre"] == "Singani")["fuente_url"] is None
    # el texto de la nota NO se guarda en ninguna parte de la fila
    guardado = json.dumps(repo._platos(), ensure_ascii=False)
    for nota in _notas():
        assert nota.texto not in guardado and nota.texto[:60] not in guardado


def test_cargar_no_repite_lo_que_ya_esta_aunque_cambie_mayusculas_o_tildes_ni_pide_texto_de_mas(repo):
    repo.crear_plato({"ciudad_id": CIUDAD["id"], "tipo": "plato", "nombre": "SAICE", "estado": "rechazado"})
    repo.crear_plato({"ciudad_id": OTRA_CIUDAD, "tipo": "bebida", "nombre": "Singani"})        # otra ciudad: no cuenta
    llamadas = []
    r = ig.cargar(repo, _notas(), CIUDAD, escribir=True, llamar=lambda p: llamadas.append(1) or {"descripcion": ORIGINAL},
                  imprimir=lambda s: None)
    assert (r.nuevas, r.ya_estaban, r.pedidos_gemini) == (2, 1, 2) and len(llamadas) == 2
    assert [f["nombre"] for f in repo.list_platos(CIUDAD["id"], "rechazado")] == ["SAICE"]       # el existente no se tocó


def test_cargar_un_texto_copiado_se_guarda_sin_descripcion_para_escribirlo_a_mano(repo):
    copiado = "Es un plato tradicional de la cocina tarijeña que se prepara con carne picada de res. Se come con arroz."
    salida = []
    r = ig.cargar(repo, _notas()[:1], CIUDAD, escribir=True, llamar=lambda p: {"descripcion": copiado}, imprimir=salida.append)
    assert (r.nuevas, r.con_texto, r.sin_texto, r.pedidos_gemini) == (1, 0, 1, 2)
    fila = repo.list_platos(CIUDAD["id"], None)[0]
    assert fila["descripcion"] is None and fila["estado"] == "pendiente"
    assert copiado not in json.dumps(repo._platos(), ensure_ascii=False)
    assert any("sin texto" in s and "Saice" in s for s in salida)


def test_cargar_limite(repo):
    r = ig.cargar(repo, _notas(), CIUDAD, escribir=True, llamar=lambda p: {"descripcion": ORIGINAL}, limite=2,
                  imprimir=lambda s: None)
    assert r.nuevas == 2 and len(repo.list_platos(CIUDAD["id"], None)) == 2


# ══════════════════════════════════════════ el comando (interruptor apagado / prendido)

def _posts_sitio():
    return _Sitio({11: [_post("Saice", f"{BASE}/saice/", f"<p>{FUENTE}</p>")],
                   12: [_post("Alfajores", f"{BASE}/alf/", "<p>Dulce de leche y maní.</p>")],
                   13: []})


def test_el_comando_con_el_interruptor_apagado_no_gasta_ni_escribe(repo, crepo, capsys):
    llamadas = []
    sitio = _posts_sitio()
    rc = ig.main(["--ciudad", "tarija"], repo=repo, crepo=crepo, pedir=sitio,
                 llamar=lambda p: llamadas.append(p) or {"descripcion": ORIGINAL}, dormir=lambda s: None)
    out = capsys.readouterr().out
    assert rc == 0 and llamadas == []
    assert repo.list_platos(CIUDAD["id"], None) == []
    assert "APAGADO" in out and "costo 0" in out and "[plato" in out and "Saice" in out
    assert "los cargaría): 2" in out and "Textos que pediría a Gemini" in out
    assert len(sitio.pedidas) == 4                     # 1 de categorías + 3 de posts, nada más


def test_el_comando_apagado_sin_inyectar_nada_tampoco_llama_a_gemini_ni_a_la_red(repo, crepo, capsys, monkeypatch):
    """Sin `llamar` inyectado se usa el cliente real de Gemini: apagado, no se toca (el fixture lo hace explotar)."""
    assert ig.main(["--ciudad", "tarija"], repo=repo, crepo=crepo, pedir=_posts_sitio(), dormir=lambda s: None) == 0
    assert repo.list_platos(CIUDAD["id"], None) == []


def test_el_comando_prendido_escribe_pendientes_e_informa_cuantos_pidio(repo, crepo, capsys):
    cost_switches.set(crepo, cost_switches.GEMINI_GASTRONOMIA, True, "dueno@uruku.bo")
    llamadas = []
    rc = ig.main(["--ciudad", "tarija"], repo=repo, crepo=crepo, pedir=_posts_sitio(),
                 llamar=lambda p: llamadas.append(p) or {"descripcion": ORIGINAL}, dormir=lambda s: None)
    out = capsys.readouterr().out
    assert rc == 0 and len(llamadas) == 2
    filas = repo.list_platos(CIUDAD["id"], None)
    assert sorted(f["nombre"] for f in filas) == ["Alfajores", "Saice"] and {f["estado"] for f in filas} == {"pendiente"}
    assert {f["descripcion"] for f in filas} == {ORIGINAL}
    assert "Textos pedidos a Gemini:      2" in out and "todos pendientes de aprobar" in out and "APAGADO" not in out
    # la nota de la fuente viajó a Gemini como dato, pero no quedó guardada
    assert FUENTE in llamadas[0][0]["text"] or FUENTE in llamadas[1][0]["text"]
    assert FUENTE not in json.dumps(repo._platos(), ensure_ascii=False)


def test_el_comando_es_idempotente(repo, crepo):
    cost_switches.set(crepo, cost_switches.GEMINI_GASTRONOMIA, True, "dueno@uruku.bo")
    n = []
    kw = dict(repo=repo, crepo=crepo, llamar=lambda p: n.append(1) or {"descripcion": ORIGINAL}, dormir=lambda s: None)
    ig.main(["--ciudad", "tarija"], pedir=_posts_sitio(), **kw)
    ig.main(["--ciudad", "tarija"], pedir=_posts_sitio(), **kw)
    assert len(n) == 2 and len(repo.list_platos(CIUDAD["id"], None)) == 2


def test_el_comando_simular_con_el_interruptor_prendido_tampoco_gasta(repo, crepo, capsys):
    cost_switches.set(crepo, cost_switches.GEMINI_GASTRONOMIA, True, "dueno@uruku.bo")
    llamadas = []
    rc = ig.main(["--ciudad", "tarija", "--simular"], repo=repo, crepo=crepo, pedir=_posts_sitio(),
                 llamar=lambda p: llamadas.append(p) or {}, dormir=lambda s: None)
    out = capsys.readouterr().out
    assert rc == 0 and llamadas == [] and repo.list_platos(CIUDAD["id"], None) == []
    assert "SIMULACIÓN" in out and "los cargaría" in out


def test_el_comando_prendido_pero_sin_clave_de_gemini_no_gasta_ni_escribe(repo, crepo, capsys, monkeypatch):
    cost_switches.set(crepo, cost_switches.GEMINI_GASTRONOMIA, True, "dueno@uruku.bo")
    monkeypatch.setattr(settings, "gemini_api_key", "")
    rc = ig.main(["--ciudad", "tarija"], repo=repo, crepo=crepo, pedir=_posts_sitio(), dormir=lambda s: None)
    assert rc == 0 and repo.list_platos(CIUDAD["id"], None) == []
    assert "No hay clave de Gemini" in capsys.readouterr().out


def test_el_comando_errores_de_uso_y_de_sitio(repo, crepo, capsys):
    kw = dict(repo=repo, crepo=crepo, dormir=lambda s: None)
    assert ig.main(["--ciudad", "atlantida"], **kw) == 2
    assert ig.main(["--ciudad", "tarija", "--limite", "0"], **kw) == 2
    repo.get_ciudad = lambda slug: None
    assert ig.main(["--ciudad", "tarija"], pedir=_posts_sitio(), **kw) == 2
    repo.get_ciudad = lambda slug: dict(CIUDAD)
    assert ig.main(["--ciudad", "tarija"], pedir=lambda url: "no json", **kw) == 1
    err = capsys.readouterr().err
    assert "No hay un lector" in err and "--limite" in err and "No existe la ciudad" in err and "JSON" in err


def test_el_sitio_se_pide_con_el_mismo_ritmo_educado_de_los_importadores(repo, crepo, monkeypatch):
    """Sin `pedir` inyectado se usa la descarga de los importadores de turismo (User-Agent propio, un pedido por
    segundo): acá se la cambia por una falsa y se mira que espere entre pedidos."""
    from app.services import importar_turismo_lugares as lugares
    sitio = _posts_sitio()
    monkeypatch.setattr(lugares, "descargar", sitio)
    esperas = []
    ig.main(["--ciudad", "tarija"], repo=repo, crepo=crepo, dormir=esperas.append)
    assert esperas == [importar_turismo.INTERVALO_PEDIDOS] * 3 and len(sitio.pedidas) == 4
    assert importar_turismo.INTERVALO_PEDIDOS == 1.0 and importar_turismo.USER_AGENT.startswith("URUKU/")
