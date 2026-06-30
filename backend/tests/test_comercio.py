"""Registro self-service, login y publicación por chatbot."""
from tests.conftest import comercio_token


# ---------------- Registro ----------------
def _registro(**kw):
    base = {"nombre": "Mi Tienda", "email": "nuevo@x.com", "password": "secreto1", "whatsapp": "59170001111", "plan": "gratis"}
    base.update(kw)
    return base


def test_registro_crea_comercio_y_loguea(client, repo):
    r = client.post("/auth/comercio/registro", json=_registro())
    assert r.status_code == 200
    data = r.json()
    assert data["access_token"]
    assert data["comercio"]["slug"] == "mi-tienda"
    assert data["comercio"]["confiable"] is False  # nace NO confiable
    assert len(repo.comercios) == 1
    assert "nuevo@x.com" in repo.usuarios


def test_registro_slug_unico_ante_colision(client, repo):
    repo.seed_comercio(slug="mi-tienda", nombre="otra")
    r = client.post("/auth/comercio/registro", json=_registro())
    assert r.json()["comercio"]["slug"] == "mi-tienda-2"


def test_registro_email_duplicado_409(client, repo):
    client.post("/auth/comercio/registro", json=_registro())
    r = client.post("/auth/comercio/registro", json=_registro(nombre="Otra"))
    assert r.status_code == 409


def test_registro_password_corta_400(client):
    r = client.post("/auth/comercio/registro", json=_registro(password="123"))
    assert r.status_code == 400


def test_registro_plan_pago_marca_pendiente(client):
    r = client.post("/auth/comercio/registro", json=_registro(email="pro@x.com", plan="premium"))
    assert r.json()["pago_pendiente"] is True


def test_registro_guarda_modalidad_y_rubro(client, repo):
    r = client.post("/auth/comercio/registro", json=_registro(
        email="resto@x.com", nombre="Resto Bermejo", modalidad="minorista", rubro_slug="gastronomia"))
    assert r.status_code == 200
    com = next(c for c in repo.comercios.values() if c.get("slug") == "resto-bermejo")
    assert com["modalidad"] == "minorista"
    assert com["rubro_id"] == "rub-2"   # gastronomia


def test_registro_modalidad_invalida_400(client):
    r = client.post("/auth/comercio/registro", json=_registro(email="z@x.com", modalidad="revendedor"))
    assert r.status_code == 400


# ---------------- Login + publicar ----------------
def test_login_y_publicar_no_confiable_va_a_moderacion(client, repo):
    reg = client.post("/auth/comercio/registro", json=_registro(email="m@x.com")).json()
    token = reg["access_token"]
    r = client.post(
        "/comercio/publicar",
        headers={"Authorization": f"Bearer {token}"},
        json={"tipo": "oferta", "titulo": "Remera", "precio": 80, "moneda": "BOB"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["publicado_directo"] is False
    assert body["estado"] == "pendiente"


def test_publicar_confiable_publica_directo(client, repo):
    repo.seed_comercio(id="com-c", slug="conf", nombre="Conf", whatsapp="591700", confiable=True)
    token = comercio_token(comercio_id="com-c", email="c@x.com")
    r = client.post(
        "/comercio/publicar",
        headers={"Authorization": f"Bearer {token}"},
        json={"tipo": "novedad", "titulo": "Llegó stock"},
    )
    assert r.json()["estado"] == "aprobado"
    assert repo.publicaciones[0]["approved_at"] is not None


def test_publicar_tipo_invalido_400(client, repo):
    repo.seed_comercio(id="com-c", slug="conf", nombre="Conf", whatsapp="591700", confiable=True)
    token = comercio_token(comercio_id="com-c")
    r = client.post("/comercio/publicar", headers={"Authorization": f"Bearer {token}"}, json={"tipo": "spam"})
    assert r.status_code == 400


def test_publicar_sin_token_401(client):
    assert client.post("/comercio/publicar", json={"tipo": "oferta"}).status_code == 401


# ---------------- Panel "Mi comercio": perfil / suscripción / métricas ----------------
def _auth(cid="com-p"):
    return {"Authorization": f"Bearer {comercio_token(comercio_id=cid)}"}


def test_get_perfil_devuelve_campos(client, repo):
    repo.seed_comercio(id="com-p", slug="perf", nombre="Perfil SA", whatsapp="591700", descripcion="hola")
    r = client.get("/comercio/perfil", headers=_auth())
    assert r.status_code == 200
    data = r.json()
    assert data["nombre"] == "Perfil SA"
    assert data["descripcion"] == "hola"
    # No expone campos sensibles fuera de la whitelist de lectura
    assert "password_hash" not in data


def test_put_perfil_actualiza_solo_whitelist(client, repo):
    repo.seed_comercio(id="com-p", slug="perf", nombre="Viejo", whatsapp="591700", confiable=False)
    r = client.put("/comercio/perfil", headers=_auth(),
                   json={"nombre": "Nuevo", "instagram_url": "ig.com/x", "confiable": True})
    assert r.status_code == 200
    assert r.json()["nombre"] == "Nuevo"
    # 'confiable' NO está en la whitelist editable: no debe cambiar
    assert repo.comercios["com-p"]["confiable"] is False
    assert repo.comercios["com-p"]["instagram_url"] == "ig.com/x"


def test_put_perfil_modalidad_invalida_400(client, repo):
    repo.seed_comercio(id="com-p", slug="perf", nombre="X", whatsapp="591700")
    r = client.put("/comercio/perfil", headers=_auth(), json={"modalidad": "revendedor"})
    assert r.status_code == 400


def test_get_suscripcion_estado(client, repo):
    repo.seed_comercio(id="com-p", slug="perf", nombre="X", whatsapp="591700",
                       plan="premium", paga_hasta="2999-01-01", suspendido=False)
    r = client.get("/comercio/suscripcion", headers=_auth())
    assert r.status_code == 200
    data = r.json()
    assert data["estado"] == "activo"
    assert data["plan"] == "premium"
    assert data["total_cargos"] == 0


def test_get_suscripcion_gratis(client, repo):
    repo.seed_comercio(id="com-p", slug="perf", nombre="X", whatsapp="591700", plan="gratis")
    assert client.get("/comercio/suscripcion", headers=_auth()).json()["estado"] == "gratis"


def test_get_metricas_cuenta_leads_y_publicaciones(client, repo):
    repo.seed_comercio(id="com-p", slug="perf", nombre="X", whatsapp="591700")
    repo.insert_lead({"comercio_id": "com-p", "tipo": "whatsapp"})
    repo.insert_lead({"comercio_id": "com-p", "tipo": "whatsapp"})
    repo.insert_lead({"comercio_id": "com-p", "tipo": "telefono"})
    repo.insert_publicacion_directa({"comercio_id": "com-p", "estado": "aprobado", "tipo": "oferta"})
    r = client.get("/comercio/metricas", headers=_auth())
    assert r.status_code == 200
    data = r.json()
    assert data["contactos_30d"] == 3
    assert data["contactos_por_tipo"]["whatsapp"] == 2
    assert data["publicaciones_total"] == 1


def test_perfil_sin_token_401(client):
    assert client.get("/comercio/perfil").status_code == 401


# ---------------- Productos (marketplace, TiendaClient en modo stub) ----------------
def test_producto_draft_clasifica_con_fallback(client, repo):
    # Sin GEMINI_API_KEY (tests) → cae al fallback "otros".
    repo.seed_comercio(id="com-p", slug="perf", nombre="X", whatsapp="591700")
    r = client.post("/comercio/productos/draft", headers=_auth(),
                    json={"titulo": "Campera de jean", "descripcion": "talles 38-46", "precio": 25000})
    assert r.status_code == 200
    data = r.json()
    assert data["categoria_slug"] == "otros"
    assert data["titulo"] == "Campera de jean"
    assert len(data["categorias"]) > 0           # lista para elegir en el preview


def test_crear_producto_publica_y_guarda_ref(client, repo):
    repo.seed_comercio(id="com-p", slug="perf", nombre="X", whatsapp="591700")
    r = client.post("/comercio/productos", headers=_auth(),
                    data={"titulo": "Remera", "precio": "120", "moneda": "ARS", "categoria_slug": "ropa"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["url"]                           # el stub devuelve una url
    assert len(repo.producto_refs) == 1
    ref = next(iter(repo.producto_refs.values()))
    assert ref["comercio_id"] == "com-p"
    assert ref["tienda_producto_id"]


def test_crear_producto_moneda_invalida_400(client, repo):
    repo.seed_comercio(id="com-p", slug="perf", nombre="X", whatsapp="591700")
    r = client.post("/comercio/productos", headers=_auth(),
                    data={"titulo": "X", "precio": "1", "moneda": "EUR", "categoria_slug": "ropa"})
    assert r.status_code == 400


def test_list_y_borrar_producto(client, repo):
    repo.seed_comercio(id="com-p", slug="perf", nombre="X", whatsapp="591700")
    client.post("/comercio/productos", headers=_auth(),
                data={"titulo": "Remera", "precio": "120", "moneda": "ARS", "categoria_slug": "ropa"})
    lst = client.get("/comercio/productos", headers=_auth()).json()
    assert lst["total"] == 1
    ref_id = lst["items"][0]["id"]
    assert client.delete(f"/comercio/productos/{ref_id}", headers=_auth()).status_code == 200
    assert client.get("/comercio/productos", headers=_auth()).json()["total"] == 0


def test_borrar_producto_de_otro_comercio_404(client, repo):
    repo.seed_comercio(id="com-p", slug="perf", nombre="X", whatsapp="591700")
    repo.seed_comercio(id="com-otro", slug="otro", nombre="Otro", whatsapp="591701")
    ref = repo.crear_producto_ref({"comercio_id": "com-otro", "tienda_producto_id": "9"})
    r = client.delete(f"/comercio/productos/{ref['id']}", headers=_auth())  # _auth = com-p
    assert r.status_code == 404


def test_productos_sin_token_401(client):
    assert client.get("/comercio/productos").status_code == 401


# ---------------- Pago QR self-service ----------------
def test_comercio_pago_queda_pendiente(client, repo):
    repo.seed_comercio(id="com-p", slug="perf", nombre="X", whatsapp="591700")
    r = client.post("/comercio/pago", headers=_auth(),
                    data={"monto": "30000", "moneda": "ARS", "metodo": "qr-bolivia"})
    assert r.status_code == 200
    assert r.json()["estado"] == "pendiente"
    assert len(repo.pagos) == 1


def test_comercio_pago_monto_invalido_400(client, repo):
    repo.seed_comercio(id="com-p", slug="perf", nombre="X", whatsapp="591700")
    r = client.post("/comercio/pago", headers=_auth(), data={"monto": "0", "metodo": "qr-bolivia"})
    assert r.status_code == 400


def test_comercio_pago_metodo_invalido_400(client, repo):
    repo.seed_comercio(id="com-p", slug="perf", nombre="X", whatsapp="591700")
    r = client.post("/comercio/pago", headers=_auth(), data={"monto": "100", "metodo": "bitcoin"})
    assert r.status_code == 400


def test_admin_confirma_pago_extiende_paga_hasta(client, repo, admin_token):
    repo.seed_comercio(id="com-p", slug="perf", nombre="X", whatsapp="591700")
    client.post("/comercio/pago", headers=_auth(), data={"monto": "30000", "metodo": "qr-bolivia"})
    auth_admin = {"Authorization": f"Bearer {admin_token}"}
    pend = client.get("/admin/pagos/pendientes", headers=auth_admin).json()
    assert pend["total"] == 1
    pago_id = pend["items"][0]["id"]
    r = client.post(f"/admin/pagos/{pago_id}/confirmar", headers=auth_admin, json={"meses": 1})
    assert r.status_code == 200
    assert repo.comercios["com-p"]["paga_hasta"]            # se extendió
    assert repo.pagos[pago_id]["estado"] == "confirmado"


def test_comercio_pago_sin_token_401(client):
    assert client.post("/comercio/pago", data={"monto": "1", "metodo": "qr-bolivia"}).status_code == 401


# ---------------- Destacado cobrable ----------------
def _crear_producto(client):
    return client.post("/comercio/productos", headers=_auth(),
                       data={"titulo": "Remera", "precio": "120", "moneda": "ARS",
                             "categoria_slug": "ropa"}).json()["producto_ref"]["id"]


def test_destacar_producto_crea_publicacion_con_costo(client, repo):
    repo.seed_comercio(id="com-p", slug="perf", nombre="X", whatsapp="591700")
    ref_id = _crear_producto(client)
    r = client.post(f"/comercio/productos/{ref_id}/destacar", headers=_auth())
    assert r.status_code == 200
    assert r.json()["costo"] == 1000.0
    pub = next(p for p in repo.publicaciones if p.get("costo"))
    assert pub["costo"] == 1000.0
    assert repo.producto_refs[ref_id]["destacado_pub_id"] == pub["id"]


def test_destacar_dos_veces_409(client, repo):
    repo.seed_comercio(id="com-p", slug="perf", nombre="X", whatsapp="591700")
    ref_id = _crear_producto(client)
    client.post(f"/comercio/productos/{ref_id}/destacar", headers=_auth())
    r = client.post(f"/comercio/productos/{ref_id}/destacar", headers=_auth())
    assert r.status_code == 409


def test_destacar_producto_ajeno_404(client, repo):
    repo.seed_comercio(id="com-p", slug="perf", nombre="X", whatsapp="591700")
    repo.seed_comercio(id="com-o", slug="o", nombre="O", whatsapp="591701")
    ref = repo.crear_producto_ref({"comercio_id": "com-o", "tienda_producto_id": "9"})
    r = client.post(f"/comercio/productos/{ref['id']}/destacar", headers=_auth())
    assert r.status_code == 404


def test_destacado_se_acumula_y_el_pago_lo_salda(client, repo, admin_token):
    repo.seed_comercio(id="com-p", slug="perf", nombre="X", whatsapp="591700")
    ref_id = _crear_producto(client)
    client.post(f"/comercio/productos/{ref_id}/destacar", headers=_auth())
    assert client.get("/comercio/suscripcion", headers=_auth()).json()["total_cargos"] == 1000.0

    client.post("/comercio/pago", headers=_auth(), data={"monto": "31000", "metodo": "qr-bolivia"})
    auth_admin = {"Authorization": f"Bearer {admin_token}"}
    pago_id = client.get("/admin/pagos/pendientes", headers=auth_admin).json()["items"][0]["id"]
    client.post(f"/admin/pagos/{pago_id}/confirmar", headers=auth_admin, json={"meses": 1})

    assert client.get("/comercio/suscripcion", headers=_auth()).json()["total_cargos"] == 0


# ---------------- Mensajería ----------------
def test_cliente_deja_mensaje_y_comercio_lo_ve(client, repo):
    repo.seed_comercio(id="com-p", slug="perf", nombre="X", whatsapp="591700")
    r = client.post("/mensaje", json={"comercio_id": "com-p", "nombre": "Ana",
                                      "cuerpo": "¿Tenés stock?", "contacto": "5491133"})
    assert r.status_code == 200
    box = client.get("/comercio/mensajes", headers=_auth()).json()
    assert box["no_leidos"] == 1
    assert box["items"][0]["autor"] == "cliente"
    assert box["items"][0]["contacto"] == "5491133"


def test_mensaje_sin_cuerpo_400(client, repo):
    repo.seed_comercio(id="com-p", slug="perf", nombre="X", whatsapp="591700")
    r = client.post("/mensaje", json={"comercio_id": "com-p", "nombre": "Ana", "cuerpo": "  "})
    assert r.status_code == 400


def test_mensaje_comercio_inexistente_404(client):
    r = client.post("/mensaje", json={"comercio_id": "nope", "nombre": "Ana", "cuerpo": "hola"})
    assert r.status_code == 404


def test_admin_envia_mensaje_al_comercio(client, repo, admin_token):
    repo.seed_comercio(id="com-p", slug="perf", nombre="X", whatsapp="591700")
    r = client.post("/admin/comercio/com-p/mensaje",
                    headers={"Authorization": f"Bearer {admin_token}"}, json={"cuerpo": "Pago confirmado"})
    assert r.status_code == 200
    box = client.get("/comercio/mensajes", headers=_auth()).json()
    assert any(m["autor"] == "admin" for m in box["items"])


def test_comercio_marca_mensaje_leido(client, repo):
    repo.seed_comercio(id="com-p", slug="perf", nombre="X", whatsapp="591700")
    client.post("/mensaje", json={"comercio_id": "com-p", "nombre": "Ana", "cuerpo": "hola"})
    mid = client.get("/comercio/mensajes", headers=_auth()).json()["items"][0]["id"]
    assert client.post(f"/comercio/mensajes/{mid}/leido", headers=_auth()).status_code == 200
    assert client.get("/comercio/mensajes", headers=_auth()).json()["no_leidos"] == 0


def test_mensajes_sin_token_401(client):
    assert client.get("/comercio/mensajes").status_code == 401


# ---------------- Editar / baja de publicaciones ----------------
def _pub(repo, cid, **kw):
    return repo.insert_publicacion_directa(
        {"comercio_id": cid, "tipo": "oferta", "titulo": "T", "estado": "aprobado", **kw}
    )


def test_editar_publicacion_confiable_actualiza_y_clampa(client, repo):
    repo.seed_comercio(id="com-c", slug="c", nombre="C", whatsapp="591", confiable=True)
    pub = _pub(repo, "com-c", precio=100)
    token = comercio_token(comercio_id="com-c")
    r = client.patch(
        f"/comercio/publicaciones/{pub['id']}",
        headers={"Authorization": f"Bearer {token}"},
        json={"precio": 80, "descuento_pct": 200, "vence_el": "2026-08-01"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["estado"] == "aprobado"
    assert data["item"]["precio"] == 80
    assert data["item"]["descuento_pct"] == 99   # clamp 1..99
    assert data["item"]["vence_el"] == "2026-08-01"


def test_editar_publicacion_no_confiable_vuelve_a_pendiente(client, repo):
    repo.seed_comercio(id="com-n", slug="n", nombre="N", whatsapp="591", confiable=False)
    pub = _pub(repo, "com-n", precio=100)
    token = comercio_token(comercio_id="com-n")
    r = client.patch(
        f"/comercio/publicaciones/{pub['id']}",
        headers={"Authorization": f"Bearer {token}"}, json={"descuento_pct": 10},
    )
    assert r.status_code == 200
    assert r.json()["estado"] == "pendiente"


def test_editar_publicacion_ajena_404(client, repo):
    repo.seed_comercio(id="com-a", slug="a", nombre="A", whatsapp="591", confiable=True)
    repo.seed_comercio(id="com-b", slug="b", nombre="B", whatsapp="591", confiable=True)
    pub = _pub(repo, "com-a", precio=100)
    token_b = comercio_token(comercio_id="com-b")
    r = client.patch(
        f"/comercio/publicaciones/{pub['id']}",
        headers={"Authorization": f"Bearer {token_b}"}, json={"precio": 1},
    )
    assert r.status_code == 404


def test_editar_sin_campos_400(client, repo):
    repo.seed_comercio(id="com-c", slug="c", nombre="C", whatsapp="591", confiable=True)
    pub = _pub(repo, "com-c")
    token = comercio_token(comercio_id="com-c")
    r = client.patch(
        f"/comercio/publicaciones/{pub['id']}",
        headers={"Authorization": f"Bearer {token}"}, json={},
    )
    assert r.status_code == 400


def test_baja_publicacion_soft_delete(client, repo):
    repo.seed_comercio(id="com-c", slug="c", nombre="C", whatsapp="591", confiable=True)
    pub = _pub(repo, "com-c")
    token = comercio_token(comercio_id="com-c")
    r = client.delete(f"/comercio/publicaciones/{pub['id']}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert repo.list_publicaciones_de_comercio("com-c") == []


def test_baja_publicacion_ajena_404(client, repo):
    repo.seed_comercio(id="com-a", slug="a", nombre="A", whatsapp="591", confiable=True)
    repo.seed_comercio(id="com-b", slug="b", nombre="B", whatsapp="591", confiable=True)
    pub = _pub(repo, "com-a")
    token_b = comercio_token(comercio_id="com-b")
    r = client.delete(f"/comercio/publicaciones/{pub['id']}", headers={"Authorization": f"Bearer {token_b}"})
    assert r.status_code == 404
