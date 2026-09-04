"""La cola de revisión humana de rubros y lo que pasa al dar el veredicto.

Lo que se cuida acá no es que la pantalla dibuje: es que una corrección hecha a
mano no se pierda. Se hicieron más de 200 antes de que existiera cualquier
marca, y no se distinguían de las automáticas — cualquier corrida masiva las
pisaba sin dar error.
"""


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def test_la_cola_trae_los_que_el_diccionario_contradice(client, repo, admin_token):
    """Un comercio cuyo texto grita "calzado" y está puesto en ropa."""
    c = repo.seed_comercio(slug="zapa", nombre="Zapatería El Paso",
                           prod_det_ia="zapatilla, sandalia", activo=True)
    repo.set_comercio_rubros(c["id"], [repo.rubros["ropa"]])

    r = client.get("/admin/rubros/revision", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    codigos = [i["comercio_id"] for i in r.json()["items"]]
    assert c["id"] in codigos
    fila = next(i for i in r.json()["items"] if i["comercio_id"] == c["id"])
    assert fila["principal"] == "ropa"
    assert "calzado" in fila["sugeridos"]


def test_el_que_ya_cierra_no_entra_en_la_cola(client, repo, admin_token):
    c = repo.seed_comercio(slug="ok", nombre="Calzados Ana",
                           prod_det_ia="zapatilla", activo=True)
    repo.set_comercio_rubros(c["id"], [repo.rubros["calzado"]])

    r = client.get("/admin/rubros/revision", headers=_h(admin_token))
    assert c["id"] not in [i["comercio_id"] for i in r.json()["items"]]


def test_decir_que_esta_bien_lo_saca_de_la_cola_sin_cambiar_el_rubro(client, repo, admin_token):
    """El veredicto "ok" no toca la clasificación, pero sí la marca.

    Es la mitad que se olvida: si sólo se anotaran las correcciones, los que una
    persona ya miró y dio por buenos volverían a aparecer para siempre, y una
    cola que no baja se deja de mirar."""
    c = repo.seed_comercio(slug="mixto", nombre="Tienda Mixta",
                           prod_det_ia="zapatilla y remera", activo=True)
    repo.set_comercio_rubros(c["id"], [repo.rubros["ropa"]])

    r = client.post(f"/admin/rubros/revision/{c['id']}",
                    json={"veredicto": "ok", "rubro_antes": "ropa"}, headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert repo.get_comercio_rubros(c["id"])[0] == "ropa"
    assert repo.comercios[c["id"]]["rubro_revisado_at"]
    assert c["id"] not in [i["comercio_id"] for i in
                           client.get("/admin/rubros/revision", headers=_h(admin_token)).json()["items"]]


def test_corregir_pone_el_rubro_nuevo_primero_y_conserva_los_otros(client, repo, admin_token):
    """El corregido pasa a principal SIN borrar los demás.

    Mandar sólo el nuevo dejaría al comercio con un rubro solo: el buscador
    dejaría de encontrarlo por los que ya tenía, y eso no se ve desde el panel.
    """
    c = repo.seed_comercio(slug="zapa2", nombre="El Paso",
                           prod_det_ia="zapatilla", activo=True)
    repo.set_comercio_rubros(c["id"], [repo.rubros["ropa"]])

    r = client.post(f"/admin/rubros/revision/{c['id']}",
                    json={"veredicto": "corregido", "rubro_slug": "calzado",
                          "rubro_antes": "ropa"}, headers=_h(admin_token))
    assert r.status_code == 200, r.text
    quedaron = repo.get_comercio_rubros(c["id"])
    assert quedaron[0] == "calzado"
    assert "ropa" in quedaron


def test_la_correccion_queda_anotada_con_el_texto_que_se_juzgo(client, repo, admin_token):
    """Sin el texto congelado, dentro de un mes no se sabe qué leyó el
    clasificador cuando falló: la descripción del comercio se edita."""
    c = repo.seed_comercio(slug="zapa3", nombre="Zapas Sur",
                           prod_det_ia="zapatilla", activo=True)
    repo.set_comercio_rubros(c["id"], [repo.rubros["ropa"]])

    client.post(f"/admin/rubros/revision/{c['id']}",
                json={"veredicto": "corregido", "rubro_slug": "calzado",
                      "rubro_antes": "ropa"}, headers=_h(admin_token))

    anotado = repo.correcciones_rubro[-1]
    assert anotado["veredicto"] == "corregido"
    assert anotado["rubro_antes"] == "ropa"
    assert anotado["rubro_nuevo"] == "calzado"
    assert "zapatilla" in anotado["texto"]


def test_corregir_a_un_rubro_que_no_existe_se_rechaza(client, repo, admin_token):
    c = repo.seed_comercio(slug="x", nombre="X", activo=True)
    r = client.post(f"/admin/rubros/revision/{c['id']}",
                    json={"veredicto": "corregido", "rubro_slug": "no-existe"},
                    headers=_h(admin_token))
    assert r.status_code == 400


def test_corregir_sin_decir_a_que_rubro_se_rechaza(client, repo, admin_token):
    c = repo.seed_comercio(slug="y", nombre="Y", activo=True)
    r = client.post(f"/admin/rubros/revision/{c['id']}",
                    json={"veredicto": "corregido"}, headers=_h(admin_token))
    assert r.status_code == 400


def test_la_palabra_de_la_correccion_entra_al_diccionario(client, repo, admin_token):
    """Es lo único que hace que una corrección sirva para el próximo comercio:
    el clasificador es un diccionario, y "aprender" es escribir en él."""
    c = repo.seed_comercio(slug="zapa4", nombre="Botines Bermejo",
                           prod_det_ia="zapatilla", activo=True)
    repo.set_comercio_rubros(c["id"], [repo.rubros["ropa"]])

    r = client.post(f"/admin/rubros/revision/{c['id']}",
                    json={"veredicto": "corregido", "rubro_slug": "calzado",
                          "rubro_antes": "ropa", "palabras": "botin, botines"},
                    headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert repo.correcciones_rubro[-1]["palabras"] == "botin, botines"


def test_el_resumen_cuenta_lo_que_falta(client, repo, admin_token):
    c = repo.seed_comercio(slug="z", nombre="Z", prod_det_ia="zapatilla", activo=True)
    repo.set_comercio_rubros(c["id"], [repo.rubros["ropa"]])

    resumen = client.get("/admin/rubros/revision", headers=_h(admin_token)).json()["resumen"]
    assert resumen["dudosos"] >= 1

    client.post(f"/admin/rubros/revision/{c['id']}",
                json={"veredicto": "ok", "rubro_antes": "ropa"}, headers=_h(admin_token))
    despues = client.get("/admin/rubros/revision", headers=_h(admin_token)).json()["resumen"]
    assert despues["revisados"] >= 1
    assert despues["dudosos"] == resumen["dudosos"] - 1


def test_las_sugerencias_separan_diccionario_de_ia(client, repo, admin_token, monkeypatch):
    """Van por separado a propósito: el diccionario es lo que clasifica de
    verdad, la IA es una segunda opinión. Mezcladas, la de la IA taparía que el
    diccionario no sabe — y ese hueco es el que dice qué palabra agregar."""
    from app.services import clasificador

    monkeypatch.setattr(clasificador, "sugerir_rubros_explicado",
                        lambda nombre, texto, rubros: {"rubros": ["ropa"],
                                                       "motivo": "el nombre dice boutique"})
    c = repo.seed_comercio(slug="mix", nombre="Boutique Sur",
                           prod_det_ia="zapatilla", activo=True)

    r = client.post(f"/admin/comercio/{c['id']}/rubro/sugerencias", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    d = r.json()
    assert [x["slug"] for x in d["diccionario"]] == ["calzado"]
    assert [x["slug"] for x in d["ia"]["rubros"]] == ["ropa"]
    assert "zapatilla" in d["texto"]


def test_sin_ia_configurada_las_sugerencias_siguen_saliendo(client, repo, admin_token, monkeypatch):
    """El diccionario es la fuente. Si Gemini no está o falla, la pantalla tiene
    que servir igual: sin esto, una clave vencida deja la revisión sin usar."""
    from app.services import clasificador

    monkeypatch.setattr(clasificador, "sugerir_rubros_explicado",
                        lambda nombre, texto, rubros: None)
    c = repo.seed_comercio(slug="solo-dicc", nombre="Gomería Norte",
                           prod_det_ia="neumatico", activo=True)

    r = client.post(f"/admin/comercio/{c['id']}/rubro/sugerencias", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["ia"] is None
    assert [x["slug"] for x in r.json()["diccionario"]] == ["neumaticos"]


def test_pedir_sugerencias_de_un_comercio_que_no_existe(client, admin_token):
    r = client.post("/admin/comercio/no-existe/rubro/sugerencias", headers=_h(admin_token))
    assert r.status_code == 404


def test_varios_rubros_en_orden_el_primero_manda(client, repo, admin_token):
    """Un comercio casi nunca es una sola cosa.

    El puesto de coca machucada también vende bebidas y golosinas: dejarlo en un
    rubro solo lo saca de las otras dos búsquedas. Se guarda la lista completa,
    y el orden es la respuesta — el primero es el principal."""
    c = repo.seed_comercio(slug="coca", nombre="Coca Machucada Rey", activo=True)
    repo.set_comercio_rubros(c["id"], [repo.rubros["ropa"]])

    r = client.post(f"/admin/rubros/revision/{c['id']}",
                    json={"veredicto": "corregido",
                          "rubro_slugs": ["calzado", "ropa", "ferreteria"],
                          "rubro_antes": "ropa"}, headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert repo.get_comercio_rubros(c["id"]) == ["calzado", "ropa", "ferreteria"]


def test_la_lista_explicita_puede_SACAR_un_rubro_mal_puesto(client, repo, admin_token):
    """Es la mitad de para qué se abre esta pantalla. Si a la lista marcada se
    le sumaran los que ya tenía, un rubro mal puesto no habría forma de quitarlo
    desde acá."""
    c = repo.seed_comercio(slug="saca", nombre="Zapas", activo=True)
    repo.set_comercio_rubros(c["id"], [repo.rubros["ropa"], repo.rubros["ferreteria"]])

    client.post(f"/admin/rubros/revision/{c['id']}",
                json={"veredicto": "corregido", "rubro_slugs": ["calzado"]},
                headers=_h(admin_token))
    assert repo.get_comercio_rubros(c["id"]) == ["calzado"]


def test_el_atajo_de_un_toque_sigue_sumando_sin_borrar(client, repo, admin_token):
    """La cola de revisión manda un solo rubro y ahí SÍ se conserva el resto:
    es un toque rápido para poner el principal, no una edición de la lista."""
    c = repo.seed_comercio(slug="suma", nombre="Mixto", activo=True)
    repo.set_comercio_rubros(c["id"], [repo.rubros["ropa"]])

    client.post(f"/admin/rubros/revision/{c['id']}",
                json={"veredicto": "corregido", "rubro_slug": "calzado"},
                headers=_h(admin_token))
    assert repo.get_comercio_rubros(c["id"]) == ["calzado", "ropa"]


# ═════════════════════════════════ recálculo del principal, sólo lo inequívoco
def test_el_recalculo_toca_solo_los_de_UNA_sugerencia(client, repo, admin_token):
    """Con dos o más, "la primera" no significa nada.

    `rubros_sugeridos` devuelve un array_agg(distinct), o sea alfabético: entre
    calzado y ropa gana calzado por la C, no por describir mejor al comercio.
    Elegir ahí es criterio humano."""
    claro = repo.seed_comercio(slug="claro", nombre="Zapas", prod_det_ia="zapatilla", activo=True)
    repo.set_comercio_rubros(claro["id"], [repo.rubros["ferreteria"]])
    ambiguo = repo.seed_comercio(slug="ambiguo", nombre="Mixto",
                                 prod_det_ia="zapatilla y remera", activo=True)
    repo.set_comercio_rubros(ambiguo["id"], [repo.rubros["ferreteria"]])

    r = client.post("/admin/rubros/recalcular-principal", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    d = r.json()
    assert [x["comercio_id"] for x in d["detalle"]] == [claro["id"]]
    assert d["ambiguos"] >= 1


def test_sin_aplicar_no_escribe_nada(client, repo, admin_token):
    """La vista previa es previa. Si escribiera, no habría dónde decir que no."""
    c = repo.seed_comercio(slug="prev", nombre="Zapas", prod_det_ia="zapatilla", activo=True)
    repo.set_comercio_rubros(c["id"], [repo.rubros["ferreteria"]])

    client.post("/admin/rubros/recalcular-principal", headers=_h(admin_token))
    assert repo.get_comercio_rubros(c["id"]) == ["ferreteria"]


def test_aplicar_pone_el_principal_y_conserva_los_otros(client, repo, admin_token):
    c = repo.seed_comercio(slug="apl", nombre="Zapas", prod_det_ia="zapatilla", activo=True)
    repo.set_comercio_rubros(c["id"], [repo.rubros["ferreteria"]])

    r = client.post("/admin/rubros/recalcular-principal?aplicar=true", headers=_h(admin_token))
    assert r.json()["cambiados"] == 1
    assert repo.get_comercio_rubros(c["id"]) == ["calzado", "ferreteria"]


def test_el_recalculo_NO_marca_el_comercio_como_revisado_por_una_persona(client, repo, admin_token):
    """La marca separa lo que miró alguien de lo que hizo una corrida. Si el
    recálculo la pusiera, dejaría de servir para lo único que sirve.

    Igual sale de la cola: la cola es "el principal no está entre las
    sugerencias", y después de esto sí está."""
    c = repo.seed_comercio(slug="nomarca", nombre="Zapas", prod_det_ia="zapatilla", activo=True)
    repo.set_comercio_rubros(c["id"], [repo.rubros["ferreteria"]])

    client.post("/admin/rubros/recalcular-principal?aplicar=true", headers=_h(admin_token))
    assert not repo.comercios[c["id"]].get("rubro_revisado_at")
    en_cola = client.get("/admin/rubros/revision", headers=_h(admin_token)).json()["items"]
    assert c["id"] not in [i["comercio_id"] for i in en_cola]


def test_queda_dicho_que_lo_cambio_una_corrida_y_no_una_persona(client, repo, admin_token):
    c = repo.seed_comercio(slug="audit", nombre="Zapas", prod_det_ia="zapatilla", activo=True)
    repo.set_comercio_rubros(c["id"], [repo.rubros["ferreteria"]])

    client.post("/admin/rubros/recalcular-principal?aplicar=true", headers=_h(admin_token))
    assert "recalculo-automatico" in repo.correcciones_rubro[-1]["revisado_por"]
