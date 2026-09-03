"""Endpoints del panel que no tenía nadie probando.

Salieron a la luz cuando /admin/reclamos y /admin/solicitudes-cambio-numero
empezaron a devolver 500 en producción: eran justamente los únicos que ningún
test tocaba. Todo lo que se ejercita acá pasa por el mismo camino que usa el
panel — misma ruta, mismo rol, misma forma de respuesta.
"""
from datetime import date, timedelta

import pytest


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _fecha(dias: int) -> str:
    return (date.today() + timedelta(days=dias)).isoformat()


# ══════════════════════════════════════════════════════ grupo de WhatsApp
def test_el_grupo_aparece_en_el_perfil_del_comercio(client, repo, admin_token):
    c = repo.seed_comercio(slug="mendo", nombre="Mendo")
    repo.vincular_grupo_comercio("120363@g.us", c["id"], "Ofertas Mendo", "codigo", "ingest")

    r = client.get(f"/admin/comercio/{c['id']}/grupos", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["grupo_jid"] == "120363@g.us"


def test_atar_un_chat_directo_como_si_fuera_grupo_se_rechaza(client, repo, admin_token):
    """Un JID de persona termina en @c.us. Si se atara uno, el comercio pasaría
    a recibir como propio todo lo que le escriba cualquiera a ese número."""
    c = repo.seed_comercio(slug="mendo", nombre="Mendo")
    r = client.post(f"/admin/comercio/{c['id']}/grupos",
                    json={"grupo_jid": "59170000007@c.us"}, headers=_h(admin_token))
    assert r.status_code == 400
    assert "@g.us" in r.json()["detail"]


def test_no_se_puede_robar_el_grupo_de_otro_comercio(client, repo, admin_token):
    a = repo.seed_comercio(slug="a", nombre="Comercial A")
    b = repo.seed_comercio(slug="b", nombre="Comercial B")
    repo.vincular_grupo_comercio("120363@g.us", a["id"], None, "codigo", "ingest")

    r = client.post(f"/admin/comercio/{b['id']}/grupos",
                    json={"grupo_jid": "120363@g.us"}, headers=_h(admin_token))
    assert r.status_code == 409
    assert "Comercial A" in r.json()["detail"]
    assert repo.wa_grupos["120363@g.us"]["comercio_id"] == a["id"]


def test_soltar_el_grupo_no_borra_lo_ya_publicado(client, repo, admin_token):
    c = repo.seed_comercio(slug="mendo", nombre="Mendo")
    repo.vincular_grupo_comercio("120363@g.us", c["id"], None, "admin", "yo")
    repo.insert_publicacion({"comercio_id": c["id"], "tipo": "oferta", "estado": "aprobado"})

    r = client.delete(f"/admin/comercio/{c['id']}/grupos/120363%40g.us", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["grupos"] == []
    assert len(repo.publicaciones) == 1      # la oferta existió: no se borra


# ══════════════════════════════════════════════════════════ reclamos
def test_listar_reclamos_vacio_no_rompe(client, repo, admin_token):
    r = client.get("/admin/reclamos", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert r.json() == {"items": [], "total": 0}


def test_listar_reclamos_devuelve_items_y_total(client, repo, admin_token):
    c = repo.seed_comercio(slug="x", nombre="Casa Pepe", activo=True)
    repo.crear_reclamo({"comercio_id": c["id"], "texto": "No atendieron"})

    r = client.get("/admin/reclamos", headers=_h(admin_token))
    body = r.json()
    assert r.status_code == 200
    assert body["total"] == 1
    assert body["items"][0]["texto"] == "No atendieron"


def test_filtrar_reclamos_por_estado(client, repo, admin_token):
    c = repo.seed_comercio(slug="x", nombre="Casa Pepe", activo=True)
    uno = repo.crear_reclamo({"comercio_id": c["id"], "texto": "a"})
    repo.crear_reclamo({"comercio_id": c["id"], "texto": "b"})
    repo.responder_reclamo(uno["id"], "resuelto", "admin@x")

    pendientes = client.get("/admin/reclamos?estado=pendiente", headers=_h(admin_token)).json()
    assert pendientes["total"] == 1
    assert pendientes["items"][0]["texto"] == "b"


def test_responder_reclamo(client, repo, admin_token):
    c = repo.seed_comercio(slug="x", nombre="Casa Pepe", activo=True)
    rec = repo.crear_reclamo({"comercio_id": c["id"], "texto": "No atendieron"})

    r = client.post(f"/admin/reclamos/{rec['id']}/responder",
                    json={"respuesta": "Ya se contactaron"}, headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert repo.reclamos[rec["id"]]["estado"] == "respondido"


def test_responder_reclamo_inexistente_da_404(client, repo, admin_token):
    r = client.post("/admin/reclamos/no-existe/responder",
                    json={"respuesta": "x"}, headers=_h(admin_token))
    assert r.status_code == 404


def test_reclamos_requiere_admin(client, repo):
    assert client.get("/admin/reclamos").status_code in (401, 403)


# ═══════════════════════════════════════ solicitudes de cambio de número
def test_listar_solicitudes_vacio_no_rompe(client, repo, admin_token):
    r = client.get("/admin/solicitudes-cambio-numero", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert r.json() == {"items": [], "total": 0}


def test_aprobar_solicitud_cambia_el_whatsapp_del_comercio(client, repo, admin_token):
    """Es el efecto que importa: aprobar no marca un estado, cambia el número por
    el que le van a llegar las reservas."""
    c = repo.seed_comercio(slug="x", nombre="Casa Pepe", whatsapp="59170000001", activo=True)
    sol = repo.crear_solicitud_cambio_numero({"comercio_id": c["id"], "whatsapp_nuevo": "59170000002"})

    r = client.post(f"/admin/solicitudes-cambio-numero/{sol['id']}/aprobar", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert repo.comercios[c["id"]]["whatsapp"] == "59170000002"
    assert repo.solicitudes_numero[sol["id"]]["estado"] == "aprobada"


def test_rechazar_solicitud_no_toca_el_whatsapp(client, repo, admin_token):
    c = repo.seed_comercio(slug="x", nombre="Casa Pepe", whatsapp="59170000001", activo=True)
    sol = repo.crear_solicitud_cambio_numero({"comercio_id": c["id"], "whatsapp_nuevo": "59170000002"})

    r = client.post(f"/admin/solicitudes-cambio-numero/{sol['id']}/rechazar", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert repo.comercios[c["id"]]["whatsapp"] == "59170000001"
    assert repo.solicitudes_numero[sol["id"]]["estado"] == "rechazada"


def test_aprobar_solicitud_inexistente_da_404(client, repo, admin_token):
    r = client.post("/admin/solicitudes-cambio-numero/no-existe/aprobar", headers=_h(admin_token))
    assert r.status_code == 404


def test_solicitudes_requiere_admin(client, repo):
    assert client.get("/admin/solicitudes-cambio-numero").status_code in (401, 403)


# ══════════════════════════════════════════════════════ suscripciones
def test_listar_suscripciones_vacio_no_rompe(client, repo, admin_token):
    r = client.get("/admin/suscripciones", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 0


@pytest.mark.parametrize("kwargs,esperado", [
    ({},                                             "sin_plan"),
    ({"paga_hasta": None},                           "sin_plan"),
    ({"paga_hasta": "2020-01-01"},                   "vencido"),
    ({"suspendido": True, "paga_hasta": "2099-01-01"}, "suspendido"),
])
def test_estado_de_suscripcion(client, repo, admin_token, kwargs, esperado):
    repo.seed_comercio(slug="x", nombre="Casa Pepe", activo=True, **kwargs)
    items = client.get("/admin/suscripciones", headers=_h(admin_token)).json()["items"]
    assert items[0]["suscripcion_estado"] == esperado


def test_suscripcion_al_dia_y_por_vencer(client, repo, admin_token):
    repo.seed_comercio(slug="a", nombre="Al día", paga_hasta=_fecha(60), activo=True)
    repo.seed_comercio(slug="b", nombre="Por vencer", paga_hasta=_fecha(2), activo=True)

    por_slug = {c["slug"]: c["suscripcion_estado"]
                for c in client.get("/admin/suscripciones", headers=_h(admin_token)).json()["items"]}
    assert por_slug["a"] == "activo"
    assert por_slug["b"] == "por_vencer"


def test_suscripciones_ignora_los_dados_de_baja(client, repo, admin_token):
    repo.seed_comercio(slug="baja", nombre="De baja", activo=False)
    assert client.get("/admin/suscripciones", headers=_h(admin_token)).json()["total"] == 0


# ═════════════════════════════════════════ suspender / activar comercio
def test_suspender_y_reactivar(client, repo, admin_token):
    c = repo.seed_comercio(slug="x", nombre="Casa Pepe", activo=True)

    client.post(f"/admin/comercio/{c['id']}/suspender", headers=_h(admin_token))
    assert repo.comercios[c["id"]]["suspendido"] is True

    client.post(f"/admin/comercio/{c['id']}/activar", headers=_h(admin_token))
    assert repo.comercios[c["id"]]["suspendido"] is False
    assert repo.comercios[c["id"]]["activo"] is True


def test_suspender_requiere_admin(client, repo):
    assert client.post("/admin/comercio/x/suspender").status_code in (401, 403)


# ═══════════════════════════════════════════════════════ estadísticas
def test_estadisticas_devuelve_la_forma_que_el_panel_espera(client, repo, admin_token):
    """El panel lee estas claves directo; si alguna falta, la pantalla se rompe."""
    repo.seed_comercio(slug="x", nombre="Casa Pepe", activo=True)

    r = client.get("/admin/estadisticas", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    body = r.json()
    for clave in ["comercios_nuevos_7d", "comercios_nuevos_30d", "alertas",
                  "ofertas_total", "ofertas_top_comercios", "contactos_30d",
                  "contactos_top_comercios"]:
        assert clave in body, f"el panel espera '{clave}' y no viene"
    for alerta in ["vencido", "suspendido", "por_vencer"]:
        assert alerta in body["alertas"]


def test_estadisticas_requiere_admin(client, repo):
    assert client.get("/admin/estadisticas").status_code in (401, 403)


# ════════════════════════════════════════════ búsqueda pública por nombre
def test_buscar_comercio_por_nombre(client, repo):
    """Sin login: la usa el dueño que perdió el acceso a su número."""
    repo.seed_comercio(slug="x", nombre="Ferretería Roque", activo=True)
    repo.seed_comercio(slug="y", nombre="Panadería Sol", activo=True)

    items = client.get("/comercio/buscar?q=ferre").json()["items"]
    assert len(items) == 1 and items[0]["slug"] == "x"


def test_buscar_ignora_mayusculas(client, repo):
    repo.seed_comercio(slug="x", nombre="Ferretería Roque", activo=True)
    assert len(client.get("/comercio/buscar?q=FERRE").json()["items"]) == 1


def test_buscar_exige_minimo_dos_letras(client, repo):
    assert client.get("/comercio/buscar?q=a").status_code == 422


# ══════════════════════════════════════════════ altas por día
def test_altas_por_dia_agrupa_y_cuenta_lo_que_falta(client, repo, admin_token):
    repo.seed_comercio(slug="a", nombre="Ferretería Sur", whatsapp="59170000001",
                       created_at="2026-08-30T10:00:00+00:00", portada_url="u", ia_analizado_at="x")
    repo.seed_comercio(slug="b", nombre="Comercio 12", whatsapp=None,
                       created_at="2026-08-30T11:00:00+00:00")
    repo.seed_comercio(slug="c", nombre="Kiosko Ana", whatsapp="59170000002",
                       created_at="2026-08-29T09:00:00+00:00")

    r = client.get("/admin/altas-por-dia", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    dias = {d["dia"]: d for d in r.json()["items"]}
    assert dias["2026-08-30"]["altas"] == 2
    assert dias["2026-08-30"]["con_whatsapp"] == 1
    assert dias["2026-08-30"]["analizados"] == 1
    # "Comercio 12" es el nombre que pone el sistema, no un nombre real:
    # contarlo haría ver completo lo que no lo está.
    assert dias["2026-08-30"]["con_nombre"] == 1
    assert r.json()["total"] == 3


def test_altas_por_dia_viene_del_dia_mas_nuevo_al_mas_viejo(client, repo, admin_token):
    repo.seed_comercio(slug="a", nombre="X", created_at="2026-08-28T10:00:00+00:00")
    repo.seed_comercio(slug="b", nombre="Y", created_at="2026-08-30T10:00:00+00:00")
    items = client.get("/admin/altas-por-dia", headers=_h(admin_token)).json()["items"]
    assert [d["dia"] for d in items] == ["2026-08-30", "2026-08-28"]


# ══════════════════════════════════════════════ rubros de un comercio
def test_editar_rubros_REEMPLAZA_en_vez_de_sumar(client, repo, admin_token):
    """Lo que faltaba: hasta ahora sólo se podía agregar. Un rubro mal puesto no
    se podía sacar desde ningún lado, y un rubro de más no es un dato extra —
    es un local apareciendo en una búsqueda que no le corresponde."""
    c = repo.seed_comercio(slug="x", nombre="X")
    repo.reemplazar_comercio_rubros(c["id"], [repo.rubros["calzado"], repo.rubros["ropa"]])

    r = client.put(f"/admin/comercio/{c['id']}/rubros",
                   json={"rubro_slugs": ["calzado"]}, headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["rubro_slugs"] == ["calzado"]


def test_el_primero_de_la_lista_queda_como_principal(client, repo, admin_token):
    c = repo.seed_comercio(slug="x", nombre="X")
    client.put(f"/admin/comercio/{c['id']}/rubros",
               json={"rubro_slugs": ["ropa", "calzado"]}, headers=_h(admin_token))
    assert repo.comercios[c["id"]]["rubro_id"] == repo.rubros["ropa"]


def test_un_rubro_que_no_existe_no_se_ignora_en_silencio(client, repo, admin_token):
    """Ignorarlo dejaría al comercio con menos rubros de los que el panel
    muestra como guardados."""
    c = repo.seed_comercio(slug="x", nombre="X")
    r = client.put(f"/admin/comercio/{c['id']}/rubros",
                   json={"rubro_slugs": ["calzado", "no-existe"]}, headers=_h(admin_token))
    assert r.status_code == 400
    assert "no-existe" in r.json()["detail"]


def test_se_puede_dejar_un_comercio_sin_rubros(client, repo, admin_token):
    """Es una decisión válida: mejor sin rubro que con uno inventado."""
    c = repo.seed_comercio(slug="x", nombre="X")
    repo.reemplazar_comercio_rubros(c["id"], [repo.rubros["calzado"]])
    r = client.put(f"/admin/comercio/{c['id']}/rubros",
                   json={"rubro_slugs": []}, headers=_h(admin_token))
    assert r.status_code == 200
    assert r.json()["rubro_slugs"] == []


# ── Vencimientos ─────────────────────────────────────────────────────────────

def test_vencimiento_rechaza_tipo_inventado(client, admin_token, repo):
    """Un tipo que la base no acepta explota en el insert con un 500 y la fila
    no se guarda: mejor decir cuál es el problema."""
    r = client.post("/admin/vencimientos",
                    json={"nombre": "Algo", "tipo": "criptomoneda"}, headers=_h(admin_token))
    assert r.status_code == 400
    assert "criptomoneda" in r.json()["detail"]


def test_vencimiento_sin_nombre_no_se_crea(client, admin_token):
    r = client.post("/admin/vencimientos", json={"nombre": "  "}, headers=_h(admin_token))
    assert r.status_code == 400


def test_vencimiento_se_crea_sin_fecha(client, admin_token, repo):
    """Una fila sin fecha es 'hay que averiguarla', y eso es informacion.
    Obligar la fecha llevaria a inventar una, que es peor: deja de avisar
    creyendo que avisa."""
    r = client.post("/admin/vencimientos",
                    json={"nombre": "Dominio nuevo", "tipo": "dominio"}, headers=_h(admin_token))
    assert r.status_code == 200
    assert len(repo.vencimientos) == 1


def test_se_puede_borrar_la_fecha(client, admin_token, repo):
    """Con `if v is not None` mandar null se leia como 'no lo toques', asi que
    una fecha mal cargada no se podia sacar."""
    v = repo.crear_vencimiento({"nombre": "X", "vence_el": "2026-12-01"})
    r = client.put(f"/admin/vencimientos/{v['id']}", json={"vence_el": None}, headers=_h(admin_token))
    assert r.status_code == 200
    assert repo.vencimientos[v["id"]]["vence_el"] is None


def test_borrar_es_baja_logica(client, admin_token, repo):
    """Si algo se deja de vigilar conviene saber que ALGUIEN lo decidio, no que
    la fila desaparecio y nadie se acuerda de por que."""
    v = repo.crear_vencimiento({"nombre": "X"})
    client.delete(f"/admin/vencimientos/{v['id']}", headers=_h(admin_token))
    assert repo.vencimientos[v["id"]]["activo"] is False
    assert repo.list_vencimientos() == []
